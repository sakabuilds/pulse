const defaults = {
  supervisor: { name: "Supervisor", description: "Your command center. Sees every signal and drafts replies for your approval.", platforms: ["telegram", "mattermost"] },
  community: { name: "Community", description: "Listens to public conversations and captures the signals your community is sending.", platforms: ["discord", "mattermost"] },
  team: { name: "Team", description: "Connects public feedback to internal context without exposing private supervisor signals.", platforms: ["slack", "mattermost"] },
};
const platforms = [
  ["telegram", "Telegram", "Best for your supervisor", "➤", "telegram"],
  ["slack", "Slack", "Internal team workspace", "✣", "slack"],
  ["discord", "Discord", "Community conversations", "⌁", "discord"],
  ["mattermost", "Mattermost", "Local Switch room", "M", "mattermost"],
];
const colors = { telegram: "#55aeda", slack: "#d9766b", discord: "#6f5ce8", mattermost: "#4f9d8c" };
const saved = JSON.parse(localStorage.getItem("pulse-assignments") || "null") || structuredClone(defaults);
let selected = "supervisor";

function render() {
  const agent = saved[selected];
  document.querySelector("#selected-agent").textContent = agent.name;
  document.querySelector("#agent-description").textContent = agent.description;
  document.querySelector("#connection-count").textContent = agent.platforms.length;
  document.querySelectorAll(".agent-tab").forEach((tab) => tab.classList.toggle("active", tab.dataset.agent === selected));
  document.querySelector("#platform-list").innerHTML = platforms.map(([id, name, hint, icon, className]) => {
    const on = agent.platforms.includes(id);
    return `<div class="platform-row ${on ? "connected" : ""}">
      <span class="platform-logo ${className}" style="background:${colors[id]}">${icon}</span>
      <span class="platform-info"><strong>${name}</strong><small>${hint}</small></span>
      <button class="toggle ${on ? "on" : ""}" data-platform="${id}" aria-label="Toggle ${name}" aria-pressed="${on}"></button>
    </div>`;
  }).join("");
  document.querySelectorAll(".toggle").forEach((toggle) => toggle.addEventListener("click", () => {
    const id = toggle.dataset.platform;
    saved[selected].platforms = saved[selected].platforms.includes(id) ? saved[selected].platforms.filter((item) => item !== id) : [...saved[selected].platforms, id];
    render();
  }));
}

document.querySelectorAll(".agent-tab").forEach((tab) => tab.addEventListener("click", () => { selected = tab.dataset.agent; render(); }));
document.querySelector("#save-button").addEventListener("click", () => {
  localStorage.setItem("pulse-assignments", JSON.stringify(saved));
  const message = document.querySelector("#save-message");
  message.textContent = "Assignments saved locally ✓";
  setTimeout(() => { message.textContent = ""; }, 2600);
});
document.querySelectorAll("[data-scroll]").forEach((button) => button.addEventListener("click", () => document.querySelector(button.dataset.scroll).scrollIntoView({ behavior: "smooth" })));
render();
