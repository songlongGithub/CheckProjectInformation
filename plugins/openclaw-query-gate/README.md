# openclaw-query-gate

Silent-buffer bare media + non-query text on gated OpenClaw channels, so the
agent only answers on explicit query keywords.

## Problem

On WeChat (and similar IM) channels, a user often sends a burst of images +
one file + a text question. OpenClaw's default behavior fires one agent turn
per inbound message, causing the agent to reply to every image before the
user's real question arrives. See Obsidian note
`2026-04-22 OpenClaw-微信多媒体输入触发策略设计.md` for full analysis.

## How it works

Registers a `before_dispatch` hook that inspects the inbound text content:

1. **Bare media** (empty text, from images/files) → `{ handled: true }`
   (silent, no agent run, no LLM tokens burned).
2. **Text without trigger keyword** → `{ handled: true }` (same).
3. **Text with trigger keyword** (`核对 / 比对 / 帮我看看 / ...`) → `undefined`
   (falls through to default dispatch; the agent sees the full accumulated
   session history including all the previously-buffered images/files).

The `recordInboundSession` step fires **before** `before_dispatch`, so even
suppressed messages are preserved in the session transcript. When the trigger
finally arrives, the agent gets full context in one turn.

## Config

All keys are optional; defaults shown below.

```jsonc
{
  "plugins": {
    "entries": {
      "openclaw-query-gate": {
        "enabled": true,
        "channels": ["openclaw-weixin"],
        "triggerKeywords": [
          "核对", "比对", "帮我看看", "帮我", "开始处理",
          "对比", "汇总", "提取", "执行", "处理",
          "分析", "总结", "查询", "检查"
        ],
        "suppressMediaOnly": true,
        "mediaAckText": ""
      }
    }
  }
}
```

- Set `enabled: false` to disable without uninstalling.
- Add your own channels to `channels` (e.g. `"telegram"`) — but typically only
  WeChat benefits because Telegram / Feishu have native `requireMention`.
- Set `mediaAckText` (non-empty) to send a one-shot ACK on the first media
  burst in a conversation (10 min window). Leave blank for full silence.

## Install (local dev)

```bash
openclaw plugins install /abs/path/to/plugins/openclaw-query-gate --dangerously-force-unsafe-install
openclaw gateway restart
grep query-gate ~/.openclaw/logs/gateway.log | tail -5
```

The `--dangerously-force-unsafe-install` flag is only needed if OpenClaw's
static analysis flags something; our plugin uses no `child_process`/shell so
it should pass clean.

## Verify

Send the bot a bare image on the gated channel. Expected:
1. Nothing appears in the chat.
2. `gateway.log` shows `[query-gate] silent media-only: conv=...`.
3. `before_dispatch_handled` appears in OpenClaw's dispatch log.

Then send a text with a trigger keyword like "帮我核对"; agent should reply
once, using the accumulated media as context.

## Disable / Uninstall

```bash
# Temporary disable
openclaw config set plugins.entries.openclaw-query-gate.enabled false
openclaw gateway restart

# Full remove
openclaw plugins uninstall openclaw-query-gate
```
