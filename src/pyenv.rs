//! Finds the project's Python for `profile` and `equiv`: the venv in `$VIRTUAL_ENV`, then the
//! nearest `.venv` above the working directory, then `python3` on `PATH`.

use std::{
    env,
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

fn venv_root() -> Option<PathBuf> {
    if let Some(p) = env::var_os("VIRTUAL_ENV") {
        return Some(PathBuf::from(p));
    }
    let cwd = env::current_dir().ok()?;
    cwd.ancestors()
        .map(|d| d.join(".venv"))
        .find(|p| p.is_dir())
}

fn path_python() -> Option<PathBuf> {
    let path = env::var_os("PATH")?;
    env::split_paths(&path)
        .flat_map(|d| ["python3", "python3.exe"].map(|name| d.join(name)))
        .find(|p| p.is_file())
}
