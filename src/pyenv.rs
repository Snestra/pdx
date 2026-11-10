//! Finds the project's Python and its pandas version without starting Python on the hot path.
//!
//! Order: `--pandas`, `PDX_PANDAS_MAJOR`, a venv (`$VIRTUAL_ENV`, then the nearest `.venv`
//! above the working directory), the cached site-packages of `python3` on `PATH`, then asking
//! that Python once and caching its answer.

use std::{
    env, fs,
    path::{Path, PathBuf},
    process::Command,
    time::UNIX_EPOCH,
};

/// Used when no pandas install is found: the newest major pdx has rules for.
const DEFAULT_MAJOR: u32 = 3;

/// Prints the folders Python imports installed packages from, one per line, in the order
/// Python searches them: the user site folder comes before the interpreter's own.
const SITE_DIRS_PY: &str = "import site, sysconfig; print(site.getusersitepackages()); print(sysconfig.get_paths()['purelib'])";

/// Where the pandas version came from, reported in pdx output.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub(crate) enum Source {
    Flag,
    Env,
    Venv,
    Cache,
    Python,
    Default,
}

impl Source {
    pub(crate) fn as_str(self) -> &'static str {
        match self {
            Self::Flag => "flag",
            Self::Env => "env",
            Self::Venv => "venv",
            Self::Cache => "cache",
            Self::Python => "python",
            Self::Default => "default",
        }
    }
}

#[derive(Debug)]
pub(crate) struct Pandas {
    pub(crate) version: Option<String>,
    pub(crate) major: u32,
    pub(crate) source: Source,
}

impl Pandas {
    fn found(version: String, source: Source) -> Self {
        let major = version
            .split('.')
            .next()
            .and_then(|s| s.parse().ok())
            .unwrap_or(DEFAULT_MAJOR);
        Self {
            version: Some(version),
            major,
            source,
        }
    }

    fn major_only(major: u32, source: Source) -> Self {
        Self {
            version: None,
            major,
            source,
        }
    }
}

pub(crate) fn detect(override_major: Option<u32>) -> Pandas {
    if let Some(m) = override_major {
        return Pandas::major_only(m, Source::Flag);
    }
    if let Some(m) = env::var("PDX_PANDAS_MAJOR")
        .ok()
        .and_then(|m| m.parse().ok())
    {
        return Pandas::major_only(m, Source::Env);
    }
    if let Some(venv) = venv_root()
        && let Some(v) = version_in(&venv_site_dirs(&venv))
    {
        return Pandas::found(v, Source::Venv);
    }
    let Some(python) = path_python() else {
        return Pandas::major_only(DEFAULT_MAJOR, Source::Default);
    };
    let (dirs, source) = match cache::lookup(&python) {
        Some(dirs) => (dirs, Source::Cache),
        None => match ask_site_dirs(&python) {
            Some(dirs) => {
                cache::store(&python, &dirs);
                (dirs, Source::Python)
            }
            None => return Pandas::major_only(DEFAULT_MAJOR, Source::Default),
        },
    };
    // The site folders are scanned on every run, so installing, upgrading, or removing pandas
    // shows up without asking Python again.
    match version_in(&dirs) {
        Some(v) => Pandas::found(v, source),
        None => Pandas::major_only(DEFAULT_MAJOR, Source::Default),
    }
}

/// Interpreter for `profile` and `equiv`: the venv's Python, then `python3` on `PATH`.
pub(crate) fn python() -> PathBuf {
    if let Some(venv) = venv_root() {
        for rel in ["bin/python", "Scripts/python.exe"] {
            let p = venv.join(rel);
            if p.is_file() {
                return p;
            }
        }
    }
    path_python().unwrap_or_else(|| PathBuf::from("python3"))
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

fn venv_site_dirs(venv: &Path) -> Vec<PathBuf> {
    let mut dirs = vec![venv.join("Lib").join("site-packages")];
    if let Ok(entries) = fs::read_dir(venv.join("lib")) {
        dirs.extend(entries.flatten().map(|e| e.path().join("site-packages")));
    }
    dirs
}

/// Reads the version from a `pandas-X.Y.Z.dist-info` folder name in any of `dirs`.
fn version_in(dirs: &[PathBuf]) -> Option<String> {
    dirs.iter()
        .filter_map(|d| fs::read_dir(d).ok())
        .flat_map(Iterator::flatten)
        .find_map(|e| {
            let name = e.file_name();
            let name = name.to_str()?;
            name.strip_prefix("pandas-")?
                .strip_suffix(".dist-info")
                .map(str::to_owned)
        })
}

fn path_python() -> Option<PathBuf> {
    let path = env::var_os("PATH")?;
    env::split_paths(&path)
        .flat_map(|d| ["python3", "python3.exe"].map(|name| d.join(name)))
        .find(|p| p.is_file())
}

fn ask_site_dirs(python: &Path) -> Option<Vec<PathBuf>> {
    let out = Command::new(python)
        .args(["-c", SITE_DIRS_PY])
        .output()
        .ok()?;
    out.status.success().then(|| {
        String::from_utf8_lossy(&out.stdout)
            .lines()
            .map(PathBuf::from)
            .collect()
    })
}

/// Remembers each Python's site folders, so only the first run per interpreter starts Python.
mod cache {
    use super::{PathBuf, UNIX_EPOCH, env, fs};
    use std::path::Path;

    /// An entry stays valid while the interpreter file, its modification time, and the
    /// working directory are unchanged. The directory is part of the key because version
    /// managers such as mise point one `python3` shim at different interpreters per project.
    fn key(python: &Path) -> Option<String> {
        let real = fs::canonicalize(python).ok()?;
        let mtime = fs::metadata(&real)
            .ok()?
            .modified()
            .ok()?
            .duration_since(UNIX_EPOCH)
            .ok()?
            .as_secs();
        let cwd = env::current_dir().ok()?;
        Some(format!("{}|{mtime}|{}", real.display(), cwd.display()))
    }

    fn file() -> Option<PathBuf> {
        let base = env::var_os("XDG_CACHE_HOME")
            .map(PathBuf::from)
            .or_else(|| env::var_os("HOME").map(|h| PathBuf::from(h).join(".cache")))?;
        Some(base.join("pdx").join("site-dirs"))
    }

    /// One line per entry: the key, then each site folder, separated by tabs.
    pub(super) fn lookup(python: &Path) -> Option<Vec<PathBuf>> {
        let key = key(python)?;
        let text = fs::read_to_string(file()?).ok()?;
        text.lines().find_map(|line| {
            let mut fields = line.split('\t');
            (fields.next()? == key).then(|| fields.map(PathBuf::from).collect())
        })
    }

    /// Best effort: a cache that can't be written only costs the next run one Python start.
    pub(super) fn store(python: &Path, dirs: &[PathBuf]) {
        let (Some(key), Some(file)) = (key(python), file()) else {
            return;
        };
        let Some(folder) = file.parent() else { return };
        if fs::create_dir_all(folder).is_err() {
            return;
        }
        let old = fs::read_to_string(&file).unwrap_or_default();
        let mut lines: Vec<String> = old
            .lines()
            .filter(|l| l.split('\t').next() != Some(key.as_str()))
            .map(str::to_owned)
            .collect();
        let dirs: Vec<String> = dirs.iter().map(|d| d.display().to_string()).collect();
        lines.push(format!("{key}\t{}", dirs.join("\t")));
        let mut text = lines.join("\n");
        text.push('\n');
        // Write a temporary file and rename it, so a parallel pdx never reads half a file.
        let tmp = folder.join(format!("site-dirs.{}", std::process::id()));
        if fs::write(&tmp, text).is_ok() && fs::rename(&tmp, &file).is_err() {
            let _ = fs::remove_file(&tmp); // best effort; a leftover temp file is harmless
        }
    }
}
