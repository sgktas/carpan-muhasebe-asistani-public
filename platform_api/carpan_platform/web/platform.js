const $ = (id) => document.getElementById(id);
const loginView = $("login-view"), dashboardView = $("dashboard-view");
let accessToken = sessionStorage.getItem("carpan_platform_owner_access") || "";
let operatorName = sessionStorage.getItem("carpan_platform_owner_name") || "";
let companiesByCode = new Map();
const modules = {
  manim_transfer: "MANİM Aktarma", report_editing: "FOM Rapor Düzenleme",
  bank_reconciliation: "Banka Mutabakatı", cari_reconciliation: "Cari Mutabakat",
  customer_list_import: "Müşteri Listesi",
};

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

function renderModuleChoices(targetId) {
  const target = $(targetId); target.innerHTML = "";
  Object.entries(modules).forEach(([id, label]) => {
    const choice = document.createElement("label"), input = document.createElement("input"), text = document.createElement("span");
    input.type = "checkbox"; input.value = id; input.checked = true; text.textContent = label;
    choice.append(input, text); target.append(choice);
  });
}

function selectedModules(targetId) { return [...$(targetId).querySelectorAll("input:checked")].map((input) => input.value); }

function setModules(targetId, enabled) {
  const values = new Set(enabled || []);
  $(targetId).querySelectorAll("input").forEach((input) => { input.checked = values.has(input.value); });
}

function selectLicenseCompany(code) {
  const company = companiesByCode.get(code); if (!company) return;
  const license = company.license || {};
  $("license-plan-code").value = license.plan_code || "TRIAL";
  $("license-status").value = license.status || "TRIAL";
  $("license-enforce").checked = Boolean(license.enforcement_required);
  $("license-grace-hours").value = license.offline_grace_hours ?? 168;
  setModules("license-modules", license.enabled_modules || []);
}

function renderCompanies(companies) {
  const target = $("company-list"); target.innerHTML = ""; $("company-list-total").textContent = companies.length;
  companiesByCode = new Map(companies.map((company) => [company.code, company]));
  const companySelect = $("license-company"); companySelect.innerHTML = "";
  companies.forEach((company) => { const option = document.createElement("option"); option.value = company.code; option.textContent = `${company.name} (${company.code})`; companySelect.append(option); });
  if (companies.length) selectLicenseCompany(companySelect.value);
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
renderModuleChoices("new-modules"); renderModuleChoices("license-modules");
$("license-company").addEventListener("change", (event) => selectLicenseCompany(event.target.value));
$("company-form").addEventListener("submit", async (event) => {
  event.preventDefault(); const error = $("company-create-error"), output = $("company-invite-link"); error.textContent = ""; output.textContent = "";
  try {
    const response = await fetch("/v1/platform/companies", {method:"POST",headers:{...headers(),"Content-Type":"application/json"},body:JSON.stringify({
      code:$("new-company-code").value.trim(), name:$("new-company-name").value.trim(), admin_username:$("new-admin-username").value.trim(), admin_display_name:$("new-admin-name").value.trim(),
      plan_code:$("new-plan-code").value.trim(), license_status:$("new-license-status").value, module_ids:selectedModules("new-modules"), enforce_central:false, offline_grace_hours:168,
    })});
    const payload = await response.json().catch(() => ({})); if (!response.ok) throw new Error(payload.detail || "Firma kurulamadı.");
    output.textContent = `İlk yönetici daveti (bir kez kopyalayın): ${location.origin}/invite?token=${payload.initial_admin_invitation.token}`;
    $("company-form").reset(); renderModuleChoices("new-modules"); await loadDashboard();
  } catch (value) { error.textContent = value.message; }
});
$("license-form").addEventListener("submit", async (event) => {
  event.preventDefault(); const error = $("license-update-error"); error.textContent = ""; const code = $("license-company").value;
  try {
    const response = await fetch(`/v1/platform/companies/${encodeURIComponent(code)}/license`, {method:"PUT",headers:{...headers(),"Content-Type":"application/json"},body:JSON.stringify({
      plan_code:$("license-plan-code").value.trim(), license_status:$("license-status").value, module_ids:selectedModules("license-modules"), enforce_central:$("license-enforce").checked, offline_grace_hours:Number($("license-grace-hours").value),
    })});
    if (!response.ok) { const payload = await response.json().catch(() => ({})); throw new Error(payload.detail || "Lisans güncellenemedi."); }
    await loadDashboard();
  } catch (value) { error.textContent = value.message; }
});
if (accessToken) { loginView.classList.add("hidden"); dashboardView.classList.remove("hidden"); loadDashboard(); }
