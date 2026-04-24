// @ts-check
// OpenClaw plugin: openclaw-query-gate
//
// 策略（v0.4.0 · 语义路由版）：
//   - 媒体消息（content 为空）：
//     plugin 从 ~/.openclaw/media/inbound/ 扫出新文件 → 写入 buffer
//     return { handled: true } → agent 完全不跑
//     （与 v0.3 的差别：v0.3 让 agent 跑以触发 OCR+session；v0.4 完全 bypass）
//
//   - 文本消息：放行 agent
//
//   - agent 准备 LLM 调用前（before_prompt_build hook）：
//     把 buffer 内的媒体路径 + mime + 元数据注入 prependContext
//     agent 看到"用户发了这些媒体，请根据 query 语义选择合适工具处理"
//     由 agent 自主决策（skill / OCR / vision / 直接读文件）
//
//   - agent run 结束（agent_end hook）：
//     清空本会话 buffer
//
// 对比 v0.3：
//   v0.3: 每张媒体都跑一个 agent turn 做 OCR，agent 自己生成中间"部分核对"
//         消息污染 session，导致最终核对结论自相矛盾（2026-04-24 实测）
//   v0.4: 0 agent turn / 0 token 处理媒体，语义路由由 agent 决定工具
//
// 不碰百度 OCR / 多模态 LLM 凭据。plugin 只 scan 本地 FS。

import fs from "node:fs";
import path from "node:path";
import os from "node:os";
import { execFile } from "node:child_process";
import { promisify } from "node:util";

const execFileP = promisify(execFile);

const DEFAULT_CHANNELS = ["openclaw-weixin"];
const INBOUND_DIR = path.join(os.homedir(), ".openclaw", "media", "inbound");

const BUFFER_TTL_MS = 30 * 60 * 1000; // 30 min

/**
 * 已被 plugin "认领"（加入过任何 buffer）的文件路径 —— 防止同一文件被多次加入。
 * @type {Set<string>}
 */
const claimedFiles = new Set();

/**
 * 每个 conversation 的 media buffer。
 * @type {Map<string, { items: Array<{ path: string, name: string, mime: string, sizeBytes: number, receivedAt: number }>, lastUpdate: number }>}
 */
const mediaBuffer = new Map();

const MIME_BY_EXT = {
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".png": "image/png",
  ".gif": "image/gif",
  ".webp": "image/webp",
  ".heic": "image/heic",
  ".pdf": "application/pdf",
  ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  ".xls": "application/vnd.ms-excel",
  ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  ".doc": "application/msword",
  ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
  ".txt": "text/plain",
  ".csv": "text/csv",
  ".md": "text/markdown",
  ".json": "application/json",
  ".mp3": "audio/mpeg",
  ".m4a": "audio/mp4",
  ".wav": "audio/wav",
  ".silk": "audio/silk",
  ".ogg": "audio/ogg",
  ".mp4": "video/mp4",
  ".mov": "video/quicktime",
};

function guessMime(filename) {
  const ext = path.extname(filename).toLowerCase();
  return MIME_BY_EXT[ext] || "application/octet-stream";
}

/**
 * 跨 hook 的 conversation key。不同 hook 给 plugin 的 ctx 字段不一致：
 *   - before_dispatch:     ctx={channelId, accountId, conversationId, sessionKey, senderId}
 *   - before_prompt_build: ctx={runId, agentId, sessionKey, sessionId, ...} ← 无 conversationId!
 *   - agent_end:           ctx=PluginHookAgentContext 同上
 *   - message_sending:     ctx={channelId, accountId} ← 又不同
 *
 * 最稳的跨 hook 标识：sessionKey（所有 ctx 都有）。
 * 其形如 "agent:main:openclaw-weixin:direct:o9cq803yhS...@im.wechat"。
 */
function convKeyOf(channelId, event, ctx) {
  if (ctx?.sessionKey) return ctx.sessionKey;
  const id =
    (ctx && ctx.conversationId) ||
    (event && typeof event.to === "string" && event.to) ||
    (ctx && ctx.senderId) ||
    "unknown";
  return `${channelId ?? "nochan"}:${id}`;
}

/**
 * 从 sessionKey 提取 channelId（用于 before_prompt_build 里 channel 判断，
 * 因为它的 ctx 不给 channelId）。
 * sessionKey 格式：agent:main:<channelId>:<chatType>:<peer>
 */
function channelIdFromSessionKey(sessionKey) {
  if (typeof sessionKey !== "string") return undefined;
  const parts = sessionKey.split(":");
  return parts[0] === "agent" && parts.length >= 3 ? parts[2] : undefined;
}

function scanInboundDir() {
  try {
    const entries = fs.readdirSync(INBOUND_DIR, { withFileTypes: true });
    const result = [];
    for (const e of entries) {
      if (!e.isFile()) continue;
      const full = path.join(INBOUND_DIR, e.name);
      let stat;
      try {
        stat = fs.statSync(full);
      } catch {
        continue;
      }
      result.push({
        path: full,
        name: e.name,
        sizeBytes: stat.size,
        mtime: stat.mtimeMs,
      });
    }
    return result;
  } catch (err) {
    // directory doesn't exist or permission — return empty
    return [];
  }
}

function detectNewFiles(maxAgeMs = 60_000) {
  const now = Date.now();
  const files = scanInboundDir()
    .filter((f) => f.mtime >= now - maxAgeMs)
    .filter((f) => !claimedFiles.has(f.path))
    .filter((f) => f.sizeBytes > 0)
    .sort((a, b) => a.mtime - b.mtime);
  for (const f of files) claimedFiles.add(f.path);
  return files;
}

function pruneExpiredBuffer(convKey) {
  const b = mediaBuffer.get(convKey);
  if (!b) return;
  if (Date.now() - b.lastUpdate > BUFFER_TTL_MS) {
    mediaBuffer.delete(convKey);
  }
}

function clearBuffer(convKey) {
  mediaBuffer.delete(convKey);
}

function formatBufferForPrompt(buf) {
  if (!buf || buf.items.length === 0) return "";
  const lines = [];
  lines.push("【Plugin 注入 · 最近媒体 buffer】");
  lines.push(
    `用户在本次 query 前发了 ${buf.items.length} 个媒体文件（路径已就绪，内容未处理）：`,
  );
  lines.push("");
  buf.items.forEach((it, idx) => {
    const kb = (it.sizeBytes / 1024).toFixed(1);
    lines.push(`${idx + 1}. ${it.name}`);
    lines.push(`   path: ${it.path}`);
    lines.push(`   mime: ${it.mime}, size: ${kb} KB`);
  });
  lines.push("");
  lines.push("请根据用户当前 query 的语义选择合适的处理方式：");
  lines.push("- 体检方案/订单核对 → 调用 `medical-exam-checker` skill");
  lines.push("- 需要精确文字提取（OCR） → 百度 OCR 或相关 skill");
  lines.push("- 图片视觉理解（识图/描述/解读） → 使用多模态 LLM 直接看 image 内容");
  lines.push("- Excel / PDF / docx 等结构化文件 → 对应解析工具或 skill");
  lines.push("- 无需处理媒体的 query（纯闲聊/问候） → 忽略 buffer 直接对话");
  lines.push("");
  lines.push("不要盲目 OCR。根据文件类型和 query 意图做语义路由。");
  return lines.join("\n");
}

export default {
  id: "openclaw-query-gate",
  name: "Query Gate",
  description:
    "v0.4 语义路由版：媒体零成本 buffer（不做 OCR、不跑 agent），文本触发时通过 before_prompt_build 注入媒体路径清单让 agent 自主选工具。",

  register(api) {
    const cfg = api.pluginConfig ?? {};
    const enabled = cfg.enabled !== false;
    const channels =
      Array.isArray(cfg.channels) && cfg.channels.length > 0
        ? cfg.channels
        : DEFAULT_CHANNELS;
    const inboundScanAgeMs =
      typeof cfg.inboundScanAgeMs === "number" ? cfg.inboundScanAgeMs : 60_000;

    const log = api.logger ?? console;

    log.info?.(
      `[query-gate] v0.4.0 enabled=${enabled} channels=${JSON.stringify(channels)} ` +
        `inboundScanAgeMs=${inboundScanAgeMs}`,
    );

    if (!enabled) {
      log.info?.("[query-gate] master switch off.");
      return;
    }

    if (typeof api.on !== "function") {
      log.warn?.("[query-gate] api.on unavailable; plugin disabled.");
      return;
    }

    // baseline scan：认领所有已存在文件，避免把历史文件塞进 buffer
    try {
      const baseline = scanInboundDir();
      for (const f of baseline) claimedFiles.add(f.path);
      log.info?.(
        `[query-gate] baseline scan: ${baseline.length} existing files in ${INBOUND_DIR}`,
      );
    } catch (err) {
      log.warn?.(`[query-gate] baseline scan failed: ${String(err)}`);
    }

    // ────── before_dispatch ──────
    api.on("before_dispatch", (event, ctx) => {
      const channelId = ctx?.channelId;
      if (!channelId || !channels.includes(channelId)) return undefined;

      const content = typeof event?.content === "string" ? event.content.trim() : "";
      const convKey = convKeyOf(channelId, event, ctx);
      pruneExpiredBuffer(convKey);

      if (content.length === 0) {
        // 媒体消息 → 扫文件 + buffer，不跑 agent
        const newFiles = detectNewFiles(inboundScanAgeMs);
        let buf = mediaBuffer.get(convKey);
        if (!buf) {
          buf = { items: [], lastUpdate: Date.now() };
          mediaBuffer.set(convKey, buf);
        }
        for (const f of newFiles) {
          buf.items.push({
            path: f.path,
            name: f.name,
            mime: guessMime(f.name),
            sizeBytes: f.sizeBytes,
            receivedAt: f.mtime,
          });
        }
        buf.lastUpdate = Date.now();

        log.info?.(
          `[query-gate] media-bypassed: conv=${convKey} new=${newFiles.length} ` +
            `buffer_total=${buf.items.length}`,
        );
        return { handled: true };
      }

      // 文本 → 放行
      log.info?.(
        `[query-gate] text-through: conv=${convKey} text="${content.slice(0, 40)}${
          content.length > 40 ? "…" : ""
        }"`,
      );
      return undefined;
    });

    // ────── before_prompt_build ──────
    // agent 准备调 LLM 前，注入 media buffer 让 agent 语义路由
    //
    // 注意：此 hook 的 ctx 是 PluginHookAgentContext，不含 channelId / conversationId。
    // 要从 ctx.sessionKey 自行解析 channelId 做 channel gate 判断。
    api.on("before_prompt_build", (event, ctx) => {
      // sessionKey 是跨 hook 的 conversation key（所有 ctx 都有）
      const sessionKey = ctx?.sessionKey;
      const channelFromSk = channelIdFromSessionKey(sessionKey);

      if (!channelFromSk || !channels.includes(channelFromSk)) {
        return undefined; // 非 gated channel 的 agent run：静默放行
      }

      const convKey = convKeyOf(undefined, event, ctx);
      pruneExpiredBuffer(convKey);
      const buf = mediaBuffer.get(convKey);
      if (!buf || buf.items.length === 0) {
        log.info?.(
          `[query-gate] before_prompt_build: conv=${convKey} no buffer; no inject`,
        );
        return undefined;
      }

      const prepend = formatBufferForPrompt(buf);
      log.info?.(
        `[query-gate] prompt-inject: conv=${convKey} buffer_items=${buf.items.length} ` +
          `prepend_bytes=${prepend.length}`,
      );
      return { prependContext: prepend };
    });

    // ────── agent_end ──────
    // 一次 agent run 结束 → 清空 buffer（下一批媒体重新累计）
    // agent_end 的 ctx 也是 PluginHookAgentContext，没有 channelId。
    api.on("agent_end", (event, ctx) => {
      const channelFromSk = channelIdFromSessionKey(ctx?.sessionKey);
      if (!channelFromSk || !channels.includes(channelFromSk)) return undefined;

      const convKey = convKeyOf(undefined, event, ctx);
      if (mediaBuffer.has(convKey)) {
        const count = mediaBuffer.get(convKey)?.items.length ?? 0;
        clearBuffer(convKey);
        log.info?.(`[query-gate] buffer-cleared on agent_end: conv=${convKey} cleared=${count}`);
      }
      return undefined;
    });

    log.info?.(
      "[query-gate] hooks registered: before_dispatch + before_prompt_build + agent_end",
    );

    // ────── tool: medical_exam_check ──────
    // 把 medical-exam-checker skill 包装成 agent 可以直接 tool_use 的 tool。
    // 原因：OpenClaw 的 skill 只进 system prompt 作文档参考，不注册成 function tool。
    // 于是 agent 在处理体检核对时倾向调 `image` tool 硬啃，准确度不稳。
    // 本 tool 给 agent 一条直通路径：直接 tool_use → shell 调 skill check.py → 拿 chat 报告。
    registerMedicalExamCheckTool(api, log);
  },
};

// ============================================================================
// medical_exam_check tool 注册
// ============================================================================
function registerMedicalExamCheckTool(api, log) {
  if (typeof api?.registerTool !== "function") {
    log.warn?.("[query-gate] api.registerTool unavailable; medical_exam_check not registered.");
    return;
  }

  const SKILL_ROOT = path.join(os.homedir(), ".agents/skills/medical-exam-checker");
  const CHECK_SCRIPT = path.join(SKILL_ROOT, "scripts/check.py");
  const VENV_PY = path.join(SKILL_ROOT, ".venv/bin/python");

  if (!fs.existsSync(CHECK_SCRIPT)) {
    log.warn?.(
      `[query-gate] skill not found at ${SKILL_ROOT}; medical_exam_check tool skipped.`,
    );
    return;
  }

  api.registerTool({
    name: "medical_exam_check",
    label: "Medical Exam Check",
    description:
      "体检方案智能核对工具（封装 medical-exam-checker skill）。\n\n" +
      "【调用场景】当用户同时提供了**体检方案 Excel (.xlsx)** 和**体检订单图片/截图**，" +
      "要求「核对」「比对」「找差异」「查漏项」时，直接调用此工具。\n\n" +
      "【禁用场景】\n" +
      "- 用户只发了图片没发 Excel → 不要调用，向用户要 Excel\n" +
      "- 非体检场景（订单对账、商品清单等）→ 不要调用\n" +
      "- 纯视觉理解需求（描述图、解释流程图）→ 用 image tool 不是此工具\n\n" +
      "【为什么不用 image tool】\n" +
      "本工具内部封装百度 OCR + 三层匹配（规则/fuzzy/LLM）+ composites 父子项展开，" +
      "对体检场景精度显著高于通用视觉模型。用 image tool 会重复做 OCR 且结果不稳定。\n\n" +
      "【输入】\n" +
      "- excelPath: Excel 方案文件绝对路径（如 /Users/long/.openclaw/media/inbound/xxx.xlsx）\n" +
      "- imagePaths: 订单图片绝对路径数组（≥1 张，支持 jpg/png）\n\n" +
      "【输出】JSON。成功时包含 `chat` 字段（预格式化的 chat 报告，emoji + 紧凑摘要），" +
      "可以直接或稍作润色发给用户。失败时 `success: false` + error。",
    parameters: {
      type: "object",
      properties: {
        excelPath: {
          type: "string",
          description: "体检方案 Excel 文件的绝对路径（.xlsx）",
        },
        imagePaths: {
          type: "array",
          items: { type: "string" },
          minItems: 1,
          description: "订单图片的绝对路径列表（至少 1 张，支持 jpg/jpeg/png）",
        },
      },
      required: ["excelPath", "imagePaths"],
    },
    async execute(_toolCallId, params) {
      const excelPath = String(params?.excelPath || "");
      const imagePaths = Array.isArray(params?.imagePaths)
        ? params.imagePaths.filter((p) => typeof p === "string" && p.length > 0)
        : [];

      if (!excelPath || !fs.existsSync(excelPath)) {
        return JSON.stringify({
          success: false,
          error: `excelPath 不存在：${excelPath}`,
        });
      }
      if (imagePaths.length === 0) {
        return JSON.stringify({
          success: false,
          error: "imagePaths 为空",
        });
      }
      const missingImgs = imagePaths.filter((p) => !fs.existsSync(p));
      if (missingImgs.length > 0) {
        return JSON.stringify({
          success: false,
          error: `imagePaths 中有文件不存在: ${missingImgs.join(", ")}`,
        });
      }

      const python = fs.existsSync(VENV_PY) ? VENV_PY : "python3";
      const chatOutPath = `/tmp/med-exam-check-${Date.now()}-${Math.random().toString(36).slice(2, 8)}.txt`;
      const jsonOutPath = chatOutPath.replace(/\.txt$/, ".json");

      const args = [
        CHECK_SCRIPT,
        "--excel",
        excelPath,
        "--images",
        ...imagePaths,
        "--chat-output",
        chatOutPath,
        "--output",
        jsonOutPath,
      ];

      log.info?.(
        `[query-gate:tool] medical_exam_check running: python=${python} excel=${path.basename(
          excelPath,
        )} images=${imagePaths.length}`,
      );

      try {
        const { stderr } = await execFileP(python, args, {
          timeout: 300_000, // 5 min
          maxBuffer: 10 * 1024 * 1024,
        });
        const chatText = fs.existsSync(chatOutPath)
          ? fs.readFileSync(chatOutPath, "utf-8")
          : "(no chat output produced)";
        let summary;
        try {
          const jsonObj = JSON.parse(fs.readFileSync(jsonOutPath, "utf-8"));
          summary = jsonObj?.summary;
        } catch {
          summary = null;
        }
        // 清理临时文件
        try { fs.unlinkSync(chatOutPath); } catch {}
        try { fs.unlinkSync(jsonOutPath); } catch {}

        log.info?.(
          `[query-gate:tool] medical_exam_check done: summary=${JSON.stringify(summary)} chat_bytes=${chatText.length}`,
        );
        return JSON.stringify({
          success: true,
          chat: chatText,
          summary,
          stderrTail: (stderr || "").slice(-300),
        });
      } catch (err) {
        const errMsg = err?.message ? String(err.message) : String(err);
        const stderrTail = err?.stderr ? String(err.stderr).slice(-500) : "";
        log.error?.(`[query-gate:tool] medical_exam_check failed: ${errMsg}`);
        // 清理可能半成的临时文件
        try { fs.unlinkSync(chatOutPath); } catch {}
        try { fs.unlinkSync(jsonOutPath); } catch {}
        return JSON.stringify({
          success: false,
          error: errMsg,
          stderrTail,
        });
      }
    },
  });

  log.info?.(`[query-gate] registered tool: medical_exam_check (skill=${SKILL_ROOT})`);
}
