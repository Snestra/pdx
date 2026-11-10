//! pdx lints Python code for library habits that give slow or wrong results, for humans and
//! coding agents. Each library gets a rule pack chosen for its installed version; pandas is
//! the first.

mod pyenv;
mod report;
mod rules;
mod scan;

use std::{
    collections::HashMap,
    env,
    io::{self, IsTerminal, Read},
    path::{Path, PathBuf},
    process::{Command, ExitCode},
    str::FromStr,
};

use anyhow::{Context, Result, bail};
use clap::{Parser, Subcommand, ValueEnum};
use serde_json::Value;

use crate::{pyenv::Versions, report::Report};

const SKILL: &str = include_str!("../SKILL.md");
const PROFILE_PY: &str = include_str!("../py/profile.py");
const EQUIV_PY: &str = include_str!("../py/equiv.py");

/// Exit code when pdx itself fails, as opposed to finding issues.
const CHECK_FAILED: u8 = 2;
/// Claude Code shows stderr to the agent only when a hook exits 2.
const HOOK_BLOCK: u8 = 2;
/// Any other non-zero hook exit shows stderr to the user without blocking the agent.
const HOOK_FAILED: u8 = 1;
/// The shell's code for a command that could not be started.
const PYTHON_NOT_STARTED: u8 = 127;

/// pdx: fast linter for Python library habits, for humans and coding agents.
#[derive(Debug, Parser)]
#[command(name = "pdx", version, about)]
struct Cli {
    #[command(subcommand)]
    cmd: Cmd,
}

#[derive(Debug, Clone, Copy, ValueEnum)]
enum Format {
    Text,
    Json,
}

#[derive(Debug, Subcommand)]
enum Cmd {
    /// Lint Python files. Exit 0 when clean, 1 on any error-severity issue, 2 if pdx can't run.
    ///
    /// A library's rules run only on files that import it, and follow its installed version.
    ///
    /// Examples:
    ///   pdx check src/
    ///   pdx check analysis.py --format json
    ///   pdx check . --pin pandas=2
    Check {
        /// Files or directories (directories respect .gitignore).
        #[arg(default_value = ".")]
        paths: Vec<PathBuf>,
        /// Output format. Default: text on a terminal, json otherwise.
        #[arg(long, value_enum)]
        format: Option<Format>,
        #[command(flatten)]
        pins: Pins,
    },
    /// Claude Code `PostToolUse` hook: reads hook JSON on stdin and lints the edited .py file.
    ///
    /// Exit 2 with issues on stderr so the agent sees them, 1 if pdx can't run, 0 otherwise.
    Hook {
        #[command(flatten)]
        pins: Pins,
    },
    /// Profile a data file (csv, parquet, feather, json, xlsx). Needs pandas.
    Profile { file: PathBuf },
    /// Check that two scripts produce an equal `result` (`DataFrame` or Series). Needs pandas.
    Equiv { old: PathBuf, new: PathBuf },
    /// Print the agent skill (SKILL.md) for this pdx version.
    Skill,
}

#[derive(Debug, clap::Args)]
struct Pins {
    /// Use the rules for a library's major version instead of the installed one, e.g.
    /// `--pin pandas=2`. Repeatable. Also read from `PDX_PIN`, comma-separated.
    #[arg(long = "pin", value_name = "MODULE=MAJOR")]
    pins: Vec<Pin>,
}

/// A library's major version given by the user rather than found on disk.
#[derive(Debug, Clone, PartialEq, Eq)]
struct Pin {
    module: String,
    major: u32,
}

impl FromStr for Pin {
    type Err = anyhow::Error;

    fn from_str(s: &str) -> Result<Self> {
        let (module, major) = s
            .split_once('=')
            .with_context(|| format!("expected MODULE=MAJOR, got {s:?}"))?;
        let major = major
            .trim()
            .parse()
            .with_context(|| format!("bad major version in {s:?}"))?;
        Ok(Self {
            module: module.trim().to_owned(),
            major,
        })
    }
}

impl Pins {
    /// Merges `PDX_PIN` with the flags; a flag wins over the environment for the same module.
    fn resolve(&self) -> Result<HashMap<String, u32>> {
        let from_env = env::var("PDX_PIN").unwrap_or_default();
        let env_pins = from_env
            .split(',')
            .filter(|s| !s.trim().is_empty())
            .map(|s| Pin::from_str(s).context("in PDX_PIN"));
        let mut map = HashMap::new();
        for pin in env_pins.chain(self.pins.iter().cloned().map(Ok)) {
            let pin = pin?;
            if !rules::modules().any(|m| m == pin.module) {
                let known: Vec<&str> = rules::modules().collect();
                bail!(
                    "no rule pack for {:?}; packs: {}",
                    pin.module,
                    known.join(", ")
                );
            }
            map.insert(pin.module, pin.major);
        }
        Ok(map)
    }
}

fn main() -> ExitCode {
    match Cli::parse().cmd {
        Cmd::Check {
            paths,
            format,
            pins,
        } => {
            let format = format.unwrap_or(if io::stdout().is_terminal() {
                Format::Text
            } else {
                Format::Json
            });
            check(&paths, format, &pins)
        }
        Cmd::Hook { pins } => hook(&pins),
        Cmd::Profile { file } => run_py(PROFILE_PY, &[file]),
        Cmd::Equiv { old, new } => run_py(EQUIV_PY, &[old, new]),
        Cmd::Skill => {
            print!("{SKILL}");
            ExitCode::SUCCESS
        }
    }
}

fn lint(paths: &[PathBuf], pins: &Pins) -> Result<Report> {
    let pins = pins.resolve()?;
    let versions = Versions::new(&pins);
    let packs =
        rules::load(|module| versions.installed(module)).context("invalid embedded rules")?;
    let files = scan::collect_files(paths)?;
    let issues = scan::scan(&files, &packs)?;
    Ok(Report { packs, issues })
}

fn check(paths: &[PathBuf], format: Format, pins: &Pins) -> ExitCode {
    let report = match lint(paths, pins) {
        Ok(r) => r,
        Err(e) => {
            eprintln!("pdx: {e:#}");
            return ExitCode::from(CHECK_FAILED);
        }
    };
    match format {
        Format::Json => println!("{}", report.to_json()),
        Format::Text => {
            for i in &report.issues {
                println!("{i}");
            }
            eprintln!("pdx: {}", report.summary());
        }
    }
    if report.has_errors() {
        ExitCode::FAILURE
    } else {
        ExitCode::SUCCESS
    }
}

fn hook(pins: &Pins) -> ExitCode {
    let mut input = String::new();
    if let Err(e) = io::stdin().read_to_string(&mut input) {
        eprintln!("pdx hook: cannot read stdin: {e}");
        return ExitCode::from(HOOK_FAILED);
    }
    let value: Value = match serde_json::from_str(&input) {
        Ok(v) => v,
        Err(e) => {
            eprintln!("pdx hook: stdin is not hook JSON: {e}");
            return ExitCode::from(HOOK_FAILED);
        }
    };
    let Some(path) = value
        .pointer("/tool_input/file_path")
        .and_then(Value::as_str)
    else {
        return ExitCode::SUCCESS;
    };
    if !scan::is_python(Path::new(path)) {
        return ExitCode::SUCCESS;
    }
    let report = match lint(&[PathBuf::from(path)], pins) {
        Ok(r) => r,
        Err(e) => {
            eprintln!("pdx hook: {e:#}");
            return ExitCode::from(HOOK_FAILED);
        }
    };
    if report.issues.is_empty() {
        return ExitCode::SUCCESS;
    }
    for i in &report.issues {
        eprintln!("{i}");
    }
    ExitCode::from(HOOK_BLOCK)
}

fn run_py(script: &str, args: &[PathBuf]) -> ExitCode {
    match Command::new(pyenv::python())
        .arg("-c")
        .arg(script)
        .args(args)
        .status()
    {
        Ok(status) => status
            .code()
            .and_then(|c| u8::try_from(c).ok())
            .map_or(ExitCode::FAILURE, ExitCode::from),
        Err(e) => {
            eprintln!("pdx: could not start python: {e}");
            ExitCode::from(PYTHON_NOT_STARTED)
        }
    }
}
