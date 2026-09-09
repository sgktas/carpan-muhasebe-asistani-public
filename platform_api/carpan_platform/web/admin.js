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

function teamRow(member) {
  const item = row(member.display_name, `${member.username} · ${statusLabel(member.role)}`, member.active ? "ETKİN" : "PASİF", !member.active);
  const actions = document.createElement("div"); actions.className = "member-actions";
  const select = document.createElement("select"); ["ADMIN","OPERATOR","APPROVER","AUDITOR"].forEach((role) => { const option=document.createElement("option"); option.value=role; option.textContent=statusLabel(role); option.selected=role===member.role; select.appendChild(option); });
  const save = document.createElement("button"); save.type="button"; save.textContent="Rolü kaydet";
  const toggle = document.createElement("button"); toggle.type="button"; toggle.textContent=member.active ? "Pasife al" : "Etkinleştir";
  const update = async (payload) => { save.disabled=toggle.disabled=true; try { const response=await fetch(`/v1/management/team/${encodeURIComponent(member.username)}`,{method:"PATCH",headers:{...authHeaders(),"Content-Type":"application/json"},body:JSON.stringify(payload)}); if(!response.ok){const body=await response.json();throw new Error(body.detail||"Kullanıcı güncellenemedi.");} await loadDashboard(); } catch(error){$("dashboard-error").textContent=error.message;} finally {save.disabled=toggle.disabled=false;} };
  save.addEventListener("click",()=>update({role:select.value})); toggle.addEventListener("click",()=>update({active:!member.active})); actions.append(select,save,toggle); item.firstChild.append(actions); return item;
}

function deviceRow(device) {
  const item = row(device.label || "Adsız kurulum", device.assigned_username, statusLabel(device.status), device.status !== "ACTIVE");
  if (device.status !== "ACTIVE") return item;
  const actions = document.createElement("div"); actions.className = "device-actions";
  const revoke = document.createElement("button"); revoke.type="button"; revoke.textContent="Cihazı iptal et";
  revoke.addEventListener("click", async () => {
    if (!confirm("Bu cihazın merkezi oturumlarını iptal etmek istiyor musunuz? Cihaz yeniden giriş yaparak tekrar etkinleşebilir.")) return;
    revoke.disabled=true;
    try {
      const response=await fetch("/v1/management/devices/revoke", {method:"POST",headers:{...authHeaders(),"Content-Type":"application/json"},body:JSON.stringify({assigned_username:device.assigned_username,device_label:device.label || null})});
      if(!response.ok){const body=await response.json();throw new Error(body.detail||"Cihaz iptal edilemedi.");}
      await loadDashboard();
    } catch(error) { $("dashboard-error").textContent=error.message; } finally { revoke.disabled=false; }
  });
  actions.append(revoke); item.firstChild.append(actions); return item;
}

function auditRow(event) {
  const when = event.created_at ? new Date(event.created_at).toLocaleString("tr-TR") : "Zaman bilgisi yok";
  const actor = event.actor_display_name || "Sistem";
  return row(statusLabel(event.event_type), `${actor} · ${when}`, statusLabel(event.outcome), event.outcome !== "SUCCESS");
}

async function loadDashboard() {
  $("dashboard-error").textContent = "";
  try {
    const [overview, team, devices, audits] = await Promise.all([api("/v1/management/overview"), api("/v1/management/team"), api("/v1/management/devices"), api("/v1/management/audit-events")]);
    $("company-name").textContent = overview.company.name;
    $("role-label").textContent = currentRole || "YÖNETİCİ";
    $("user-count").textContent = text(overview.users.active_count, "0");
    $("role-counts").textContent = Object.entries(overview.users.roles).map(([role,count]) => `${statusLabel(role)} ${count}`).join(" · ") || "Rol kaydı yok";
    $("device-count").textContent = text(overview.devices.active_count, "0");
    $("revoked-count").textContent = overview.devices.revoked_count ? `${overview.devices.revoked_count} iptal edilmiş` : "İptal edilmiş cihaz yok";
    $("license-plan").textContent = overview.license.plan_code || "Tanımlı değil";
    if (overview.license.status) {
      const policy = overview.license.enforcement_required
        ? `Merkezi kontrol · çevrimdışı ${overview.license.offline_grace_hours} saat`
        : "Yerel çalışma korunuyor";
      $("license-status").textContent = `${statusLabel(overview.license.status)} · ${policy}`;
    } else {
      $("license-status").textContent = "Lisans henüz tanımlanmadı";
    }
    $("team-total").textContent = team.members.length;
    $("device-total").textContent = devices.devices.length;
    $("audit-total").textContent = audits.events.length;
    renderRows("team-list", team.members, teamRow, "Ekip kullanıcısı yok.");
    renderRows("device-list", devices.devices, deviceRow, "Cihaz kaydı yok.");
    renderRows("audit-list", audits.events, auditRow, "Henüz yönetim kaydı yok.");
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
$("invite-toggle").addEventListener("click", () => $("invite-form").classList.toggle("hidden"));
$("invite-form").addEventListener("submit", async (event) => {
  event.preventDefault(); const error=$("invite-create-error"), output=$("invite-link"); error.textContent=""; output.textContent="";
  try { const response=await fetch("/v1/management/invitations",{method:"POST",headers:{...authHeaders(),"Content-Type":"application/json"},body:JSON.stringify({username:$("invite-username").value.trim(),display_name:$("invite-name").value.trim(),role:$("invite-role").value})}); const payload=await response.json(); if(!response.ok) throw new Error(payload.detail||"Davet oluşturulamadı."); output.textContent=`Davet bağlantısı (bir kez kopyalayın): ${location.origin}/invite?token=${payload.invite_token}`; } catch(errorValue) { error.textContent=errorValue.message; }
});
if (accessToken) { loginView.classList.add("hidden"); dashboardView.classList.remove("hidden"); loadDashboard(); }
