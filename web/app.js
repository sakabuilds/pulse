const defaults = {
  supervisor: { name: "Supervisor", description: "Your private command center. Sees every signal and drafts replies for your approval.", platforms: ["telegram", "mattermost"], privateOnly: true },
  community: { name: "Community", description: "Listens to public conversations and captures the signals your community is sending.", platforms: ["discord", "mattermost"] },
  team: { name: "Team", description: "Connects public feedback to internal context without exposing private supervisor signals.", platforms: ["slack", "mattermost"] },
};
const platforms = [["telegram", "Telegram", "Best for your supervisor", "➤", "telegram"], ["slack", "Slack", "Internal team workspace", "✣", "slack"], ["discord", "Discord", "Community conversations", "⌁", "discord"], ["mattermost", "Mattermost", "Local Switch room", "M", "mattermost"]];
const colors = { telegram: "#55aeda", slack: "#d9766b", discord: "#6f5ce8", mattermost: "#4f9d8c" };
const API = "/api";
let saved = structuredClone(defaults);
let connections = {};
let selected = "supervisor";
let apiOnline = false;

function note(message, state = "") {
  const element = document.querySelector("#api-note");
  element.className = `api-note ${state}`;
  element.innerHTML = `<span></span> ${message}`;
}

async function api(path, options = {}) {
  const response = await fetch(`${API}${path}`, { headers: { "Content-Type": "application/json" }, ...options });
  const body = await response.json();
  if (!response.ok) throw new Error(body.error || "Pulse control plane request failed");
  return body;
}

async function loadWorkspace() {
  try {
    const state = await api("/state");
    connections = state.connections || {};
    Object.entries(state.assignments || {}).forEach(([mode, config]) => { if (saved[mode]) saved[mode].platforms = config.platforms || []; });
    apiOnline = true;
    note("Workspace control plane connected", "ready");
  } catch (error) {
    note("Preview mode — start the control plane to save assignments", "error");
  }
  render();
}

function render() {
  const agent = saved[selected];
  document.querySelector("#selected-agent").textContent = agent.name;
  document.querySelector("#agent-description").textContent = agent.description;
  document.querySelector("#connection-count").textContent = agent.platforms.length;
  document.querySelectorAll(".agent-tab").forEach((tab) => tab.classList.toggle("active", tab.dataset.agent === selected));
  document.querySelector("#platform-list").innerHTML = platforms.map(([id, name, hint, icon, className]) => {
    const assigned = agent.platforms.includes(id);
    const connection = connections[id];
    const pending = connection && connection.status !== "connected";
    const action = connection ? (pending ? "OAuth pending" : "Connected") : "Connect app";
    return `<div class="platform-row ${assigned ? "connected" : ""} ${pending ? "waiting" : ""}"><span class="platform-logo ${className}" style="background:${colors[id]}">${icon}</span><span class="platform-info"><strong>${name}</strong><small>${connection ? (pending ? "Finish authorization to activate" : hint) : hint}</small><button class="connection-action ${connection && !pending ? "connected" : ""}" data-connect="${id}" ${connection && !pending ? "disabled" : ""}>${action}</button></span><button class="toggle ${assigned ? "on" : ""}" data-platform="${id}" aria-label="Toggle ${name}" aria-pressed="${assigned}" ${!connection ? "disabled" : ""}></button></div>`;
  }).join("");
  document.querySelectorAll(".toggle").forEach((toggle) => toggle.addEventListener("click", () => { const id = toggle.dataset.platform; saved[selected].platforms = saved[selected].platforms.includes(id) ? saved[selected].platforms.filter((item) => item !== id) : [...saved[selected].platforms, id]; render(); }));
  document.querySelectorAll("[data-connect]").forEach((button) => button.addEventListener("click", () => connectPlatform(button.dataset.connect)));
}

async function connectPlatform(platform) {
  try {
    if (apiOnline) {
      const state = await api("/connections", { method: "POST", body: JSON.stringify({ platform, label: `${platform[0].toUpperCase()}${platform.slice(1)} connection` }) });
      connections = state.connections;
      note(`${platform} connection created — OAuth handoff is next`, "ready");
    } else { connections[platform] = { status: "pending_oauth" }; note("Preview connection added locally", "ready"); }
    render();
  } catch (error) { note(error.message, "error"); }
}

document.querySelectorAll(".agent-tab").forEach((tab) => tab.addEventListener("click", () => { selected = tab.dataset.agent; render(); }));
document.querySelector("#save-button").addEventListener("click", async () => {
  const message = document.querySelector("#save-message");
  try {
    const assignments = Object.fromEntries(Object.entries(saved).map(([mode, agent]) => [mode, { room_type: agent.privateOnly ? "private" : "shared", platforms: agent.platforms }]));
    if (apiOnline) { await api("/assignments", { method: "POST", body: JSON.stringify(assignments) }); message.textContent = "Assignments saved to Pulse ✓"; }
    else { localStorage.setItem("pulse-assignments", JSON.stringify(saved)); message.textContent = "Saved in preview mode ✓"; }
    setTimeout(() => { message.textContent = ""; }, 2600);
  } catch (error) { message.textContent = error.message; }
});
document.querySelectorAll("[data-scroll]").forEach((button) => button.addEventListener("click", () => document.querySelector(button.dataset.scroll).scrollIntoView({ behavior: "smooth" })));
loadWorkspace();
