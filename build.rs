//! Embeds the rule packs under rules/ into the binary.
//!
//! Each folder `rules/<module>/` is the pack for the Python library imported as `<module>`.
//! It holds `common/` for every version of the library and `v<N>/` for major version N, with
//! one ast-grep rule per .yml file. This script writes `OUT_DIR/packs.rs`, which src/rules.rs
//! includes, so adding a rule or a pack needs no Rust change.

use std::{
    env, fs,
    path::{Path, PathBuf},
};

fn main() {
    let out = PathBuf::from(env::var("OUT_DIR").expect("cargo sets OUT_DIR for build scripts"));
    let root = Path::new("rules");
    // Cargo rescans a directory given here for changes to any file inside it.
    println!("cargo:rerun-if-changed={}", root.display());
    let mut code = String::from("&[\n");
    for pack in sorted_dirs(root) {
        code.push_str(&pack_source(&pack));
    }
    code.push(']');
    let target = out.join("packs.rs");
    fs::write(&target, code).unwrap_or_else(|e| panic!("write {}: {e}", target.display()));
}

/// Renders one `PackSource` literal for the pack folder `pack`.
fn pack_source(pack: &Path) -> String {
    let module = file_name(pack);
    assert!(
        is_module_name(&module),
        "rules/{module}: the folder name must be a Python module name"
    );
    let mut common = String::new();
    let mut versions = Vec::new();
    for set in sorted_dirs(pack) {
        let name = file_name(&set);
        if name == "common" {
            common = joined_rules(&set);
        } else if let Some(major) = name.strip_prefix('v').and_then(|n| n.parse::<u32>().ok()) {
            versions.push((major, joined_rules(&set)));
        } else {
            panic!("rules/{module}/{name}: expected a folder named common or v<major>");
        }
    }
    assert!(
        !common.is_empty() || !versions.is_empty(),
        "rules/{module}: the pack has no rules"
    );
    versions.sort_by_key(|(major, _)| *major);
    let versions: Vec<String> = versions
        .iter()
        .map(|(major, docs)| format!("({major}, {docs:?})"))
        .collect();
    let versions = versions.join(", ");
    format!(
        "    PackSource {{ module: {module:?}, common: {common:?}, versions: &[{versions}] }},\n"
    )
}

/// Joins the .yml rules in `dir` into one multi-document YAML string, sorted by file name.
fn joined_rules(dir: &Path) -> String {
    let mut files: Vec<PathBuf> = entries(dir)
        .into_iter()
        .filter(|p| p.extension().is_some_and(|x| x == "yml" || x == "yaml"))
        .collect();
    files.sort();
    let docs: Vec<String> = files
        .iter()
        .map(|p| {
            fs::read_to_string(p)
                .unwrap_or_else(|e| panic!("read {}: {e}", p.display()))
                .trim()
                .to_owned()
        })
        .collect();
    docs.join("\n---\n")
}

fn sorted_dirs(dir: &Path) -> Vec<PathBuf> {
    let mut dirs: Vec<PathBuf> = entries(dir).into_iter().filter(|p| p.is_dir()).collect();
    dirs.sort();
    dirs
}

fn entries(dir: &Path) -> Vec<PathBuf> {
    fs::read_dir(dir)
        .unwrap_or_else(|e| panic!("read {}: {e}", dir.display()))
        .map(|entry| entry.map(|e| e.path()))
        .collect::<Result<_, _>>()
        .unwrap_or_else(|e| panic!("list {}: {e}", dir.display()))
}

fn file_name(path: &Path) -> String {
    path.file_name().and_then(|n| n.to_str()).map_or_else(
        || panic!("{} has no UTF-8 name", path.display()),
        str::to_owned,
    )
}

/// Module names also go into a regex and a dist-info lookup, so only identifiers are allowed.
fn is_module_name(name: &str) -> bool {
    let mut chars = name.chars();
    chars
        .next()
        .is_some_and(|c| c.is_ascii_lowercase() || c == '_')
        && chars.all(|c| c.is_ascii_lowercase() || c.is_ascii_digit() || c == '_')
}
