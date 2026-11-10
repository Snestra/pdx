//! Finds where the project's Python keeps installed packages, and their versions, without
//! starting Python on the hot path.
//!
//! The site folders come from a venv (`$VIRTUAL_ENV`, then the nearest `.venv` above the working
//! directory), else from `python3` on `PATH`: first from the cache, then by asking that Python
//! once and caching its answer. Versions are read from `<module>-<version>.dist-info` folders.

use std::{
    env, fs,
    path::{Path, PathBuf},
    process::Command,
    time::UNIX_EPOCH,
};

/// Prints the folders Python imports installed packages from, one per line, in the order
/// Python searches them: the user site folder comes before the interpreter's own.
const SITE_DIRS_PY: &str = "import site, sysconfig; print(site.getusersitepackages()); print(sysconfig.get_paths()['purelib'])";

/// Where a library's version came from, reported in pdx output.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub(crate) enum Source {
    /// `--pin` or `PDX_PIN`.
    Pin,
    Venv,
    Cache,
    Python,
    /// No install found; the pack's newest rule set applies.
    Missing,
}

impl Source {
    pub(crate) fn as_str(self) -> &'static str {
        match self {
            Self::Pin => "pin",
            Self::Venv => "venv",
            Self::Cache => "cache",
            Self::Python => "python",
            Self::Missing => "missing",
        }
    }
}

/// The installed version of one library, as far as pdx could tell.
#[derive(Debug, Clone, PartialEq, Eq)]
pub(crate) struct Installed {
    /// Full version from the dist-info folder; `None` for a pin or a missing install.
    pub(crate) version: Option<String>,
    pub(crate) major: Option<u32>,
    pub(crate) source: Source,
}

impl Installed {
    pub(crate) fn pinned(major: u32) -> Self {
        Self {
            version: None,
            major: Some(major),
            source: Source::Pin,
        }
    }

    pub(crate) fn missing() -> Self {
        Self {
            version: None,
            major: None,
            source: Source::Missing,
        }
    }
}

/// The folders one Python imports installed packages from.
#[derive(Debug)]
pub(crate) struct Site {
    dirs: Vec<PathBuf>,
    source: Source,
}

impl Site {
    /// Finds the site folders, or `None` when there is no venv and no `python3` on `PATH`.
    pub(crate) fn locate() -> Option<Self> {
        if let Some(venv) = venv_root() {
            return Some(Self {
                dirs: venv_site_dirs(&venv),
                source: Source::Venv,
            });
        }
        let python = path_python()?;
        if let Some(dirs) = cache::lookup(&python) {
            return Some(Self {
                dirs,
                source: Source::Cache,
            });
        }
        let dirs = ask_site_dirs(&python)?;
        cache::store(&python, &dirs);
        Some(Self {
            dirs,
            source: Source::Python,
        })
    }

    /// Reads the installed version of `module`. The folders are scanned on every run, so an
    /// install, upgrade, or removal shows up without asking Python again.
    pub(crate) fn installed(&self, module: &str) -> Installed {
        let prefix = format!("{module}-");
        let version = self
            .dirs
            .iter()
            .filter_map(|d| fs::read_dir(d).ok())
            .flat_map(Iterator::flatten)
            .find_map(|e| {
                let name = e.file_name();
                let name = name.to_str()?;
                name.strip_prefix(&prefix)?
                    .strip_suffix(".dist-info")
                    .map(str::to_owned)
            });
        match version {
            Some(version) => {
                let major = version.split('.').next().and_then(|s| s.parse().ok());
                Installed {
                    version: Some(version),
                    major,
                    source: self.source,
                }
            }
            None => Installed::missing(),
        }
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
