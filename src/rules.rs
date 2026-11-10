//! Rule packs embedded at compile time by build.rs, one per Python library.

use ast_grep_config::{GlobalRules, RuleConfig, from_yaml_string};
use ast_grep_language::SupportLang;

use crate::pyenv::Installed;

/// One pack as build.rs found it under `rules/<module>/`.
struct PackSource {
    module: &'static str,
    common: &'static str,
    /// Rule sets by major version, sorted ascending.
    versions: &'static [(u32, &'static str)],
}

const SOURCES: &[PackSource] = include!(concat!(env!("OUT_DIR"), "/packs.rs"));

/// Module names of every embedded pack, in folder order.
pub(crate) fn modules() -> impl Iterator<Item = &'static str> {
    SOURCES.iter().map(|s| s.module)
}

/// One library's rules, chosen for the version the project has installed.
pub(crate) struct Pack {
    pub(crate) module: &'static str,
    pub(crate) installed: Installed,
    /// Major version of the chosen `v<N>` set, or `None` when the pack has only common rules.
    pub(crate) set: Option<u32>,
    /// Matches an import of the module, so files that don't use the library are skipped.
    pub(crate) gate: RuleConfig<SupportLang>,
    pub(crate) rules: Vec<RuleConfig<SupportLang>>,
}

/// Loads every pack, asking `installed` which version of each library the project has.
pub(crate) fn load(mut installed: impl FnMut(&str) -> Installed) -> Result<Vec<Pack>, String> {
    SOURCES
        .iter()
        .map(|src| {
            let installed = installed(src.module);
            let chosen = choose(src.versions, installed.major);
            let mut rules = parse(src.common, src.module)?;
            if let Some((_, docs)) = chosen {
                rules.extend(parse(docs, src.module)?);
            }
            let gate = parse(&gate_yaml(src.module), src.module)?
                .pop()
                .ok_or_else(|| format!("{}: the import rule did not parse", src.module))?;
            Ok(Pack {
                module: src.module,
                installed,
                set: chosen.map(|(major, _)| major),
                gate,
                rules,
            })
        })
        .collect()
}

/// Picks the newest set at or below `major`. An older install than every set gets the oldest
/// set, and an unknown version gets the newest.
fn choose(versions: &[(u32, &'static str)], major: Option<u32>) -> Option<(u32, &'static str)> {
    let chosen = match major {
        Some(major) => versions
            .iter()
            .rev()
            .find(|(m, _)| *m <= major)
            .or_else(|| versions.first()),
        None => versions.last(),
    };
    chosen.copied()
}

/// An ast-grep rule matching `import <module>`, `import <module>.sub as x` and
/// `from <module> import x`. It checks only the imported module, so `from other import <module>`
/// and `import os as <module>` don't match.
fn gate_yaml(module: &str) -> String {
    format!(
        "id: {module}-import
language: python
rule:
  any:
    - kind: import_statement
      has:
        any:
          - kind: dotted_name
            regex: ^{module}(\\.|$)
          - kind: aliased_import
            has:
              field: name
              regex: ^{module}(\\.|$)
    - kind: import_from_statement
      has:
        field: module_name
        regex: ^{module}(\\.|$)
"
    )
}

fn parse(src: &str, module: &str) -> Result<Vec<RuleConfig<SupportLang>>, String> {
    if src.trim().is_empty() {
        return Ok(Vec::new());
    }
    from_yaml_string(src, &GlobalRules::default()).map_err(|e| format!("rules/{module}: {e}"))
}
