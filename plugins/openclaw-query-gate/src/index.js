// @ts-check
// OpenClaw plugin: openclaw-query-gate
//
// 策略（v0.3.0 · 精简版）：
//   - 媒体消息（content 为空）：放行让 OpenClaw 做 OCR + 写 session；
//     随后 agent 产出的 reply 在 message_sending 被 cancel（用户不见）。
//   - 任何文本消息：放行，agent 正常对话。用户的跟进问句（如"罗列下详情"、
//     "说细点"）一律被响应。
//
// 对比 v0.2.0 的改动：
//   v0.2.0 用 triggerKeywords 白名单过滤文本，结果把正常对话中的跟进
//   问句也挡了（如"罗列下详情"不含关键词被静默）。v0.3.0 取消文本过滤，
//   只用 media-vs-text 这一个硬分类：
//     - 媒体 → cancel reply（避免刷屏）
//     - 文本 → allow reply（保证对话连贯）
//   这样 triggerKeywords 变成**可选严格模式**（用 config.strictMode
//   开启才回到 v0.2.0 行为）。

const DEFAULT_CHANNELS = ["openclaw-weixin"];

// 严格模式下使用的触发词（默认不启用）
const DEFAULT_TRIGGER_KEYWORDS = [
  "核对",
  "比对",
  "帮我看看",
  "帮我",
  "开始处理",
  "开始核对",
  "对比",
  "汇总",
  "提取",
  "执行",
  "处理",
  "分析",
  "总结",
  "查询",
  "检查",
];

/**
 * 按会话追踪"最近一次 inbound 是不是用户主动对话（text 文本）"。
 * message_sending 要读这个：true→allow, false(media)→cancel。
 *
 * @type {Map<string, { isText: boolean, timestamp: number }>}
 */
const lastInboundTag = new Map();
const LAST_INBOUND_TTL_MS = 60 * 60 * 1000;

function convKeyOf(channelId, event, ctx) {
  const id =
    (ctx && ctx.conversationId) ||
    (event && typeof event.to === "string" && event.to) ||
    (ctx && ctx.senderId) ||
    "unknown";
  return `${channelId}:${id}`;
}

function tagInbound(convKey, isText) {
  lastInboundTag.set(convKey, { isText, timestamp: Date.now() });
  setTimeout(() => {
    const e = lastInboundTag.get(convKey);
    if (e && Date.now() - e.timestamp >= LAST_INBOUND_TTL_MS) {
      lastInboundTag.delete(convKey);
    }
  }, LAST_INBOUND_TTL_MS + 1000).unref?.();
}

function shouldAllowReply(convKey) {
  const e = lastInboundTag.get(convKey);
  if (!e) return true; // 无记录保守放行
  if (Date.now() - e.timestamp > LAST_INBOUND_TTL_MS) return true;
  return e.isText; // 文本触发的 reply 放行；媒体触发的 reply cancel
}

export default {
  id: "openclaw-query-gate",
  name: "Query Gate",
  description:
    "Query-gate v0.3: 媒体让 dispatch 跑完以丰富 session，媒体的 agent reply 在 outbound 处 cancel；所有文本一律放行以保证跟进对话不被误挡。",

  register(api) {
    const cfg = api.pluginConfig ?? {};
    const enabled = cfg.enabled !== false;
    const channels =
      Array.isArray(cfg.channels) && cfg.channels.length > 0
        ? cfg.channels
        : DEFAULT_CHANNELS;
    const strictMode = cfg.strictMode === true; // 默认关闭：文本一律放行
    const triggerKeywords =
      Array.isArray(cfg.triggerKeywords) && cfg.triggerKeywords.length > 0
        ? cfg.triggerKeywords
        : DEFAULT_TRIGGER_KEYWORDS;

    const log = api.logger ?? console;

    log.info?.(
      `[query-gate] v0.3.0 enabled=${enabled} channels=${JSON.stringify(channels)} ` +
        `strictMode=${strictMode}${strictMode ? ` keywords=${triggerKeywords.length}` : ""}`,
    );

    if (!enabled) {
      log.info?.("[query-gate] master switch off.");
      return;
    }

    if (typeof api.on !== "function") {
      log.warn?.("[query-gate] api.on unavailable; plugin disabled.");
      return;
    }

    // ────── before_dispatch ──────
    api.on("before_dispatch", (event, ctx) => {
      const channelId = ctx?.channelId;
      if (!channelId || !channels.includes(channelId)) return undefined;

      const content = typeof event?.content === "string" ? event.content.trim() : "";
      const convKey = convKeyOf(channelId, event, ctx);

      // 1. 纯媒体：放行 dispatch（跑 OCR + 写 session），标记为 media
      if (content.length === 0) {
        tagInbound(convKey, false); // media
        log.info?.(`[query-gate] media-through (ocr+session): conv=${convKey}`);
        return undefined;
      }

      // 2. 严格模式：文本还要过触发词
      if (strictMode) {
        const hit = triggerKeywords.some((kw) => content.includes(kw));
        if (!hit) {
          tagInbound(convKey, false); // 视同 media：cancel
          log.info?.(
            `[query-gate] silent non-query text (strictMode): conv=${convKey} text="${content.slice(0, 50)}${
              content.length > 50 ? "…" : ""
            }"`,
          );
          return { handled: true };
        }
      }

      // 3. 文本（宽松模式或命中触发词）：放行，标记为 text
      tagInbound(convKey, true);
      log.info?.(
        `[query-gate] text-through: conv=${convKey} text="${content.slice(0, 40)}${
          content.length > 40 ? "…" : ""
        }"`,
      );
      return undefined;
    });

    // ────── message_sending ──────
    api.on("message_sending", (event, ctx) => {
      const channelId = ctx?.channelId;
      if (!channelId || !channels.includes(channelId)) return undefined;

      const convKey = convKeyOf(channelId, event, ctx);
      if (shouldAllowReply(convKey)) {
        return undefined; // 文本引发的 reply：放行
      }

      // 媒体引发的 reply：cancel（避免刷屏）
      const preview =
        typeof event?.content === "string" ? event.content.slice(0, 60).replace(/\n/g, " ") : "";
      log.info?.(
        `[query-gate] cancel reply (media-driven): conv=${convKey} preview="${preview}"`,
      );
      return { cancel: true };
    });

    log.info?.("[query-gate] before_dispatch + message_sending hooks registered.");
  },
};
