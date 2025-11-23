import { useCallback, useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Send } from "lucide-react";

import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Textarea } from "@/components/ui/textarea";
import { SmartComponentRenderer } from "@/components/SmartComponentRenderer";
import type { AgentStructuredResponse, AgentUIComponent } from "@/types/agent";

const API_BASE =
  import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, "") ?? "http://localhost:8000";
const THREAD_KEY = "crypto-agent-thread";
const HISTORY_KEY = "crypto-chat-history-v4";

const flowLog = (...args: unknown[]) => {
  // eslint-disable-next-line no-console
  console.log("%c[AgentFlow]", "color:#38bdf8;font-weight:bold", ...args);
};

type Message = {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: string;
  components: AgentUIComponent[];
  structured?: AgentStructuredResponse | null;
};

type SSEPacket = {
  event: string;
  data: any;
};

const welcomeComponent: AgentUIComponent = {
  id: crypto.randomUUID(),
  type: "text",
  content:
    "Welcome to the Crypto Analyst console. Ask for market breakdowns, comparisons, strategy context, or let me track your portfolio and I'll respond with reasoning + charts.",
};

const welcomeMessage: Message = {
  id: crypto.randomUUID(),
  role: "assistant",
  content: welcomeComponent.content ?? "",
  timestamp: new Date().toISOString(),
  components: [welcomeComponent],
  structured: { summary: welcomeComponent.content ?? "", responses: [welcomeComponent] },
};

const parseHistory = () => {
  if (typeof window === "undefined") return [welcomeMessage];
  const cached = window.localStorage.getItem(HISTORY_KEY);
  if (!cached) return [welcomeMessage];
  try {
    const parsed = JSON.parse(cached) as Message[];
    if (!Array.isArray(parsed) || !parsed.length) return [welcomeMessage];
    return parsed.map((msg) => ({
      ...msg,
      components: msg.components ?? [],
      structured: msg.structured ?? null,
    }));
  } catch {
    return [welcomeMessage];
  }
};

const parseSSEChunk = (previousBuffer: string, chunk: string) => {
  const combined = previousBuffer + chunk;
  const blocks = combined.split("\n\n");
  const trailing = blocks.pop() ?? "";
  let carryover = trailing;
  const packets: SSEPacket[] = [];
  for (const block of blocks) {
    if (!block.trim()) continue;
    const lines = block.split("\n");
    let eventType = "message";
    let dataBuffer = "";
    for (const rawLine of lines) {
      const line = rawLine.trim();
      if (line.startsWith("event:")) {
        eventType = line.slice(6).trim();
      } else if (line.startsWith("data:")) {
        dataBuffer += rawLine.slice(5);
      }
    }
    if (!dataBuffer) continue;
    try {
      packets.push({ event: eventType, data: JSON.parse(dataBuffer) });
    } catch {
      carryover = `${block}` + "\n\n" + carryover;
    }
  }
  return { events: packets, buffer: carryover };
};

const stripCodeFences = (value: string) => {
  if (!value) return "";
  return value
    .replace(/```json/gi, "")
    .replace(/```/g, "")
    .replace(/^\s*json\b[:=\s-]*/i, "")
    .trim();
};

const extractJsonPayload = (value: string) => {
  if (!value) return "";
  const fencedMatch = value.match(/```json\s*([\s\S]+?)```/i);
  const candidate = fencedMatch ? fencedMatch[1] : value;
  const cleaned = stripCodeFences(candidate);
  if (!cleaned) return "";
  if (cleaned.trimStart().startsWith("{")) return cleaned.trim();
  const firstBrace = cleaned.indexOf("{");
  const lastBrace = cleaned.lastIndexOf("}");
  if (firstBrace !== -1 && lastBrace > firstBrace) {
    return cleaned.slice(firstBrace, lastBrace + 1).trim();
  }
  return cleaned.trim();
};

const parseStructuredFromText = (value: string): AgentStructuredResponse | null => {
  const payload = extractJsonPayload(value);
  if (!payload) return null;
  try {
    const parsed = JSON.parse(payload);
    if (parsed && Array.isArray(parsed.responses)) {
      return parsed as AgentStructuredResponse;
    }
  } catch {
    return null;
  }
  return null;
};

const toolEventToComponent = (type: string, payload: any): AgentUIComponent => ({
  id: crypto.randomUUID(),
  type,
  data: payload,
});

const mergeComponentData = (
  incoming?: Record<string, unknown> | null,
  existing?: Record<string, unknown> | null
) => {
  if (!incoming || Object.keys(incoming).length === 0) return existing ?? undefined;
  if (!existing || Object.keys(existing).length === 0) return incoming ?? undefined;
  return { ...existing, ...incoming };
};

const TOOL_COMPONENT_TYPES = new Set<AgentUIComponent["type"]>([
  "asset_intel",
  "asset_overview",
  "compare_assets",
  "fundamentals_snapshot",
  "price_quotes",
  "trending_coins",
  "technical_analysis",
  "market_pulse",
  "portfolio",
  "watchlist",
  "metric_grid",
  "news_list",
  "alerts_panel",
  "chart",
  "table",
]);

const isLikelyJsonPayload = (value: string) => {
  const trimmed = value.trim();
  if (!trimmed) return false;
  if (trimmed.startsWith("{") || trimmed.startsWith("[")) return true;
  return /"responses"\s*:/.test(trimmed);
};

export default function App() {
  const [messages, setMessages] = useState<Message[]>(() => parseHistory());
  const [inputValue, setInputValue] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [chatError, setChatError] = useState<string | null>(null);
  const [statuses, setStatuses] = useState<string[]>([]);

  const threadId = usePersistentThreadId();
  const scrollRef = useRef<HTMLDivElement>(null);
  const activeAssistantIdRef = useRef<string | null>(null);
  const toolPayloadCacheRef = useRef<Record<string, AgentUIComponent[]>>({});

  useEffect(() => {
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [messages, statuses]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    window.localStorage.setItem(HISTORY_KEY, JSON.stringify(messages));
  }, [messages]);

  const pushStatus = useCallback((text: string) => {
    setStatuses((prev) => [...prev, text]);
  }, []);

  const resetStatuses = useCallback(() => setStatuses([]), []);

  const appendMessage = (message: Message) =>
    setMessages((prev) => [...prev, message]);

  const updateAssistantMessage = useCallback((id: string, delta: string) => {
    setMessages((prev) =>
      prev.map((message) =>
        message.id === id
          ? { ...message, content: message.content + delta }
          : message
      )
    );
  }, []);

  const overwriteAssistantMessage = useCallback((id: string, text: string) => {
    setMessages((prev) =>
      prev.map((message) =>
        message.id === id ? { ...message, content: text } : message
      )
    );
  }, []);

  const appendComponent = useCallback((component: AgentUIComponent) => {
    const targetId = activeAssistantIdRef.current;
    if (!targetId) return;
    flowLog("Streaming component received", { targetId, type: component.type });
    toolPayloadCacheRef.current[targetId] = [
      ...(toolPayloadCacheRef.current[targetId] ?? []),
      component,
    ];
    setMessages((prev) =>
      prev.map((message) =>
        message.id === targetId
          ? {
              ...message,
              components: [...(message.components ?? []), component],
            }
          : message
      )
    );
  }, []);

  const finalizeAssistantMessage = useCallback(
    (id: string, text: string, options?: { preserveExisting?: boolean }) => {
      flowLog("Finalizing assistant message", { id, preserveExisting: options?.preserveExisting, textPreview: text });
      setMessages((prev) =>
        prev.map((message) =>
          message.id === id
            ? options?.preserveExisting
              ? message
              : { ...message, content: text }
            : message
        )
      );
      activeAssistantIdRef.current = null;
    },
    []
  );

  const applyStructuredPayload = useCallback(
    (id: string, structured: AgentStructuredResponse | undefined) => {
      if (!structured) return;
      flowLog("Structured payload received", {
        id,
        summary: structured.summary,
        responseTypes: (structured.responses ?? []).map((component) => component.type),
      });
      const cachedComponents = toolPayloadCacheRef.current[id] ?? [];
      const cacheConsumed = new Set<number>();

      const findCachedComponent = (type: string) => {
        const cacheIndex = cachedComponents.findIndex((cached, idx) => {
          if (cacheConsumed.has(idx)) return false;
          return cached.type === type;
        });
        if (cacheIndex >= 0) {
          cacheConsumed.add(cacheIndex);
          return cachedComponents[cacheIndex];
        }
        return undefined;
      };

      setMessages((prev) =>
        prev.map((message) => {
          if (message.id !== id) return message;

          const priorComponents = message.components ?? [];
          const consumed = new Set<number>();

          const hydrateComponent = (component: AgentUIComponent, index: number) => {
            const existingIndex = priorComponents.findIndex((existing, existingIdx) => {
              if (consumed.has(existingIdx)) return false;
              return existing.type === component.type;
            });
            let matched = existingIndex >= 0 ? priorComponents[existingIndex] : undefined;
            if (!matched) {
              matched = findCachedComponent(component.type);
            }
            if (existingIndex >= 0) consumed.add(existingIndex);
            const preferExisting = !!matched && TOOL_COMPONENT_TYPES.has(component.type);
            const mergedData = preferExisting
              ? matched?.data
              : mergeComponentData(component.data ?? null, matched?.data ?? null);

            const mergedOptions = preferExisting
              ? matched?.options
              : component.options && matched?.options
              ? { ...matched.options, ...component.options }
              : component.options ?? matched?.options;

            const mergedChartType = preferExisting ? matched?.chart_type : component.chart_type ?? matched?.chart_type;

            const mergedContent = component.content ?? matched?.content;
            return {
              ...(preferExisting ? matched : matched ?? {}),
              ...(!preferExisting ? component : { type: component.type }),
              id: component.id ?? matched?.id ?? crypto.randomUUID(),
              data: mergedData,
              chart_type: mergedChartType,
              options: mergedOptions,
              content: mergedContent,
            };
          };

          const structuredComponents = (structured.responses ?? []).map(hydrateComponent);
          flowLog("Structured components hydrated", {
            id,
            structuredCount: structuredComponents.length,
            cachedCount: cachedComponents.length,
          });
          const leftovers = priorComponents.filter((_, idx) => !consumed.has(idx));
          const mergedComponents =
            structuredComponents.length > 0 ? [...structuredComponents, ...leftovers] : priorComponents;

          return {
            ...message,
            structured,
            components: mergedComponents,
            content: structured.summary ?? message.content,
          };
        })
      );
      delete toolPayloadCacheRef.current[id];
      flowLog("Structured payload applied", {
        id,
        totalComponents: structured.responses?.length ?? 0,
      });
    },
    []
  );

  const handleSuggestion = (prompt: string) => {
    setInputValue(prompt);
  };

  const handleSend = async () => {
    if (!inputValue.trim() || isStreaming) return;
    flowLog("handleSend invoked", { threadId, prompt: inputValue.trim() });
    setChatError(null);
    const userMessage: Message = {
      id: crypto.randomUUID(),
      role: "user",
      content: inputValue.trim(),
      timestamp: new Date().toISOString(),
      components: [],
      structured: null,
    };
    const assistantMessage: Message = {
      id: crypto.randomUUID(),
      role: "assistant",
      content: "Analyzing market data...",
      timestamp: new Date().toISOString(),
      components: [],
      structured: null,
    };
    appendMessage(userMessage);
    appendMessage(assistantMessage);
    setInputValue("");
    setIsStreaming(true);
    activeAssistantIdRef.current = assistantMessage.id;
    resetStatuses();

    try {
      let sseBuffer = "";
      let structuredStreamDetected = false;
      let placeholderSet = false;
      let structuredSeen = false;
      let latestStructured: AgentStructuredResponse | undefined;
      const response = await fetch(`${API_BASE}/api/chat/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: userMessage.content,
          thread_id: threadId,
        }),
      });
      if (!response.ok || !response.body) throw new Error("Streaming request failed");

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let fullText = "";

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        const chunk = decoder.decode(value, { stream: true });
        const { events, buffer } = parseSSEChunk(sseBuffer, chunk);
        sseBuffer = buffer;
        events.forEach(({ event, data }) => {
          flowLog("SSE event", { event, data });
          if (event === "status") {
            pushStatus(data?.message ?? "Running tool...");
          } else if (event === "visual") {
            appendComponent(
              toolEventToComponent(
                data?.type ?? data?.tool ?? "visual",
                data?.payload ?? data?.output
              )
            );
          } else if (event === "layout") {
            structuredSeen = true;
            latestStructured = data as AgentStructuredResponse;
            applyStructuredPayload(assistantMessage.id, latestStructured);
          } else if (event === "message") {
            if (data?.event === "end") return;
            if (data?.chunk) {
              const chunkText = data.chunk;
              fullText += chunkText;
              const candidatePayload = extractJsonPayload(chunkText);
              const chunkSignalsStructured =
                /```json/i.test(chunkText) ||
                /^\s*json\b/i.test(chunkText) ||
                (candidatePayload?.trim().startsWith("{") ?? false);
              if (chunkSignalsStructured) {
                structuredStreamDetected = true;
                if (!placeholderSet) {
                  overwriteAssistantMessage(
                    assistantMessage.id,
                    "Synthesizing structured response..."
                  );
                  placeholderSet = true;
                }
              } else {
                const cleanedChunk = stripCodeFences(chunkText);
                if (cleanedChunk) {
                  updateAssistantMessage(assistantMessage.id, cleanedChunk);
                }
              }
            }
          }
        });
      }

      if (!structuredSeen) {
        const parsedFromStream = parseStructuredFromText(fullText);
        if (parsedFromStream) {
          structuredSeen = true;
          latestStructured = parsedFromStream;
          applyStructuredPayload(assistantMessage.id, parsedFromStream);
        }
      }

      if (!fullText && !structuredSeen) {
        const fallback = await fetch(`${API_BASE}/api/chat`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            message: userMessage.content,
            thread_id: threadId,
          }),
        });
        if (!fallback.ok) throw new Error("Fallback chat request failed");
        const payload = await fallback.json();
        flowLog("Fallback /api/chat response", payload);
        fullText = payload.content;
        if (payload.structured) {
          structuredSeen = true;
          latestStructured = payload.structured;
          applyStructuredPayload(assistantMessage.id, payload.structured);
        }
      }

      const cleanedText = stripCodeFences(fullText);
      if (structuredSeen) {
        finalizeAssistantMessage(
          assistantMessage.id,
          latestStructured?.summary ?? cleanedText ?? "",
          { preserveExisting: true }
        );
      } else {
        finalizeAssistantMessage(
          assistantMessage.id,
          cleanedText || "I wasn't able to retrieve a response."
        );
      }
    } catch (error) {
      console.error(error);
      flowLog("Streaming error", error);
      setChatError(error instanceof Error ? error.message : "Unable to reach the agent.");
      finalizeAssistantMessage(assistantMessage.id, "I hit an error retrieving data.");
    } finally {
      setIsStreaming(false);
      resetStatuses();
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-black px-4 py-8 text-foreground">
      <div className="mx-auto flex max-w-4xl flex-col gap-6">
        <motion.header
          className="rounded-[32px] border border-white/5 bg-white/5 p-6 shadow-2xl backdrop-blur"
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
        >
          <p className="text-xs uppercase tracking-[0.6rem] text-primary/70">LangGraph Agent</p>
          <h1 className="mt-2 text-3xl font-semibold">Crypto Analyst Workspace</h1>
          <p className="text-sm text-muted-foreground">
            Real-time reasoning + CoinGecko, news, and on-chain context. Every answer streams into this chat with interactive components�no extra panels required.
          </p>
        </motion.header>

        <section className="rounded-[32px] border border-white/5 bg-gradient-to-b from-white/5 to-white/0 p-6 backdrop-blur">
          <ScrollArea className="h-[65vh]" ref={scrollRef}>
            <div className="space-y-6 pr-4">
              <AnimatePresence>
                {messages.map((message) => {
                  const rawText = message.content ?? "";
                  const normalizedText =
                    message.role === "assistant"
                      ? stripCodeFences(rawText)
                      : rawText;
                  const hideAssistantText =
                    message.role === "assistant" &&
                    (isLikelyJsonPayload(normalizedText) ||
                      (!normalizedText.trim() &&
                        (message.components?.length ?? 0) > 0));

                  return (
                    <motion.div
                      key={message.id}
                      initial={{ opacity: 0, y: 16 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, y: -16 }}
                      className={`flex flex-col gap-3 ${
                        message.role === "assistant" ? "" : "items-end"
                      }`}
                    >
                      {!hideAssistantText && (
                        <div
                          className={`max-w-[90%] rounded-3xl border px-5 py-4 text-base leading-relaxed shadow-lg ${
                            message.role === "assistant"
                              ? "border-white/5 bg-white/5"
                              : "border-primary/40 bg-primary/15 text-primary-foreground"
                          }`}
                        >
                          <p className="text-[10px] uppercase tracking-[0.45rem] text-muted-foreground">
                            {message.role === "assistant" ? "Analyst" : "You"}
                          </p>
                          <p className="mt-2 whitespace-pre-line">
                            {normalizedText || rawText || "..."}
                          </p>
                        </div>
                      )}
                      {message.components?.length ? (
                        <div className="flex flex-col gap-4">
                          {message.components.map((component) => (
                            <SmartComponentRenderer
                              key={component.id}
                              component={component}
                              onFollowUp={handleSuggestion}
                            />
                          ))}
                        </div>
                      ) : null}
                    </motion.div>
                  );
                })}
              </AnimatePresence>

              {isStreaming && statuses.length > 0 && (
                <motion.div
                  initial={{ opacity: 0, y: 12 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="flex flex-col gap-2 text-xs text-muted-foreground"
                >
                  {statuses.map((status) => (
                    <div
                      key={status}
                      className="max-w-[80%] rounded-2xl border border-white/10 bg-black/30 px-3 py-2"
                    >
                      {status}
                    </div>
                  ))}
                </motion.div>
              )}
            </div>
          </ScrollArea>

          {chatError && (
            <p className="mt-4 text-sm text-destructive">{chatError}</p>
          )}

          <div className="mt-6 space-y-3 rounded-3xl border border-white/10 bg-black/40 p-4">
            <Textarea
              placeholder="e.g. Compare BTC vs ETH, show volume and risk context"
              value={inputValue}
              onChange={(event) => setInputValue(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  handleSend();
                }
              }}
              disabled={isStreaming}
            />
            <div className="flex flex-wrap items-center justify-between gap-3 text-xs text-muted-foreground">
              <span>Shift + Enter for newline � Thread ID {threadId.slice(0, 8)}�</span>
              <Button className="gap-2" disabled={isStreaming || !inputValue.trim()} onClick={handleSend}>
                {isStreaming ? "Streaming�" : "Send"}
                <Send className="h-4 w-4" />
              </Button>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}

function usePersistentThreadId() {
  const [threadId] = useState(() => {
    if (typeof window === "undefined") return crypto.randomUUID();
    const cached = window.localStorage.getItem(THREAD_KEY);
    if (cached) return cached;
    const generated = crypto.randomUUID();
    window.localStorage.setItem(THREAD_KEY, generated);
    return generated;
  });
  return threadId;
}




