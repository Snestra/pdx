//! The findings of one lint run, and how `check` and `hook` print them.

use std::{fmt, path::PathBuf};

use ast_grep_config::Severity;
use serde_json::{Value, json};

use crate::rules::Pack;

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

impl fmt::Display for Issue {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(
            f,
            "{}:{}:{}: {} [{}/{}] {}",
            self.file.display(),
            self.line,
            self.column,
            severity_name(&self.severity),
            self.package,
            self.rule,
            self.message
        )
    }
}

impl Issue {
    fn to_json(&self) -> Value {
        json!({"package": self.package, "rule": self.rule, "file": self.file.display().to_string(), "line": self.line,
               "column": self.column, "severity": severity_name(&self.severity), "message": self.message})
    }
}

fn set_name(pack: &Pack) -> String {
    pack.set
        .map_or_else(|| "common".to_owned(), |m| format!("v{m}"))
}

pub(crate) struct Report {
    pub(crate) packs: Vec<Pack>,
    pub(crate) issues: Vec<Issue>,
}

impl Report {
    pub(crate) fn has_errors(&self) -> bool {
        self.issues.iter().any(|i| i.severity == Severity::Error)
    }

    pub(crate) fn to_json(&self) -> Value {
        let packages: Vec<Value> = self
            .packs
            .iter()
            .map(|p| {
                json!({"name": p.module, "version": p.installed.version, "major": p.installed.major,
                       "source": p.installed.source.as_str(), "ruleset": set_name(p)})
            })
            .collect();
        let issues: Vec<Value> = self.issues.iter().map(Issue::to_json).collect();
        json!({"packages": packages, "issues": issues})
    }

    pub(crate) fn summary(&self) -> String {
        let packages: Vec<String> = self
            .packs
            .iter()
            .map(|p| {
                let version = p.installed.version.as_deref().unwrap_or("?");
                format!(
                    "{} {version} ({}, rules {})",
                    p.module,
                    p.installed.source.as_str(),
                    set_name(p)
                )
            })
            .collect();
        format!("{} issue(s); {}", self.issues.len(), packages.join("; "))
    }
}
