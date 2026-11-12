//! The dataflow of Python files: which node or step reads which, and what does not connect.
//!
//! A file with a pipeline of steps is read as step code, each pipeline on its own. The other
//! files are read as Hamilton modules of one Driver, as `with_modules(a, b)` takes them.
//! Nothing is imported or run, so this needs no Python and no Hamilton.

use std::collections::{BTreeMap, BTreeSet};
use std::fs;
use std::path::{Path, PathBuf};

use anyhow::{Context, Result};
use serde_json::{Value, json};

use crate::nodes::{self, Level, NodeDef};
use crate::steps::{self, Pipeline};

/// A name shorter than this is not compared with the node names, because short names such as
/// `x1` and `x2` are one edit apart by design.
const SHORTEST_NAME_TO_COMPARE: usize = 4;

/// One node with the file that defines it.
#[derive(Debug)]
struct Placed {
    file: PathBuf,
    def: NodeDef,
}

/// A finding with the file it is about.
#[derive(Debug)]
struct Problem {
    file: PathBuf,
    line: usize,
    level: Level,
    message: String,
}

/// A name that nodes read and no node defines, so the caller has to pass it.
#[derive(Debug)]
struct ExternalInput {
    name: String,
    /// Every reader has a default for it.
    optional: bool,
    readers: Vec<String>,
}

/// One pipeline of steps with the file that defines it.
#[derive(Debug)]
struct PlacedPipeline {
    file: PathBuf,
    pipeline: Pipeline,
}

/// The dataflow of a set of modules.
#[derive(Debug)]
pub(crate) struct Graph {
    pipelines: Vec<PlacedPipeline>,
    nodes: Vec<Placed>,
    inputs: Vec<ExternalInput>,
    /// Nodes that no other node reads, which are the ends of the dataflow.
    unread: Vec<String>,
    problems: Vec<Problem>,
    files: usize,
    functions: usize,
}

impl Graph {
    /// Reads `files` as the modules of one dataflow.
    ///
    /// # Errors
    ///
    /// When a file cannot be read.
    pub(crate) fn read(files: &[PathBuf]) -> Result<Self> {
        let mut pipelines = Vec::new();
        let mut nodes = Vec::new();
        let mut problems = Vec::new();
        let mut functions = 0;
        for file in files {
            let src = fs::read_to_string(file)
                .with_context(|| format!("cannot read {}", file.display()))?;
            let found = steps::read(&src);
            let is_step_code = !found.is_empty();
            for mut pipeline in found {
                problems.extend(pipeline.findings.drain(..).map(|found| Problem {
                    file: file.clone(),
                    line: found.line,
                    level: found.level,
                    message: found.message,
                }));
                pipelines.push(PlacedPipeline {
                    file: file.clone(),
                    pipeline,
                });
            }
            // The steps of a pipeline are no Hamilton nodes, unless the file says it is both.
            if is_step_code && !imports_hamilton(&src) {
                continue;
            }
            let module = nodes::read(&src);
            functions += module.functions;
            nodes.extend(module.nodes.into_iter().map(|def| Placed {
                file: file.clone(),
                def,
            }));
            problems.extend(module.findings.into_iter().map(|found| Problem {
                file: file.clone(),
                line: found.line,
                level: found.level,
                message: found.message,
            }));
        }
        nodes.sort_by(|a, b| (&a.file, a.def.line).cmp(&(&b.file, b.def.line)));
        problems.extend(defined_twice(&nodes));
        let inputs = external_inputs(&nodes);
        problems.extend(near_misses(&nodes, &inputs));
        problems.sort_by(|a, b| (&a.file, a.line, a.level).cmp(&(&b.file, b.line, b.level)));
        let read: BTreeSet<&str> = nodes
            .iter()
            .flat_map(|n| n.def.inputs.iter().map(|input| input.name.as_str()))
            .collect();
        let unread: BTreeSet<String> = nodes
            .iter()
            .map(|n| n.def.name.as_str())
            .filter(|name| !read.contains(name))
            .map(str::to_owned)
            .collect();
        Ok(Self {
            pipelines,
            unread: unread.into_iter().collect(),
            nodes,
            inputs,
            problems,
            files: files.len(),
            functions,
        })
    }

    /// Whether the code would raise, or Python drops a function.
    pub(crate) fn has_errors(&self) -> bool {
        self.problems.iter().any(|p| p.level == Level::Error)
    }

    /// The errors and warnings about step code, one line each, for the hook.
    pub(crate) fn step_lines(src_path: &Path, src: &str) -> Vec<String> {
        let mut found: Vec<_> = steps::read(src)
            .into_iter()
            .flat_map(|pipeline| pipeline.findings)
            .filter(|finding| finding.level != Level::Note)
            .collect();
        found.sort_by_key(|f| (f.line, f.level));
        found
            .iter()
            .map(|f| {
                format!(
                    "{}: {} [graph] {}",
                    place(src_path, f.line),
                    f.level.as_str(),
                    f.message
                )
            })
            .collect()
    }

    /// One line per node, then the inputs, the nodes nobody reads, and the problems.
    pub(crate) fn to_text(&self) -> String {
        let mut lines = Vec::new();
        for placed in &self.pipelines {
            let pipeline = &placed.pipeline;
            let columns: usize = pipeline.steps.iter().map(|s| s.writes.len()).sum();
            lines.push(format!(
                "{}: {}: {}, {}",
                place(&placed.file, pipeline.line),
                pipeline.name,
                count(pipeline.steps.len(), "step"),
                count(columns, "column")
            ));
            for step in &pipeline.steps {
                let from: Vec<&str> = pipeline
                    .links
                    .iter()
                    .filter(|link| link.to == step.name)
                    .map(|link| link.from.as_str())
                    .collect();
                let from = if from.is_empty() {
                    "(source columns)".to_owned()
                } else {
                    from.join(" + ")
                };
                let computed = if step.computed {
                    " and computed names"
                } else {
                    ""
                };
                lines.push(format!(
                    "{}:   {from} -> {}  [{}{computed}]",
                    place(&placed.file, step.line),
                    step.name,
                    count(step.writes.len(), "column")
                ));
            }
            let free = pipeline.free_steps();
            if !free.is_empty() {
                lines.push(format!("order is free for: {}", free.join(", ")));
            }
        }
        for node in &self.nodes {
            let inputs: Vec<String> = node
                .def
                .inputs
                .iter()
                .map(|input| {
                    if input.optional {
                        format!("{}?", input.name)
                    } else {
                        input.name.clone()
                    }
                })
                .collect();
            let from = if inputs.is_empty() {
                "(no input)".to_owned()
            } else {
                inputs.join(" + ")
            };
            let origin = node
                .def
                .origin
                .tag(&node.def.function)
                .map(|tag| format!("  [{tag}]"));
            let config = node.def.config.as_ref().map(|c| format!("  [{c}]"));
            lines.push(format!(
                "{}: {from} -> {}{}{}",
                place(&node.file, node.def.line),
                node.def.name,
                origin.unwrap_or_default(),
                config.unwrap_or_default()
            ));
        }
        if !self.inputs.is_empty() {
            let names: Vec<String> = self
                .inputs
                .iter()
                .map(|input| {
                    let mark = if input.optional { "?" } else { "" };
                    format!("{}{mark}", input.name)
                })
                .collect();
            lines.push(format!("inputs: {}", names.join(", ")));
        }
        if !self.unread.is_empty() {
            lines.push(format!("read by no node: {}", self.unread.join(", ")));
        }
        for problem in &self.problems {
            lines.push(format!(
                "{}: {}: {}",
                place(&problem.file, problem.line),
                problem.level.as_str(),
                problem.message
            ));
        }
        lines.join("\n")
    }

    pub(crate) fn to_json(&self) -> Value {
        let nodes: Vec<Value> = self
            .nodes
            .iter()
            .map(|node| {
                let inputs: Vec<Value> = node
                    .def
                    .inputs
                    .iter()
                    .map(|input| json!({"name": input.name, "optional": input.optional}))
                    .collect();
                json!({
                    "name": node.def.name,
                    "file": node.file.display().to_string(),
                    "line": node.def.line,
                    "function": node.def.function,
                    "inputs": inputs,
                    "kind": node.def.origin.as_str(),
                    "config": node.def.config,
                })
            })
            .collect();
        let inputs: Vec<Value> = self
            .inputs
            .iter()
            .map(|input| json!({"name": input.name, "optional": input.optional, "readers": input.readers}))
            .collect();
        let problems: Vec<Value> = self
            .problems
            .iter()
            .map(|problem| {
                json!({
                    "file": problem.file.display().to_string(),
                    "line": problem.line,
                    "severity": problem.level.as_str(),
                    "message": problem.message,
                })
            })
            .collect();
        let pipelines: Vec<Value> = self
            .pipelines
            .iter()
            .map(|placed| {
                let pipeline = &placed.pipeline;
                let steps: Vec<Value> = pipeline
                    .steps
                    .iter()
                    .map(|step| {
                        json!({
                            "name": step.name,
                            "line": step.line,
                            "reads": step.reads,
                            "columns": step.writes,
                            "computed": step.computed,
                        })
                    })
                    .collect();
                let links: Vec<Value> = pipeline
                    .links
                    .iter()
                    .map(|l| json!({"from": l.from, "to": l.to, "columns": l.columns}))
                    .collect();
                json!({
                    "name": pipeline.name,
                    "file": placed.file.display().to_string(),
                    "line": pipeline.line,
                    "steps": steps,
                    "links": links,
                    "free": pipeline.free_steps(),
                })
            })
            .collect();
        json!({"pipelines": pipelines, "nodes": nodes, "inputs": inputs, "unread": self.unread, "problems": problems})
    }

    /// For example `10 nodes from 8 functions in 1 file, 14 inputs, 2 errors`.
    pub(crate) fn summary(&self) -> String {
        let mut parts = Vec::new();
        if !self.pipelines.is_empty() {
            let steps: usize = self.pipelines.iter().map(|p| p.pipeline.steps.len()).sum();
            parts.push(format!(
                "{} with {}",
                count(self.pipelines.len(), "pipeline"),
                count(steps, "step")
            ));
        }
        if !self.nodes.is_empty() || self.pipelines.is_empty() {
            parts.push(format!(
                "{} from {}",
                count(self.nodes.len(), "node"),
                count(self.functions, "function")
            ));
            parts.push(count(self.inputs.len(), "input"));
        }
        if let Some(first) = parts.first_mut() {
            *first = format!("{first} in {}", count(self.files, "file"));
        }
        for (level, word) in [
            (Level::Error, "error"),
            (Level::Warning, "warning"),
            (Level::Note, "note"),
        ] {
            let found = self.problems.iter().filter(|p| p.level == level).count();
            if found > 0 {
                parts.push(count(found, word));
            }
        }
        parts.join(", ")
    }
}

/// Whether the source imports the `hamilton` module.
fn imports_hamilton(src: &str) -> bool {
    src.lines().map(str::trim_start).any(|line| {
        ["import hamilton", "from hamilton"].iter().any(|start| {
            line.strip_prefix(start)
                .is_some_and(|rest| rest.starts_with([' ', '.']) || rest.is_empty())
        })
    })
}

fn place(file: &Path, line: usize) -> String {
    format!("{}:{line}", file.display())
}

fn count(n: usize, word: &str) -> String {
    if n == 1 {
        format!("1 {word}")
    } else {
        format!("{n} {word}s")
    }
}

/// A node name that more than one function defines. Versions under `@config.when` share a
/// name on purpose, because the config picks one of them.
fn defined_twice(nodes: &[Placed]) -> Vec<Problem> {
    let mut by_name: BTreeMap<&str, Vec<&Placed>> = BTreeMap::new();
    for node in nodes {
        by_name.entry(&node.def.name).or_default().push(node);
    }
    let mut problems = Vec::new();
    for (name, defs) in by_name {
        let plain: Vec<&&Placed> = defs.iter().filter(|d| d.def.config.is_none()).collect();
        let versions = defs.len() - plain.len();
        let Some(first) = plain.first() else {
            continue;
        };
        if plain.len() > 1 {
            let places: Vec<String> = plain
                .iter()
                .map(|d| {
                    format!(
                        "{} at {}",
                        d.def.origin.made_by(&d.def.function),
                        place(&d.file, d.def.line)
                    )
                })
                .collect();
            problems.push(Problem {
                file: first.file.clone(),
                line: first.def.line,
                level: Level::Error,
                message: format!(
                    "The node {name} is defined {} times: by {}. Hamilton raises \"Cannot define function {name} more than once\" when the Driver is built.",
                    plain.len(),
                    places.join(", and by ")
                ),
            });
        } else if versions > 0 {
            problems.push(Problem {
                file: first.file.clone(),
                line: first.def.line,
                level: Level::Error,
                message: format!(
                    "The node {name} has this def and a @config.when version. When the config selects the version, Hamilton raises \"Cannot define function {name} more than once\". Put this def under @config.when_not, as {name}__default."
                ),
            });
        }
    }
    problems
}

/// The names that nodes read and no node defines.
fn external_inputs(nodes: &[Placed]) -> Vec<ExternalInput> {
    let defined: BTreeSet<&str> = nodes.iter().map(|n| n.def.name.as_str()).collect();
    let mut found: BTreeMap<&str, ExternalInput> = BTreeMap::new();
    for node in nodes {
        for input in &node.def.inputs {
            if defined.contains(input.name.as_str()) {
                continue;
            }
            let entry = found.entry(&input.name).or_insert_with(|| ExternalInput {
                name: input.name.clone(),
                optional: true,
                readers: Vec::new(),
            });
            entry.optional &= input.optional;
            if !entry.readers.contains(&node.def.name) {
                entry.readers.push(node.def.name.clone());
            }
        }
    }
    found.into_values().collect()
}

/// An input one edit away from a node name is likely a typing error. Hamilton reports it only
/// at execute, as a required input that nobody passed.
fn near_misses(nodes: &[Placed], inputs: &[ExternalInput]) -> Vec<Problem> {
    let names: BTreeSet<&str> = nodes.iter().map(|n| n.def.name.as_str()).collect();
    let mut problems = Vec::new();
    for input in inputs {
        if input.name.chars().count() < SHORTEST_NAME_TO_COMPARE {
            continue;
        }
        // A trailing underscore is a way to name an input after a node on purpose.
        let Some(near) = names.iter().find(|name| {
            one_edit_apart(&input.name, name) && input.name.trim_end_matches('_') != **name
        }) else {
            continue;
        };
        for reader in nodes
            .iter()
            .filter(|n| n.def.inputs.iter().any(|i| i.name == input.name))
        {
            problems.push(Problem {
                file: reader.file.clone(),
                line: reader.def.line,
                level: Level::Warning,
                message: format!(
                    "{} reads {}, which no function defines and which is one edit from the node {near}. If it is a typing error, Hamilton raises \"Required input {} not provided\" at execute.",
                    reader.def.name, input.name, input.name
                ),
            });
        }
    }
    problems
}

/// Whether one changed, added, removed or swapped character turns `a` into `b`.
fn one_edit_apart(a: &str, b: &str) -> bool {
    let a: Vec<char> = a.chars().collect();
    let b: Vec<char> = b.chars().collect();
    let (short, long) = if a.len() <= b.len() {
        (&a, &b)
    } else {
        (&b, &a)
    };
    let prefix = short
        .iter()
        .zip(long.iter())
        .take_while(|(x, y)| x == y)
        .count();
    match long.len() - short.len() {
        0 => {
            let rest_equal = |from: usize| short[from..] == long[from..];
            prefix < short.len()
                && (rest_equal(prefix + 1)
                    || (prefix + 1 < short.len()
                        && short[prefix] == long[prefix + 1]
                        && short[prefix + 1] == long[prefix]
                        && rest_equal(prefix + 2)))
        }
        1 => short[prefix..] == long[prefix + 1..],
        _ => false,
    }
}
