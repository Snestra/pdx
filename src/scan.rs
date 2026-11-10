//! Walks paths, parses each Python file once, and runs the rule packs for the libraries it imports.

use std::{
    collections::HashSet,
    fs,
    path::{Path, PathBuf},
};

use anyhow::{Context, Result};
use ast_grep_core::tree_sitter::LanguageExt;
use ast_grep_language::SupportLang;
use rayon::iter::{IntoParallelRefIterator, ParallelIterator};

use crate::{report::Issue, rules::Pack};

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

/// Runs each pack only on files that import its library, because rules match names such as
/// `merge` and `inplace` that other libraries share.
pub(crate) fn scan(files: &[PathBuf], packs: &[Pack]) -> Result<Vec<Issue>> {
    let per_file: Vec<Vec<Issue>> = files
        .par_iter()
        .map(|path| {
            let src = fs::read_to_string(path).with_context(|| cannot_read(path))?;
            let mut root = None;
            let mut found = Vec::new();
            for pack in packs.iter().filter(|p| src.contains(p.module)) {
                let root = root.get_or_insert_with(|| SupportLang::Python.ast_grep(&src));
                if root.root().find(&pack.gate.matcher).is_none() {
                    continue;
                }
                for rule in &pack.rules {
                    for m in root.root().find_all(&rule.matcher) {
                        let pos = m.start_pos();
                        found.push(Issue {
                            package: pack.module,
                            rule: rule.id.clone(),
                            file: path.clone(),
                            line: pos.line() + 1,
                            column: pos.column(&m) + 1,
                            severity: rule.severity.clone(),
                            message: rule.get_message(&m),
                        });
                    }
                }
            }
            Ok(found)
        })
        .collect::<Result<_>>()?;
    let mut issues: Vec<Issue> = per_file.into_iter().flatten().collect();
    issues.sort_by(|a, b| (&a.file, a.line, a.column).cmp(&(&b.file, b.line, b.column)));
    Ok(issues)
}
