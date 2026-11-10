//! Joins rules/<set>/*.yml into one multi-document YAML per set in `OUT_DIR`,
//! so src/rules.rs embeds each set with `include_str!`.

use std::{env, fs, path::Path};

const SETS: [&str; 3] = ["common", "v2", "v3"];

fn main() {
    let out = env::var("OUT_DIR").expect("cargo sets OUT_DIR for build scripts");
    for set in SETS {
        let dir = Path::new("rules").join(set);
        println!("cargo:rerun-if-changed={}", dir.display());
        let mut files: Vec<_> = fs::read_dir(&dir)
            .unwrap_or_else(|e| panic!("read {}: {e}", dir.display()))
            .map(|entry| entry.map(|e| e.path()))
            .collect::<Result<_, _>>()
            .unwrap_or_else(|e| panic!("list {}: {e}", dir.display()));
        files.retain(|p| p.extension().is_some_and(|x| x == "yml" || x == "yaml"));
        files.sort();
        let docs: Vec<String> = files
            .iter()
            .map(|p| {
                println!("cargo:rerun-if-changed={}", p.display());
                fs::read_to_string(p)
                    .unwrap_or_else(|e| panic!("read {}: {e}", p.display()))
                    .trim()
                    .to_owned()
            })
            .collect();
        let target = Path::new(&out).join(format!("{set}.yml"));
        fs::write(&target, docs.join("\n---\n"))
            .unwrap_or_else(|e| panic!("write {}: {e}", target.display()));
    }
}
