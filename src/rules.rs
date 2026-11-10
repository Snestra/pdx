//! Rule packs embedded at compile time by build.rs, one per Python library.

use anyhow::{Context, Result};
use ast_grep_config::{GlobalRules, RuleConfig, Severity, from_yaml_string};
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

/// One library's rules, chosen for the version the project has installed.
pub(crate) struct Pack {
    pub(crate) module: &'static str,
    pub(crate) installed: Installed,
    /// Major version of the chosen `v<N>` set, or `None` when the pack has only common rules.
    pub(crate) set: Option<u32>,
    pub(crate) gate: RuleConfig<SupportLang>,
    pub(crate) rules: Vec<RuleConfig<SupportLang>>,
}

pub(crate) fn load(mut installed: impl FnMut(&str) -> Installed) -> Result<Vec<Pack>> {
    SOURCES
        .iter()
        .map(|src| {
            let installed = installed(src.module);
            let chosen = choose(src.versions, installed.major);
            let mut rules = parse(src.common, src.module)?;
            if let Some((_, docs)) = chosen {
                rules.extend(parse(docs, src.module)?);
            }
            rules.retain(|r| r.severity != Severity::Off);
            let gate = parse(&gate_yaml(src.module), src.module)?
                .pop()
                .with_context(|| format!("rules/{}: the import rule did not parse", src.module))?;
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

fn parse(src: &str, module: &str) -> Result<Vec<RuleConfig<SupportLang>>> {
    from_yaml_string(src, &GlobalRules::default()).with_context(|| format!("rules/{module}"))
}
