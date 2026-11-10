const DEFAULT_DISCOVERY_ORIGIN = "https://j6tgemptpq36.ramnaymcloud.com";
const SESSION_ENDPOINTS_KEY = "sortmyplate_session_endpoints";
const SESSION_AUTH_KEY = "sortmyplate_session_auth";

const BIOMARKER_CATALOG = {
  APOB: {
    loinc_code: "1884-6",
    display_name: "Apolipoprotein B (ApoB)",
    category: "Lipid Panel",
    unit: "mg/dL",
    reference_interval: { low: 40, high: 90 }
  },
  LDL_C: {
    loinc_code: "2089-1",
    display_name: "LDL Cholesterol",
    category: "Lipid Panel",
    unit: "mg/dL",
    reference_interval: { low: 0, high: 100 }
  },
  HBA1C: {
    loinc_code: "4548-4",
    display_name: "Hemoglobin A1c",
    category: "Glycemic Control",
    unit: "%",
    reference_interval: { low: 4.0, high: 5.6 }
  },
  FERRITIN: {
    loinc_code: "24331-1",
    display_name: "Serum Ferritin",
    category: "Iron Status",
    unit: "ng/mL",
    reference_interval: { low: 30, high: 200 }
  },
  HS_CRP: {
    loinc_code: "30934-4",
    display_name: "High-Sensitivity CRP",
    category: "Inflammation",
    unit: "mg/L",
    reference_interval: { low: 0, high: 1.0 }
  }
};

let sessionDiscovery = null;
let currentToken = "";
let currentUser = null;
let currentGroup = null;
let currentObservations = {};
let activeMemberIds = [];

document.addEventListener("DOMContentLoaded", async () => {
  setupEventListeners();
  await discoverEndpointsForSession();

  if (sessionDiscovery) {
    await checkLlmStatus();
    await restoreSessionAuth();
  }
});

function getDiscoveryOrigin() {
  const params = new URLSearchParams(window.location.search);
  const queryApi = params.get("api");
  if (queryApi) {
    return queryApi.replace(/\/+$/, "");
  }
  if (window.location.protocol.startsWith("http")) {
    return window.location.origin.replace(/\/+$/, "");
  }
  return DEFAULT_DISCOVERY_ORIGIN;
}

async function discoverEndpointsForSession() {
  const statusEl = document.getElementById("discovery-status");
  const baseUrlEl = document.getElementById("discovery-base-url");

  const primaryOrigin = getDiscoveryOrigin();
  const candidates = primaryOrigin === DEFAULT_DISCOVERY_ORIGIN
    ? [primaryOrigin]
    : [primaryOrigin, DEFAULT_DISCOVERY_ORIGIN];

  for (const origin of candidates) {
    try {
      const res = await fetch(`${origin}/bootstrap`, {
        headers: { "Accept": "application/json" }
      });
      if (!res.ok) continue;

      const data = await res.json();
      if (!data || !data.endpoints) continue;

      let resolvedBase = (data.base_url || origin).replace(/\/+$/, "");
      if (origin.startsWith("https://") && resolvedBase.startsWith("http://")) {
        resolvedBase = origin;
      }

      sessionDiscovery = {
        base_url: resolvedBase,
        endpoints: data.endpoints,
        google_client_id: data.google_client_id || null,
        version: data.version || "1.0.0"
      };

      sessionStorage.setItem(SESSION_ENDPOINTS_KEY, JSON.stringify(sessionDiscovery));

      const count = Object.keys(sessionDiscovery.endpoints).length;
      statusEl.textContent = `Resolved ${count} endpoints for this session`;
      statusEl.style.color = "var(--accent-emerald)";
      baseUrlEl.textContent = sessionDiscovery.base_url;
      return;
    } catch (err) {
      console.warn(`Discovery attempt failed on ${origin}:`, err);
    }
  }

  // Fallback to cached session endpoints if temporarily offline
  const cached = sessionStorage.getItem(SESSION_ENDPOINTS_KEY);
  if (cached) {
    try {
      sessionDiscovery = JSON.parse(cached);
      statusEl.textContent = "Using cached session endpoints";
      statusEl.style.color = "var(--accent-amber)";
      baseUrlEl.textContent = sessionDiscovery.base_url;
      return;
    } catch (_) {
      sessionStorage.removeItem(SESSION_ENDPOINTS_KEY);
    }
  }

  statusEl.textContent = "Endpoint discovery failed";
  statusEl.style.color = "var(--accent-rose)";
  showBanner("auth-error", "Could not connect to SortMyPlate discovery service. Please try again shortly.", true);
}

function resolveEndpoint(key, params = {}) {
  if (!sessionDiscovery || !sessionDiscovery.endpoints) {
    const cached = sessionStorage.getItem(SESSION_ENDPOINTS_KEY);
    if (cached) {
      sessionDiscovery = JSON.parse(cached);
    }
  }
  if (!sessionDiscovery || !sessionDiscovery.endpoints || !sessionDiscovery.endpoints[key]) {
    throw new Error(`Endpoint '${key}' not discovered yet for this session.`);
  }

  let path = sessionDiscovery.endpoints[key];
  for (const [paramKey, paramVal] of Object.entries(params)) {
    path = path.replace(`{${paramKey}}`, encodeURIComponent(String(paramVal)));
  }

  if (path.startsWith("http://") || path.startsWith("https://")) {
    return path;
  }
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  return `${sessionDiscovery.base_url}${normalizedPath}`;
}

function setupEventListeners() {
  document.getElementById("google-auth-form").addEventListener("submit", handleGoogleSignIn);
  document.getElementById("btn-logout").addEventListener("click", handleSignOut);
  document.getElementById("btn-create-group").addEventListener("click", handleCreateGroup);
  document.getElementById("btn-join-group").addEventListener("click", handleJoinGroup);
  document.getElementById("btn-leave-group").addEventListener("click", handleLeaveGroup);
  document.getElementById("quick-biomarker-form").addEventListener("submit", handleSaveQuickBiomarker);
  document.getElementById("pdf-input").addEventListener("change", uploadPdfReport);
  document.getElementById("btn-next-meal").addEventListener("click", getNextMeal);
}

function showBanner(elementId, message, isError = false) {
  const el = document.getElementById(elementId);
  if (!el) return;
  if (!message) {
    el.textContent = "";
    el.className = isError ? "status-banner error" : "status-banner";
    return;
  }
  el.textContent = message;
  el.className = `status-banner show ${isError ? "error" : "success"}`;
}

async function checkLlmStatus() {
  const el = document.getElementById("llm-model-name");
  try {
    const url = resolveEndpoint("llm_status");
    const res = await fetch(url);
    if (!res.ok) {
      el.textContent = "Clinical AI Unavailable";
      return;
    }
    const data = await res.json();
    if (data.provider === "deepseek") {
      el.textContent = `DeepSeek-V3 (${data.status})`;
    } else if (data.provider === "claude") {
      el.textContent = `Claude 3.5 (${data.status})`;
    } else if (data.provider === "openai") {
      el.textContent = `OpenAI GPT-4o (${data.status})`;
    } else if (data.provider === "ollama") {
      el.textContent = `Local Ollama (${data.status})`;
    } else {
      el.textContent = `Clinical AI (${data.latency_ms ?? 1}ms)`;
    }
  } catch (err) {
    console.error("LLM status check error:", err);
    el.textContent = "Clinical AI Ready";
  }
}

async function restoreSessionAuth() {
  const savedAuth = sessionStorage.getItem(SESSION_AUTH_KEY);
  if (!savedAuth) {
    showAuthView();
    return;
  }

  try {
    const parsed = JSON.parse(savedAuth);
    if (!parsed.access_token) {
      showAuthView();
      return;
    }

    const res = await fetch(resolveEndpoint("auth_me"), {
      headers: { "Authorization": `Bearer ${parsed.access_token}` }
    });
    if (!res.ok) {
      sessionStorage.removeItem(SESSION_AUTH_KEY);
      showAuthView();
      return;
    }

    const userData = await res.json();
    currentToken = parsed.access_token;
    currentUser = { ...userData, access_token: currentToken };
    await enterDashboard();
  } catch (err) {
    console.warn("Session restore failed:", err);
    sessionStorage.removeItem(SESSION_AUTH_KEY);
    showAuthView();
  }
}

async function handleGoogleSignIn(e) {
  e.preventDefault();
  showBanner("auth-error", "", true);

  const email = document.getElementById("login-email").value.trim();
  const name = document.getElementById("login-name").value.trim();
  const allergiesRaw = document.getElementById("login-allergies").value;
  const allergies = allergiesRaw
    .split(",")
    .map(item => item.trim().toLowerCase())
    .filter(Boolean);

  if (!email || !name) {
    showBanner("auth-error", "Please enter both your email address and full name.", true);
    return;
  }

  const submitBtn = document.getElementById("btn-google-signin");
  submitBtn.disabled = true;

  try {
    const authUrl = resolveEndpoint("auth_google");
    const res = await fetch(authUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email,
        name,
        allergies,
        diet_preference: "omnivore"
      })
    });

    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || "Sign-In failed");
    }

    currentToken = data.access_token;
    currentUser = data;
    sessionStorage.setItem(SESSION_AUTH_KEY, JSON.stringify(data));

    await enterDashboard();
  } catch (err) {
    showBanner("auth-error", `Sign-in failed: ${err.message}`, true);
  } finally {
    submitBtn.disabled = false;
  }
}

async function enterDashboard() {
  document.getElementById("auth-section").style.display = "none";
  document.getElementById("dashboard-section").style.display = "block";
  document.getElementById("user-badge").style.display = "flex";

  document.getElementById("user-name").textContent = currentUser.full_name;
  document.getElementById("user-email").textContent = currentUser.email;
  document.getElementById("subject-token-display").textContent = currentUser.subject_token;
  document.getElementById("user-avatar").src =
    currentUser.picture_url ||
    `https://ui-avatars.com/api/?name=${encodeURIComponent(currentUser.full_name)}&background=38bdf8&color=0f172a`;

  await Promise.all([loadBiomarkers(), loadGroups()]);
}

function handleSignOut() {
  currentToken = "";
  currentUser = null;
  currentGroup = null;
  currentObservations = {};
  activeMemberIds = [];
  sessionStorage.removeItem(SESSION_AUTH_KEY);

  document.getElementById("meal-result-container").classList.remove("show");
  document.getElementById("google-auth-form").reset();
  showAuthView();
}

function showAuthView() {
  document.getElementById("auth-section").style.display = "block";
  document.getElementById("dashboard-section").style.display = "none";
  document.getElementById("user-badge").style.display = "none";
}

async function loadBiomarkers() {
  const tbody = document.getElementById("biomarkers-tbody");
  const labInfo = document.getElementById("lab-provider-info");

  try {
    const res = await fetch(resolveEndpoint("biomarkers_latest"), {
      headers: { "Authorization": `Bearer ${currentToken}` }
    });

    if (res.status === 404) {
      currentObservations = {};
      labInfo.textContent = "No report uploaded";
      renderEmptyBiomarkersTable(tbody);
      return;
    }

    if (!res.ok) return;
    const panel = await res.json();
    currentObservations = panel.observations || {};

    tbody.innerHTML = "";
    const testedDate = panel.report_date ? new Date(panel.report_date).toLocaleDateString() : "Today";
    labInfo.textContent = `${panel.lab_provider} • Tested ${testedDate}`;

    const entries = Object.entries(currentObservations);
    if (entries.length === 0) {
      renderEmptyBiomarkersTable(tbody);
      return;
    }

    for (const [code, obs] of entries) {
      const tr = document.createElement("tr");

      const nameTd = document.createElement("td");
      const strongName = document.createElement("strong");
      strongName.textContent = obs.display_name;
      const br = document.createElement("br");
      const loincSmall = document.createElement("small");
      loincSmall.style.color = "var(--text-muted)";
      loincSmall.textContent = `LOINC: ${obs.loinc_code || code}`;
      nameTd.append(strongName, br, loincSmall);

      const valTd = document.createElement("td");
      const strongVal = document.createElement("strong");
      strongVal.textContent = String(obs.numeric_value);
      valTd.append(strongVal, document.createTextNode(` ${obs.unit}`));

      const statusTd = document.createElement("td");
      const badge = document.createElement("span");
      let badgeClass = "badge-normal";
      if (obs.status === "HIGH" || obs.status === "CRITICAL_HIGH") badgeClass = "badge-high";
      if (obs.status === "LOW" || obs.status === "CRITICAL_LOW") badgeClass = "badge-low";
      badge.className = `badge ${badgeClass}`;
      badge.textContent = obs.status;
      statusTd.appendChild(badge);

      tr.append(nameTd, valTd, statusTd);
      tbody.appendChild(tr);
    }
  } catch (err) {
    console.error("Biomarker load error:", err);
  }
}

function renderEmptyBiomarkersTable(tbody) {
  tbody.innerHTML = "";
  const tr = document.createElement("tr");
  const td = document.createElement("td");
  td.colSpan = 3;
  td.style.color = "var(--text-muted)";
  td.style.textAlign = "center";
  td.style.padding = "18px";
  td.textContent = "Upload a PDF or enter biomarkers below to personalize meals.";
  tr.appendChild(td);
  tbody.appendChild(tr);
}

async function handleSaveQuickBiomarker(e) {
  e.preventDefault();
  showBanner("biomarker-status", "", false);

  const code = document.getElementById("biomarker-code").value;
  const numericValue = parseFloat(document.getElementById("biomarker-value").value);

  if (Number.isNaN(numericValue)) {
    showBanner("biomarker-status", "Please enter a valid numeric lab value.", true);
    return;
  }

  const meta = BIOMARKER_CATALOG[code] || {
    loinc_code: code,
    display_name: code,
    category: "Clinical Marker",
    unit: "unit",
    reference_interval: { low: 0, high: 100 }
  };

  const mergedMap = { ...currentObservations };
  mergedMap[code] = {
    code,
    loinc_code: meta.loinc_code,
    display_name: meta.display_name,
    category: meta.category,
    numeric_value: numericValue,
    unit: meta.unit,
    reference_interval: meta.reference_interval,
    status: "NORMAL"
  };

  try {
    const res = await fetch(resolveEndpoint("biomarkers_record"), {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${currentToken}`
      },
      body: JSON.stringify({
        lab_provider: "Manual Clinical Entry",
        observations: Object.values(mergedMap)
      })
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Failed to save biomarker");
    }

    document.getElementById("biomarker-value").value = "";
    showBanner("biomarker-status", `Saved ${meta.display_name} into AES-256 PHI Vault.`, false);
    await loadBiomarkers();
  } catch (err) {
    showBanner("biomarker-status", `Error saving biomarker: ${err.message}`, true);
  }
}

async function loadGroups() {
  try {
    const res = await fetch(resolveEndpoint("groups_my"), {
      headers: { "Authorization": `Bearer ${currentToken}` }
    });
    if (!res.ok) return;
    const groups = await res.json();

    if (!groups || groups.length === 0) {
      currentGroup = null;
      activeMemberIds = [];
      renderSoloGroupState();
      return;
    }

    renderActiveGroup(groups[0]);
  } catch (err) {
    console.error("Group load error:", err);
  }
}

function renderSoloGroupState() {
  document.getElementById("group-name").textContent = "Household / Flat Circle";
  document.getElementById("group-code-wrapper").style.display = "none";
  document.getElementById("group-invite-code").textContent = "";

  const listEl = document.getElementById("member-list");
  listEl.innerHTML = "";
  const msg = document.createElement("p");
  msg.style.fontSize = "12px";
  msg.style.color = "var(--text-muted)";
  msg.textContent = "No group joined yet — eating in Solo Mode.";
  listEl.appendChild(msg);
}

function renderActiveGroup(group) {
  currentGroup = group;
  document.getElementById("group-name").textContent = group.name;
  document.getElementById("group-invite-code").textContent = group.invite_code;
  document.getElementById("group-code-wrapper").style.display = "inline-flex";

  const listEl = document.getElementById("member-list");
  listEl.innerHTML = "";

  activeMemberIds = group.members.map(m => m.id);

  group.members.forEach(member => {
    const isYou = currentUser && member.id === currentUser.user_id;
    const item = document.createElement("div");
    item.className = "member-item active";
    item.id = `member-card-${member.id}`;

    const infoDiv = document.createElement("div");
    infoDiv.className = "member-info";

    const avatar = document.createElement("img");
    avatar.src =
      member.picture_url ||
      `https://ui-avatars.com/api/?name=${encodeURIComponent(member.full_name)}&background=1e293b&color=38bdf8`;
    avatar.alt = `${member.full_name} avatar`;

    const metaDiv = document.createElement("div");
    metaDiv.className = "member-meta";

    const nameHeading = document.createElement("h4");
    nameHeading.textContent = member.full_name;
    if (isYou) {
      const youSpan = document.createElement("span");
      youSpan.style.color = "var(--accent-cyan)";
      youSpan.style.fontSize = "11px";
      youSpan.textContent = " (You)";
      nameHeading.appendChild(youSpan);
    }

    const emailPara = document.createElement("p");
    emailPara.textContent = member.email;
    if (member.allergies && member.allergies.length > 0) {
      const allergySpan = document.createElement("span");
      allergySpan.style.color = "var(--accent-rose)";
      allergySpan.style.fontSize = "11px";
      allergySpan.style.fontWeight = "600";
      allergySpan.textContent = ` (Allergic to ${member.allergies.join(", ")})`;
      emailPara.appendChild(allergySpan);
    }

    metaDiv.append(nameHeading, emailPara);
    infoDiv.append(avatar, metaDiv);

    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.className = "checkbox-custom";
    checkbox.checked = true;
    checkbox.dataset.userId = member.id;
    checkbox.ariaLabel = `Include ${member.full_name} in next meal`;

    checkbox.addEventListener("change", (e) => {
      if (e.target.checked) {
        if (!activeMemberIds.includes(member.id)) activeMemberIds.push(member.id);
        item.classList.add("active");
      } else {
        activeMemberIds = activeMemberIds.filter(id => id !== member.id);
        item.classList.remove("active");
      }
    });

    item.append(infoDiv, checkbox);
    listEl.appendChild(item);
  });
}

async function handleCreateGroup() {
  showBanner("group-status", "", false);
  const nameInput = document.getElementById("new-group-name");
  const name = nameInput.value.trim();
  if (!name) {
    showBanner("group-status", "Enter a name for your new household or flat group.", true);
    return;
  }

  try {
    const res = await fetch(resolveEndpoint("groups_create"), {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${currentToken}`
      },
      body: JSON.stringify({ name })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Could not create group");

    nameInput.value = "";
    renderActiveGroup(data);
    showBanner("group-status", `Created '${data.name}' (Invite code: ${data.invite_code}).`, false);
  } catch (err) {
    showBanner("group-status", `Group creation failed: ${err.message}`, true);
  }
}

async function handleJoinGroup() {
  showBanner("group-status", "", false);
  const codeInput = document.getElementById("join-group-code");
  const inviteCode = codeInput.value.trim();
  if (!inviteCode) {
    showBanner("group-status", "Enter an invite code to join a group.", true);
    return;
  }

  try {
    const res = await fetch(resolveEndpoint("groups_join"), {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${currentToken}`
      },
      body: JSON.stringify({ invite_code: inviteCode })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Invalid invite code");

    codeInput.value = "";
    renderActiveGroup(data);
    showBanner("group-status", `Joined '${data.name}' successfully.`, false);
  } catch (err) {
    showBanner("group-status", `Could not join group: ${err.message}`, true);
  }
}

async function handleLeaveGroup() {
  if (!currentGroup) return;
  showBanner("group-status", "", false);

  try {
    const res = await fetch(resolveEndpoint("groups_leave", { group_id: currentGroup.id }), {
      method: "POST",
      headers: { "Authorization": `Bearer ${currentToken}` }
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Could not leave group");

    await loadGroups();
    showBanner("group-status", "Left group. Switched back to Solo Mode.", false);
  } catch (err) {
    showBanner("group-status", `Leave group failed: ${err.message}`, true);
  }
}

async function uploadPdfReport(e) {
  const file = e.target.files[0];
  if (!file) return;

  const statusText = document.getElementById("upload-status");
  statusText.textContent = `Parsing & Encrypting ${file.name}...`;

  const formData = new FormData();
  formData.append("file", file);

  try {
    const res = await fetch(resolveEndpoint("biomarkers_upload_pdf"), {
      method: "POST",
      headers: { "Authorization": `Bearer ${currentToken}` },
      body: formData
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Upload failed");
    }

    statusText.textContent = "✓ Successfully parsed & encrypted report!";
    await loadBiomarkers();
  } catch (err) {
    statusText.textContent = `⚠️ Error: ${err.message}`;
  } finally {
    e.target.value = "";
  }
}

async function getNextMeal() {
  showBanner("meal-error", "", true);
  const btn = document.getElementById("btn-next-meal");
  const originalNodes = Array.from(btn.childNodes).map(n => n.cloneNode(true));
  btn.textContent = "";
  const spinner = document.createElement("span");
  spinner.className = "spinner";
  btn.append(spinner, document.createTextNode(" Consulting Biomarkers..."));
  btn.disabled = true;

  const mealSlot = document.getElementById("meal-slot-select").value;

  try {
    const payload = {
      meal_slot: mealSlot,
      max_prep_time_minutes: 35
    };

    if (currentGroup && activeMemberIds.length > 0) {
      payload.active_member_ids = activeMemberIds;
      payload.group_id = currentGroup.id;
    }

    const res = await fetch(resolveEndpoint("meals_next"), {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${currentToken}`
      },
      body: JSON.stringify(payload)
    });

    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || "Failed to generate meal");
    }

    renderMealResult(data);
  } catch (err) {
    showBanner("meal-error", `Meal generation failed: ${err.message}`, true);
  } finally {
    btn.textContent = "";
    originalNodes.forEach(n => btn.appendChild(n));
    btn.disabled = false;
  }
}

function renderMealResult(data) {
  const container = document.getElementById("meal-result-container");
  container.classList.add("show");

  document.getElementById("meal-title-text").textContent = data.title;
  document.getElementById("meal-desc-text").textContent = data.description;
  document.getElementById("meal-prep-badge").textContent = `⏱️ ${data.prep_time_minutes} mins prep`;

  document.getElementById("macro-calories").textContent = `${data.macros_per_serving.calories} kcal`;
  document.getElementById("macro-protein").textContent = `${data.macros_per_serving.protein_g}g`;
  document.getElementById("macro-fiber").textContent = `${data.macros_per_serving.fiber_g}g`;
  document.getElementById("macro-gl").textContent = String(data.macros_per_serving.glycemic_load);

  const allergenBanner = document.getElementById("allergen-safeguard-banner");
  allergenBanner.textContent = "";
  if (data.allergens_strictly_avoided && data.allergens_strictly_avoided.length > 0) {
    allergenBanner.style.display = "flex";
    const strongLabel = document.createElement("strong");
    strongLabel.textContent = "Safety Safeguard:";
    allergenBanner.append(
      document.createTextNode("🛡️ "),
      strongLabel,
      document.createTextNode(` Strictly avoided allergens: ${data.allergens_strictly_avoided.join(", ")}`)
    );
  } else {
    allergenBanner.style.display = "none";
  }

  document.getElementById("consensus-summary-text").textContent = data.overall_consensus_reasoning;

  const ingList = document.getElementById("ingredients-list");
  ingList.innerHTML = "";
  (data.shared_base_ingredients || []).forEach(i => {
    const li = document.createElement("li");
    const strong = document.createElement("strong");
    strong.textContent = i.name;
    li.append(strong, document.createTextNode(` — ${i.amount} ${i.unit}`));
    ingList.appendChild(li);
  });

  const rationalesContainer = document.getElementById("clinical-rationales-container");
  rationalesContainer.innerHTML = "";

  (data.member_customizations || []).forEach(item => {
    const card = document.createElement("div");
    card.className = "clinical-card";

    const h4 = document.createElement("h4");
    const nameSpan = document.createElement("span");
    nameSpan.textContent = `👤 ${item.member_name}`;
    const targetSpan = document.createElement("span");
    targetSpan.style.fontSize = "11px";
    targetSpan.style.color = "var(--accent-emerald)";
    targetSpan.textContent = `🎯 Target: ${(item.targeted_biomarkers || []).join(", ")}`;
    h4.append(nameSpan, targetSpan);

    const p = document.createElement("p");
    const strongMech = document.createElement("strong");
    strongMech.textContent = "Clinical Mechanism: ";
    p.append(strongMech, document.createTextNode(item.mechanism));

    card.append(h4, p);

    if (item.suggested_custom_finish) {
      const badge = document.createElement("div");
      badge.className = "topping-badge";
      badge.textContent = `✨ Custom Finishing Topping: ${item.suggested_custom_finish}`;
      card.appendChild(badge);
    }

    rationalesContainer.appendChild(card);
  });

  container.scrollIntoView({ behavior: "smooth", block: "start" });
}
