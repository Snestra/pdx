//! Rule sets embedded at compile time by build.rs.

use ast_grep_config::{GlobalRules, RuleConfig, from_yaml_string};
use ast_grep_language::SupportLang;

const COMMON: &str = include_str!(concat!(env!("OUT_DIR"), "/common.yml"));
const V2: &str = include_str!(concat!(env!("OUT_DIR"), "/v2.yml"));
const V3: &str = include_str!(concat!(env!("OUT_DIR"), "/v3.yml"));
const PANDAS_IMPORT: &str = include_str!("pandas-import.yml");

/// Rules for one pandas major version: the common set plus the version set.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub(crate) enum RuleSet {
    V2,
    V3,
}

impl RuleSet {
    /// pandas 3 and later get v3; everything older gets v2.
    pub(crate) fn for_major(major: u32) -> Self {
        if major >= 3 { Self::V3 } else { Self::V2 }
    }

    pub(crate) fn name(self) -> &'static str {
        match self {
            Self::V2 => "v2",
            Self::V3 => "v3",
        }
    }

    pub(crate) fn load(self) -> Result<Vec<RuleConfig<SupportLang>>, String> {
        let specific = match self {
            Self::V2 => V2,
            Self::V3 => V3,
        };
        let mut rules = parse(COMMON)?;
        rules.extend(parse(specific)?);
        Ok(rules)
    }
}

/// The rule that decides whether a file imports pandas at all.
pub(crate) fn pandas_import() -> Result<RuleConfig<SupportLang>, String> {
    parse(PANDAS_IMPORT)?
        .pop()
        .ok_or_else(|| "pandas-import.yml holds no rule".to_owned())
}

fn parse(src: &str) -> Result<Vec<RuleConfig<SupportLang>>, String> {
    if src.trim().is_empty() {
        return Ok(Vec::new());
    }
    from_yaml_string(src, &GlobalRules::default()).map_err(|e| e.to_string())
}
