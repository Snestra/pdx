//! pdx is an opinionated linter for Python library habits that give slow or wrong results, for
//! humans and coding agents. Each library gets one rule pack; pandas is the first.

mod pyenv;
mod report;
mod rules;
mod scan;

use std::{
    io::{self, IsTerminal, Read},
    path::{Path, PathBuf},
    process::{Command, ExitCode},
};

use anyhow::{Context, Result};
use clap::{Parser, Subcommand, ValueEnum};
use serde_json::Value;

use crate::{
    report::Report,
    rules::{Applicability, Version},
};

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
    /// A library's rules run only on files that import it. `[*]` marks an issue `--fix` fixes.
    ///
    /// Examples:
    ///   pdx check src/
    ///   pdx check analysis.py --format json
    ///   pdx check . --fix
    ///   pdx check . --fix --unsafe-fixes
    Check {
        /// Files or directories (directories respect .gitignore).
        #[arg(default_value = ".")]
        paths: Vec<PathBuf>,
        /// Output format. Default: text on a terminal, json otherwise.
        #[arg(long, value_enum)]
        format: Option<Format>,
        /// Apply safe fixes, and report what is left.
        #[arg(long)]
        fix: bool,
        /// Also count unsafe fixes, which may change behavior: apply them with --fix, or mark
        /// them as fixable without it.
        #[arg(long)]
        unsafe_fixes: bool,
    },
    /// Claude Code `PostToolUse` hook: reads hook JSON on stdin and lints the edited .py file.
    ///
    /// Exit 2 with issues on stderr so the agent sees them, 1 if pdx can't run, 0 otherwise.
    Hook,
    /// Profile a data file (csv, parquet, feather, json, xlsx). Needs pandas.
    Profile { file: PathBuf },
    /// Check that two scripts produce an equal `result` (`DataFrame` or Series). Needs pandas.
    Equiv { old: PathBuf, new: PathBuf },
    /// Print the agent skill (SKILL.md) for this pdx version.
    Skill,
}

fn main() -> ExitCode {
    match Cli::parse().cmd {
        Cmd::Check {
            paths,
            format,
            fix,
            unsafe_fixes,
        } => {
            let format = format.unwrap_or(if io::stdout().is_terminal() {
                Format::Text
            } else {
                Format::Json
            });
            let allowed = if unsafe_fixes {
                Applicability::Unsafe
            } else {
                Applicability::Safe
            };
            check(&paths, format, fix.then_some(allowed), allowed)
        }
        Cmd::Hook => hook(),
        Cmd::Profile { file } => run_py(PROFILE_PY, &[file]),
        Cmd::Equiv { old, new } => run_py(EQUIV_PY, &[old, new]),
        Cmd::Skill => {
            print!("{SKILL}");
            ExitCode::SUCCESS
        }
    }
}

/// Lints `paths`, after writing fixes up to `fix` when it is set. Each pack keeps the rules for
/// the library version installed in the project.
fn lint(paths: &[PathBuf], fix: Option<Applicability>) -> Result<Report> {
    let mut packs = rules::load().context("invalid embedded rules")?;
    for pack in &mut packs {
        let installed = pyenv::installed_version(pack.module).and_then(|v| Version::parse(&v));
        pack.keep_rules_for(installed.as_ref());
    }
    let files = scan::collect_files(paths)?;
    let scanned = scan::scan(&files, &packs, fix)?;
    Ok(Report {
        issues: scanned.issues,
        fixed: scanned.fixed,
    })
}

/// `allowed` is the fix level that `[*]` and the summary count as fixable.
fn check(
    paths: &[PathBuf],
    format: Format,
    fix: Option<Applicability>,
    allowed: Applicability,
) -> ExitCode {
    let report = match lint(paths, fix) {
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
                println!("{}", i.line(allowed));
            }
            eprintln!("pdx: {}", report.summary(allowed));
        }
    }
    if report.has_errors() {
        ExitCode::FAILURE
    } else {
        ExitCode::SUCCESS
    }
}

fn hook() -> ExitCode {
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
    let report = match lint(&[PathBuf::from(path)], None) {
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
        eprintln!("{}", i.line(Applicability::Safe));
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
