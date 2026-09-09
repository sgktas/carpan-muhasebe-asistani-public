const $ = (id) => document.getElementById(id);
const loginView = $("login-view"), dashboardView = $("dashboard-view");
let accessToken = sessionStorage.getItem("carpan_platform_owner_access") || "";
let operatorName = sessionStorage.getItem("carpan_platform_owner_name") || "";

function headers() { return { Authorization: `Bearer ${accessToken}` }; }
function text(value, fallback = "—") { return value === null || value === undefined || value === "" ? fallback : String(value); }
function status(value) { return text(value, "Tanımlı değil").replaceAll("_", " "); }

async function request(path) {
  const response = await fetch(path, { headers: headers() });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.detail || "Platform servisi yanıt vermedi.");
  return payload;
}

function companyRow(company) {
  const row = document.createElement("div"); row.className = "row platform-company-row";
  const copy = document.createElement("div"), title = document.createElement("strong"), subtitle = document.createElement("small");
  title.textContent = company.name;
  subtitle.textContent = `${company.code} · Lisans: ${status(company.license.plan_code)} / ${status(company.license.status)} · ${company.devices.active_count} etkin cihaz`;
  copy.append(title, subtitle);
  const state = document.createElement("span"); state.className = `state${company.status !== "ACTIVE" ? " muted" : ""}`; state.textContent = status(company.status);
  row.append(copy, state); return row;
}

function renderCompanies(companies) {
  const target = $("company-list"); target.innerHTML = ""; $("company-list-total").textContent = companies.length;
  if (!companies.length) { target.className = "list empty"; target.textContent = "Henüz firma kaydı yok."; return; }
  target.className = "list"; companies.forEach((company) => target.appendChild(companyRow(company)));
}

async function loadDashboard() {
  $("dashboard-error").textContent = "";
  try {
    const overview = await request("/v1/platform/overview");
    $("operator-name").textContent = operatorName || "PLATFORM SAHİBİ";
    $("company-count").textContent = text(overview.companies.total_count, "0");
    $("active-company-count").textContent = `${text(overview.companies.active_count, "0")} etkin firma`;
    $("device-count").textContent = text(overview.devices.active_count, "0");
    renderCompanies(overview.companies.items || []);
  } catch (error) {
    $("dashboard-error").textContent = error.message;
    if (error.message.includes("Platform oturumu") || error.message.includes("Platform erişimi")) signOut();
  }
}

async function signIn(event) {
  event.preventDefault(); const button = $("login-button"), error = $("login-error"); error.textContent = ""; button.disabled = true;
  try {
    const response = await fetch("/v1/platform/auth/login", { method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({username:$("username").value.trim(), password:$("password").value}) });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(payload.detail || "Giriş yapılamadı.");
    accessToken = payload.access_token; operatorName = payload.display_name;
    sessionStorage.setItem("carpan_platform_owner_access", accessToken); sessionStorage.setItem("carpan_platform_owner_name", operatorName);
    $("password").value = ""; loginView.classList.add("hidden"); dashboardView.classList.remove("hidden"); await loadDashboard();
  } catch (value) { error.textContent = value.message; } finally { button.disabled = false; }
}

function signOut() {
  sessionStorage.removeItem("carpan_platform_owner_access"); sessionStorage.removeItem("carpan_platform_owner_name"); accessToken = ""; operatorName = "";
  dashboardView.classList.add("hidden"); loginView.classList.remove("hidden");
}

$("login-form").addEventListener("submit", signIn);
$("logout-button").addEventListener("click", signOut);
if (accessToken) { loginView.classList.add("hidden"); dashboardView.classList.remove("hidden"); loadDashboard(); }
