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

/// A release number such as `3.1` or `3.1.1`. Missing parts count as zero, so `3.1` equals
/// `3.1.0`. Anything after the leading numbers, such as `rc1` in `3.2.0rc1`, is ignored.
#[derive(Debug, Clone)]
pub(crate) struct Version(Vec<u32>);

impl Version {
    pub(crate) fn parse(text: &str) -> Option<Self> {
        let numeric = text
            .split(|c: char| !(c.is_ascii_digit() || c == '.'))
            .next()?;
        let parts = numeric
            .split('.')
            .take_while(|p| !p.is_empty())
            .map(str::parse)
            .collect::<Result<Vec<u32>, _>>()
            .ok()?;
        (!parts.is_empty()).then_some(Self(parts))
    }

    fn part(&self, i: usize) -> u32 {
        self.0.get(i).copied().unwrap_or(0)
    }
}

impl Ord for Version {
    fn cmp(&self, other: &Self) -> std::cmp::Ordering {
        (0..self.0.len().max(other.0.len()))
            .map(|i| self.part(i).cmp(&other.part(i)))
            .find(|o| o.is_ne())
            .unwrap_or(std::cmp::Ordering::Equal)
    }
}

impl PartialOrd for Version {
    fn partial_cmp(&self, other: &Self) -> Option<std::cmp::Ordering> {
        Some(self.cmp(other))
    }
}

impl PartialEq for Version {
    fn eq(&self, other: &Self) -> bool {
        self.cmp(other).is_eq()
    }
}

impl Eq for Version {}

pub(crate) struct Rule {
    pub(crate) config: RuleConfig<SupportLang>,
    /// `None` when the rule has no fix.
    pub(crate) fix: Option<Applicability>,
    /// The first library version the rule applies to, from `metadata.since`.
    since: Option<Version>,
}

/// One library's rules.
pub(crate) struct Pack {
    pub(crate) module: &'static str,
    pub(crate) gate: RuleConfig<SupportLang>,
    pub(crate) rules: Vec<Rule>,
}

impl Pack {
    /// Drops the rules whose `metadata.since` is newer than `installed`. With no installed
    /// version every rule stays, so a project without the library gets the newest advice.
    pub(crate) fn keep_rules_for(&mut self, installed: Option<&Version>) {
        if let Some(installed) = installed {
            self.rules
                .retain(|r| r.since.as_ref().is_none_or(|since| since <= installed));
        }
    }
}

pub(crate) fn load() -> Result<Vec<Pack>> {
    SOURCES
        .iter()
        .map(|src| {
            let rules = parse(src.rules, src.module)?
                .into_iter()
                .filter(|r| r.severity != Severity::Off)
                .map(|config| {
                    let context = || format!("rules/{}/{}", src.module, config.id);
                    let fix = applicability(&config).with_context(context)?;
                    let since = since(&config).with_context(context)?;
                    Ok(Rule { config, fix, since })
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

/// `metadata: { since: "3.1" }` names the first library version a rule applies to.
fn since(rule: &RuleConfig<SupportLang>) -> Result<Option<Version>> {
    let metadata = rule
        .metadata
        .as_ref()
        .map(serde_json::to_value)
        .transpose()?;
    match metadata.as_ref().and_then(|m| m.get("since")) {
        None => Ok(None),
        Some(value) => value
            .as_str()
            .and_then(Version::parse)
            .map(Some)
            .with_context(|| {
                format!("metadata.since must be a version such as \"3.1\", not {value}")
            }),
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
