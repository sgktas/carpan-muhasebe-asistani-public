const $ = (id) => document.getElementById(id);
const loginView = $("login-view"), dashboardView = $("dashboard-view");
let accessToken = sessionStorage.getItem("carpan_admin_access") || "";
let currentRole = sessionStorage.getItem("carpan_admin_role") || "";

function authHeaders() { return { Authorization: `Bearer ${accessToken}` }; }
function text(value, fallback = "—") { return value === null || value === undefined || value === "" ? fallback : String(value); }
function statusLabel(value) { return text(value).replaceAll("_", " "); }

async function api(path) {
  const response = await fetch(path, { headers: authHeaders() });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || "Merkezi servis yanıt vermedi.");
  }
  return response.json();
}

function renderRows(target, rows, render, emptyText) {
  const node = $(target); node.innerHTML = "";
  if (!rows.length) { node.className = "list empty"; node.textContent = emptyText; return; }
  node.className = "list"; rows.forEach((row) => node.appendChild(render(row)));
}

function row(title, subtitle, state, muted = false) {
  const item = document.createElement("div"); item.className = "row";
  const copy = document.createElement("div"), titleNode = document.createElement("strong"), subNode = document.createElement("small");
  titleNode.textContent = title; subNode.textContent = subtitle; copy.append(titleNode, subNode);
  const pill = document.createElement("span"); pill.className = `state${muted ? " muted" : ""}`; pill.textContent = state;
  item.append(copy, pill); return item;
}

async function loadDashboard() {
  $("dashboard-error").textContent = "";
  try {
    const [overview, team, devices] = await Promise.all([api("/v1/management/overview"), api("/v1/management/team"), api("/v1/management/devices")]);
    $("company-name").textContent = overview.company.name;
    $("role-label").textContent = currentRole || "YÖNETİCİ";
    $("user-count").textContent = text(overview.users.active_count, "0");
    $("role-counts").textContent = Object.entries(overview.users.roles).map(([role,count]) => `${statusLabel(role)} ${count}`).join(" · ") || "Rol kaydı yok";
    $("device-count").textContent = text(overview.devices.active_count, "0");
    $("revoked-count").textContent = overview.devices.revoked_count ? `${overview.devices.revoked_count} iptal edilmiş` : "İptal edilmiş cihaz yok";
    $("license-plan").textContent = overview.license.plan_code || "Tanımlı değil";
    $("license-status").textContent = overview.license.status ? statusLabel(overview.license.status) : "Lisans henüz tanımlanmadı";
    $("team-total").textContent = team.members.length;
    $("device-total").textContent = devices.devices.length;
    renderRows("team-list", team.members, (member) => row(member.display_name, `${member.username} · ${statusLabel(member.role)}`, member.active ? "ETKİN" : "PASİF", !member.active), "Ekip kullanıcısı yok.");
    renderRows("device-list", devices.devices, (device) => row(device.label || "Adsız kurulum", device.assigned_username, statusLabel(device.status), device.status !== "ACTIVE"), "Cihaz kaydı yok.");
  } catch (error) {
    $("dashboard-error").textContent = error.message;
  }
}

async function signIn(event) {
  event.preventDefault();
  const button = $("login-button"), error = $("login-error"); error.textContent = ""; button.disabled = true;
  try {
    const response = await fetch("/v1/auth/login", { method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({company_code:$("company-code").value.trim(), username:$("username").value.trim(), password:$("password").value}) });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(payload.detail || "Giriş yapılamadı.");
    accessToken = payload.access_token; currentRole = payload.role;
    sessionStorage.setItem("carpan_admin_access", accessToken); sessionStorage.setItem("carpan_admin_role", currentRole);
    $("password").value = ""; loginView.classList.add("hidden"); dashboardView.classList.remove("hidden"); await loadDashboard();
  } catch (err) { error.textContent = err.message; } finally { button.disabled = false; }
}

$("login-form").addEventListener("submit", signIn);
$("logout-button").addEventListener("click", () => { sessionStorage.removeItem("carpan_admin_access"); sessionStorage.removeItem("carpan_admin_role"); accessToken = ""; dashboardView.classList.add("hidden"); loginView.classList.remove("hidden"); });
if (accessToken) { loginView.classList.add("hidden"); dashboardView.classList.remove("hidden"); loadDashboard(); }
