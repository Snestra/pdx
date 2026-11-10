//! Package checks: packages a library works better with, reported once per project when the
//! project's venv has the library but not the package.

use std::env;
use std::fs;
use std::path::{Path, PathBuf};

use ast_grep_config::Severity;
use serde::Deserialize;

use crate::pack::Pack;
use crate::report::Issue;
use crate::venv::{Distributions, Venv};

/// One entry under `packages` in a pack's `pack.yml`.
#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub(crate) struct PackageCheck {
    /// Rule name in the report, such as `missing-pyarrow`.
    id: String,
    /// Distribution name, such as `pandas-stubs`.
    package: String,
    /// When not empty, the check runs only in a project that uses one of these tools.
    #[serde(default)]
    only_with: Vec<String>,
    message: String,
}

impl PackageCheck {
    /// `configured` holds the tools with a table in the project's `pyproject.toml`.
    fn is_missing(&self, installed: &Distributions, configured: &[&str]) -> bool {
        let uses = |tool: &str| configured.contains(&tool) || installed.version(tool).is_some();
        installed.version(&self.package).is_none()
            && (self.only_with.is_empty() || self.only_with.iter().any(|tool| uses(tool)))
    }
}

/// One warning for each package that a pack asks for and the venv lacks. A pack is checked only
/// when the venv has its library. `installed` is what `venv` holds.
pub(crate) fn missing(packs: &[Pack], venv: &Venv, installed: &Distributions) -> Vec<Issue> {
    let pyproject = venv.root().with_file_name("pyproject.toml");
    let pyproject_text = fs::read_to_string(&pyproject).ok();
    let configured = pyproject_text.as_deref().map(configured_tools);
    let configured = configured.as_deref().unwrap_or_default();
    // The issue points at the file where the dependency is added, or else at the venv.
    let file = shown(if pyproject_text.is_some() {
        &pyproject
    } else {
        venv.root()
    });
    packs
        .iter()
        .filter(|pack| installed.version(pack.module).is_some())
        .flat_map(|pack| pack.package_checks.iter().map(move |check| (pack, check)))
        .filter(|(_, check)| check.is_missing(installed, configured))
        .map(|(pack, check)| Issue {
            package: pack.module,
            rule: check.id.clone(),
            file: file.clone(),
            position: None,
            severity: Severity::Warning,
            message: check.message.clone(),
            fix: None,
        })
        .collect()
}

/// The names in the `[tool.<name>]` and `[tool.<name>.<part>]` table headers of a
/// `pyproject.toml`.
fn configured_tools(pyproject: &str) -> Vec<&str> {
    pyproject
        .lines()
        .filter_map(|line| line.trim().strip_prefix("[tool."))
        .filter_map(|rest| rest.split(['.', ']']).next())
        .collect()
}

/// `path` relative to the working directory when it is inside it, as the other issues show
/// their files.
fn shown(path: &Path) -> PathBuf {
    env::current_dir()
        .ok()
        .and_then(|cwd| path.strip_prefix(cwd).ok().map(Path::to_path_buf))
        .unwrap_or_else(|| path.to_path_buf())
}
