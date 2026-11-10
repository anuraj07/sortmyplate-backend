let currentToken = "";
let currentUser = null;
let currentGroup = null;
let activeMemberIds = [];

const API_BASE = "/v1";

document.addEventListener("DOMContentLoaded", async () => {
  // Auto-login as pre-seeded Dummy User (Alex Demo) on first load
  await loginAsAlexDemo();
  await checkLlmStatus();
  setupEventListeners();
});

async function checkLlmStatus() {
  try {
    const res = await fetch("/health/llm-status");
    if (res.ok) {
      const data = await res.json();
      const el = document.getElementById("llm-model-name");
      if (data.provider === "deepseek") {
        el.textContent = `DeepSeek-V3 (${data.status})`;
      } else if (data.provider === "claude") {
        el.textContent = `Claude 3.5 (${data.status})`;
      } else if (data.provider === "openai") {
        el.textContent = `OpenAI GPT-4o (${data.status})`;
      } else if (data.provider === "ollama") {
        el.textContent = `Local Ollama (${data.status})`;
      } else {
        el.textContent = `Clinical AI (${data.latency_ms || 2}ms)`;
      }
    }
  } catch (err) {
    console.error("LLM status check error:", err);
  }
}

function setupEventListeners() {
  document.getElementById("btn-next-meal").addEventListener("click", getNextMeal);
  document.getElementById("btn-switch-user").addEventListener("click", loginAsAlexDemo);
  
  // PDF upload
  const fileInput = document.getElementById("pdf-input");
  fileInput.addEventListener("change", uploadPdfReport);
}

async function loginAsAlexDemo() {
  try {
    const res = await fetch(`${API_BASE}/auth/google/dev-login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email: "alex.demo@gmail.com",
        full_name: "Alex Demo"
      })
    });
    
    if (!res.ok) throw new Error("Login failed");
    const data = await res.json();
    currentToken = data.access_token;
    currentUser = data;

    updateUserUI();
    await loadBiomarkers();
    await loadGroups();
  } catch (err) {
    console.error("Auth error:", err);
  }
}

function updateUserUI() {
  document.getElementById("user-name").textContent = currentUser.full_name;
  document.getElementById("user-email").textContent = currentUser.email;
  document.getElementById("subject-token-display").textContent = currentUser.subject_token;
  if (currentUser.picture_url) {
    document.getElementById("user-avatar").src = currentUser.picture_url;
  }
}

async function loadBiomarkers() {
  try {
    const res = await fetch(`${API_BASE}/health/biomarkers/latest`, {
      headers: { "Authorization": `Bearer ${currentToken}` }
    });
    if (!res.ok) return;
    const panel = await res.json();
    
    const tbody = document.getElementById("biomarkers-tbody");
    tbody.innerHTML = "";

    const labInfo = document.getElementById("lab-provider-info");
    labInfo.textContent = `${panel.lab_provider} • Tested ${new Date(panel.report_date).toLocaleDateString()}`;

    for (const [code, obs] of Object.entries(panel.observations)) {
      const tr = document.createElement("tr");
      
      let badgeClass = "badge-normal";
      if (obs.status === "HIGH" || obs.status === "CRITICAL_HIGH") badgeClass = "badge-high";
      if (obs.status === "LOW" || obs.status === "CRITICAL_LOW") badgeClass = "badge-low";

      tr.innerHTML = `
        <td><strong>${obs.display_name}</strong><br><small style="color: var(--text-muted)">LOINC: ${obs.loinc_code || code}</small></td>
        <td><strong>${obs.numeric_value}</strong> ${obs.unit}</td>
        <td><span class="badge ${badgeClass}">${obs.status}</span></td>
      `;
      tbody.appendChild(tr);
    }
  } catch (err) {
    console.error("Biomarker load error:", err);
  }
}

async function loadGroups() {
  try {
    const res = await fetch(`${API_BASE}/groups/my`, {
      headers: { "Authorization": `Bearer ${currentToken}` }
    });
    if (!res.ok) return;
    const groups = await res.json();
    if (groups.length === 0) return;

    currentGroup = groups[0];
    document.getElementById("group-name").textContent = currentGroup.name;
    document.getElementById("group-invite-code").textContent = currentGroup.invite_code;

    const listEl = document.getElementById("member-list");
    listEl.innerHTML = "";
    
    // Default all members as active
    activeMemberIds = currentGroup.members.map(m => m.id);

    currentGroup.members.forEach(member => {
      const isYou = member.id === currentUser.user_id;
      const item = document.createElement("div");
      item.className = "member-item active";
      item.id = `member-card-${member.id}`;

      let allergyBadge = "";
      if (member.allergies && member.allergies.length > 0) {
        allergyBadge = `<span style="color: var(--accent-rose); font-size: 11px; font-weight: 600;">(Allergic to ${member.allergies.join(", ")})</span>`;
      }

      item.innerHTML = `
        <div class="member-info">
          <img src="${member.picture_url || 'https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=100'}" alt="${member.full_name}">
          <div class="member-meta">
            <h4>${member.full_name} ${isYou ? '<span style="color: var(--accent-cyan); font-size: 11px;">(You)</span>' : ''}</h4>
            <p>${member.email} ${allergyBadge}</p>
          </div>
        </div>
        <input type="checkbox" class="checkbox-custom" checked data-user-id="${member.id}">
      `;

      const checkbox = item.querySelector("input");
      checkbox.addEventListener("change", (e) => {
        if (e.target.checked) {
          if (!activeMemberIds.includes(member.id)) activeMemberIds.push(member.id);
          item.classList.add("active");
        } else {
          activeMemberIds = activeMemberIds.filter(id => id !== member.id);
          item.classList.remove("active");
        }
      });

      listEl.appendChild(item);
    });
  } catch (err) {
    console.error("Group load error:", err);
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
    const res = await fetch(`${API_BASE}/health/biomarkers/upload-pdf`, {
      method: "POST",
      headers: { "Authorization": `Bearer ${currentToken}` },
      body: formData
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Upload failed");
    }

    statusText.textContent = `✓ Successfully parsed & encrypted report!`;
    await loadBiomarkers();
  } catch (err) {
    statusText.textContent = `⚠️ Error: ${err.message}`;
  }
}

async function getNextMeal() {
  const btn = document.getElementById("btn-next-meal");
  const originalText = btn.innerHTML;
  btn.innerHTML = `<span class="spinner"></span> Consulting Biomarkers...`;
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

    const res = await fetch(`${API_BASE}/meals/next`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${currentToken}`
      },
      body: JSON.stringify(payload)
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Failed to generate meal");
    }

    const data = await res.json();
    renderMealResult(data);
  } catch (err) {
    alert(`Error: ${err.message}`);
  } finally {
    btn.innerHTML = originalText;
    btn.disabled = false;
  }
}

function renderMealResult(data) {
  const container = document.getElementById("meal-result-container");
  container.classList.add("show");

  document.getElementById("meal-title-text").textContent = data.title;
  document.getElementById("meal-desc-text").textContent = data.description;
  document.getElementById("meal-prep-badge").textContent = `⏱️ ${data.prep_time_minutes} mins prep`;

  // Macros
  document.getElementById("macro-calories").textContent = `${data.macros_per_serving.calories} kcal`;
  document.getElementById("macro-protein").textContent = `${data.macros_per_serving.protein_g}g`;
  document.getElementById("macro-fiber").textContent = `${data.macros_per_serving.fiber_g}g`;
  document.getElementById("macro-gl").textContent = data.macros_per_serving.glycemic_load;

  // Allergens
  const allergenBanner = document.getElementById("allergen-safeguard-banner");
  if (data.allergens_strictly_avoided && data.allergens_strictly_avoided.length > 0) {
    allergenBanner.style.display = "flex";
    allergenBanner.innerHTML = `🛡️ <strong>Safety Safeguard:</strong> Strictly avoided allergens: ${data.allergens_strictly_avoided.join(", ")}`;
  } else {
    allergenBanner.style.display = "none";
  }

  // Consensus Summary
  document.getElementById("consensus-summary-text").textContent = data.overall_consensus_reasoning;

  // Ingredients list
  const ingList = document.getElementById("ingredients-list");
  ingList.innerHTML = data.shared_base_ingredients
    .map(i => `<li><strong>${i.name}</strong> — ${i.amount} ${i.unit}</li>`)
    .join("");

  // Clinical Reasoning per Member
  const rationalesContainer = document.getElementById("clinical-rationales-container");
  rationalesContainer.innerHTML = "";

  data.member_customizations.forEach(item => {
    const card = document.createElement("div");
    card.className = "clinical-card";
    card.innerHTML = `
      <h4>
        <span>👤 ${item.member_name}</span>
        <span style="font-size: 11px; color: var(--accent-emerald);">🎯 Target: ${item.targeted_biomarkers.join(", ")}</span>
      </h4>
      <p><strong>Clinical Mechanism:</strong> ${item.mechanism}</p>
      <div class="topping-badge">✨ Custom Finishing Topping: ${item.suggested_custom_finish}</div>
    `;
    rationalesContainer.appendChild(card);
  });

  // Scroll smoothly to the meal result
  container.scrollIntoView({ behavior: "smooth", block: "start" });
}
