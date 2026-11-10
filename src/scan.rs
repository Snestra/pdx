//! Walks paths, parses each Python file once, and runs the rule packs for the libraries it imports.

use std::{
    collections::HashSet,
    fmt, fs,
    path::{Path, PathBuf},
};

use anyhow::{Context, Result};
use ast_grep_config::Severity;
use ast_grep_core::tree_sitter::LanguageExt;
use ast_grep_language::SupportLang;
use rayon::iter::{IntoParallelRefIterator, ParallelIterator};
use serde_json::{Value, json};

use crate::rules::Pack;

/// How serious a finding is. Only `Error` fails `pdx check`.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub(crate) enum Level {
    Error,
    Warning,
    Info,
    Hint,
}

impl Level {
    fn from_severity(s: &Severity) -> Option<Self> {
        match s {
            Severity::Error => Some(Self::Error),
            Severity::Warning => Some(Self::Warning),
            Severity::Info => Some(Self::Info),
            Severity::Hint => Some(Self::Hint),
            Severity::Off => None,
        }
    }

    fn as_str(self) -> &'static str {
        match self {
            Self::Error => "error",
            Self::Warning => "warning",
            Self::Info => "info",
            Self::Hint => "hint",
        }
    }
}

impl fmt::Display for Level {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(self.as_str())
    }
}

#[derive(Debug)]
pub(crate) struct Issue {
    /// Module name of the pack the rule belongs to.
    pub(crate) package: &'static str,
    pub(crate) rule: String,
    pub(crate) file: PathBuf,
    pub(crate) line: usize,
    pub(crate) column: usize,
    pub(crate) level: Level,
    pub(crate) message: String,
}

impl Issue {
    pub(crate) fn to_json(&self) -> Value {
        json!({"package": self.package, "rule": self.rule, "file": self.file.display().to_string(), "line": self.line,
               "column": self.column, "severity": self.level.as_str(), "message": self.message})
    }
}

/// The context every read error carries, so the message names the path.
fn cannot_read(path: &Path) -> String {
    format!("cannot read {}", path.display())
}

/// Expands paths into Python files. Directories are walked with .gitignore respected. A file
/// reached through several paths, such as `a.py ./a.py` or `. src/`, is listed once.
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
            let path = entry.path();
            if entry.file_type().is_some_and(|t| t.is_file())
                && path
                    .extension()
                    .is_some_and(|x| x.eq_ignore_ascii_case("py"))
            {
                add(path)?;
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
            // A file that never names the module can't import it, so it is never parsed.
            let mut root = None;
            let mut found = Vec::new();
            for pack in packs.iter().filter(|p| src.contains(p.module)) {
                let root = root.get_or_insert_with(|| SupportLang::Python.ast_grep(&src));
                if root.root().find(&pack.gate.matcher).is_none() {
                    continue;
                }
                for rule in &pack.rules {
                    let Some(level) = Level::from_severity(&rule.severity) else {
                        continue;
                    };
                    for m in root.root().find_all(&rule.matcher) {
                        let pos = m.start_pos();
                        found.push(Issue {
                            package: pack.module,
                            rule: rule.id.clone(),
                            file: path.clone(),
                            line: pos.line() + 1,
                            column: pos.column(&m) + 1,
                            level,
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
