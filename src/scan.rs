//! Walks paths, fixes and lints each Python file with the rule packs for the libraries it imports.

use std::{
    collections::HashSet,
    fs,
    path::{Path, PathBuf},
};

use anyhow::{Context, Result};
use ast_grep_core::{
    AstGrep, NodeMatch,
    source::Edit,
    tree_sitter::{LanguageExt, StrDoc},
};
use ast_grep_language::SupportLang;
use rayon::iter::{IntoParallelRefIterator, ParallelIterator};

use crate::{
    report::Issue,
    rules::{Applicability, Pack, Rule},
};

type Root = AstGrep<StrDoc<SupportLang>>;

/// Short names a fix may write, each with the module it must be imported as. A fix that writes
/// `pd.` applies only in a file with `import pandas as pd`. Elsewhere its issue has no fix.
const IMPORT_NAMES: &[(&str, &str)] = &[("pd", "pandas"), ("np", "numpy")];

pub(crate) fn is_python(path: &Path) -> bool {
    path.extension()
        .is_some_and(|x| x.eq_ignore_ascii_case("py"))
}

fn cannot_read(path: &Path) -> String {
    format!("cannot read {}", path.display())
}

pub(crate) fn collect_files(paths: &[PathBuf]) -> Result<Vec<PathBuf>> {
    let mut files = Vec::new();
    let mut seen = HashSet::new();
    let mut add = |path: &Path| -> Result<()> {
        let real = fs::canonicalize(path).with_context(|| cannot_read(path))?;
        if seen.insert(real) {
            files.push(path.to_path_buf());
        }
        Ok(())
    };
    for p in paths {
        let meta = fs::metadata(p).with_context(|| cannot_read(p))?;
        if meta.is_file() {
            add(p)?;
            continue;
        }
        for entry in ignore::WalkBuilder::new(p).build() {
            let entry = entry.with_context(|| cannot_read(p))?;
            if entry.file_type().is_some_and(|t| t.is_file()) && is_python(entry.path()) {
                add(entry.path())?;
            }
        }
    }
    Ok(files)
}

/// What a scan found, after any fixes it wrote.
pub(crate) struct Scanned {
    pub(crate) issues: Vec<Issue>,
    /// Number of fixes written to disk.
    pub(crate) fixed: usize,
}

/// A fix can create a match for another fix, so fixing repeats until nothing changes, at
/// most this many times per file.
const MAX_FIX_PASSES: usize = 100;

/// Lints each file, after applying fixes up to `fix` when it is set and writing them back.
pub(crate) fn scan(
    files: &[PathBuf],
    packs: &[Pack],
    fix: Option<Applicability>,
) -> Result<Scanned> {
    let per_file: Vec<(Vec<Issue>, usize)> = files
        .par_iter()
        .map(|path| {
            let mut src = fs::read_to_string(path).with_context(|| cannot_read(path))?;
            let mut fixed = 0;
            if let Some(allowed) = fix {
                for _ in 0..MAX_FIX_PASSES {
                    let (next, applied) = fix_pass(&src, packs, allowed);
                    if applied == 0 {
                        break;
                    }
                    src = next;
                    fixed += applied;
                }
                if fixed > 0 {
                    fs::write(path, &src)
                        .with_context(|| format!("cannot write {}", path.display()))?;
                }
            }
            Ok((lint(path, &src, packs), fixed))
        })
        .collect::<Result<_>>()?;
    let fixed = per_file.iter().map(|(_, n)| n).sum();
    let mut issues: Vec<Issue> = per_file.into_iter().flat_map(|(i, _)| i).collect();
    issues.sort_by(|a, b| (&a.file, a.line, a.column).cmp(&(&b.file, b.line, b.column)));
    Ok(Scanned { issues, fixed })
}

/// Parses `src` only when it names a pack's module, and yields each pack whose library the
/// file imports. Rules run only on those files, because they match names such as `merge` and
/// `inplace` that other libraries share.
fn imported<'p>(root: &Root, src: &str, packs: &'p [Pack]) -> impl Iterator<Item = &'p Pack> {
    packs
        .iter()
        .filter(move |p| src.contains(p.module) && root.root().find(&p.gate.matcher).is_some())
}

fn lint(path: &Path, src: &str, packs: &[Pack]) -> Vec<Issue> {
    if !packs.iter().any(|p| src.contains(p.module)) {
        return Vec::new();
    }
    let root = SupportLang::Python.ast_grep(src);
    let names = bound_names(&root);
    let mut found = Vec::new();
    for pack in imported(&root, src, packs) {
        for rule in &pack.rules {
            for m in root.root().find_all(&rule.config.matcher) {
                let pos = m.start_pos();
                let fix = rule.fix.filter(|_| usable_edit(rule, &m, &names).is_some());
                found.push(Issue {
                    package: pack.module,
                    rule: rule.config.id.clone(),
                    file: path.to_path_buf(),
                    line: pos.line() + 1,
                    column: pos.column(&m) + 1,
                    severity: rule.config.severity.clone(),
                    message: rule.config.get_message(&m),
                    fix,
                });
            }
        }
    }
    found
}

/// Applies every fix up to `allowed` that does not overlap an earlier one, and returns the new
/// source with the number of fixes applied. Overlapping fixes wait for the next pass.
fn fix_pass(src: &str, packs: &[Pack], allowed: Applicability) -> (String, usize) {
    if !packs.iter().any(|p| src.contains(p.module)) {
        return (src.to_owned(), 0);
    }
    let root = SupportLang::Python.ast_grep(src);
    let names = bound_names(&root);
    let mut edits = Vec::new();
    for pack in imported(&root, src, packs) {
        for rule in &pack.rules {
            if rule.fix.is_none_or(|a| a > allowed) {
                continue;
            }
            for m in root.root().find_all(&rule.config.matcher) {
                let Some(edit) = usable_edit(rule, &m, &names) else {
                    continue;
                };
                let old = &src.as_bytes()[edit.position..edit.position + edit.deleted_length];
                if edit.inserted_text != old {
                    edits.push(edit);
                }
            }
        }
    }
    edits.sort_by_key(|e| e.position);
    let mut out = Vec::with_capacity(src.len());
    let mut copied = 0;
    let mut applied = 0;
    for edit in edits {
        if edit.position < copied {
            continue;
        }
        out.extend_from_slice(&src.as_bytes()[copied..edit.position]);
        out.extend_from_slice(&edit.inserted_text);
        copied = edit.position + edit.deleted_length;
        applied += 1;
    }
    out.extend_from_slice(&src.as_bytes()[copied..]);
    let out = String::from_utf8(out).expect("fixes splice UTF-8 text at node boundaries");
    (out, applied)
}

/// The names from `IMPORT_NAMES` that the file binds with `import <module> as <name>`.
fn bound_names(root: &Root) -> Vec<&'static str> {
    let aliases: Vec<(String, String)> = root
        .root()
        .dfs()
        .filter(|n| n.kind() == "aliased_import")
        .filter_map(|n| {
            Some((
                n.field("name")?.text().into(),
                n.field("alias")?.text().into(),
            ))
        })
        .collect();
    IMPORT_NAMES
        .iter()
        .filter(|(name, module)| aliases.iter().any(|(m, a)| m == module && a == name))
        .map(|(name, _)| *name)
        .collect()
}

/// The edit `rule` makes for `m`, or `None` when the rule has no fix or its fix writes a name
/// from `IMPORT_NAMES` that is not in `bound`.
fn usable_edit(
    rule: &Rule,
    m: &NodeMatch<'_, StrDoc<SupportLang>>,
    bound: &[&str],
) -> Option<Edit<String>> {
    let fixer = rule.config.fixer.first()?;
    let edit = m.make_edit(&rule.config.matcher, fixer);
    let unbound = IMPORT_NAMES
        .iter()
        .any(|(name, _)| !bound.contains(name) && writes_name(&edit.inserted_text, name));
    (!unbound).then_some(edit)
}

/// Whether `text` uses `name` as the start of a dotted name, such as `pd.col`.
fn writes_name(text: &[u8], name: &str) -> bool {
    let needle = format!("{name}.");
    text.windows(needle.len()).enumerate().any(|(i, w)| {
        w == needle.as_bytes()
            && (i == 0
                || !(text[i - 1].is_ascii_alphanumeric() || matches!(text[i - 1], b'_' | b'.')))
    })
}
