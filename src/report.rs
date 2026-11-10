//! The findings of one lint run, and how `check` and `hook` print them.

use std::path::PathBuf;

use ast_grep_config::Severity;
use serde_json::{Value, json};

use crate::rules::Applicability;

#[derive(Debug)]
pub(crate) struct Issue {
    /// Module name of the pack the rule belongs to.
    pub(crate) package: &'static str,
    pub(crate) rule: String,
    pub(crate) file: PathBuf,
    pub(crate) line: usize,
    pub(crate) column: usize,
    pub(crate) severity: Severity,
    pub(crate) message: String,
    /// `None` when the rule has no fix.
    pub(crate) fix: Option<Applicability>,
}

fn severity_name(severity: &Severity) -> &'static str {
    match severity {
        Severity::Error => "error",
        Severity::Warning => "warning",
        Severity::Info => "info",
        Severity::Hint => "hint",
        Severity::Off => "off",
    }
}

impl Issue {
    fn fixable(&self, allowed: Applicability) -> bool {
        self.fix.is_some_and(|a| a <= allowed)
    }

    /// One line per issue. `[*]` marks an issue that `--fix` fixes at the `allowed` level.
    pub(crate) fn line(&self, allowed: Applicability) -> String {
        let mark = if self.fixable(allowed) { " [*]" } else { "" };
        format!(
            "{}:{}:{}: {} [{}/{}]{mark} {}",
            self.file.display(),
            self.line,
            self.column,
            severity_name(&self.severity),
            self.package,
            self.rule,
            self.message
        )
    }

    fn to_json(&self) -> Value {
        json!({"package": self.package, "rule": self.rule, "file": self.file.display().to_string(), "line": self.line,
               "column": self.column, "severity": severity_name(&self.severity), "message": self.message,
               "fix": self.fix.map(Applicability::as_str)})
    }
}

pub(crate) struct Report {
    pub(crate) issues: Vec<Issue>,
    /// Number of fixes `--fix` wrote.
    pub(crate) fixed: usize,
}

impl Report {
    pub(crate) fn has_errors(&self) -> bool {
        self.issues.iter().any(|i| i.severity == Severity::Error)
    }

    pub(crate) fn to_json(&self) -> Value {
        let issues: Vec<Value> = self.issues.iter().map(Issue::to_json).collect();
        json!({"fixed": self.fixed, "issues": issues})
    }

    /// For example `fixed 2, 3 issue(s), 1 fixable with --fix, 1 more with --fix --unsafe-fixes`.
    pub(crate) fn summary(&self, allowed: Applicability) -> String {
        let mut parts = Vec::new();
        if self.fixed > 0 {
            parts.push(format!("fixed {}", self.fixed));
        }
        parts.push(format!("{} issue(s)", self.issues.len()));
        let fixable = self.issues.iter().filter(|i| i.fixable(allowed)).count();
        if fixable > 0 {
            let flags = match allowed {
                Applicability::Safe => "--fix",
                Applicability::Unsafe => "--fix --unsafe-fixes",
            };
            parts.push(format!("{fixable} fixable with {flags}"));
        }
        let hidden = self.issues.iter().filter(|i| i.fix > Some(allowed)).count();
        if hidden > 0 {
            parts.push(format!("{hidden} more with --fix --unsafe-fixes"));
        }
        parts.join(", ")
    }
}
