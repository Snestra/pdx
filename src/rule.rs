//! One lint rule: an ast-grep rule, plus the settings pdx reads from its `metadata`.

use std::fmt;

use anyhow::{Context, Error, Result, bail};
use ast_grep_config::RuleConfig;
use ast_grep_language::SupportLang;
use serde::Deserialize;

use crate::version::Version;

/// Whether a fix keeps the code's behavior. `pdx check --fix` applies safe fixes, and
/// `--unsafe-fixes` adds the unsafe ones. The order matters: a fix applies when its
/// applicability is at or below the one asked for.
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash, Deserialize)]
#[serde(rename_all = "lowercase")]
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

/// What a rule's `metadata` may hold, such as `metadata: { fix: unsafe, since: "3.1" }`.
#[derive(Debug, Default, Deserialize)]
#[serde(deny_unknown_fields)]
struct Metadata {
    fix: Option<Applicability>,
    since: Option<Version>,
}

/// One rule document of a pack.
pub(crate) struct Rule {
    pub(crate) config: RuleConfig<SupportLang>,
    /// `None` when the rule has no fix.
    pub(crate) fix: Option<Applicability>,
    /// The first library version the rule applies to.
    since: Option<Version>,
}

impl TryFrom<RuleConfig<SupportLang>> for Rule {
    type Error = Error;

    /// A rule with `fix:` must say how safe the fix is with `metadata.fix`, and it may have
    /// only one fix, because `--fix` applies it without asking.
    fn try_from(config: RuleConfig<SupportLang>) -> Result<Self> {
        let metadata = match &config.metadata {
            Some(metadata) => serde_json::to_value(metadata)
                .and_then(serde_json::from_value)
                .context("metadata may hold fix: safe or unsafe, and since: \"<version>\"")?,
            None => Metadata::default(),
        };
        let fix = match (config.fixer.len(), metadata.fix) {
            (0, None) => None,
            (1, Some(applicability)) => Some(applicability),
            (0, Some(_)) => bail!("metadata.fix is set, but the rule has no fix"),
            (1, None) => bail!("a rule with a fix needs metadata.fix: safe or unsafe"),
            (fixes, _) => bail!("a rule may have only one fix, and this one has {fixes}"),
        };
        Ok(Self {
            config,
            fix,
            since: metadata.since,
        })
    }
}

impl Rule {
    /// Whether the rule's advice works on the `installed` version of its library.
    pub(crate) fn applies_to(&self, installed: &Version) -> bool {
        self.since.as_ref().is_none_or(|since| since <= installed)
    }
}

impl fmt::Debug for Rule {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.debug_struct("Rule")
            .field("id", &self.config.id)
            .field("fix", &self.fix)
            .field("since", &self.since)
            .finish_non_exhaustive()
    }
}
