//! Walks paths, parses each Python file that imports pandas once, and runs every rule.

use std::{fmt, fs, io, path::PathBuf};

use ast_grep_config::{RuleConfig, Severity};
use ast_grep_core::tree_sitter::LanguageExt;
use ast_grep_language::SupportLang;
use rayon::prelude::*;
use serde_json::{Value, json};

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
    pub(crate) rule: String,
    pub(crate) file: String,
    pub(crate) line: usize,
    pub(crate) column: usize,
    pub(crate) level: Level,
    pub(crate) message: String,
}

impl Issue {
    pub(crate) fn to_json(&self) -> Value {
        json!({"rule": self.rule, "file": self.file, "line": self.line,
               "column": self.column, "severity": self.level.as_str(), "message": self.message})
    }
}

/// A path pdx was asked to check but could not read.
#[derive(Debug)]
pub(crate) struct ReadPathError {
    path: PathBuf,
    cause: String,
}

impl fmt::Display for ReadPathError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "cannot read {}: {}", self.path.display(), self.cause)
    }
}

impl std::error::Error for ReadPathError {}

impl ReadPathError {
    fn io(path: PathBuf, e: &io::Error) -> Self {
        Self {
            path,
            cause: e.to_string(),
        }
    }
}

/// Expands paths into Python files. Directories are walked with .gitignore respected.
pub(crate) fn collect_files(paths: &[PathBuf]) -> Result<Vec<PathBuf>, ReadPathError> {
    let mut files = Vec::new();
    for p in paths {
        let meta = fs::metadata(p).map_err(|e| ReadPathError::io(p.clone(), &e))?;
        if meta.is_file() {
            files.push(p.clone());
            continue;
        }
        for entry in ignore::WalkBuilder::new(p).build() {
            let entry = entry.map_err(|e| ReadPathError {
                path: p.clone(),
                cause: e.to_string(),
            })?;
            let path = entry.path();
            if entry.file_type().is_some_and(|t| t.is_file())
                && path
                    .extension()
                    .is_some_and(|x| x.eq_ignore_ascii_case("py"))
            {
                files.push(path.to_path_buf());
            }
        }
    }
    Ok(files)
}

/// Runs every rule over every file that imports pandas. Files without a pandas import are skipped,
/// because the rules match names such as `merge` and `inplace` that other libraries share.
pub(crate) fn scan(
    files: &[PathBuf],
    rules: &[RuleConfig<SupportLang>],
    pandas_import: &RuleConfig<SupportLang>,
) -> Result<Vec<Issue>, ReadPathError> {
    let per_file: Vec<Vec<Issue>> = files
        .par_iter()
        .map(|path| {
            let src = fs::read_to_string(path).map_err(|e| ReadPathError::io(path.clone(), &e))?;
            if !src.contains("pandas") {
                return Ok(Vec::new());
            }
            let root = SupportLang::Python.ast_grep(&src);
            if root.root().find(&pandas_import.matcher).is_none() {
                return Ok(Vec::new());
            }
            let mut found = Vec::new();
            for rule in rules {
                let Some(level) = Level::from_severity(&rule.severity) else {
                    continue;
                };
                for m in root.root().find_all(&rule.matcher) {
                    let pos = m.start_pos();
                    found.push(Issue {
                        rule: rule.id.clone(),
                        file: path.display().to_string(),
                        line: pos.line() + 1,
                        column: pos.column(&m) + 1,
                        level,
                        message: rule.get_message(&m),
                    });
                }
            }
            Ok(found)
        })
        .collect::<Result<_, _>>()?;
    let mut issues: Vec<Issue> = per_file.into_iter().flatten().collect();
    issues.sort_by(|a, b| (&a.file, a.line, a.column).cmp(&(&b.file, b.line, b.column)));
    Ok(issues)
}
