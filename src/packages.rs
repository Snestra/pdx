//! Package checks: packages a library works better with, reported once per project when the
//! project's venv has the library but not the package.

use std::{
    env, fs,
    path::{Path, PathBuf},
};

use anyhow::{Context, Result};
use ast_grep_config::Severity;
use serde_json::Value;

use crate::{pyenv, report::Issue, rules::Pack};

/// One entry of a pack's `packages.json`.
#[derive(Debug)]
pub(crate) struct PackageCheck {
    /// Rule name in the report, such as `missing-pyarrow`.
    id: String,
    /// Distribution name, such as `pandas-stubs`.
    package: String,
    /// When not empty, the check runs only in a project that uses one of these tools.
    only_with: Vec<String>,
    message: String,
}

/// Reads a `packages.json`: a list of objects with `id`, `package` and `message`, and an
/// optional list `only_with`.
pub(crate) fn parse(json: &str) -> Result<Vec<PackageCheck>> {
    let entries: Vec<Value> = serde_json::from_str(json)?;
    entries.iter().map(check_from).collect()
}

fn check_from(entry: &Value) -> Result<PackageCheck> {
    let text = |key: &str| {
        entry
            .get(key)
            .and_then(Value::as_str)
            .map(str::to_owned)
            .with_context(|| format!("an entry needs a text field {key:?}: {entry}"))
    };
    let only_with = match entry.get("only_with") {
        None => Vec::new(),
        Some(tools) => tools
            .as_array()
            .and_then(|tools| {
                tools
                    .iter()
                    .map(|tool| tool.as_str().map(str::to_owned))
                    .collect()
            })
            .with_context(|| format!("only_with must be a list of tool names: {entry}"))?,
    };
    Ok(PackageCheck {
        id: text("id")?,
        package: text("package")?,
        only_with,
        message: text("message")?,
    })
}

/// One warning for each package that a pack asks for and the project's venv lacks. A pack is
/// checked only when the venv has its library, and a project without a venv gets no warning,
/// because nothing says what is installed.
pub(crate) fn missing(packs: &[Pack]) -> Vec<Issue> {
    let Some(venv) = pyenv::venv_root() else {
        return Vec::new();
    };
    let pyproject = venv.with_file_name("pyproject.toml");
    let configured = fs::read_to_string(&pyproject)
        .map(|text| configured_tools(&text))
        .unwrap_or_default();
    // The issue points at the file where the dependency is added, or else at the venv.
    let file = shown(if pyproject.is_file() {
        &pyproject
    } else {
        &venv
    });
    packs
        .iter()
        .filter(|pack| pyenv::installed_version(pack.module).is_some())
        .flat_map(|pack| pack.packages.iter().map(move |check| (pack, check)))
        .filter(|(_, check)| check.is_missing(&configured))
        .map(|(pack, check)| Issue {
            package: pack.module,
            rule: check.id.clone(),
            file: file.clone(),
            line: 1,
            column: 1,
            severity: Severity::Warning,
            message: check.message.clone(),
            fix: None,
        })
        .collect()
}

impl PackageCheck {
    /// `configured` holds the tools with a table in the project's `pyproject.toml`.
    fn is_missing(&self, configured: &[String]) -> bool {
        let uses =
            |tool: &String| configured.contains(tool) || pyenv::installed_version(tool).is_some();
        pyenv::installed_version(&self.package).is_none()
            && (self.only_with.is_empty() || self.only_with.iter().any(uses))
    }
}

/// The names in the `[tool.<name>]` and `[tool.<name>.<part>]` table headers of a
/// `pyproject.toml`.
fn configured_tools(pyproject: &str) -> Vec<String> {
    pyproject
        .lines()
        .filter_map(|line| line.trim().strip_prefix("[tool."))
        .filter_map(|rest| rest.split(['.', ']']).next())
        .map(str::to_owned)
        .collect()
}

/// `path` relative to the working directory when it is inside it, as the other issues show
/// their files.
fn shown(path: &Path) -> PathBuf {
    env::current_dir()
        .ok()
        .and_then(|cwd| path.strip_prefix(cwd).ok())
        .unwrap_or(path)
        .to_path_buf()
}
