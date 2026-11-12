# Claude Code

`xpd hook` runs as a `PostToolUse` hook. After each edit to a `.py` file, Claude Code sends
the event to xpd. When xpd finds issues, it prints them and exits 2, which shows them to the
agent so it fixes them in the same turn. For a file with a pipeline of steps, the issues include
the errors and warnings of [`xpd graph`](commands.md#step-code), such as a formula that another
step computes already.

Add this to `.claude/settings.json` in your project:

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [{ "type": "command", "command": "xpd hook" }]
      }
    ]
  }
}
```

| Exit code | Effect |
| --- | --- |
| 0 | Clean, or not a Python file |
| 1 | xpd could not run. Claude Code shows the message to you, not the agent |
| 2 | Issues found. Claude Code shows them to the agent |

## Agent skill

To teach the agent when to run `profile` and `equiv` too, save the skill that ships with xpd:

```sh
mkdir -p .claude/skills/xpd && xpd skill > .claude/skills/xpd/SKILL.md
```
