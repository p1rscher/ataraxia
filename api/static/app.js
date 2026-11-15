"use strict";
// Ataraxia dashboard. Plain JavaScript, no build step. All URLs are relative
// so the dashboard also works when served from a sub-path such as /dashboard/.

const app = document.getElementById("app");
const state = { me: null, guilds: [], invite: null, guild: null, tab: "xp" };

function h(tag, attrs, ...children) {
  const el = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs || {})) {
    if (value === null || value === undefined || value === false) continue;
    if (key.startsWith("on")) el.addEventListener(key.slice(2), value);
    else if (key === "class") el.className = value;
    else if (key in el && key !== "list") el[key] = value;
    else el.setAttribute(key, value);
  }
  for (const child of children.flat()) {
    if (child === null || child === undefined || child === false) continue;
    el.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return el;
}

// replaceChildren() would print null/false as text; this drops them.
function show(parent, ...children) {
  parent.replaceChildren(...children.flat().filter((c) => c !== null && c !== undefined && c !== false));
}

let toastTimer;
function toast(message, isError) {
  const el = document.getElementById("toast");
  el.textContent = message;
  el.className = "show" + (isError ? " error" : "");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { el.className = ""; }, isError ? 6000 : 2500);
}

async function api(method, path, body) {
  const options = { method, credentials: "same-origin", headers: { "X-Requested-With": "ataraxia-dashboard" } };
  if (body !== undefined) {
    options.headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(body);
  }
  let response;
  try {
    response = await fetch(path, options);
  } catch (error) {
    throw new Error("The dashboard server is not reachable.");
  }
  let data = null;
  try { data = await response.json(); } catch (error) { /* empty body */ }
  if (response.status === 401) {
    state.me = null;
    renderLogin();
    throw new Error((data && data.detail) || "Please log in again.");
  }
  if (!response.ok) throw new Error((data && data.detail) || "Request failed (" + response.status + ")");
  return data;
}

// Runs an action, shows the outcome and never leaves a rejected promise behind.
async function run(action, successMessage) {
  try {
    const result = await action();
    if (successMessage) toast(successMessage);
    return result;
  } catch (error) {
    toast(error.message, true);
    return undefined;
  }
}

const guildPath = (suffix) => "api/guilds/" + state.guild.id + (suffix || "");
const roleName = (id) => { const r = state.guild.roles.find((x) => x.id === id); return r ? "@" + r.name : "deleted role (" + id + ")"; };
const channelName = (id) => { const c = state.guild.channels.find((x) => x.id === id); return c ? "#" + c.name : "deleted channel (" + id + ")"; };

function roleSelect(onlyAssignable, selected) {
  const roles = state.guild.roles.filter((r) => !r.everyone && (!onlyAssignable || r.assignable));
  return h("select", {},
    h("option", { value: "" }, "Choose a role…"),
    roles.map((r) => h("option", { value: r.id, selected: r.id === selected }, "@" + r.name)));
}

function channelSelect(types, selected, emptyLabel) {
  const channels = state.guild.channels.filter((c) => types.includes(c.type));
  return h("select", {},
    h("option", { value: "" }, emptyLabel || "Choose a channel…"),
    channels.map((c) => h("option", { value: c.id, selected: c.id === selected }, (c.type === "voice" || c.type === "stage" ? "🔊 " : "#") + c.name)));
}

// ------------------------------------------------------------------ screens

function renderUser() {
  const box = document.getElementById("user");
  box.replaceChildren();
  if (!state.me) return;
  box.append(h("span", {}, state.me.username), h("button", {
    onclick: async () => {
      await run(() => api("POST", "auth/logout"));
      state.me = null; state.guild = null;
      renderUser(); renderLogin();
    },
  }, "Log out"));
}

function renderLogin() {
  renderUser();
  const reason = new URLSearchParams(location.search).get("login");
  show(app, h("div", { class: "card center" },
    h("h1", {}, "Ataraxia Dashboard"),
    h("p", { class: "muted" }, "Log in with Discord to change the settings of the servers you administer."),
    reason === "failed" ? h("p", { style: "color: var(--danger)" }, "The login did not complete. Please try again.") : null,
    h("a", { class: "button primary", href: "auth/login" }, "Log in with Discord")));
}

function renderGuilds() {
  state.guild = null;
  const icon = (g) => g.icon
    ? h("img", { src: "https://cdn.discordapp.com/icons/" + g.id + "/" + g.icon + ".png?size=96", alt: "" })
    : h("span", { class: "ph" }, g.name.slice(0, 1).toUpperCase());
  show(app, 
    h("h1", {}, "Your servers"),
    h("p", { class: "hint" }, "Servers where you are an administrator."),
    state.guilds.length === 0 ? h("div", { class: "card" }, "You are not an administrator of any server.") : null,
    h("div", { class: "guilds" }, state.guilds.map((g) => g.bot_present
      ? h("button", { class: "guild", onclick: () => openGuild(g.id) }, icon(g), h("span", {}, g.name, h("small", {}, "Open settings")))
      : h("a", { class: "button guild", href: state.invite + "&guild_id=" + g.id, target: "_blank", rel: "noopener" },
          icon(g), h("span", {}, g.name, h("small", {}, "Add Ataraxia to this server"))))));
}

async function openGuild(id) {
  show(app, h("p", { class: "muted" }, "Loading…"));
  const guild = await run(() => api("GET", "api/guilds/" + id));
  if (!guild) { if (state.me) renderGuilds(); return; }
  state.guild = guild;
  renderGuild();
}

const TABS = [
  ["xp", "XP", tabXp], ["multipliers", "Multipliers", tabMultipliers], ["logs", "Log channels", tabLogs],
  ["level-roles", "Level roles", tabLevelRoles], ["auto-roles", "Auto roles", tabAutoRoles],
  ["leaderboard", "Leaderboard", tabLeaderboard],
];

function renderGuild() {
  const body = h("div", {}, h("p", { class: "muted" }, "Loading…"));
  show(app, 
    h("button", { onclick: renderGuilds }, "← All servers"),
    h("h1", { style: "margin-top: 14px" }, state.guild.name),
    h("nav", { class: "tabs" }, TABS.map(([id, label]) => h("button", {
      class: id === state.tab ? "active" : "",
      onclick: () => { state.tab = id; renderGuild(); },
    }, label))),
    body);
  const tab = TABS.find(([id]) => id === state.tab);
  run(() => tab[2](body));
}

// --------------------------------------------------------------------- tabs

async function tabXp(body) {
  const [xp, voice] = await Promise.all([api("GET", guildPath("/xp")), api("GET", guildPath("/voice-requirements"))]);
  const number = (key, label, min, max) => h("label", { class: "field" }, label,
    h("input", { type: "number", name: key, min, max, value: xp[key], required: true }));
  const xpForm = h("form", { class: "card", onsubmit: (event) => {
    event.preventDefault();
    const values = {};
    for (const input of xpForm.querySelectorAll("input")) values[input.name] = Number(input.value);
    run(() => api("PUT", guildPath("/xp"), values), "XP settings saved");
  } },
    h("h2", {}, "XP amounts"),
    h("p", { class: "hint" }, "How much XP members earn. Each grant is a random amount between minimum and maximum."),
    h("div", { class: "grid" },
      number("message_xp_min", "Message XP, minimum", 1, 1000), number("message_xp_max", "Message XP, maximum", 1, 1000),
      number("message_cooldown", "Seconds between message XP", 0, 3600),
      number("voice_xp_min", "Voice XP, minimum", 1, 1000), number("voice_xp_max", "Voice XP, maximum", 1, 1000),
      number("voice_interval", "Seconds between voice XP", 60, 3600)),
    h("button", { class: "primary" }, "Save"));

  const labels = {
    require_non_afk: "Not in the AFK channel", require_non_deaf: "Not deafened",
    require_non_muted: "Not muted", require_others_in_channel: "At least one other member in the channel",
  };
  const voiceForm = h("form", { class: "card", onsubmit: (event) => {
    event.preventDefault();
    const values = {};
    for (const input of voiceForm.querySelectorAll("input")) values[input.name] = input.checked;
    run(() => api("PUT", guildPath("/voice-requirements"), values), "Voice requirements saved");
  } },
    h("h2", {}, "Voice XP requirements"),
    h("p", { class: "hint" }, "Members only earn voice XP while all checked conditions are met."),
    Object.keys(labels).map((key) => h("label", { class: "check" },
      h("input", { type: "checkbox", name: key, checked: voice[key] }), labels[key])),
    h("button", { class: "primary", style: "margin-top: 10px" }, "Save"));
  show(body, xpForm, voiceForm);
}

async function tabMultipliers(body) {
  const draw = (data) => {
    const section = (kind, title, hint, nameOf, picker) => {
      const value = h("input", { type: "number", min: 0, max: 10, step: 0.05, value: 2 });
      return h("div", { class: "card" }, h("h2", {}, title), h("p", { class: "hint" }, hint),
        h("ul", { class: "list" }, data[kind].length === 0 ? h("li", { class: "muted" }, "None set") : null,
          data[kind].map((m) => h("li", {}, h("span", {}, nameOf(m.id), " — ×", m.multiplier),
            h("button", { class: "danger", onclick: async () => {
              const next = await run(() => api("DELETE", guildPath("/multipliers/" + kind + "/" + m.id)), "Removed");
              if (next) draw(next);
            } }, "Remove")))),
        h("div", { class: "row" }, picker, h("label", { class: "field" }, "Multiplier", value),
          h("button", { class: "primary", onclick: async () => {
            if (!picker.value) return toast("Choose one first.", true);
            const next = await run(() => api("PUT", guildPath("/multipliers/" + kind + "/" + picker.value),
              { multiplier: Number(value.value) }), "Saved");
            if (next) draw(next);
          } }, "Set")));
    };
    show(body, 
      section("channels", "Channel multipliers", "XP earned in a channel is multiplied by this value. 0 disables XP there.",
        channelName, channelSelect(["text", "announcement", "voice", "stage", "forum"])),
      section("roles", "Role multipliers", "Applies to members who have the role.", roleName, roleSelect(false)));
  };
  draw(await api("GET", guildPath("/multipliers")));
}

async function tabLogs(body) {
  const logs = await api("GET", guildPath("/logs"));
  const labels = { message: "Message log (edits and deletions)", voice: "Voice log", mod: "Moderation log",
    traffic: "Join / leave log", ticket: "Ticket log", say: "Say-command log", level: "Level-up announcements" };
  const pickers = {};
  for (const key of Object.keys(labels)) pickers[key] = channelSelect(["text", "announcement"], logs[key], key === "level" ? "Where the member is chatting" : "Off");
  const levelOff = h("input", { type: "checkbox", checked: logs.level_disabled });
  show(body, h("form", { class: "card", onsubmit: (event) => {
    event.preventDefault();
    const values = { level_disabled: levelOff.checked };
    for (const key of Object.keys(labels)) values[key] = pickers[key].value || null;
    if (levelOff.checked) values.level = null;
    run(() => api("PUT", guildPath("/logs"), values), "Log channels saved");
  } },
    h("h2", {}, "Log channels"), h("p", { class: "hint" }, "Where the bot posts its logs."),
    h("div", { class: "grid" }, Object.keys(labels).map((key) => h("label", { class: "field" }, labels[key], pickers[key]))),
    h("label", { class: "check" }, levelOff, "Turn level-up announcements off completely"),
    h("button", { class: "primary", style: "margin-top: 10px" }, "Save")));
}

async function tabLevelRoles(body) {
  const draw = (rows) => {
    const level = h("input", { type: "number", min: 1, max: 1000, value: 5 });
    const picker = roleSelect(true);
    show(body, h("div", { class: "card" },
      h("h2", {}, "Level roles"),
      h("p", { class: "hint" }, "Roles members receive when they reach a level. Only roles below the bot's own role can be given."),
      h("ul", { class: "list" }, rows.length === 0 ? h("li", { class: "muted" }, "None set") : null,
        rows.map((r) => h("li", {}, h("span", {}, "Level ", r.level, " → ", roleName(r.role_id)),
          h("button", { class: "danger", onclick: async () => {
            const next = await run(() => api("DELETE", guildPath("/level-roles/" + r.level)), "Removed");
            if (next) draw(next);
          } }, "Remove")))),
      h("div", { class: "row" }, h("label", { class: "field" }, "Level", level), picker,
        h("button", { class: "primary", onclick: async () => {
          if (!picker.value) return toast("Choose a role first.", true);
          const next = await run(() => api("PUT", guildPath("/level-roles/" + Number(level.value)), { role_id: picker.value }), "Saved");
          if (next) draw(next);
        } }, "Set"))));
  };
  draw(await api("GET", guildPath("/level-roles")));
}

async function tabAutoRoles(body) {
  const draw = (data) => {
    const save = async (next, message) => {
      const result = await run(() => api("PUT", guildPath("/auto-roles"), next), message);
      if (result) draw(result);
    };
    const section = (key, title) => {
      const picker = roleSelect(true);
      return h("div", {}, h("h2", { style: "margin-top: 16px" }, title),
        h("ul", { class: "list" }, data[key].length === 0 ? h("li", { class: "muted" }, "None") : null,
          data[key].map((id) => h("li", {}, roleName(id), h("button", { class: "danger",
            onclick: () => save({ ...data, [key]: data[key].filter((x) => x !== id) }, "Removed") }, "Remove")))),
        h("div", { class: "row" }, picker, h("button", { onclick: () => {
          if (!picker.value) return toast("Choose a role first.", true);
          save({ ...data, [key]: [...data[key], picker.value] }, "Added");
        } }, "Add")));
    };
    show(body, h("div", { class: "card" },
      h("h2", {}, "Auto roles"), h("p", { class: "hint" }, "Roles given automatically when someone joins the server."),
      h("label", { class: "check" }, h("input", { type: "checkbox", checked: data.enabled,
        onchange: (event) => save({ ...data, enabled: event.target.checked }, event.target.checked ? "Auto roles on" : "Auto roles off") }),
        "Auto roles enabled"),
      section("user_role_ids", "For new members"), section("bot_role_ids", "For new bots")));
  };
  draw(await api("GET", guildPath("/auto-roles")));
}

async function tabLeaderboard(body) {
  const data = await api("GET", guildPath("/leaderboard?limit=50"));
  show(body, h("div", { class: "card" },
    h("h2", {}, "Leaderboard"), h("p", { class: "hint" }, data.total + (data.total === 1 ? " member has" : " members have") + " earned XP. Recent XP can take a minute to appear."),
    data.entries.length === 0 ? h("p", { class: "muted" }, "Nobody has earned XP yet.") : h("table", {},
      h("thead", {}, h("tr", {}, h("th", {}, "#"), h("th", {}, "Member"), h("th", { class: "num" }, "Level"), h("th", { class: "num" }, "XP"))),
      h("tbody", {}, data.entries.map((e) => h("tr", {}, h("td", {}, e.rank), h("td", {}, e.username || e.user_id),
        h("td", { class: "num" }, e.level), h("td", { class: "num" }, e.xp.toLocaleString())))))));
}

// --------------------------------------------------------------------- start

(async function start() {
  try {
    state.me = await api("GET", "api/me");
  } catch (error) {
    return; // the login screen is already showing
  }
  renderUser();
  const data = await run(() => api("GET", "api/guilds"));
  if (!data) return;
  state.guilds = data.guilds;
  state.invite = data.invite_url;
  renderGuilds();
})();
