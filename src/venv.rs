//! The project's Python virtual environment. `profile` and `equiv` run its Python, and `check`
//! reads the installed versions from it without starting Python.

use std::env;
use std::fs;
use std::path::{Path, PathBuf};

use crate::version::Version;

/// A Python virtual environment folder.
#[derive(Debug)]
pub(crate) struct Venv {
    root: PathBuf,
}

impl Venv {
    /// The venv in `$VIRTUAL_ENV`, or else the nearest `.venv` above the working directory.
    pub(crate) fn find() -> Option<Self> {
        if let Some(root) = env::var_os("VIRTUAL_ENV") {
            return Some(Self { root: root.into() });
        }
        let cwd = env::current_dir().ok()?;
        cwd.ancestors()
            .map(|dir| dir.join(".venv"))
            .find(|root| root.is_dir())
            .map(|root| Self { root })
    }

    /// The venv folder. The folder that holds it is the project.
    pub(crate) fn root(&self) -> &Path {
        &self.root
    }

    fn python(&self) -> Option<PathBuf> {
        ["bin/python", "Scripts/python.exe"]
            .map(|rel| self.root.join(rel))
            .into_iter()
            .find(|python| python.is_file())
    }

    /// Lists what is installed, from the `<name>-<version>.dist-info` folders.
    pub(crate) fn distributions(&self) -> Distributions {
        let mut dist_infos: Vec<PathBuf> = self
            .site_dirs()
            .iter()
            .filter_map(|dir| fs::read_dir(dir).ok())
            .flatten()
            .flatten()
            .map(|entry| entry.path())
            .collect();
        // In name order, so a module that two distributions provide always resolves the same way.
        dist_infos.sort();
        let found = dist_infos
            .into_iter()
            .filter_map(|dist_info| {
                let folder = dist_info
                    .file_name()?
                    .to_str()?
                    .strip_suffix(".dist-info")?;
                let (name, version) = folder.split_once('-')?;
                Some(Distribution {
                    name: normalized(name),
                    version: version.parse().ok()?,
                    dist_info,
                })
            })
            .collect();
        Distributions { found }
    }

    /// `Lib/site-packages` on Windows, `lib/python3.x/site-packages` elsewhere, and
    /// `lib64/python3.x/site-packages`, where Fedora and similar systems put compiled packages.
    fn site_dirs(&self) -> Vec<PathBuf> {
        let mut dirs = vec![self.root.join("Lib").join("site-packages")];
        for lib in ["lib", "lib64"] {
            if let Ok(entries) = fs::read_dir(self.root.join(lib)) {
                dirs.extend(entries.flatten().map(|e| e.path().join("site-packages")));
            }
        }
        dirs
    }
}

/// What a venv has installed.
#[derive(Debug)]
pub(crate) struct Distributions {
    found: Vec<Distribution>,
}

/// One installed distribution.
#[derive(Debug)]
struct Distribution {
    /// Normalized, such as `pandas_stubs`.
    name: String,
    version: Version,
    dist_info: PathBuf,
}

impl Distributions {
    /// The installed version of `name`, which is a distribution name such as `pandas-stubs`, or
    /// a module name that a distribution lists in its `top_level.txt`, as scikit-learn lists
    /// `sklearn`. A distribution name wins over a module name.
    pub(crate) fn version(&self, name: &str) -> Option<&Version> {
        let name = normalized(name);
        self.found
            .iter()
            .find(|dist| dist.name == name)
            .or_else(|| self.found.iter().find(|dist| dist.lists_module(&name)))
            .map(|dist| &dist.version)
    }
}

impl Distribution {
    fn lists_module(&self, module: &str) -> bool {
        fs::read_to_string(self.dist_info.join("top_level.txt"))
            .is_ok_and(|text| text.lines().any(|line| line.trim() == module))
    }
}

/// Distribution names compare without case, and `-`, `.` and `_` count as the same character.
fn normalized(name: &str) -> String {
    name.to_ascii_lowercase().replace(['-', '.'], "_")
}

/// The Python that `profile` and `equiv` run: the venv's, or else `python3` on `PATH`.
pub(crate) fn project_python() -> PathBuf {
    Venv::find()
        .and_then(|venv| venv.python())
        .or_else(path_python)
        .unwrap_or_else(|| PathBuf::from("python3"))
}

fn path_python() -> Option<PathBuf> {
    let path = env::var_os("PATH")?;
    env::split_paths(&path)
        .flat_map(|dir| ["python3", "python3.exe"].map(|name| dir.join(name)))
        .find(|python| python.is_file())
}
