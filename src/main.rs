//! pdx is an opinionated linter for Python library habits that give slow or wrong results, for
//! humans and coding agents. Each library gets one rule pack under `rules/`.

mod cli;
mod graph;
mod nodes;
mod pack;
mod package_check;
mod report;
mod rule;
mod scan;
mod venv;
mod version;

use std::process::ExitCode;

fn main() -> ExitCode {
    cli::run()
}
