// Multilingual Translations
const translations = {
  en: {
    dashboard: "Dashboard",
    logout: "Logout",
    book: "Book Appointment",
    cancel: "Cancel",
    join: "Join Consultation",
    welcome: "Welcome back",
  },
  es: {
    dashboard: "Panel de control",
    logout: "Cerrar Sesión",
    book: "Reservar Cita",
    cancel: "Cancelar",
    join: "Unirse a la Consulta",
    welcome: "Bienvenido de nuevo",
  }
};

let currentLang = 'en';

function toggleLang() {
  currentLang = currentLang === 'en' ? 'es' : 'en';
  document.getElementById('langToggleBtn').innerText = currentLang === 'en' ? 'ES' : 'EN';
  applyTranslations();
  showToast("Language changed to " + (currentLang === 'en' ? 'English' : 'Español'));
}

function applyTranslations() {
  document.querySelectorAll('[data-lang-key]').forEach(el => {
    const key = el.getAttribute('data-lang-key');
    if (translations[currentLang] && translations[currentLang][key]) {
      el.innerText = translations[currentLang][key];
    }
  });
}

document.addEventListener('DOMContentLoaded', applyTranslations);

// UI Helpers (Loader & Toasts)
function showLoader() {
  const loader = document.getElementById('global-loader');
  if(loader) loader.classList.remove('hidden');
}

function hideLoader() {
  const loader = document.getElementById('global-loader');
  if(loader) loader.classList.add('hidden');
}

function showToast(message, type = 'success') {
  let container = document.getElementById('toast-container');
  if (!container) {
    container = document.createElement('div');
    container.id = 'toast-container';
    document.body.appendChild(container);
  }
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.innerText = message;
  container.appendChild(toast);
  setTimeout(() => {
    toast.remove();
  }, 4000);
}

// Auth Helpers
function getToken() {
  const t = localStorage.getItem('token');
  // strict check to avoid bugs where "undefined" is saved as a literal string
  if (t === 'undefined' || t === 'null') return null;
  return t; 
}

function setAuth(token, user) {
  if (token) {
    localStorage.setItem('token', token);
    localStorage.setItem('user', JSON.stringify(user));
  }
}

function getUser() {
  const u = localStorage.getItem('user');
  if (u === 'undefined' || u === 'null') return null;
  return u ? JSON.parse(u) : null;
}

function logout() {
  localStorage.clear();
  window.location.href = '/';
}

// API Wrapper
async function apiCall(endpoint, method = 'GET', body = null) {
  showLoader();
  try {
    const headers = { 'Content-Type': 'application/json' };
    const token = getToken();
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    const options = { method, headers };
    if (body) options.body = JSON.stringify(body);

    const res = await fetch(endpoint, options);
    
    hideLoader();

    if (res.status === 401) {
      showToast("Session expired or Invalid Auth. Please login again.", "error");
      localStorage.clear();
      setTimeout(() => { window.location.href = '/'; }, 1500);
      throw new Error("Unauthorized");
    }

    if (!res.ok) {
      let err;
      try {
        err = await res.json();
      } catch (e) {
        throw new Error("API Error");
      }
      throw new Error(err.detail || "API Error");
    }
    
    // Some routes might return pure text or no body (e.g. 204), handle safely
    const contentType = res.headers.get("content-type");
    if (contentType && contentType.indexOf("application/json") !== -1) {
      return res.json();
    } else {
      return await res.text();
    }
  } catch (error) {
    hideLoader();
    throw error;
  }
}

// ==========================================
// MULTILINGUAL TRANSLATION MODULE
// ==========================================

const SUPPORTED_LANGUAGES = [
  { code: 'auto', name: '🔍 Auto-Detect' },
  { code: 'en', name: '🇬🇧 English' },
  { code: 'hi', name: '🇮🇳 Hindi (हिन्दी)' },
  { code: 'mr', name: '🇮🇳 Marathi (मराठी)' },
  { code: 'ta', name: '🇮🇳 Tamil (தமிழ்)' },
  { code: 'te', name: '🇮🇳 Telugu (తెలుగు)' },
  { code: 'bn', name: '🇮🇳 Bengali (বাংলা)' },
  { code: 'gu', name: '🇮🇳 Gujarati (ગુજરાતી)' },
  { code: 'kn', name: '🇮🇳 Kannada (ಕನ್ನಡ)' },
  { code: 'ml', name: '🇮🇳 Malayalam (മലയാളം)' },
  { code: 'pa', name: '🇮🇳 Punjabi (ਪੰਜਾਬੀ)' },
  { code: 'ur', name: '🇵🇰 Urdu (اردو)' },
  { code: 'es', name: '🇪🇸 Spanish' },
  { code: 'fr', name: '🇫🇷 French' },
  { code: 'ar', name: '🇸🇦 Arabic' },
];

// Target languages (no auto-detect)
const TARGET_LANGUAGES = SUPPORTED_LANGUAGES.filter(l => l.code !== 'auto');

/**
 * Call the backend translate API
 */
async function translateText(text, sourceLang = 'auto', targetLang = 'en') {
  if (!text || !text.trim()) {
    showToast('Please enter text to translate.', 'error');
    return null;
  }
  try {
    const res = await apiCall('/api/translate', 'POST', {
      text: text.trim(),
      source_lang: sourceLang,
      target_lang: targetLang
    });
    return res;
  } catch (e) {
    showToast('Translation failed. Using original text.', 'error');
    return { original_text: text, translated_text: text, detected_lang: sourceLang, target_lang: targetLang, success: false };
  }
}

/**
 * Start browser speech recognition and fill a target input
 */
function startSpeechRecognition(targetInputId, langCode = 'auto') {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) {
    showToast('Speech recognition not supported in this browser. Use Chrome.', 'error');
    return;
  }

  const recognition = new SpeechRecognition();
  recognition.continuous = false;
  recognition.interimResults = false;

  // Map language codes to BCP 47 for speech recognition
  const langMap = {
    'auto': '', 'en': 'en-US', 'hi': 'hi-IN', 'mr': 'mr-IN',
    'ta': 'ta-IN', 'te': 'te-IN', 'bn': 'bn-IN', 'gu': 'gu-IN',
    'kn': 'kn-IN', 'ml': 'ml-IN', 'pa': 'pa-IN', 'ur': 'ur-PK',
    'es': 'es-ES', 'fr': 'fr-FR', 'ar': 'ar-SA'
  };
  if (langCode !== 'auto' && langMap[langCode]) {
    recognition.lang = langMap[langCode];
  }

  const micBtn = document.querySelector(`[data-mic-for="${targetInputId}"]`);
  if (micBtn) {
    micBtn.classList.add('mic-active');
    micBtn.innerHTML = '⏺️';
  }

  recognition.onresult = function(event) {
    const transcript = event.results[0][0].transcript;
    const targetInput = document.getElementById(targetInputId);
    if (targetInput) {
      targetInput.value = (targetInput.value ? targetInput.value + ' ' : '') + transcript;
    }
    showToast('Voice captured successfully!');
  };

  recognition.onerror = function(event) {
    console.error('Speech recognition error:', event.error);
    if (event.error === 'not-allowed') {
      showToast('Microphone access denied. Please allow microphone.', 'error');
    } else {
      showToast('Voice input error: ' + event.error, 'error');
    }
  };

  recognition.onend = function() {
    if (micBtn) {
      micBtn.classList.remove('mic-active');
      micBtn.innerHTML = '🎤';
    }
  };

  recognition.start();
  showToast('Listening... Speak now.');
}

/**
 * Build and inject translation widget HTML into a container
 * @param {string} containerId - ID of the div to inject the widget into
 * @param {string} textareaId - ID of the textarea that holds the source text
 * @param {string} fillTargetId - ID of the input to auto-fill with translated text (can be same as textareaId)
 */
function buildTranslateWidget(containerId, textareaId, fillTargetId) {
  const container = document.getElementById(containerId);
  if (!container) return;

  const sourceOptions = SUPPORTED_LANGUAGES.map(l => `<option value="${l.code}">${l.name}</option>`).join('');
  const targetOptions = TARGET_LANGUAGES.map(l => `<option value="${l.code}" ${l.code === 'en' ? 'selected' : ''}>${l.name}</option>`).join('');

  container.innerHTML = `
    <div class="translate-panel">
      <div class="translate-header">
        <span class="translate-icon">🌐</span>
        <span class="translate-title">Multilingual Translation</span>
      </div>
      <div class="translate-controls">
        <div class="lang-select-group">
          <label>From</label>
          <select id="${containerId}_srcLang" class="lang-select">${sourceOptions}</select>
        </div>
        <span class="translate-arrow">→</span>
        <div class="lang-select-group">
          <label>To</label>
          <select id="${containerId}_tgtLang" class="lang-select">${targetOptions}</select>
        </div>
      </div>
      <div class="translate-actions">
        <button type="button" class="translate-btn" onclick="doTranslate('${containerId}', '${textareaId}', '${fillTargetId}')">
          🌐 Translate
        </button>
        <button type="button" class="mic-btn" data-mic-for="${textareaId}" onclick="doVoiceInput('${containerId}', '${textareaId}')">
          🎤
        </button>
      </div>
      <div id="${containerId}_result" class="translate-result hidden">
        <div class="translate-result-row">
          <div class="translate-original">
            <span class="result-label">Original</span>
            <p id="${containerId}_origText"></p>
          </div>
          <div class="translate-translated">
            <span class="result-label">Translated</span>
            <p id="${containerId}_transText"></p>
          </div>
        </div>
        <div class="translate-meta" id="${containerId}_meta"></div>
      </div>
    </div>
  `;
}

/**
 * Execute translation using the widget controls
 */
async function doTranslate(containerId, textareaId, fillTargetId) {
  const text = document.getElementById(textareaId)?.value;
  const srcLang = document.getElementById(`${containerId}_srcLang`)?.value || 'auto';
  const tgtLang = document.getElementById(`${containerId}_tgtLang`)?.value || 'en';

  const result = await translateText(text, srcLang, tgtLang);
  if (!result) return;

  // Show result
  const resultDiv = document.getElementById(`${containerId}_result`);
  if (resultDiv) resultDiv.classList.remove('hidden');

  const origEl = document.getElementById(`${containerId}_origText`);
  const transEl = document.getElementById(`${containerId}_transText`);
  const metaEl = document.getElementById(`${containerId}_meta`);

  if (origEl) origEl.innerText = result.original_text;
  if (transEl) transEl.innerText = result.translated_text;

  const langName = SUPPORTED_LANGUAGES.find(l => l.code === result.detected_lang)?.name || result.detected_lang;
  if (metaEl) {
    metaEl.innerHTML = result.success
      ? `✅ Detected: <strong>${langName}</strong> → Translated to <strong>${result.target_lang.toUpperCase()}</strong>`
      : `⚠️ Translation unavailable. Showing original text.`;
  }

  // Auto-fill target
  if (fillTargetId && result.success) {
    const fillEl = document.getElementById(fillTargetId);
    if (fillEl) {
      fillEl.value = result.translated_text;
      showToast('Translated text auto-filled!');
    }
  }
}

/**
 * Voice input using speech recognition, respects selected source language
 */
function doVoiceInput(containerId, textareaId) {
  const srcLang = document.getElementById(`${containerId}_srcLang`)?.value || 'auto';
  startSpeechRecognition(textareaId, srcLang);
}

