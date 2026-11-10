# Claude Code

`pdx hook` runs as a `PostToolUse` hook. After each edit to a `.py` file, Claude Code sends
the event to pdx. When pdx finds issues, it prints them and exits 2, which shows them to the
agent so it fixes them in the same turn.

Add this to `.claude/settings.json` in your project:

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [{ "type": "command", "command": "pdx hook" }]
      }
    ]
  }
}
```

| Exit code | Effect |
| --- | --- |
| 0 | Clean, or not a Python file |
| 1 | pdx could not run. Claude Code shows the message to you, not the agent |
| 2 | Issues found. Claude Code shows them to the agent |

## Agent skill

To teach the agent when to run `profile` and `equiv` too, save the skill that ships with pdx:

```sh
mkdir -p .claude/skills/pdx && pdx skill > .claude/skills/pdx/SKILL.md
```
