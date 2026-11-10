//! Rule packs embedded at compile time by build.rs, one per Python library.

use anyhow::{Context, Result, bail};
use ast_grep_config::{GlobalRules, RuleConfig, Severity, from_yaml_string};
use ast_grep_language::SupportLang;

/// One pack as build.rs found it under `rules/<module>/`.
struct PackSource {
    module: &'static str,
    rules: &'static str,
}

const SOURCES: &[PackSource] = include!(concat!(env!("OUT_DIR"), "/packs.rs"));

/// Whether a fix keeps the code's behavior. `pdx check --fix` applies safe fixes, and
/// `--unsafe-fixes` adds the unsafe ones. The order matters: a fix applies when its
/// applicability is at or below the one asked for.
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub(crate) enum Applicability {
    Safe,
    Unsafe,
}

impl Applicability {
    pub(crate) fn as_str(self) -> &'static str {
        match self {
            Self::Safe => "safe",
            Self::Unsafe => "unsafe",
        }
    }
}

pub(crate) struct Rule {
    pub(crate) config: RuleConfig<SupportLang>,
    /// `None` when the rule has no fix.
    pub(crate) fix: Option<Applicability>,
}

/// One library's rules.
pub(crate) struct Pack {
    pub(crate) module: &'static str,
    pub(crate) gate: RuleConfig<SupportLang>,
    pub(crate) rules: Vec<Rule>,
}

pub(crate) fn load() -> Result<Vec<Pack>> {
    SOURCES
        .iter()
        .map(|src| {
            let rules = parse(src.rules, src.module)?
                .into_iter()
                .filter(|r| r.severity != Severity::Off)
                .map(|config| {
                    let fix = applicability(&config)
                        .with_context(|| format!("rules/{}/{}", src.module, config.id))?;
                    Ok(Rule { config, fix })
                })
                .collect::<Result<_>>()?;
            let gate = parse(&gate_yaml(src.module), src.module)?
                .pop()
                .with_context(|| format!("rules/{}: the import rule did not parse", src.module))?;
            Ok(Pack {
                module: src.module,
                gate,
                rules,
            })
        })
        .collect()
}

/// A rule with `fix:` must say how safe the fix is with `metadata: { fix: safe }` or
/// `metadata: { fix: unsafe }`, and only one fix, because `--fix` applies it without asking.
fn applicability(rule: &RuleConfig<SupportLang>) -> Result<Option<Applicability>> {
    let declared = rule
        .metadata
        .as_ref()
        .map(serde_json::to_value)
        .transpose()?
        .and_then(|m| m.get("fix").cloned());
    let declared = declared.as_ref().map(|v| v.as_str());
    match (rule.fixer.len(), declared) {
        (0, None) => Ok(None),
        (1, Some(Some("safe"))) => Ok(Some(Applicability::Safe)),
        (1, Some(Some("unsafe"))) => Ok(Some(Applicability::Unsafe)),
        (0, Some(_)) => bail!("metadata.fix is set, but the rule has no fix"),
        (1, _) => bail!("a rule with a fix needs metadata.fix: safe or unsafe"),
        _ => bail!("a rule may have only one fix"),
    }
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
