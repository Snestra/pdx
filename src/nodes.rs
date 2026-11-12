//! Reads the Hamilton nodes that one Python module defines.
//!
//! Hamilton turns every function at module level into a node, unless its name starts with an
//! underscore: the function name is the node and the parameter names are its inputs. Decorators
//! from `hamilton.function_modifiers` rename a node, add nodes, or change its inputs. This
//! module reads the decorators whose arguments are literals, and says so for the rest.

use std::collections::BTreeSet;

use ast_grep_core::Node;
use ast_grep_core::tree_sitter::StrDoc;
use ast_grep_language::SupportLang;

use crate::scan;

/// A node of the syntax tree of a Python file.
type Syntax<'r> = Node<'r, StrDoc<SupportLang>>;

/// Decorators that build nodes in a way this module does not read.
const UNREAD: &[&str] = &[
    "does",
    "dynamic_transform",
    "model",
    "parameterize_extract_columns",
    "parameterize_frame",
    "parameterize_subdag",
    "pipe",
    "pipe_input",
    "pipe_output",
    "resolve",
    "resolve_from_config",
    "subdag",
    "with_columns",
];

/// One node of the dataflow, as one function defines it.
#[derive(Debug)]
pub(crate) struct NodeDef {
    pub(crate) name: String,
    /// The function that defines the node, by the name it has in the file.
    pub(crate) function: String,
    /// The line of the `def`, counted from 1.
    pub(crate) line: usize,
    pub(crate) inputs: Vec<Input>,
    /// How the function makes this node.
    pub(crate) origin: Origin,
    /// The text of the `@config.when` decorator, when the function has one.
    pub(crate) config: Option<String>,
}

/// One input of a node: the name of another node, or of a value the caller passes.
#[derive(Debug, Clone, PartialEq, Eq)]
pub(crate) struct Input {
    pub(crate) name: String,
    /// The parameter has a default, so Hamilton does not ask for it.
    pub(crate) optional: bool,
}

/// How a function makes a node.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub(crate) enum Origin {
    /// The node is the function.
    Function,
    /// The node is one of several that a `@parameterize` decorator names.
    Parameterized,
    /// The node is a part of the function's result, such as a column under `@extract_columns`.
    Extracted,
    /// The node saves the function's result, under `@save_to`.
    Saved,
}

impl Origin {
    /// How the function `function` makes a node of this kind, for a message.
    pub(crate) fn made_by(self, function: &str) -> String {
        match self {
            Self::Function => format!("the function {function}"),
            Self::Parameterized => format!("@parameterize on {function}"),
            Self::Extracted => format!("a part of the result of {function}"),
            Self::Saved => format!("@save_to on {function}"),
        }
    }

    /// The kind of node, as the JSON report names it.
    pub(crate) fn as_str(self) -> &'static str {
        match self {
            Self::Function => "function",
            Self::Parameterized => "parameterized",
            Self::Extracted => "extracted",
            Self::Saved => "saved",
        }
    }

    /// What the text report puts after a node that is not the function itself.
    pub(crate) fn tag(self, function: &str) -> Option<String> {
        match self {
            Self::Function => None,
            Self::Parameterized => Some(format!("@parameterize on {function}")),
            Self::Extracted => Some(format!("part of {function}")),
            Self::Saved => Some(format!("@save_to on {function}")),
        }
    }
}

/// How sure a finding is.
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub(crate) enum Level {
    /// Hamilton raises, or Python drops the function.
    Error,
    /// A guess that a person should look at.
    Warning,
    /// Something `xpd graph` could not read.
    Note,
}

impl Level {
    pub(crate) fn as_str(self) -> &'static str {
        match self {
            Self::Error => "error",
            Self::Warning => "warning",
            Self::Note => "note",
        }
    }
}

/// Something about one function that the graph alone does not show.
#[derive(Debug)]
pub(crate) struct Finding {
    pub(crate) line: usize,
    pub(crate) level: Level,
    pub(crate) message: String,
}

/// What one module defines.
#[derive(Debug, Default)]
pub(crate) struct Module {
    pub(crate) nodes: Vec<NodeDef>,
    pub(crate) findings: Vec<Finding>,
    /// The functions that became nodes.
    pub(crate) functions: usize,
}

/// One parameter of a function. `*args` and `**kwargs` are not inputs and are left out.
#[derive(Debug)]
struct Param {
    name: String,
    hinted: bool,
    optional: bool,
}

/// One decorator: its dotted name, and the call when it has arguments.
struct Decorator<'r> {
    /// The last part of the dotted name, such as `when` for `config.when`.
    name: String,
    /// The dotted name, such as `config.when` or `load_from.csv`.
    path: String,
    call: Option<Syntax<'r>>,
    text: String,
}

/// Reads the nodes of the module in `src`.
pub(crate) fn read(src: &str) -> Module {
    let root = scan::parse(src);
    let mut module = Module::default();
    let mut defined: Vec<(String, usize)> = Vec::new();
    let mut kept: Vec<(String, Vec<NodeDef>, Vec<Finding>)> = Vec::new();
    for statement in root.root().children() {
        let (function, decorators) = match statement.kind().as_ref() {
            "function_definition" => (statement, Vec::new()),
            "decorated_definition" => {
                let Some(function) = statement
                    .field("definition")
                    .filter(|d| d.kind() == "function_definition")
                else {
                    continue;
                };
                let decorators = statement
                    .children()
                    .filter(|child| child.kind() == "decorator")
                    .filter_map(|d| decorator(&d))
                    .collect();
                (function, decorators)
            }
            _ => continue,
        };
        let Some(name) = function.field("name").map(|n| n.text().into_owned()) else {
            continue;
        };
        let line = function.start_pos().line() + 1;
        // A @mutate function is no node of its own, with or without an underscore: Hamilton
        // applies it to the nodes the decorator names.
        if decorators.iter().any(|d| d.name == "mutate") {
            module.findings.push(Finding {
                line,
                level: Level::Note,
                message: format!(
                    "@mutate on {name} changes other nodes in a way xpd graph does not read."
                ),
            });
            continue;
        }
        if name.starts_with('_') || decorators.iter().any(|d| d.name == "hamilton_exclude") {
            continue;
        }
        defined.push((name.clone(), line));
        let (nodes, findings) = function_nodes(&name, line, &function, &decorators);
        kept.push((name, nodes, findings));
    }
    // Python binds a name to its last `def`, so an earlier one never reaches Hamilton.
    for (index, (name, nodes, findings)) in kept.into_iter().enumerate() {
        let lines: Vec<usize> = defined
            .iter()
            .filter(|(other, _)| *other == name)
            .map(|(_, line)| *line)
            .collect();
        let last = defined.iter().rposition(|(other, _)| *other == name);
        if last != Some(index) {
            let places: Vec<String> = lines.iter().map(usize::to_string).collect();
            let advice = if nodes.iter().any(|node| node.config.is_some()) {
                format!(" Name each version {name}__<suffix>, and Hamilton removes the suffix.")
            } else {
                String::new()
            };
            module.findings.push(Finding {
                line: defined[index].1,
                level: Level::Error,
                message: format!(
                    "{name} is defined {} times in this file, at lines {}. Python keeps the last def only, so this one never reaches Hamilton.{advice}",
                    lines.len(),
                    places.join(" and ")
                ),
            });
            continue;
        }
        module.functions += 1;
        module.nodes.extend(nodes);
        module.findings.extend(findings);
    }
    module
}

/// The dotted name and the arguments of one decorator.
fn decorator<'r>(node: &Syntax<'r>) -> Option<Decorator<'r>> {
    let expression = node.children().find(Node::is_named)?;
    let (target, call) = if expression.kind() == "call" {
        (expression.field("function")?, Some(expression.clone()))
    } else {
        (expression.clone(), None)
    };
    let path = target.text().into_owned();
    let name = path.rsplit('.').next().unwrap_or(&path).to_owned();
    Some(Decorator {
        name,
        path,
        call,
        text: expression.text().into_owned(),
    })
}

impl<'r> Decorator<'r> {
    fn has_part(&self, part: &str) -> bool {
        self.path.split('.').any(|p| p == part)
    }

    /// The arguments of the call, without the punctuation between them.
    fn arguments(&self) -> Vec<Syntax<'r>> {
        self.call
            .as_ref()
            .and_then(|call| call.field("arguments"))
            .map(|list| list.children().filter(Node::is_named).collect())
            .unwrap_or_default()
    }
}

/// What the decorators of one function change about its nodes.
#[derive(Default)]
struct Effects {
    /// Parameters that a decorator fills, so they are no inputs.
    filled: BTreeSet<String>,
    /// Nodes that a decorator reads with `source("name")`.
    sources: Vec<String>,
    /// The nodes of a `@parameterize` decorator, which replace the function's own node.
    variants: Option<Vec<Variant>>,
    /// Nodes that are a part of the result, such as the columns of `@extract_columns`.
    extracted: Vec<String>,
    /// Nodes that save the result, from `@save_to`.
    saved: Vec<String>,
    /// What could not be read.
    notes: Vec<String>,
}

impl Effects {
    fn read(name: &str, params: &[Param], decorators: &[Decorator<'_>]) -> Self {
        let mut effects = Self::default();
        for d in decorators {
            let arguments = d.arguments();
            match d.name.as_str() {
                "extract_columns" | "unpack_fields" | "extract_fields" => {
                    let (names, complete) = literal_names(&arguments);
                    effects.extracted.extend(names);
                    if !complete {
                        effects.notes.push(format!(
                            "@{} on {name} takes names that the file computes, so some of its nodes are not listed.",
                            d.name
                        ));
                    }
                }
                "parameterize" | "parameterize_sources" | "parameterize_values" => {
                    let variants = parameterized(d);
                    if variants.is_none() {
                        effects.notes.push(format!(
                            "@{} on {name} takes names that the file computes, so its nodes are not listed.",
                            d.name
                        ));
                    }
                    effects.variants = Some(variants.unwrap_or_default());
                }
                "inject" => {
                    for argument in arguments.iter().filter(|a| a.kind() == "keyword_argument") {
                        if let (Some(param), Some(value)) =
                            (argument.field("name"), argument.field("value"))
                        {
                            effects.filled.insert(param.text().into_owned());
                            effects.sources.extend(source_names(&value));
                        }
                    }
                }
                _ if d.has_part("load_from") => {
                    let injected = keyword(&arguments, "inject_")
                        .and_then(|value| literal(&value))
                        .or_else(|| match params {
                            [only] => Some(only.name.clone()),
                            _ => None,
                        });
                    effects.filled.extend(injected);
                    effects
                        .sources
                        .extend(arguments.iter().flat_map(source_names));
                }
                _ if d.has_part("save_to") => {
                    let output = keyword(&arguments, "output_name_").and_then(|v| literal(&v));
                    effects.saved.extend(output);
                    effects
                        .sources
                        .extend(arguments.iter().flat_map(source_names));
                }
                other if UNREAD.contains(&other) => {
                    // A step such as step(_tax, rates=source("rates")) reads the node it names.
                    if other.starts_with("pipe") {
                        effects
                            .sources
                            .extend(arguments.iter().flat_map(source_names));
                    }
                    effects.notes.push(format!(
                        "@{other} on {name} changes the nodes in a way xpd graph does not read."
                    ));
                }
                _ => {}
            }
        }
        effects
    }

    /// The inputs of a node of the function: its parameters, without the ones a decorator or
    /// `assigned` fills, and with the nodes that the decorators and `read` name.
    fn inputs(&self, params: &[Param], assigned: &BTreeSet<String>, read: &[String]) -> Vec<Input> {
        let mut inputs: Vec<Input> = params
            .iter()
            .filter(|p| !self.filled.contains(&p.name) && !assigned.contains(&p.name))
            .map(|p| Input {
                name: p.name.clone(),
                optional: p.optional,
            })
            .collect();
        for source in self.sources.iter().chain(read) {
            if !inputs.iter().any(|input| input.name == *source) {
                inputs.push(Input {
                    name: source.clone(),
                    optional: false,
                });
            }
        }
        inputs
    }
}

/// The finding for a function that lacks a type hint, which Hamilton needs on the return
/// value and on every parameter.
fn missing_hints(
    name: &str,
    line: usize,
    function: &Syntax<'_>,
    params: &[Param],
) -> Option<Finding> {
    let unhinted: Vec<&str> = params
        .iter()
        .filter(|p| !p.hinted)
        .map(|p| p.name.as_str())
        .collect();
    let mut missing: Vec<String> = Vec::new();
    if function.field("return_type").is_none() {
        missing.push("the return value".to_owned());
    }
    match unhinted.as_slice() {
        [] => {}
        [only] => missing.push(format!("the parameter {only}")),
        many => missing.push(format!("the parameters {}", many.join(", "))),
    }
    if missing.is_empty() {
        return None;
    }
    Some(Finding {
        line,
        level: Level::Error,
        message: format!(
            "{name} has no type hint for {}. Hamilton raises \"Missing type hint\" when the Driver is built. Add the hint, or name a helper _{name}.",
            missing.join(" and ")
        ),
    })
}

/// The nodes one function defines, and what is wrong with it.
fn function_nodes(
    name: &str,
    line: usize,
    function: &Syntax<'_>,
    decorators: &[Decorator<'_>],
) -> (Vec<NodeDef>, Vec<Finding>) {
    let params = parameters(function);
    let effects = Effects::read(name, &params, decorators);
    let mut findings: Vec<Finding> = effects
        .notes
        .iter()
        .map(|message| Finding {
            line,
            level: Level::Note,
            message: message.clone(),
        })
        .collect();
    findings.extend(missing_hints(name, line, function, &params));

    let config = decorators
        .iter()
        .find(|d| d.has_part("config"))
        .map(|d| d.text.clone());
    // Hamilton drops what follows the last `__` of a function under @config.
    let own_name = match (&config, name.rfind("__")) {
        (Some(_), Some(at)) if at > 0 => &name[..at],
        _ => name,
    };
    let define = |node_name: String, inputs: Vec<Input>, origin: Origin| NodeDef {
        name: node_name,
        function: name.to_owned(),
        line,
        inputs,
        origin,
        config: config.clone(),
    };

    let mut nodes = Vec::new();
    if let Some(variants) = &effects.variants {
        for variant in variants {
            let inputs = effects.inputs(&params, &variant.assigned, &variant.sources);
            nodes.push(define(variant.name.clone(), inputs, Origin::Parameterized));
        }
    } else {
        let inputs = effects.inputs(&params, &BTreeSet::new(), &[]);
        nodes.push(define(own_name.to_owned(), inputs, Origin::Function));
    }
    // A part of a result, and a saver, read the nodes they come from.
    let results: Vec<Input> = nodes
        .iter()
        .map(|result| Input {
            name: result.name.clone(),
            optional: false,
        })
        .collect();
    for (parts, origin) in [
        (&effects.extracted, Origin::Extracted),
        (&effects.saved, Origin::Saved),
    ] {
        for part in parts {
            nodes.push(define(part.clone(), results.clone(), origin));
        }
    }
    (nodes, findings)
}

/// The named parameters of a function.
fn parameters(function: &Syntax<'_>) -> Vec<Param> {
    let Some(list) = function.field("parameters") else {
        return Vec::new();
    };
    list.children()
        .filter_map(|param| {
            let (name, hinted, optional) = match param.kind().as_ref() {
                "identifier" => (param.clone(), false, false),
                "typed_parameter" => {
                    let name = param.children().find(|c| c.kind() == "identifier")?;
                    (name, true, false)
                }
                "default_parameter" => (param.field("name")?, false, true),
                "typed_default_parameter" => (param.field("name")?, true, true),
                _ => return None,
            };
            Some(Param {
                name: name.text().into_owned(),
                hinted,
                optional,
            })
        })
        .collect()
}

/// One node that a `@parameterize` decorator names.
struct Variant {
    name: String,
    /// The parameters the decorator gives a value or a source.
    assigned: BTreeSet<String>,
    /// The nodes the decorator reads for those parameters.
    sources: Vec<String>,
}

/// The nodes of `@parameterize`, `@parameterize_sources` and `@parameterize_values`, or `None`
/// when the names are not literals.
fn parameterized(d: &Decorator<'_>) -> Option<Vec<Variant>> {
    let arguments = d.arguments();
    if arguments
        .iter()
        .any(|a| matches!(a.kind().as_ref(), "dictionary_splat" | "list_splat"))
    {
        return None;
    }
    if d.name == "parameterize_values" {
        // parameterize_values(parameter="n", assigned_output={("name", "doc"): value})
        let parameter =
            positional_or_keyword(&arguments, 0, "parameter").and_then(|v| literal(&v))?;
        let outputs = positional_or_keyword(&arguments, 1, "assigned_output")
            .filter(|v| v.kind() == "dictionary")?;
        return outputs
            .children()
            .filter(|pair| pair.kind() == "pair")
            .map(|pair| {
                let key = pair.field("key").filter(|k| k.kind() == "tuple")?;
                let name = key
                    .children()
                    .find(Node::is_named)
                    .and_then(|n| literal(&n))?;
                Some(Variant {
                    name,
                    assigned: BTreeSet::from([parameter.clone()]),
                    sources: Vec::new(),
                })
            })
            .collect();
    }
    let by_string = d.name == "parameterize_sources";
    arguments
        .iter()
        .map(|argument| {
            if argument.kind() != "keyword_argument" {
                return None;
            }
            let name = argument.field("name")?.text().into_owned();
            let value = argument.field("value")?;
            let assignment = assignment_of(&value)?;
            let mut assigned = BTreeSet::new();
            let mut sources = Vec::new();
            for (param, given) in pairs(&assignment)? {
                assigned.insert(param);
                if by_string {
                    sources.push(literal(&given)?);
                } else {
                    sources.extend(source_names(&given));
                }
            }
            Some(Variant {
                name,
                assigned,
                sources,
            })
        })
        .collect()
}

/// The `dict(...)` call or `{...}` literal that maps parameters to what they get. The value
/// may also be a tuple of that mapping and a docstring.
fn assignment_of<'r>(value: &Syntax<'r>) -> Option<Syntax<'r>> {
    match value.kind().as_ref() {
        "dictionary" => Some(value.clone()),
        "call" if value.field("function")?.text() == "dict" => Some(value.clone()),
        "tuple" => {
            let first = value.children().find(Node::is_named)?;
            assignment_of(&first)
        }
        _ => None,
    }
}

/// The `name: value` pairs of a `dict(...)` call or a `{...}` literal with literal keys.
fn pairs<'r>(mapping: &Syntax<'r>) -> Option<Vec<(String, Syntax<'r>)>> {
    if mapping.kind() == "dictionary" {
        return mapping
            .children()
            .filter(Node::is_named)
            .map(|pair| {
                if pair.kind() != "pair" {
                    return None;
                }
                Some((literal(&pair.field("key")?)?, pair.field("value")?))
            })
            .collect();
    }
    if mapping.kind() != "call" || mapping.field("function")?.text() != "dict" {
        return None;
    }
    mapping
        .field("arguments")?
        .children()
        .filter(Node::is_named)
        .map(|argument| {
            if argument.kind() != "keyword_argument" {
                return None;
            }
            Some((
                argument.field("name")?.text().into_owned(),
                argument.field("value")?,
            ))
        })
        .collect()
}

/// The names in `source("name")` calls anywhere inside `node`.
fn source_names(node: &Syntax<'_>) -> Vec<String> {
    node.dfs()
        .filter(|n| n.kind() == "call")
        .filter(|call| {
            call.field("function")
                .is_some_and(|f| f.text().rsplit('.').next() == Some("source"))
        })
        .filter_map(|call| {
            let arguments = call.field("arguments")?;
            let first = arguments.children().find(Node::is_named)?;
            literal(&first)
        })
        .collect()
}

/// The literal names among the arguments of `@extract_columns("a", "b")` and of
/// `@extract_fields({"a": int})`, and whether every argument was one.
fn literal_names(arguments: &[Syntax<'_>]) -> (Vec<String>, bool) {
    let mut names = Vec::new();
    let mut complete = true;
    for argument in arguments {
        match argument.kind().as_ref() {
            "string" => match literal(argument) {
                Some(name) => names.push(name),
                None => complete = false,
            },
            "dictionary" | "call" => match pairs(argument) {
                Some(found) => names.extend(found.into_iter().map(|(name, _)| name)),
                None => complete = false,
            },
            // extract_fields(fields={...}) names the nodes. fill_with= and the like name none.
            "keyword_argument" => {
                let is_fields = argument.field("name").is_some_and(|n| n.text() == "fields");
                if let Some(value) = argument.field("value").filter(|_| is_fields) {
                    let (found, all) = literal_names(&[value]);
                    names.extend(found);
                    complete &= all;
                }
            }
            _ => complete = false,
        }
    }
    (names, complete)
}

/// The value of the keyword argument `name`.
fn keyword<'r>(arguments: &[Syntax<'r>], name: &str) -> Option<Syntax<'r>> {
    arguments
        .iter()
        .filter(|a| a.kind() == "keyword_argument")
        .find(|a| a.field("name").is_some_and(|n| n.text() == name))
        .and_then(|a| a.field("value"))
}

/// The argument at `position`, or else the keyword argument `name`.
fn positional_or_keyword<'r>(
    arguments: &[Syntax<'r>],
    position: usize,
    name: &str,
) -> Option<Syntax<'r>> {
    arguments
        .iter()
        .filter(|a| a.kind() != "keyword_argument")
        .nth(position)
        .cloned()
        .or_else(|| keyword(arguments, name))
}

/// The text of a string literal with no interpolation, without its quotes.
pub(crate) fn literal(node: &Syntax<'_>) -> Option<String> {
    if node.kind() != "string" {
        return None;
    }
    let mut text = String::new();
    for part in node.children() {
        match part.kind().as_ref() {
            "string_content" => text.push_str(&part.text()),
            "string_start" | "string_end" => {}
            _ => return None,
        }
    }
    Some(text)
}
