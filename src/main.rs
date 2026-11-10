//! pdx lints pandas code for habits that give slow or wrong results, for humans and coding agents.

mod pyenv;
mod rules;
mod scan;

use std::{
    io::{self, IsTerminal, Read},
    path::{Path, PathBuf},
    process::{Command, ExitCode},
};

use clap::{Parser, Subcommand, ValueEnum};
use serde_json::json;

use crate::{rules::RuleSet, scan::Level};

const SKILL: &str = include_str!("../SKILL.md");
const PROFILE_PY: &str = include_str!("../py/profile.py");
const EQUIV_PY: &str = include_str!("../py/equiv.py");

/// pdx: fast pandas linter and helpers for humans and coding agents.
#[derive(Debug, Parser)]
#[command(version, about)]
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
    /// Lint pandas code. Exit 0 when clean, 1 on any error-severity issue, 2 if pdx can't run.
    ///
    /// Only files that import pandas are checked.
    ///
    /// Examples:
    ///   pdx check src/
    ///   pdx check analysis.py --format json
    ///   pdx check . --pandas 2
    Check {
        /// Files or directories (directories respect .gitignore).
        #[arg(default_value = ".")]
        paths: Vec<PathBuf>,
        /// Output format. Default: text on a terminal, json otherwise.
        #[arg(long, value_enum)]
        format: Option<Format>,
        /// Override the detected pandas major version (also: `PDX_PANDAS_MAJOR`).
        #[arg(long)]
        pandas: Option<u32>,
    },
    /// Claude Code `PostToolUse` hook: reads hook JSON on stdin and lints the edited .py file.
    ///
    /// Exit 2 with issues on stderr so the agent sees them, 1 if pdx can't run, 0 otherwise.
    Hook {
        #[arg(long)]
        pandas: Option<u32>,
    },
    /// Profile a data file (csv, parquet, feather, json, xlsx). Needs pandas.
    Profile { file: PathBuf },
    /// Check that two scripts produce an equal `result` (`DataFrame` or Series). Needs pandas.
    Equiv { old: PathBuf, new: PathBuf },
    /// Print the agent skill (SKILL.md) for this pdx version.
    Skill,
}

/// Exit code when pdx itself fails, as opposed to finding issues.
const CHECK_FAILED: u8 = 2;
/// Claude Code shows stderr to the agent only when a hook exits 2.
const HOOK_BLOCK: u8 = 2;
/// Any other non-zero hook exit shows stderr to the user without blocking the agent.
const HOOK_FAILED: u8 = 1;
/// The shell's code for a command that could not be started.
const PYTHON_NOT_STARTED: u8 = 127;

fn main() -> ExitCode {
    match Cli::parse().cmd {
        Cmd::Check {
            paths,
            format,
            pandas,
        } => {
            let format = format.unwrap_or(if io::stdout().is_terminal() {
                Format::Text
            } else {
                Format::Json
            });
            check(&paths, format, pandas)
        }
        Cmd::Hook { pandas } => hook(pandas),
        Cmd::Profile { file } => run_py(PROFILE_PY, &[file]),
        Cmd::Equiv { old, new } => run_py(EQUIV_PY, &[old, new]),
        Cmd::Skill => {
            print!("{SKILL}");
            ExitCode::SUCCESS
        }
    }
}

struct Report {
    pandas: pyenv::Pandas,
    set: RuleSet,
    issues: Vec<scan::Issue>,
}

fn lint(paths: &[PathBuf], pandas: Option<u32>) -> Result<Report, String> {
    let pandas = pyenv::detect(pandas);
    let set = RuleSet::for_major(pandas.major);
    let rules = set
        .load()
        .map_err(|e| format!("invalid embedded rules: {e}"))?;
    let gate = rules::pandas_import().map_err(|e| format!("invalid embedded rules: {e}"))?;
    let files = scan::collect_files(paths).map_err(|e| e.to_string())?;
    let issues = scan::scan(&files, &rules, &gate).map_err(|e| e.to_string())?;
    Ok(Report {
        pandas,
        set,
        issues,
    })
}

fn check(paths: &[PathBuf], format: Format, pandas: Option<u32>) -> ExitCode {
    let report = match lint(paths, pandas) {
        Ok(r) => r,
        Err(e) => {
            eprintln!("pdx: {e}");
            return ExitCode::from(CHECK_FAILED);
        }
    };
    let Report {
        pandas,
        set,
        issues,
    } = &report;
    match format {
        Format::Json => println!(
            "{}",
            json!({
                "pandas": pandas.version, "pandas_major": pandas.major,
                "pandas_source": pandas.source.as_str(), "ruleset": set.name(),
                "issues": issues.iter().map(scan::Issue::to_json).collect::<Vec<_>>(),
            })
        ),
        Format::Text => {
            for i in issues {
                println!(
                    "{}:{}:{}: {} [{}] {}",
                    i.file, i.line, i.column, i.level, i.rule, i.message
                );
            }
            eprintln!(
                "pdx: {} issue(s), pandas {} ({}), rules {}",
                issues.len(),
                pandas.version.as_deref().unwrap_or("?"),
                pandas.source.as_str(),
                set.name()
            );
        }
    }
    if issues.iter().any(|i| i.level == Level::Error) {
        ExitCode::FAILURE
    } else {
        ExitCode::SUCCESS
    }
}

fn hook(pandas: Option<u32>) -> ExitCode {
    let mut input = String::new();
    if let Err(e) = io::stdin().read_to_string(&mut input) {
        eprintln!("pdx hook: cannot read stdin: {e}");
        return ExitCode::from(HOOK_FAILED);
    }
    let value: serde_json::Value = match serde_json::from_str(&input) {
        Ok(v) => v,
        Err(e) => {
            eprintln!("pdx hook: stdin is not hook JSON: {e}");
            return ExitCode::from(HOOK_FAILED);
        }
    };
    let Some(path) = value
        .pointer("/tool_input/file_path")
        .and_then(serde_json::Value::as_str)
    else {
        return ExitCode::SUCCESS;
    };
    if !Path::new(path)
        .extension()
        .is_some_and(|x| x.eq_ignore_ascii_case("py"))
    {
        return ExitCode::SUCCESS;
    }
    let report = match lint(&[PathBuf::from(path)], pandas) {
        Ok(r) => r,
        Err(e) => {
            eprintln!("pdx hook: {e}");
            return ExitCode::from(HOOK_FAILED);
        }
    };
    if report.issues.is_empty() {
        return ExitCode::SUCCESS;
    }
    for i in &report.issues {
        eprintln!(
            "{}:{}: {} [{}] {}",
            i.file, i.line, i.level, i.rule, i.message
        );
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
