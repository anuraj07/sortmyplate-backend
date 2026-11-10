const DEFAULT_DISCOVERY_ORIGIN = "https://j6tgemptpq36.ramnaymcloud.com";
const SESSION_ENDPOINTS_KEY = "sortmyplate_session_endpoints";
const SESSION_AUTH_KEY = "sortmyplate_session_auth";
const OAUTH_PENDING_STATE_KEY = "sortmyplate_oauth_state";
const ONBOARDING_DONE_PREFIX = "sortmyplate_onboarded_";

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
  },
  VITAMIN_D3: {
    loinc_code: "62292-8",
    display_name: "Vitamin D3 (25-OH)",
    category: "Micronutrients",
    unit: "ng/mL",
    reference_interval: { low: 30, high: 80 }
  },
  FASTING_GLUCOSE: {
    loinc_code: "1558-6",
    display_name: "Fasting Glucose",
    category: "Glycemic Control",
    unit: "mg/dL",
    reference_interval: { low: 70, high: 99 }
  }
};

let sessionDiscovery = null;
let currentToken = "";
let currentUser = null;
let currentGroup = null;
let currentObservations = {};
let activeMemberIds = [];
let selectedMealSlot = "DINNER";
let onboardingIndex = 0;
let activeTab = "today";
let oauthPollTimer = null;
let googleTokenClient = null;

document.addEventListener("DOMContentLoaded", async () => {
  setupEventListeners();
  setOnboardingSlide(0);

  await discoverEndpointsForSession();
  if (!sessionDiscovery) return;

  await checkLlmStatus();
  const completedRedirectAuth = await checkOAuthRedirectCallback();
  if (!completedRedirectAuth) {
    await restoreSessionAuth();
  }
  initGoogleIdentityServicesIfNeeded();
});

function getDiscoveryOrigin() {
  const params = new URLSearchParams(window.location.search);
  const queryApi = params.get("api");
  if (queryApi) return queryApi.replace(/\/+$/, "");
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
        google_oauth_enabled: Boolean(data.google_oauth_enabled),
        google_gis_enabled: Boolean(data.google_gis_enabled),
        version: data.version || "1.0.0"
      };

      sessionStorage.setItem(SESSION_ENDPOINTS_KEY, JSON.stringify(sessionDiscovery));

      const count = Object.keys(sessionDiscovery.endpoints).length;
      statusEl.textContent = `Resolved ${count} endpoints`;
      statusEl.style.color = "var(--emerald)";
      baseUrlEl.textContent = sessionDiscovery.base_url;
      return;
    } catch (err) {
      console.warn(`Discovery attempt failed on ${origin}:`, err);
    }
  }

  const cached = sessionStorage.getItem(SESSION_ENDPOINTS_KEY);
  if (cached) {
    try {
      sessionDiscovery = JSON.parse(cached);
      statusEl.textContent = "Cached endpoints active";
      baseUrlEl.textContent = sessionDiscovery.base_url;
      return;
    } catch (_) {
      sessionStorage.removeItem(SESSION_ENDPOINTS_KEY);
    }
  }

  statusEl.textContent = "Discovery offline";
  statusEl.style.color = "var(--coral)";
  showBanner("auth-error", "Could not connect to SortMyPlate backend discovery.", true);
}

function resolveEndpoint(key, params = {}) {
  if (!sessionDiscovery || !sessionDiscovery.endpoints) {
    const cached = sessionStorage.getItem(SESSION_ENDPOINTS_KEY);
    if (cached) sessionDiscovery = JSON.parse(cached);
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
  // Post-login onboarding slides
  document.querySelectorAll(".step-pill").forEach(btn => {
    btn.addEventListener("click", () => setOnboardingSlide(Number(btn.dataset.step)));
  });
  document.getElementById("btn-prev-slide").addEventListener("click", () => {
    setOnboardingSlide(Math.max(0, onboardingIndex - 1));
  });
  document.getElementById("btn-next-slide").addEventListener("click", () => {
    if (onboardingIndex < 2) {
      setOnboardingSlide(onboardingIndex + 1);
    } else {
      completeOnboardingTour();
    }
  });
  document.getElementById("btn-skip-onboarding").addEventListener("click", completeOnboardingTour);
  document.getElementById("btn-finish-onboarding").addEventListener("click", completeOnboardingTour);

  // Google Sign-In & Manual fallback
  document.getElementById("btn-google-oauth").addEventListener("click", handleContinueWithGoogle);
  document.getElementById("google-auth-form").addEventListener("submit", handleFallbackEmailSignIn);
  document.getElementById("btn-logout").addEventListener("click", handleSignOut);

  // Navigation pills & jump tiles
  document.querySelectorAll(".nav-pill, .bottom-nav-item").forEach(btn => {
    btn.addEventListener("click", () => switchTab(btn.dataset.tab));
  });
  document.querySelectorAll(".jump-tab").forEach(btn => {
    btn.addEventListener("click", () => switchTab(btn.dataset.jump));
  });

  // Meal slots & action
  document.querySelectorAll(".slot-pill").forEach(btn => {
    btn.addEventListener("click", () => {
      selectedMealSlot = btn.dataset.slot;
      document.querySelectorAll(".slot-pill").forEach(p => {
        p.classList.toggle("active", p.dataset.slot === selectedMealSlot);
      });
    });
  });
  document.getElementById("btn-next-meal").addEventListener("click", getNextMeal);

  // Groups
  document.getElementById("btn-create-group").addEventListener("click", handleCreateGroup);
  document.getElementById("btn-join-group").addEventListener("click", handleJoinGroup);
  document.getElementById("btn-leave-group").addEventListener("click", handleLeaveGroup);

  // Biomarkers
  document.getElementById("quick-biomarker-form").addEventListener("submit", handleSaveQuickBiomarker);
  document.getElementById("pdf-input").addEventListener("change", uploadPdfReport);

  // Profile update
  document.getElementById("profile-update-form").addEventListener("submit", handleUpdateProfile);

  // Modals (Guide & Insights Details) & Replay Interactive Onboarding
  const guideModal = document.getElementById("guide-modal");
  document.getElementById("btn-open-guide").addEventListener("click", () => guideModal.showModal());
  document.getElementById("btn-hero-help").addEventListener("click", () => guideModal.showModal());
  document.getElementById("btn-review-onboarding").addEventListener("click", () => {
    if (currentUser) openOnboardingTour();
    else guideModal.showModal();
  });
  document.getElementById("btn-close-guide").addEventListener("click", () => guideModal.close());
  guideModal.addEventListener("click", (e) => { if (e.target === guideModal) guideModal.close(); });

  const insightModal = document.getElementById("insight-modal");
  document.getElementById("btn-close-insight").addEventListener("click", () => insightModal.close());
  insightModal.addEventListener("click", (e) => { if (e.target === insightModal) insightModal.close(); });

  // Receive popup postMessage completion safely
  window.addEventListener("message", handleOAuthPopupMessage);
}

function setOnboardingSlide(index) {
  onboardingIndex = index;
  document.querySelectorAll(".slide").forEach(slide => {
    const match = Number(slide.dataset.slide) === index;
    slide.hidden = !match;
    slide.classList.toggle("active", match);
  });
  document.querySelectorAll(".step-pill").forEach(pill => {
    const match = Number(pill.dataset.step) === index;
    pill.classList.toggle("active", match);
    pill.setAttribute("aria-selected", match ? "true" : "false");
  });
  document.querySelectorAll(".pager-dot").forEach((dot, idx) => {
    dot.classList.toggle("active", idx === index);
  });
  document.getElementById("onboarding-counter").textContent = `${index + 1} / 3`;
  document.getElementById("btn-prev-slide").disabled = index === 0;
  const nextBtn = document.getElementById("btn-next-slide");
  const finishBtn = document.getElementById("btn-finish-onboarding");
  if (index === 2) {
    nextBtn.style.display = "none";
    finishBtn.style.display = "inline-flex";
  } else {
    nextBtn.style.display = "inline-flex";
    nextBtn.textContent = "Next";
    finishBtn.style.display = "none";
  }
}

function switchTab(tabName) {
  activeTab = tabName;
  const views = {
    today: "view-today",
    blood: "view-blood",
    insights: "view-insights",
    circle: "view-circle"
  };

  Object.entries(views).forEach(([key, domId]) => {
    const panel = document.getElementById(domId);
    const active = key === tabName;
    panel.hidden = !active;
    panel.classList.toggle("active", active);
  });

  document.querySelectorAll(".nav-pill, .bottom-nav-item").forEach(btn => {
    const active = btn.dataset.tab === tabName;
    btn.classList.toggle("active", active);
    btn.setAttribute("aria-selected", active ? "true" : "false");
  });
}

function generateSecureState() {
  const bytes = new Uint8Array(24);
  if (window.crypto && window.crypto.getRandomValues) {
    window.crypto.getRandomValues(bytes);
    return Array.from(bytes, b => b.toString(16).padStart(2, "0")).join("");
  }
  return `smp_${Date.now()}_${Math.random().toString(36).slice(2)}_${Math.random().toString(36).slice(2)}`;
}

async function checkOAuthRedirectCallback() {
  const params = new URLSearchParams(window.location.search);
  const state = params.get("oauth_state");
  const code = params.get("oauth_code");
  if (!state || !code) return false;

  // Remove sensitive one-time params from browser URL immediately
  window.history.replaceState({}, document.title, window.location.pathname);

  try {
    const res = await fetch(resolveEndpoint("auth_google_exchange"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ state, exchange_code: code })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "OAuth exchange failed");

    await completeAuthSuccess(data);
    return true;
  } catch (err) {
    showBanner("auth-error", `Google Sign-In verification failed: ${err.message}`, true);
    return false;
  }
}

function initGoogleIdentityServicesIfNeeded() {
  if (!sessionDiscovery) return;
  if (!sessionDiscovery.google_gis_enabled || !sessionDiscovery.google_client_id) return;

  const existingScript = document.getElementById("google-gsi-sdk");
  if (existingScript) return;

  const script = document.createElement("script");
  script.id = "google-gsi-sdk";
  script.src = "https://accounts.google.com/gsi/client";
  script.async = true;
  script.defer = true;
  script.onload = () => {
    if (!window.google || !window.google.accounts) return;

    if (window.google.accounts.id) {
      window.google.accounts.id.initialize({
        client_id: sessionDiscovery.google_client_id,
        callback: handleGisCredentialResponse,
        ux_mode: "popup",
        use_fedcm_for_prompt: true
      });
      const container = document.getElementById("g_id_signin_container");
      if (container) {
        window.google.accounts.id.renderButton(container, {
          theme: "outline",
          size: "large",
          shape: "pill",
          width: 340,
          text: "continue_with"
        });
      }
      if (!currentUser) {
        try {
          window.google.accounts.id.prompt();
        } catch (_) {
          // One Tap prompt optional when user prefers explicit button click
        }
      }
    }

    if (window.google.accounts.oauth2?.initTokenClient) {
      googleTokenClient = window.google.accounts.oauth2.initTokenClient({
        client_id: sessionDiscovery.google_client_id,
        scope: "openid email profile",
        callback: handleGisTokenResponse,
        error_callback: () => {
          resetGoogleButtonState();
        }
      });
    }
  };
  document.head.appendChild(script);
}

async function handleGisCredentialResponse(response) {
  if (!response || !response.credential) return;
  showBanner("auth-error", "", true);
  try {
    const res = await fetch(resolveEndpoint("auth_google"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id_token: response.credential })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Google token verification failed");
    await completeAuthSuccess(data);
  } catch (err) {
    showBanner("auth-error", `Google Sign-In failed: ${err.message}`, true);
  } finally {
    resetGoogleButtonState();
  }
}

async function handleGisTokenResponse(tokenResponse) {
  if (!tokenResponse || tokenResponse.error || !tokenResponse.access_token) {
    resetGoogleButtonState();
    if (tokenResponse?.error && tokenResponse.error !== "popup_closed_by_user") {
      showBanner("auth-error", `Google Sign-In cancelled: ${tokenResponse.error}`, true);
    }
    return;
  }

  showBanner("auth-error", "", true);
  try {
    const res = await fetch(resolveEndpoint("auth_google"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ google_access_token: tokenResponse.access_token })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Google token verification failed");
    await completeAuthSuccess(data);
  } catch (err) {
    showBanner("auth-error", `Google Sign-In failed: ${err.message}`, true);
  } finally {
    resetGoogleButtonState();
  }
}

async function handleContinueWithGoogle() {
  showBanner("auth-error", "", true);
  if (!sessionDiscovery) {
    showBanner("auth-error", "Service discovery is still initializing.", true);
    return;
  }

  // Case 1: In-Page Google Identity Services Token Client (stays inside website)
  if (googleTokenClient) {
    const btn = document.getElementById("btn-google-oauth");
    const label = document.getElementById("btn-google-oauth-label");
    btn.disabled = true;
    label.textContent = "Opening Google chooser...";
    try {
      googleTokenClient.requestAccessToken({ prompt: "select_account" });
    } catch (err) {
      resetGoogleButtonState();
      showBanner("auth-error", `Could not open in-page Google chooser: ${err.message}`, true);
    }
    return;
  }

  // Case 2: GIS ID / One Tap Prompt (in-page credential sheet)
  if (sessionDiscovery.google_gis_enabled && window.google?.accounts?.id) {
    window.google.accounts.id.prompt();
    return;
  }

  // Case 3: Centered Backend OAuth Popup (keeps current page intact via postMessage)
  if (sessionDiscovery.google_oauth_enabled) {
    const btn = document.getElementById("btn-google-oauth");
    const label = document.getElementById("btn-google-oauth-label");
    btn.disabled = true;
    label.textContent = "Connecting to Google...";

    const oauthState = generateSecureState();
    sessionStorage.setItem(OAUTH_PENDING_STATE_KEY, oauthState);

    try {
      const loginEndpoint = resolveEndpoint("auth_google_login");
      const query = new URLSearchParams({
        state: oauthState,
        platform: "popup",
        response_mode: "json"
      });
      const res = await fetch(`${loginEndpoint}?${query.toString()}`);
      const data = await res.json();
      if (!res.ok || !data.auth_url) {
        throw new Error(data.detail || "Could not start Google OAuth flow");
      }

      const width = 500;
      const height = 620;
      const left = Math.max(0, Math.round(window.screenX + (window.outerWidth - width) / 2));
      const top = Math.max(0, Math.round(window.screenY + (window.outerHeight - height) / 2));
      const popup = window.open(
        data.auth_url,
        "sortmyplate_google_oauth",
        `width=${width},height=${height},left=${left},top=${top},menubar=no,toolbar=no,status=no`
      );

      if (!popup || popup.closed) {
        resetGoogleButtonState();
        showBanner(
          "auth-error",
          "Please allow the Google sign-in window or use the Google Identity button right above so you stay inside SortMyPlate.",
          true
        );
        return;
      }

      startOAuthSessionPolling(oauthState);
    } catch (err) {
      showBanner("auth-error", err.message, true);
      resetGoogleButtonState();
    }
    return;
  }

  // Case 4: Neither GOOGLE_CLIENT_ID nor GOOGLE_CLIENT_SECRET set yet on server
  const hintBox = document.getElementById("oauth-config-hint");
  const hintText = document.getElementById("oauth-config-hint-text");
  const callbackUri = `${sessionDiscovery.base_url}/v1/auth/google/callback`;
  hintText.textContent =
    `Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in server environment variables, and add ${callbackUri} as an Authorized Redirect URI in Google Cloud Console. You can use the direct email fallback below right now.`;
  hintBox.style.display = "block";
  document.getElementById("manual-fallback-details").open = true;
}

async function handleOAuthPopupMessage(event) {
  if (!sessionDiscovery) return;
  // Strict origin verification
  const expectedOrigin = new URL(sessionDiscovery.base_url).origin;
  if (event.origin !== window.location.origin && event.origin !== expectedOrigin) return;
  const payload = event.data;
  if (!payload || payload.type !== "sortmyplate_google_auth") return;

  stopOAuthPolling();

  if (payload.error) {
    resetGoogleButtonState();
    showBanner("auth-error", `Google Sign-In cancelled: ${payload.error}`, true);
    return;
  }

  try {
    const res = await fetch(resolveEndpoint("auth_google_exchange"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ state: payload.state, exchange_code: payload.exchange_code })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "OAuth exchange error");
    await completeAuthSuccess(data);
  } catch (err) {
    showBanner("auth-error", err.message, true);
  } finally {
    resetGoogleButtonState();
  }
}

function startOAuthSessionPolling(oauthState) {
  stopOAuthPolling();
  let attempts = 0;
  oauthPollTimer = setInterval(async () => {
    attempts += 1;
    if (attempts > 90) {
      stopOAuthPolling();
      resetGoogleButtonState();
      return;
    }
    try {
      const pollUrl = resolveEndpoint("auth_google_session", { oauth_state: oauthState });
      const res = await fetch(pollUrl);
      if (!res.ok) return;
      const poll = await res.json();
      if (poll.status === "completed" && poll.auth) {
        stopOAuthPolling();
        resetGoogleButtonState();
        await completeAuthSuccess(poll.auth);
      } else if (poll.status === "error") {
        stopOAuthPolling();
        resetGoogleButtonState();
        showBanner("auth-error", poll.error || "Google sign-in failed", true);
      }
    } catch (_) {
      // Transient polling error ignored until next interval
    }
  }, 1500);
}

function stopOAuthPolling() {
  if (oauthPollTimer) {
    clearInterval(oauthPollTimer);
    oauthPollTimer = null;
  }
}

function resetGoogleButtonState() {
  const btn = document.getElementById("btn-google-oauth");
  const label = document.getElementById("btn-google-oauth-label");
  btn.disabled = false;
  label.textContent = "Continue with Google";
}

async function handleFallbackEmailSignIn(e) {
  e.preventDefault();
  showBanner("auth-error", "", true);

  const email = document.getElementById("login-email").value.trim();
  const name = document.getElementById("login-name").value.trim();
  const allergiesRaw = document.getElementById("login-allergies").value;
  const allergies = allergiesRaw.split(",").map(s => s.trim().toLowerCase()).filter(Boolean);

  if (!email || !name) {
    showBanner("auth-error", "Enter your email address and full name.", true);
    return;
  }

  const btn = document.getElementById("btn-google-signin");
  btn.disabled = true;

  try {
    const res = await fetch(resolveEndpoint("auth_google"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, name, allergies })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Sign-In failed");
    await completeAuthSuccess(data);
  } catch (err) {
    showBanner("auth-error", err.message, true);
  } finally {
    btn.disabled = false;
  }
}

function hasCompletedOnboarding(userId) {
  if (!userId) return false;
  try {
    return localStorage.getItem(`${ONBOARDING_DONE_PREFIX}${userId}`) === "true";
  } catch (_) {
    return false;
  }
}

function markOnboardingCompleted(userId) {
  if (!userId) return;
  try {
    localStorage.setItem(`${ONBOARDING_DONE_PREFIX}${userId}`, "true");
  } catch (_) {
    // Storage optional in strict private browsing modes
  }
}

function openOnboardingTour() {
  if (!currentUser) return;
  const avatarUrl = safeAvatarUrl(currentUser.picture_url, currentUser.full_name);
  const firstName = (currentUser.full_name || "Friend").split(" ")[0];

  document.getElementById("auth-section").style.display = "none";
  document.getElementById("onboarding-section").style.display = "flex";
  document.getElementById("dashboard-section").style.display = "none";
  document.getElementById("desktop-nav").style.display = "none";
  document.getElementById("mobile-nav").classList.remove("authenticated");
  document.getElementById("mobile-nav").style.display = "none";

  document.getElementById("user-badge").style.display = "flex";
  document.getElementById("user-name").textContent = currentUser.full_name;
  document.getElementById("user-email").textContent = currentUser.email;
  document.getElementById("user-avatar").src = avatarUrl;

  document.getElementById("onboard-avatar").src = avatarUrl;
  document.getElementById("onboard-greeting").textContent = `Welcome, ${firstName}`;
  document.getElementById("onboard-email").textContent = `${currentUser.email} • Google Account Connected`;
  setOnboardingSlide(0);
}

async function completeOnboardingTour() {
  if (currentUser?.user_id) {
    markOnboardingCompleted(currentUser.user_id);
  }
  await enterDashboard();
}

async function completeAuthSuccess(authData) {
  currentToken = authData.access_token;
  currentUser = authData;
  sessionStorage.setItem(SESSION_AUTH_KEY, JSON.stringify(authData));

  if (!hasCompletedOnboarding(currentUser.user_id)) {
    openOnboardingTour();
    return;
  }
  await enterDashboard();
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
    const freshUser = await res.json();
    currentToken = parsed.access_token;
    currentUser = { ...freshUser, access_token: currentToken };
    if (!hasCompletedOnboarding(currentUser.user_id)) {
      openOnboardingTour();
      return;
    }
    await enterDashboard();
  } catch (_) {
    sessionStorage.removeItem(SESSION_AUTH_KEY);
    showAuthView();
  }
}

function safeAvatarUrl(rawUrl, fullName) {
  if (rawUrl && (rawUrl.startsWith("https://") || rawUrl.startsWith("http://"))) {
    return rawUrl;
  }
  return `https://ui-avatars.com/api/?name=${encodeURIComponent(fullName || "User")}&background=2b9a5b&color=ffffff`;
}

async function enterDashboard() {
  document.getElementById("auth-section").style.display = "none";
  document.getElementById("onboarding-section").style.display = "none";
  document.getElementById("dashboard-section").style.display = "block";
  document.getElementById("desktop-nav").style.display = "inline-flex";
  document.getElementById("mobile-nav").classList.add("authenticated");
  document.getElementById("mobile-nav").style.display = "grid";
  document.getElementById("user-badge").style.display = "flex";

  const avatarUrl = safeAvatarUrl(currentUser.picture_url, currentUser.full_name);
  const firstName = (currentUser.full_name || "Friend").split(" ")[0];

  document.getElementById("user-name").textContent = currentUser.full_name;
  document.getElementById("user-email").textContent = currentUser.email;
  document.getElementById("user-avatar").src = avatarUrl;

  document.getElementById("hero-avatar").src = avatarUrl;
  document.getElementById("hero-greeting").textContent = `Hello, ${firstName}`;
  document.getElementById("hero-subline").textContent = `${currentUser.email} • AES-256 Protected`;
  document.getElementById("subject-token-display").textContent = currentUser.subject_token;

  document.getElementById("profile-avatar").src = avatarUrl;
  document.getElementById("profile-name").textContent = currentUser.full_name;
  document.getElementById("profile-email").textContent = currentUser.email;
  document.getElementById("profile-subject-token").textContent = currentUser.subject_token;
  document.getElementById("profile-diet").value = currentUser.diet_preference || "omnivore";
  document.getElementById("profile-allergies").value = (currentUser.allergies || []).join(", ");

  document.getElementById("vault-base-url").textContent = sessionDiscovery.base_url;
  document.getElementById("vault-endpoint-count").textContent = String(Object.keys(sessionDiscovery.endpoints).length);

  switchTab("today");
  await Promise.all([loadBiomarkers(), loadGroups()]);
  renderHealthInsights();
}

function handleSignOut() {
  stopOAuthPolling();
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
  document.getElementById("auth-section").style.display = "flex";
  document.getElementById("onboarding-section").style.display = "none";
  document.getElementById("dashboard-section").style.display = "none";
  document.getElementById("desktop-nav").style.display = "none";
  document.getElementById("mobile-nav").classList.remove("authenticated");
  document.getElementById("mobile-nav").style.display = "none";
  document.getElementById("user-badge").style.display = "none";
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
    const res = await fetch(resolveEndpoint("llm_status"));
    if (!res.ok) {
      el.textContent = "Clinical Engine Ready";
      return;
    }
    const data = await res.json();
    const map = {
      deepseek: "DeepSeek-V3",
      claude: "Claude 3.5",
      openai: "GPT-4o",
      ollama: "Local Ollama",
      mock: "Clinical Engine"
    };
    const providerLabel = map[data.provider] || "Clinical AI";
    el.textContent = `${providerLabel} • ${data.status || "ONLINE"}`;
  } catch (_) {
    el.textContent = "Clinical Engine";
  }
}

async function loadBiomarkers() {
  const grid = document.getElementById("biomarker-cards-grid");
  const labInfo = document.getElementById("lab-provider-info");
  const narrative = document.getElementById("blood-narrative");

  try {
    const res = await fetch(resolveEndpoint("biomarkers_latest"), {
      headers: { "Authorization": `Bearer ${currentToken}` }
    });

    if (res.status === 404) {
      currentObservations = {};
      labInfo.textContent = "No lab panel yet";
      narrative.textContent = "Upload your 6-month lab report PDF or record markers below. Your biomarkers stay encrypted in Zone B via AES-256-GCM.";
      renderEmptyBiomarkers(grid);
      updateHeroScore();
      renderHealthInsights();
      return;
    }
    if (!res.ok) return;

    const panel = await res.json();
    currentObservations = panel.observations || {};
    const testedDate = panel.report_date ? new Date(panel.report_date).toLocaleDateString() : "Recent";
    labInfo.textContent = `${panel.lab_provider} • ${testedDate}`;

    renderBiomarkerCards(grid);
    updateHeroScore();
    renderHealthInsights();
  } catch (err) {
    console.error("Biomarker load error:", err);
  }
}

function renderEmptyBiomarkers(grid) {
  grid.textContent = "";
  const empty = document.createElement("div");
  empty.className = "marker-card";
  const title = document.createElement("strong");
  title.textContent = "No biomarkers recorded yet";
  const copy = document.createElement("p");
  copy.style.fontSize = "13px";
  copy.style.color = "var(--ink-secondary)";
  copy.style.marginTop = "6px";
  copy.textContent = "Drop a diagnostic PDF below or enter one marker (e.g. ApoB or HbA1c) to personalize meals and spectrum bars.";
  empty.append(title, copy);
  grid.appendChild(empty);
}

function computeSpectrumPercent(obs) {
  const low = obs.reference_interval?.low ?? 0;
  const high = obs.reference_interval?.high ?? Math.max(obs.numeric_value * 1.4, 100);
  const span = Math.max(high - low, 1);
  // Map reference range roughly into 32%–82% (the amber/lime/emerald zone), extremes to edges
  const norm = (obs.numeric_value - low) / span;
  const pct = 32 + norm * 50;
  return Math.max(6, Math.min(94, pct));
}

function renderBiomarkerCards(grid) {
  grid.textContent = "";
  const entries = Object.entries(currentObservations);
  if (entries.length === 0) {
    renderEmptyBiomarkers(grid);
    return;
  }

  let abnormalNames = [];
  for (const [code, obs] of entries) {
    if (obs.status !== "OPTIMAL" && obs.status !== "NORMAL") {
      abnormalNames.push(obs.display_name);
    }

    const card = document.createElement("div");
    card.className = "marker-card";

    const top = document.createElement("div");
    top.className = "marker-top";
    const nameSpan = document.createElement("span");
    nameSpan.className = "marker-name";
    nameSpan.textContent = obs.display_name;
    const vnSpan = document.createElement("span");
    vnSpan.className = "marker-vn";
    const low = obs.reference_interval?.low ?? 0;
    const high = obs.reference_interval?.high ?? "—";
    vnSpan.textContent = `VN: ${low}–${high}`;
    top.append(nameSpan, vnSpan);

    const valRow = document.createElement("div");
    valRow.className = "marker-value-row";
    const valBlock = document.createElement("div");
    const numStrong = document.createElement("span");
    numStrong.className = "marker-number";
    numStrong.textContent = String(obs.numeric_value);
    const unitSpan = document.createElement("span");
    unitSpan.className = "marker-unit";
    unitSpan.textContent = ` ${obs.unit}`;
    valBlock.append(numStrong, unitSpan);

    const statusBadge = document.createElement("span");
    let statusClass = "status-normal";
    if (obs.status === "OPTIMAL") statusClass = "status-optimal";
    else if (obs.status === "LOW" || obs.status === "CRITICAL_LOW") statusClass = "status-low";
    else if (obs.status === "HIGH" || obs.status === "CRITICAL_HIGH") statusClass = "status-high";
    statusBadge.className = `badge-status ${statusClass}`;
    statusBadge.textContent = obs.status;
    valRow.append(valBlock, statusBadge);

    // Signature Multi-Zone Spectrum Bar
    const bar = document.createElement("div");
    bar.className = "spectrum-bar";
    ["spec-coral", "spec-amber", "spec-lime", "spec-emerald", "spec-violet"].forEach(cls => {
      const seg = document.createElement("span");
      seg.className = `spec-seg ${cls}`;
      bar.appendChild(seg);
    });
    const pin = document.createElement("span");
    pin.className = "spectrum-pin";
    pin.style.left = `${computeSpectrumPercent(obs)}%`;
    bar.appendChild(pin);

    const foot = document.createElement("div");
    foot.className = "marker-meta-foot";
    const catSpan = document.createElement("span");
    catSpan.textContent = obs.category || "Panel Marker";
    const loincSpan = document.createElement("span");
    loincSpan.textContent = `LOINC ${obs.loinc_code || code}`;
    foot.append(catSpan, loincSpan);

    card.append(top, valRow, bar, foot);
    grid.appendChild(card);
  }

  const narrative = document.getElementById("blood-narrative");
  if (abnormalNames.length === 0) {
    narrative.textContent = "All recorded metabolic, lipid, and inflammatory markers sit safely within clinical reference ranges.";
  } else {
    narrative.textContent = `Targeted nutrition focus active for ${abnormalNames.join(", ")} — every meal balances these findings gently.`;
  }
}

function updateHeroScore() {
  const entries = Object.values(currentObservations);
  const scoreEl = document.getElementById("readiness-score");
  const pillEl = document.getElementById("readiness-pill");
  const labHeadline = document.getElementById("today-lab-headline");
  const labDesc = document.getElementById("today-lab-desc");
  const labBadge = document.getElementById("today-lab-badge");

  if (entries.length === 0) {
    scoreEl.textContent = "86";
    pillEl.textContent = "Ready • Add Blood PDF to personalize";
    labHeadline.textContent = "Blood Lab";
    labDesc.textContent = "Upload a PDF or enter ApoB, HbA1c, Ferritin";
    labBadge.textContent = "Add Panel";
    return;
  }

  let totalPts = 0;
  let attentionCount = 0;
  entries.forEach(obs => {
    if (obs.status === "OPTIMAL") totalPts += 98;
    else if (obs.status === "NORMAL") totalPts += 88;
    else {
      totalPts += 64;
      attentionCount += 1;
    }
  });
  const avg = Math.round(totalPts / entries.length);
  scoreEl.textContent = String(avg);
  pillEl.textContent = attentionCount === 0
    ? `${entries.length} Markers Balanced`
    : `${attentionCount} Marker${attentionCount > 1 ? "s" : ""} Prioritized Today`;

  labHeadline.textContent = attentionCount === 0 ? "Optimal Labs" : `${attentionCount} Attention`;
  labDesc.textContent = `${entries.length} markers encrypted in PHI Vault`;
  labBadge.textContent = `${entries.length} Markers`;
}

function renderHealthInsights() {
  const grid = document.getElementById("insights-bento-grid");
  if (!grid) return;
  grid.textContent = "";

  const entries = Object.values(currentObservations);
  const apob = currentObservations.APOB;
  const hba1c = currentObservations.HBA1C;
  const crp = currentObservations.HS_CRP;
  const ferritin = currentObservations.FERRITIN;

  const cards = [
    {
      cls: "bento-crimson",
      kicker: "Glycemic & Fiber Pillar",
      title: "Nutrition & HbA1c",
      value: hba1c ? `${hba1c.numeric_value}%` : "94",
      status: hba1c ? hba1c.status : "Steady",
      summary: "Low-glycemic load plates rich in soluble fiber prevent sharp glucose swings after meals.",
      points: [
        { head: "Why daily consistency works", body: "Sequencing protein and soluble fiber first blunts post-meal glucose spikes by up to 30%." },
        { head: "Your lab context", body: hba1c ? `Recorded HbA1c is ${hba1c.numeric_value}% (${hba1c.status}).` : "No HbA1c recorded yet — SortMyPlate keeps glycemic load gentle by default." }
      ]
    },
    {
      cls: "bento-amber",
      kicker: "Cellular Recovery",
      title: "Inflammation",
      value: crp ? `${crp.numeric_value}` : "82",
      status: crp ? crp.unit : "mg/L Focus",
      summary: "Anti-inflammatory omega-3 lipids, turmeric, and polyphenols calm systemic inflammation over time.",
      points: [
        { head: "Daily inflammation lever", body: "Swapping refined oils for extra-virgin olive oil and omega-3 fish lowers oxidative stress." },
        { head: "Your hs-CRP signal", body: crp ? `hs-CRP reads ${crp.numeric_value} ${crp.unit} (${crp.status}).` : "Upload hs-CRP in Blood Lab to calibrate anti-inflammatory boosts." }
      ]
    },
    {
      cls: "bento-sage insight-span-2",
      kicker: "Cardiometabolic Longevity",
      title: "Lipids & ApoB Balance",
      value: apob ? `${apob.numeric_value} mg/dL` : (entries.length ? `${entries.length} Markers` : "Ready"),
      status: apob ? apob.status : "AES-256 Protected",
      summary: "Lowering ApoB and LDL-C through oat beta-glucan, legumes, nuts, and lean protein supports vascular longevity.",
      points: [
        { head: "How SortMyPlate adapts meals", body: "When ApoB or LDL-C trends high, meals prioritize plant sterols and viscous fibers that bind bile cholesterol." },
        { head: "Privacy guarantee", body: "Your lipid values remain isolated behind your synthetic subject token—never stored with PII." }
      ]
    },
    {
      cls: "bento-cerulean",
      kicker: "Oxygen & Energy",
      title: "Iron & Ferritin",
      value: ferritin ? `${ferritin.numeric_value}` : "Vital",
      status: ferritin ? ferritin.status : "Track Iron",
      summary: "Strategic Vitamin-C acidic dressings double non-heme plant iron absorption when ferritin dips.",
      points: [
        { head: "Smart plate pairing", body: "SortMyPlate finishes lentil or greens bowls with citrus zest or pickled veggies for individuals with low ferritin." },
        { head: "Your ferritin marker", body: ferritin ? `Serum Ferritin is ${ferritin.numeric_value} ${ferritin.unit} (${ferritin.status}).` : "Add Ferritin in Blood Lab if you track fatigue or endurance." }
      ]
    },
    {
      cls: "bento-olive insight-span-2",
      kicker: "Preventive Routine",
      title: "How Daily Meals Improve 6-Month Labs",
      value: "3x / day",
      status: "Daily Guide",
      summary: "Every breakfast, lunch, and dinner compounds small vascular, glycemic, and gut microbiome wins across 180 days.",
      points: [
        { head: "Zero-Friction Shared Cooking", body: "One shared household recipe keeps group prep fast while custom finishing toppings address individual labs." },
        { head: "Safe by Construction", body: "Strict allergen exclusion runs deterministically before AI clinical explanations are generated." }
      ]
    }
  ];

  cards.forEach(item => {
    const tile = document.createElement("button");
    tile.type = "button";
    tile.className = `bento-tile ${item.cls}`;

    const art = document.createElement("div");
    art.className = "bento-art";
    art.setAttribute("aria-hidden", "true");

    const kicker = document.createElement("span");
    kicker.className = "bento-kicker";
    kicker.textContent = item.kicker;

    const title = document.createElement("strong");
    title.className = "bento-title";
    title.textContent = item.title;

    const metricRow = document.createElement("div");
    metricRow.className = "insight-metric-row";
    const bigVal = document.createElement("span");
    bigVal.className = "insight-big-val";
    bigVal.textContent = item.value;
    const statusTag = document.createElement("span");
    statusTag.style.fontSize = "12px";
    statusTag.style.fontWeight = "700";
    statusTag.textContent = item.status;
    metricRow.append(bigVal, statusTag);

    const pill = document.createElement("span");
    pill.className = "bento-pill";
    pill.textContent = "Details →";

    tile.append(art, kicker, title, metricRow, pill);
    tile.addEventListener("click", () => openInsightDetailModal(item));
    grid.appendChild(tile);
  });
}

function openInsightDetailModal(item) {
  document.getElementById("insight-modal-badge").textContent = item.kicker;
  document.getElementById("insight-modal-title").textContent = item.title;
  document.getElementById("insight-modal-summary").textContent = item.summary;

  const container = document.getElementById("insight-modal-points");
  container.textContent = "";
  item.points.forEach(pt => {
    const row = document.createElement("div");
    row.className = "feature-item";
    const bodyWrap = document.createElement("div");
    const strong = document.createElement("strong");
    strong.textContent = pt.head;
    const p = document.createElement("p");
    p.textContent = pt.body;
    bodyWrap.append(strong, p);
    row.appendChild(bodyWrap);
    container.appendChild(row);
  });
  document.getElementById("insight-modal").showModal();
}

async function handleSaveQuickBiomarker(e) {
  e.preventDefault();
  showBanner("biomarker-status", "", false);

  const code = document.getElementById("biomarker-code").value;
  const numericValue = parseFloat(document.getElementById("biomarker-value").value);

  if (Number.isNaN(numericValue)) {
    showBanner("biomarker-status", "Please enter a valid numeric value.", true);
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
    showBanner("biomarker-status", `Saved ${meta.display_name} into encrypted PHI Vault.`, false);
    await loadBiomarkers();
  } catch (err) {
    showBanner("biomarker-status", `Error saving biomarker: ${err.message}`, true);
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
    statusText.textContent = "✓ Successfully parsed & encrypted blood panel!";
    await loadBiomarkers();
  } catch (err) {
    statusText.textContent = `⚠️ ${err.message}`;
  } finally {
    e.target.value = "";
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

function updateTodayCircleSummary() {
  const dinersChip = document.getElementById("active-diners-chip");
  const circleHeadline = document.getElementById("today-circle-headline");
  const circleBadge = document.getElementById("today-circle-badge");

  if (!currentGroup || activeMemberIds.length === 0) {
    dinersChip.textContent = "Solo Mode";
    circleHeadline.textContent = "Solo Mode";
    circleBadge.textContent = currentGroup ? `0/${currentGroup.members.length} Active` : "Create / Join";
    return;
  }

  dinersChip.textContent = `${currentGroup.name} • ${activeMemberIds.length} eating`;
  circleHeadline.textContent = currentGroup.name;
  circleBadge.textContent = `${activeMemberIds.length} Active`;
}

function renderSoloGroupState() {
  document.getElementById("group-name").textContent = "Household / Flat Circle";
  document.getElementById("group-code-wrapper").style.display = "none";
  document.getElementById("group-invite-code").textContent = "";

  const listEl = document.getElementById("member-list");
  listEl.textContent = "";
  const msg = document.createElement("p");
  msg.className = "muted-empty";
  msg.textContent = "No group joined yet — currently planning meals in Solo Mode.";
  listEl.appendChild(msg);
  updateTodayCircleSummary();
}

function renderActiveGroup(group) {
  currentGroup = group;
  document.getElementById("group-name").textContent = group.name;
  document.getElementById("group-invite-code").textContent = group.invite_code;
  document.getElementById("group-code-wrapper").style.display = "inline-flex";

  const listEl = document.getElementById("member-list");
  listEl.textContent = "";
  activeMemberIds = group.members.map(m => m.id);

  group.members.forEach(member => {
    const isYou = currentUser && member.id === currentUser.user_id;
    const item = document.createElement("div");
    item.className = "member-item active";

    const infoDiv = document.createElement("div");
    infoDiv.className = "member-info";

    const avatar = document.createElement("img");
    avatar.src = safeAvatarUrl(member.picture_url, member.full_name);
    avatar.alt = `${member.full_name} avatar`;

    const metaDiv = document.createElement("div");
    metaDiv.className = "member-meta";
    const nameH = document.createElement("h4");
    nameH.textContent = isYou ? `${member.full_name} (You)` : member.full_name;
    const subP = document.createElement("p");
    subP.textContent = member.allergies?.length
      ? `${member.email} • Allergy: ${member.allergies.join(", ")}`
      : member.email;

    metaDiv.append(nameH, subP);
    infoDiv.append(avatar, metaDiv);

    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.className = "checkbox-custom";
    checkbox.checked = true;
    checkbox.ariaLabel = `Include ${member.full_name} in next meal`;

    checkbox.addEventListener("change", (e) => {
      if (e.target.checked) {
        if (!activeMemberIds.includes(member.id)) activeMemberIds.push(member.id);
        item.classList.add("active");
      } else {
        activeMemberIds = activeMemberIds.filter(id => id !== member.id);
        item.classList.remove("active");
      }
      updateTodayCircleSummary();
    });

    item.append(infoDiv, checkbox);
    listEl.appendChild(item);
  });

  updateTodayCircleSummary();
}

async function handleCreateGroup() {
  showBanner("group-status", "", false);
  const input = document.getElementById("new-group-name");
  const name = input.value.trim();
  if (!name) {
    showBanner("group-status", "Enter a household or group name.", true);
    return;
  }

  try {
    const res = await fetch(resolveEndpoint("groups_create"), {
      method: "POST",
      headers: { "Content-Type": "application/json", "Authorization": `Bearer ${currentToken}` },
      body: JSON.stringify({ name })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Could not create group");
    input.value = "";
    renderActiveGroup(data);
    showBanner("group-status", `Created '${data.name}' (Invite code: ${data.invite_code}).`, false);
  } catch (err) {
    showBanner("group-status", err.message, true);
  }
}

async function handleJoinGroup() {
  showBanner("group-status", "", false);
  const input = document.getElementById("join-group-code");
  const inviteCode = input.value.trim();
  if (!inviteCode) {
    showBanner("group-status", "Enter an invite code to join.", true);
    return;
  }

  try {
    const res = await fetch(resolveEndpoint("groups_join"), {
      method: "POST",
      headers: { "Content-Type": "application/json", "Authorization": `Bearer ${currentToken}` },
      body: JSON.stringify({ invite_code: inviteCode })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Invalid invite code");
    input.value = "";
    renderActiveGroup(data);
    showBanner("group-status", `Joined '${data.name}' successfully.`, false);
  } catch (err) {
    showBanner("group-status", err.message, true);
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
    showBanner("group-status", "Left group. Switched to Solo Mode.", false);
  } catch (err) {
    showBanner("group-status", err.message, true);
  }
}

async function handleUpdateProfile(e) {
  e.preventDefault();
  showBanner("profile-status", "", false);

  const diet = document.getElementById("profile-diet").value;
  const allergiesRaw = document.getElementById("profile-allergies").value;
  const allergies = allergiesRaw.split(",").map(s => s.trim().toLowerCase()).filter(Boolean);

  try {
    const res = await fetch(resolveEndpoint("auth_profile"), {
      method: "PUT",
      headers: { "Content-Type": "application/json", "Authorization": `Bearer ${currentToken}` },
      body: JSON.stringify({ allergies, diet_preference: diet })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Could not update dietary profile");

    currentUser = { ...data, access_token: currentToken };
    sessionStorage.setItem(SESSION_AUTH_KEY, JSON.stringify(currentUser));
    showBanner("profile-status", "Saved dietary preferences & allergy guardrails.", false);
    await loadGroups();
  } catch (err) {
    showBanner("profile-status", err.message, true);
  }
}

async function getNextMeal() {
  showBanner("meal-error", "", true);
  const btn = document.getElementById("btn-next-meal");
  const originalNodes = Array.from(btn.childNodes).map(n => n.cloneNode(true));
  btn.textContent = "";
  const spinner = document.createElement("span");
  spinner.className = "spinner";
  btn.append(spinner, document.createTextNode(" Balancing Biomarkers..."));
  btn.disabled = true;

  try {
    const payload = { meal_slot: selectedMealSlot, max_prep_time_minutes: 35 };
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
    if (!res.ok) throw new Error(data.detail || "Meal generation failed");
    renderMealResult(data);
  } catch (err) {
    showBanner("meal-error", `Could not generate meal: ${err.message}`, true);
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

  document.getElementById("macro-calories").textContent = `${Math.round(data.macros_per_serving.calories || 0)} kcal`;
  document.getElementById("macro-protein").textContent = `${data.macros_per_serving.protein_g || 0}g`;
  document.getElementById("macro-fiber").textContent = `${data.macros_per_serving.fiber_g || 0}g`;
  document.getElementById("macro-gl").textContent = String(data.macros_per_serving.glycemic_load ?? 0);

  const allergenBanner = document.getElementById("allergen-safeguard-banner");
  allergenBanner.textContent = "";
  if (data.allergens_strictly_avoided && data.allergens_strictly_avoided.length > 0) {
    allergenBanner.style.display = "flex";
    const strongLabel = document.createElement("strong");
    strongLabel.textContent = "Allergen Guardrail:";
    allergenBanner.append(
      document.createTextNode("🛡️ "),
      strongLabel,
      document.createTextNode(` Strictly excluded: ${data.allergens_strictly_avoided.join(", ")}`)
    );
  } else {
    allergenBanner.style.display = "none";
  }

  document.getElementById("consensus-summary-text").textContent = data.overall_consensus_reasoning;

  const ingList = document.getElementById("ingredients-list");
  ingList.textContent = "";
  (data.shared_base_ingredients || []).forEach(i => {
    const li = document.createElement("li");
    const strong = document.createElement("strong");
    strong.textContent = i.name;
    li.append(strong, document.createTextNode(` — ${i.amount} ${i.unit}`));
    ingList.appendChild(li);
  });

  const rationalesContainer = document.getElementById("clinical-rationales-container");
  rationalesContainer.textContent = "";
  (data.member_customizations || []).forEach(item => {
    const card = document.createElement("div");
    card.className = "clinical-card";

    const h4 = document.createElement("h4");
    const nameSpan = document.createElement("span");
    nameSpan.textContent = `👤 ${item.member_name}`;
    const targetSpan = document.createElement("span");
    targetSpan.style.fontSize = "11.5px";
    targetSpan.style.color = "var(--emerald)";
    targetSpan.textContent = `Target: ${(item.targeted_biomarkers || []).join(", ")}`;
    h4.append(nameSpan, targetSpan);

    const p = document.createElement("p");
    p.textContent = item.mechanism;

    card.append(h4, p);
    if (item.suggested_custom_finish) {
      const badge = document.createElement("div");
      badge.className = "topping-badge";
      badge.textContent = `✨ Finish: ${item.suggested_custom_finish}`;
      card.appendChild(badge);
    }
    rationalesContainer.appendChild(card);
  });

  container.scrollIntoView({ behavior: "smooth", block: "nearest" });
}
