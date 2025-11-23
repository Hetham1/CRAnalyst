const form = document.getElementById("chat-form");
const input = document.getElementById("message-input");
const chatLog = document.getElementById("chat-log");

const threadKey = "crypto-analyst-thread";
const threadId = (() => {
  const existing = window.localStorage.getItem(threadKey);
  if (existing) return existing;
  const fresh = crypto.randomUUID();
  window.localStorage.setItem(threadKey, fresh);
  return fresh;
})();

const appendMessage = (role, text) => {
  const wrapper = document.createElement("article");
  wrapper.className = `message ${role}`;
  wrapper.textContent = text;
  chatLog.appendChild(wrapper);
  chatLog.scrollTop = chatLog.scrollHeight;
  return wrapper;
};

const parseSSE = (chunk, callback) => {
  const lines = chunk.split("\n");
  lines.forEach((line) => {
    if (line.startsWith("data:")) {
      const payload = line.replace("data:", "").trim();
      if (!payload) return;
      try {
        const data = JSON.parse(payload);
        callback(data);
      } catch {
        // swallow malformed payloads
      }
    }
  });
};

const streamResponse = async (message, target) => {
  const response = await fetch("/api/chat/stream", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, thread_id: threadId }),
  });

  if (!response.ok || !response.body) {
    throw new Error("Streaming failed");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    const textChunk = decoder.decode(value, { stream: true });
    parseSSE(textChunk, (event) => {
      if (event.event === "end") return;
      if (event.chunk) {
        target.textContent += event.chunk;
      }
    });
  }
};

const fallbackRequest = async (message, target) => {
  const response = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, thread_id: threadId }),
  });
  if (!response.ok) {
    throw new Error("API error");
  }
  const payload = await response.json();
  target.textContent = payload.content;
};

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const message = input.value.trim();
  if (!message) return;

  appendMessage("user", message);
  const botBubble = appendMessage("bot", "...");
  input.value = "";
  input.disabled = true;

  try {
    await streamResponse(message, botBubble);
  } catch (error) {
    botBubble.textContent = "Fetching live stream failed, retrying...";
    try {
      await fallbackRequest(message, botBubble);
    } catch (fallbackError) {
      botBubble.textContent = `Error: ${fallbackError.message}`;
    }
  } finally {
    input.disabled = false;
    input.focus();
  }
});
