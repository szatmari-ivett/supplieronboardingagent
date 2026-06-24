const chat = document.getElementById("chat");
const form = document.getElementById("chatForm");
const input = document.getElementById("messageInput");
const healthBadge = document.getElementById("healthBadge");
const progressFill = document.getElementById("progressFill");
const phaseLabel = document.getElementById("phaseLabel");
const sessionId = crypto.randomUUID();

const phases = [
  "initiated",
  "duplicate_check",
  "package_created",
  "erp_sync",
  "cloud_compliance",
  "active",
];

function addMessage(role, text, metadata = null) {
  const bubble = document.createElement("div");
  bubble.className = `message ${role}`;
  bubble.textContent = text;
  chat.appendChild(bubble);

  if (metadata?.tool_result && metadata.tool) {
    const details = document.createElement("details");
    details.className = "tool-details";
    const summary = document.createElement("summary");
    summary.textContent = `Tool: ${metadata.tool}`;
    const pre = document.createElement("pre");
    pre.textContent = JSON.stringify(metadata.tool_result, null, 2);
    details.appendChild(summary);
    details.appendChild(pre);
    chat.appendChild(details);
    updateStatusPanel(metadata.tool_result, metadata);
  }

  chat.scrollTop = chat.scrollHeight;
}

function updateStatusPanel(toolResult, metadata) {
  const phase =
    toolResult.canonical_phase ||
    toolResult.phase ||
    toolResult.onboarding?.phase ||
    metadata?.tool_result?.canonical_phase;
  const health = toolResult.health || "unknown";

  if (phase) {
    phaseLabel.textContent = `Phase: ${phase}`;
    const index = phases.indexOf(phase);
    const width = index >= 0 ? ((index + 1) / phases.length) * 100 : 20;
    progressFill.style.width = `${width}%`;
  }

  healthBadge.textContent = `Health: ${health}`;
  healthBadge.className = `badge ${health === "degraded" ? "degraded" : health === "stale" ? "stale" : "healthy"}`;
}

async function sendMessage(message) {
  addMessage("user", message);
  input.value = "";

  const response = await fetch("/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, session_id: sessionId }),
  });

  if (!response.ok) {
    addMessage("assistant", "Request failed. Please try again.");
    return;
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const chunks = buffer.split("\n\n");
    buffer = chunks.pop() || "";

    for (const chunk of chunks) {
      if (!chunk.startsWith("data: ")) continue;
      const payload = JSON.parse(chunk.slice(6));
      if (payload.type === "message") {
        addMessage("assistant", payload.response, payload.metadata);
      } else if (payload.type === "error") {
        addMessage("assistant", payload.message);
      }
    }
  }
}

form.addEventListener("submit", (event) => {
  event.preventDefault();
  const message = input.value.trim();
  if (message) sendMessage(message);
});

document.querySelectorAll(".example").forEach((button) => {
  button.addEventListener("click", () => sendMessage(button.dataset.message));
});

addMessage(
  "assistant",
  "Hello! I can check duplicate suppliers, start onboarding packages across procurement/ERP/cloud, or provide aggregated onboarding status."
);
