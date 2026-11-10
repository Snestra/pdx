//! Finds the project's Python environment: the venv in `$VIRTUAL_ENV`, then the nearest `.venv`
//! above the working directory. `profile` and `equiv` run its Python, falling back to `python3`
//! on `PATH`, and `check` reads installed versions from it without starting Python.

use std::{
    env, fs,
    path::{Path, PathBuf},
};

pub(crate) fn python() -> PathBuf {
    let venv_python = |venv: &Path| {
        ["bin/python", "Scripts/python.exe"]
            .map(|rel| venv.join(rel))
            .into_iter()
            .find(|p| p.is_file())
    };
    venv_root()
        .and_then(|venv| venv_python(&venv))
        .or_else(path_python)
        .unwrap_or_else(|| PathBuf::from("python3"))
}

/// The version of the installed distribution that provides `module`, such as `3.1.1` for
/// `pandas`, read from the name of its `<name>-<version>.dist-info` folder in the venv. A
/// distribution provides the module when its normalized name is the module name, or when its
/// `top_level.txt` lists the module, as scikit-learn lists `sklearn`. `None` when there is no
/// venv or the module is not installed in it.
pub(crate) fn installed_version(module: &str) -> Option<String> {
    let venv = venv_root()?;
    site_dirs(&venv)
        .iter()
        .filter_map(|dir| fs::read_dir(dir).ok())
        .flatten()
        .flatten()
        .find_map(|entry| dist_version(&entry.path(), module))
}

fn venv_root() -> Option<PathBuf> {
    if let Some(p) = env::var_os("VIRTUAL_ENV") {
        return Some(PathBuf::from(p));
    }
    let cwd = env::current_dir().ok()?;
    cwd.ancestors()
        .map(|d| d.join(".venv"))
        .find(|p| p.is_dir())
}

/// `Lib/site-packages` on Windows, `lib/python3.x/site-packages` elsewhere, and
/// `lib64/python3.x/site-packages`, where Fedora and similar systems put compiled packages.
fn site_dirs(venv: &Path) -> Vec<PathBuf> {
    let mut dirs = vec![venv.join("Lib").join("site-packages")];
    for lib in ["lib", "lib64"] {
        if let Ok(entries) = fs::read_dir(venv.join(lib)) {
            dirs.extend(entries.flatten().map(|e| e.path().join("site-packages")));
        }
    }
    dirs
}

/// The version in `path` when it is the dist-info folder of a distribution that provides
/// `module`.
fn dist_version(path: &Path, module: &str) -> Option<String> {
    let name = path.file_name()?.to_str()?.strip_suffix(".dist-info")?;
    let (dist, version) = name.split_once('-')?;
    let normalized = dist.to_ascii_lowercase().replace(['-', '.'], "_");
    let provides = normalized == module
        || fs::read_to_string(path.join("top_level.txt"))
            .is_ok_and(|text| text.lines().any(|line| line.trim() == module));
    provides.then(|| version.to_owned())
}

fn path_python() -> Option<PathBuf> {
    let path = env::var_os("PATH")?;
    env::split_paths(&path)
        .flat_map(|d| ["python3", "python3.exe"].map(|name| d.join(name)))
        .find(|p| p.is_file())
}
