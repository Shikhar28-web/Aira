/* ═══════════════════════════════════════════
   APNA SAATHI — app.js
   All frontend logic: theme, i18n, chat, TTS, STT
═══════════════════════════════════════════ */

// ══════════════════════════════
// I18N STRINGS
// ══════════════════════════════
const I18N = {
  en: {
    appName:        "Apna Saathi",
    welcome_title:  "Apna Saathi",
    welcome_tagline:"Your AI conversation companion",
    welcome_sub:    "Create conversations with personalized AI personas. Talk naturally in your language.",
    welcome_btn:    "Get Started",
    intro_scene1_title: "Need someone to talk to?",
    intro_scene1_sub: "We're here to listen.",
    intro_scene2_title: "Just speak naturally",
    intro_scene3_left: "You said...",
    intro_scene3_right: "Apna Saathi responds",
    intro_scene4_title: "Apna Saathi",
    intro_scene4_sub: "Your AI companion. Always available.",
    intro_enter: "Enter Apna Saathi",
    intro_skip: "Skip",
    step1_badge:    "Step 1 / 2",
    step2_badge:    "Step 2 / 2",
    setup_title:    "Create a Persona",
    setup_sub:      "Set up a personalized AI companion to chat with.",
    lbl_name:       "What's their name?",
    ph_name:        "Mom, Dad, Priya, Rajan…",
    lbl_rel:        "What's the relationship?",
    rel_choose:     "-- Select --",
    rel_mother:     "Mother",
    rel_father:     "Father",
    rel_partner:    "Partner / Spouse",
    rel_bestfriend: "Best Friend",
    rel_sibling:    "Brother / Sister",
    rel_grand:      "Grandparent",
    rel_child:      "Child",
    rel_friend:     "Friend",
    lbl_lang:       "Language",
    lbl_voice:      "Voice type",
    voice_f:        "Female",
    voice_m:        "Male",
    btn_back:       "← Back",
    btn_next:       "Next",
    train_title:    "Customize the Persona",
    train_sub:      "Add details to make conversations more personalized.",
    lbl_nickname:   "What do they call you?",
    ph_nickname:    "Dear, Sweetheart, Beta, Champ…",
    lbl_personality:"What's their personality like?",
    lbl_phrases:    "Their common phrases",
    ph_phrases:     "e.g. 'Have you eaten?', 'Take care'…",
    lbl_wisdom:     "Something they always say",
    ph_wisdom:      "'Work smart, not just hard'",
    audio_title:    "Upload voice sample (Optional)",
    audio_sub:      "Helps the AI learn their speaking style",
    btn_start:      "Start Chatting ✦",
    online:         "Online",
    ph_chat:        "Type your message…",
    toast_noname:   "Please enter a name",
    toast_norel:    "Please select a relationship",
    toast_uploading:"Uploading recording…",
    toast_uploaded: "Recording uploaded ✓",
    toast_learning: "Learning voice style…",
    toast_recording:"Listening… 🎙️",
    toast_processing:"Processing…",
    toast_heard:    "Heard: ",
    toast_nothead:  "Couldn't understand, please try again",
    toast_micfail:  "Microphone access denied",
    toast_tts_fail: "Could not play audio",
    toast_reset:    "Create a new profile?",
    sys_start:      "Start your conversation with",
    err_api:        "Server error. Please check your connection.",
    // Landing page
    landing_badge:      "AI-Powered Companion",
    landing_hero_title: "Your Personal AI<br/>Conversation Partner",
    landing_hero_sub:   "Create custom AI personas and have natural conversations in Hindi, English, or 10+ Indian languages.",
    landing_cta:        "Get Started",
    landing_learn:      "Learn More",
    landing_features:   "Features",
    landing_why:        "Why Apna Saathi?",
    landing_why_sub:    "Simple, smart, and speaks your language",
    feat_voice:         "Voice Conversations",
    feat_voice_desc:    "Speak naturally in your preferred language. Our AI understands context and nuance.",
    feat_persona:       "Custom Personas",
    feat_persona_desc:  "Create personalized AI companions with their own personality and speaking style.",
    feat_support:       "Always Available",
    feat_support_desc:  "Chat anytime, anywhere. Your AI companion is available 24/7.",
    feat_privacy:       "Private & Secure",
    feat_privacy_desc:  "Your conversations stay private. We respect your data and privacy.",
    landing_steps:      "Simple Steps",
    landing_how:        "How It Works",
    landing_how_sub:    "Get started in minutes",
    step1_title:        "Create a Profile",
    step1_desc:         "Add basic details like name and relationship type.",
    step2_title:        "Customize Personality",
    step2_desc:         "Add phrases, traits, and speaking style preferences.",
    step3_title:        "Start Chatting",
    step3_desc:         "Begin your conversation via voice or text.",
    landing_about:      "About Us",
    landing_about_title:"About Apna Saathi",
    landing_about_p1:   "Apna Saathi is an AI-powered conversation platform that lets you create and chat with personalized AI companions. Built using Sarvam AI's language models, it supports natural conversations in multiple Indian languages.",
    landing_about_p2:   "Whether you want a study buddy, a conversation partner to practice a language, or simply someone to talk to — Apna Saathi is designed to be helpful, friendly, and always available.",
    landing_cta2:       "Ready to Start?",
    landing_cta2_sub:   "Create your first AI companion today.",
    landing_begin:      "Begin Now",
    landing_tagline:    "Your AI companion. Always available.",
    landing_copy:       "© 2026 Apna Saathi. Made with ❤️ in India.",
  },
  hi: {
    appName:        "Apna Saathi",
    welcome_title:  "Apna Saathi",
    welcome_tagline:"Aapka AI conversation partner",
    welcome_sub:    "Apni pasand ka AI persona banao aur naturally baat karo — apni language mein.",
    welcome_btn:    "Shuru Karein",
    intro_scene1_title: "Kisi se baat karni hai?",
    intro_scene1_sub: "Hum sun rahe hain.",
    intro_scene2_title: "Bas naturally bolo",
    intro_scene3_left: "Aapne kaha...",
    intro_scene3_right: "Apna Saathi bolta hai",
    intro_scene4_title: "Apna Saathi",
    intro_scene4_sub: "Aapka AI companion. Hamesha available.",
    intro_enter: "Apna Saathi mein aao",
    intro_skip: "Skip",
    step1_badge:    "Step 1 / 2",
    step2_badge:    "Step 2 / 2",
    setup_title:    "Persona banao",
    setup_sub:      "Ek personalized AI companion setup karo.",
    lbl_name:       "Unka naam kya hai?",
    ph_name:        "Maa, Papa, Priya, Rajan…",
    lbl_rel:        "Relationship kya hai?",
    rel_choose:     "-- Select karo --",
    rel_mother:     "Mother (Maa)",
    rel_father:     "Father (Papa)",
    rel_partner:    "Partner / Spouse",
    rel_bestfriend: "Best Friend",
    rel_sibling:    "Bhai / Behen",
    rel_grand:      "Grandparent",
    rel_child:      "Child",
    rel_friend:     "Friend",
    lbl_lang:       "Language",
    lbl_voice:      "Voice type",
    voice_f:        "Female",
    voice_m:        "Male",
    btn_back:       "← Back",
    btn_next:       "Next",
    train_title:    "Persona customize karo",
    train_sub:      "Details add karo taaki conversation better ho.",
    lbl_nickname:   "Woh aapko kya bulaaate hain?",
    ph_nickname:    "Beta, Jaan, Champ, Dear…",
    lbl_personality:"Unka nature kaisa hai?",
    lbl_phrases:    "Unke common phrases",
    ph_phrases:     "e.g. 'Khana khaya?', 'Take care'…",
    lbl_wisdom:     "Woh hamesha kya kehte hain?",
    ph_wisdom:      "'Smart work karo, sirf hard work nahi'",
    audio_title:    "Voice sample upload karo (Optional)",
    audio_sub:      "AI ko unki speaking style samajhne mein help karega",
    btn_start:      "Chat Shuru Karo ✦",
    online:         "Online",
    ph_chat:        "Apna message likho…",
    toast_noname:   "Please naam daalo",
    toast_norel:    "Relationship select karo",
    toast_uploading:"Recording upload ho rahi hai…",
    toast_uploaded: "Recording upload ho gayi ✓",
    toast_learning: "Voice style seekh raha hai…",
    toast_recording:"Sun raha hoon… 🎙️",
    toast_processing:"Process ho raha hai…",
    toast_heard:    "Suna: ",
    toast_nothead:  "Samajh nahi aaya, dobara try karo",
    toast_micfail:  "Microphone access nahi mila",
    toast_tts_fail: "Audio play nahi ho raha",
    toast_reset:    "Naya profile banana hai?",
    sys_start:      "ke saath baat shuru karo",
    err_api:        "Server error. Connection check karo.",
    // Landing page
    landing_badge:      "AI-Powered Companion",
    landing_hero_title: "Aapka Personal AI<br/>Conversation Partner",
    landing_hero_sub:   "Custom AI personas banao aur natural conversations karo — Hindi, English, ya 10+ Indian languages mein.",
    landing_cta:        "Shuru Karo",
    landing_learn:      "Aur Jaano",
    landing_features:   "Features",
    landing_why:        "Apna Saathi kyun?",
    landing_why_sub:    "Simple, smart, aur aapki language mein baat karta hai",
    feat_voice:         "Voice Conversations",
    feat_voice_desc:    "Apni language mein naturally bolo. AI context aur nuance samajhta hai.",
    feat_persona:       "Custom Personas",
    feat_persona_desc:  "Apna personalized AI companion banao — unki apni personality ke saath.",
    feat_support:       "Hamesha Available",
    feat_support_desc:  "Kabhi bhi chat karo. Aapka AI companion 24/7 available hai.",
    feat_privacy:       "Private & Secure",
    feat_privacy_desc:  "Aapki conversations private hain. Hum aapki privacy respect karte hain.",
    landing_steps:      "Simple Steps",
    landing_how:        "Kaise Kaam Karta Hai",
    landing_how_sub:    "Minutes mein shuru ho jao",
    step1_title:        "Profile Banao",
    step1_desc:         "Basic details add karo jaise naam aur relationship.",
    step2_title:        "Personality Customize Karo",
    step2_desc:         "Phrases, traits, aur speaking style add karo.",
    step3_title:        "Chat Shuru Karo",
    step3_desc:         "Voice ya text se baat karo.",
    landing_about:      "About Us",
    landing_about_title:"Apna Saathi ke baare mein",
    landing_about_p1:   "Apna Saathi ek AI-powered conversation platform hai jahan aap personalized AI companions bana sakte ho aur unse chat kar sakte ho. Sarvam AI ke language models se bana hai, multiple Indian languages support karta hai.",
    landing_about_p2:   "Chahe aapko study buddy chahiye, language practice partner, ya bas kisi se baat karni ho — Apna Saathi helpful, friendly, aur hamesha available hai.",
    landing_cta2:       "Ready ho?",
    landing_cta2_sub:   "Aaj apna pehla AI companion banao.",
    landing_begin:      "Shuru Karo",
    landing_tagline:    "Aapka AI companion. Hamesha available.",
    landing_copy:       "© 2026 Apna Saathi. Made with ❤️ in India.",
  },
  hinglish: {
    appName:        "Apna Saathi",
    welcome_title:  "Apna Saathi",
    welcome_tagline:"Your personal AI chat buddy",
    welcome_sub:    "Create your own AI companion and have chill conversations — in your style!",
    welcome_btn:    "Let's Go!",
    intro_scene1_title: "Baat karna hai kisi se?",
    intro_scene1_sub: "We're listening, yaar.",
    intro_scene2_title: "Bas bol do jo mann mein hai",
    intro_scene3_left: "You said...",
    intro_scene3_right: "Apna Saathi says",
    intro_scene4_title: "Apna Saathi",
    intro_scene4_sub: "Your AI buddy. Always here for you.",
    intro_enter: "Let's enter!",
    intro_skip: "Skip",
    step1_badge:    "Step 1 / 2",
    step2_badge:    "Step 2 / 2",
    setup_title:    "Create your buddy",
    setup_sub:      "Setup a personalized AI companion.",
    lbl_name:       "Naam kya rakhen?",
    ph_name:        "Mom, Dad, Priya, Rajan…",
    lbl_rel:        "Rishta kya hai?",
    rel_choose:     "-- Choose one --",
    rel_mother:     "Mom",
    rel_father:     "Dad",
    rel_partner:    "Partner",
    rel_bestfriend: "Bestie",
    rel_sibling:    "Bro / Sis",
    rel_grand:      "Grandparent",
    rel_child:      "Child",
    rel_friend:     "Friend",
    lbl_lang:       "Language",
    lbl_voice:      "Voice",
    voice_f:        "Female",
    voice_m:        "Male",
    btn_back:       "← Back",
    btn_next:       "Next →",
    train_title:    "Add personality vibes",
    train_sub:      "More details = better conversations!",
    lbl_nickname:   "What do they call you?",
    ph_nickname:    "Beta, Jaan, Buddy, Champ…",
    lbl_personality:"Personality kaise hai?",
    lbl_phrases:    "Their signature phrases",
    ph_phrases:     "e.g. 'Khana khaya?', 'Chill kar'…",
    lbl_wisdom:     "Something they always say",
    ph_wisdom:      "'Tension mat le, sab hoga'",
    audio_title:    "Upload voice sample (Optional)",
    audio_sub:      "Helps make it more realistic",
    btn_start:      "Let's Chat! ✦",
    online:         "Online",
    ph_chat:        "Say something…",
    toast_noname:   "Arre naam toh daal!",
    toast_norel:    "Relationship select karo na",
    toast_uploading:"Uploading…",
    toast_uploaded: "Uploaded! ✓",
    toast_learning: "Learning the vibe…",
    toast_recording:"Listening… 🎙️",
    toast_processing:"Hold on…",
    toast_heard:    "Got it: ",
    toast_nothead:  "Didn't catch that, try again?",
    toast_micfail:  "Mic access denied yaar",
    toast_tts_fail: "Audio not working",
    toast_reset:    "Start fresh?",
    sys_start:      "Start chatting with",
    err_api:        "Server not responding. Check connection!",
    // Landing page
    landing_badge:      "AI-Powered Buddy",
    landing_hero_title: "Your Personal AI<br/>Chat Companion",
    landing_hero_sub:   "Create custom AI buddies and chat naturally — in Hindi, English, or mix it up!",
    landing_cta:        "Let's Go!",
    landing_learn:      "Know More",
    landing_features:   "Features",
    landing_why:        "Why Apna Saathi?",
    landing_why_sub:    "Simple, smart, and speaks your language",
    feat_voice:         "Voice Chat",
    feat_voice_desc:    "Talk naturally in your preferred language. AI gets the context.",
    feat_persona:       "Custom Buddies",
    feat_persona_desc:  "Create AI companions with their own personality and vibe.",
    feat_support:       "Always Available",
    feat_support_desc:  "Chat anytime. Your AI buddy is 24/7 available.",
    feat_privacy:       "Private & Safe",
    feat_privacy_desc:  "Your chats stay private. Privacy comes first.",
    landing_steps:      "Easy Steps",
    landing_how:        "How It Works",
    landing_how_sub:    "Get started in minutes",
    step1_title:        "Create Profile",
    step1_desc:         "Add name and relationship — basic stuff.",
    step2_title:        "Add Personality",
    step2_desc:         "Throw in some phrases and traits.",
    step3_title:        "Start Chatting",
    step3_desc:         "Voice or text — your choice!",
    landing_about:      "About",
    landing_about_title:"About Apna Saathi",
    landing_about_p1:   "Apna Saathi is an AI chat platform where you can create personalized AI companions and have real conversations. Built with Sarvam AI — supports Hindi, English, and many more Indian languages.",
    landing_about_p2:   "Need a study partner, someone to practice language with, or just want to chat? Apna Saathi is helpful, friendly, and always there.",
    landing_cta2:       "Ready to try?",
    landing_cta2_sub:   "Create your first AI buddy now.",
    landing_begin:      "Start Now",
    landing_tagline:    "Your AI buddy. Always here.",
    landing_copy:       "© 2026 Apna Saathi. Made with ❤️ in India.",
  },
};

// ══════════════════════════════
// STATE
// ══════════════════════════════
let uiLang = 'en';
let theme = 'dark';
let profile = {};
let chatHistory = [];
let systemPrompt = '';
let uploadedAudioFile = null;
let audioTranscript = '';
let profileVoiceId = '';
let cloneStatus = 'off';
let selectedPersonality = 'warm and caring';
let isRecording = false;
let mediaRecorder = null;
let audioChunks = [];
let toastTimer = null;
let introTimers = [];
let pendingAudioUrl = null;
let audioUnlockHandlersBound = false;
let currentUser = null;
let currentCompanionId = null;
let companions = [];
let isCompanionOnboarding = false;

function dbLanguageToUiCode(language) {
  const low = (language || '').toLowerCase();
  if (low === 'english') return 'en-IN';
  if (low === 'hindi') return 'hi-IN';
  return 'hi-IN';
}

function uiCodeToDbLanguage(code) {
  if (code === 'en-IN') return 'english';
  if (code === 'hi-IN') return 'hindi';
  return 'hinglish';
}

// Voice hint map used by backend TTS selection.
const VOICE_MAP = {
  'hi-IN': { female: 'female', male: 'male' },
  'bn-IN': { female: 'female', male: 'male' },
  'ta-IN': { female: 'female', male: 'male' },
  'te-IN': { female: 'female', male: 'male' },
  'kn-IN': { female: 'female', male: 'male' },
  'ml-IN': { female: 'female', male: 'male' },
  'mr-IN': { female: 'female', male: 'male' },
  'gu-IN': { female: 'female', male: 'male' },
  'pa-IN': { female: 'female', male: 'male' },
  'en-IN': { female: 'female', male: 'male' },
};
const LANG_SHORT = {
  'hi-IN':'HI','bn-IN':'BN','ta-IN':'TA','te-IN':'TE','kn-IN':'KN',
  'ml-IN':'ML','mr-IN':'MR','gu-IN':'GU','pa-IN':'PB','en-IN':'EN',
};

// ══════════════════════════════
// THEME
// ══════════════════════════════
function toggleTheme() {
  theme = theme === 'dark' ? 'light' : 'dark';
  document.documentElement.setAttribute('data-theme', theme);
  localStorage.setItem('saathi_theme', theme);
}

function initTheme() {
  const saved = localStorage.getItem('saathi_theme') || 'dark';
  theme = saved;
  document.documentElement.setAttribute('data-theme', theme);
}

// ══════════════════════════════
// I18N
// ══════════════════════════════
const LANGUAGES = ['en', 'hi', 'hinglish'];
const LANG_LABELS = { en: 'EN', hi: 'हि', hinglish: 'HiEn' };

function t(key) {
  return I18N[uiLang][key] || I18N['en'][key] || key;
}

function setLanguage(lang) {
  if (LANGUAGES.includes(lang)) {
    uiLang = lang;
    updateLangSelector();
    applyI18n();
    localStorage.setItem('saathi_ui_lang', uiLang);
  }
}

function toggleUiLang() {
  // Cycle through languages
  const currentIndex = LANGUAGES.indexOf(uiLang);
  const nextIndex = (currentIndex + 1) % LANGUAGES.length;
  setLanguage(LANGUAGES[nextIndex]);
}

function updateLangSelector() {
  const selector = document.getElementById('langSelector');
  const label = document.getElementById('langUiLabel');
  if (selector) selector.value = uiLang;
  if (label) label.textContent = LANG_LABELS[uiLang];
}

function initUiLang() {
  const saved = localStorage.getItem('saathi_ui_lang') || 'en';
  uiLang = LANGUAGES.includes(saved) ? saved : 'en';
  updateLangSelector();
  applyI18n();
}

function applyI18n() {
  // text content
  document.querySelectorAll('[data-i18n]').forEach(el => {
    const key = el.getAttribute('data-i18n');
    if (I18N[uiLang][key]) {
      // Handle HTML content for strings with <br/>
      if (I18N[uiLang][key].includes('<br')) {
        el.innerHTML = I18N[uiLang][key];
      } else {
        el.textContent = I18N[uiLang][key];
      }
    }
  });
  // placeholders
  document.querySelectorAll('[data-i18n-ph]').forEach(el => {
    const key = el.getAttribute('data-i18n-ph');
    if (I18N[uiLang][key]) el.placeholder = I18N[uiLang][key];
  });

  updateCloneBadge(cloneStatus);
}

function cloneBadgeLabel(state) {
  const labels = {
    off: {
      en: 'Clone Off',
      hi: 'Clone Band',
      hinglish: 'Clone Off',
    },
    warming: {
      en: 'Clone Warming',
      hi: 'Clone Warm-up',
      hinglish: 'Clone Warm-up',
    },
    on: {
      en: 'Clone Active',
      hi: 'Clone Active',
      hinglish: 'Clone Active',
    },
  };
  const lang = LANGUAGES.includes(uiLang) ? uiLang : 'en';
  return (labels[state] && labels[state][lang]) || labels.off[lang];
}

function updateCloneBadge(state) {
  const badge = document.getElementById('cloneStatusBadge');
  if (!badge) return;

  cloneStatus = state;
  badge.style.display = profileVoiceId ? 'inline-flex' : 'none';
  badge.classList.remove('clone-off', 'clone-warming', 'clone-on');

  if (!profileVoiceId) {
    badge.textContent = cloneBadgeLabel('off');
    return;
  }

  const normalized = ['off', 'warming', 'on'].includes(state) ? state : 'off';
  badge.classList.add(`clone-${normalized}`);
  badge.textContent = cloneBadgeLabel(normalized);
}

// ══════════════════════════════
// SCREEN NAV
// ══════════════════════════════
function showScreen(id) {
  document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
  const el = document.getElementById(id);
  const topbar = document.getElementById('topbar');
  if (topbar) topbar.style.display = id === 'introScreen' ? 'none' : 'flex';
  if (el) { 
    el.classList.add('active'); 
    // For scrollable screens, scroll to top
    if (id === 'landingScreen') {
      el.scrollTop = 0;
    } else {
      window.scrollTo(0, 0);
    }
  }
}

function clearIntroTimers() {
  introTimers.forEach(tid => clearTimeout(tid));
  introTimers = [];
}

function setIntroScene(index) {
  const scenes = ['introScene1', 'introScene2', 'introScene3', 'introScene4'];
  scenes.forEach((id, i) => {
    const el = document.getElementById(id);
    if (el) el.classList.toggle('active', i === index);
  });
}

function startIntroSequence() {
  showScreen('introScreen');
  clearIntroTimers();
  setIntroScene(0);

  const enterBtn = document.getElementById('introEnterBtn');
  if (enterBtn) enterBtn.classList.remove('show');

  introTimers.push(setTimeout(() => setIntroScene(1), 2600));
  introTimers.push(setTimeout(() => setIntroScene(2), 5200));
  introTimers.push(setTimeout(() => setIntroScene(3), 7800));
  introTimers.push(setTimeout(() => {
    if (enterBtn) enterBtn.classList.add('show');
  }, 9800));
}

function enterFromIntro() {
  clearIntroTimers();
  showScreen('landingScreen');
  initLandingAnimations();
}

function resetPersonaForm(prefillName = '') {
  document.getElementById('lovedName').value = prefillName;
  document.getElementById('relationship').value = '';
  document.getElementById('language').value = 'hi-IN';
  document.getElementById('voiceType').value = 'female';
  document.getElementById('q_nickname').value = '';
  document.getElementById('q_phrases').value = '';
  document.getElementById('q_wisdom').value = '';
  document.getElementById('audioFile').value = '';
  document.getElementById('audioFileTag').style.display = 'none';

  uploadedAudioFile = null;
  audioTranscript = '';
  profileVoiceId = '';
  selectedPersonality = 'warm and caring';
  document.querySelectorAll('.pers-chip').forEach((chip, i) => {
    chip.classList.toggle('selected', i === 0);
  });
}

function personalityToStyle(personality) {
  const p = (personality || '').toLowerCase();
  if (p.includes('strict') || p.includes('practical')) return 'formal';
  if (p.includes('support')) return 'supportive';
  if (p.includes('motivat')) return 'motivational';
  return 'casual';
}

async function openCompanionOnboarding(prefillName = '') {
  isCompanionOnboarding = true;
  resetPersonaForm(prefillName);
  showScreen('setupScreen');
}

async function handleGetStarted() {
  try {
    const res = await fetch('/api/companions');
    const data = await res.json().catch(() => ({}));
    const rows = (res.ok && data.ok && Array.isArray(data.companions)) ? data.companions : [];

    companions = rows;
    if (!companions.length) {
      await openCompanionOnboarding();
      return;
    }

    const first = companions[0];
    currentCompanionId = first.id;
    profile.name = first.name || 'Companion';
    profile.language = dbLanguageToUiCode(first.language);
    profile.voiceType = first.voice_type || 'female';
    profileVoiceId = first.profile_voice_id || '';
    profile.nickname = (currentUser && currentUser.username) ? currentUser.username : 'friend';

    setupChatUI();
    showScreen('chatScreen');
  } catch (_) {
    await openCompanionOnboarding();
  }
}

// ══════════════════════════════
// SETUP STEP 1
// ══════════════════════════════
function goToTraining() {
  const name = document.getElementById('lovedName').value.trim();
  const rel  = document.getElementById('relationship').value;
  if (!name) { showToast(t('toast_noname')); return; }
  if (!rel)  { showToast(t('toast_norel')); return; }

  profile.name         = name;
  profile.relationship = rel;
  profile.language     = document.getElementById('language').value;
  profile.voiceType    = document.getElementById('voiceType').value;
  showScreen('trainingScreen');
}

// ══════════════════════════════
// PERSONALITY CHIP
// ══════════════════════════════
function selectPersonality(el) {
  document.querySelectorAll('.pers-chip').forEach(c => c.classList.remove('selected'));
  el.classList.add('selected');
  selectedPersonality = el.getAttribute('data-val');
}

// ══════════════════════════════
// AUDIO UPLOAD
// ══════════════════════════════
function handleAudioUpload(e) {
  const file = e.target.files[0];
  if (!file) return;
  uploadedAudioFile = file;
  document.getElementById('audioFileName').textContent = file.name;
  document.getElementById('audioFileTag').style.display = 'inline-flex';
  showToast(t('toast_uploaded'));
}

function removeAudio(e) {
  e.stopPropagation();
  uploadedAudioFile = null;
  audioTranscript = '';
  profileVoiceId = '';
  updateCloneBadge('off');
  document.getElementById('audioFile').value = '';
  document.getElementById('audioFileTag').style.display = 'none';
}

// ══════════════════════════════
// START CHAT (Step 2 → Chat)
// ══════════════════════════════
async function startChat() {
  const btn = document.getElementById('startChatBtn');
  btn.disabled = true;
  document.querySelector('#startChatBtn span').textContent = '…';

  profile.nickname    = document.getElementById('q_nickname').value.trim() || 'beta';
  profile.personality = selectedPersonality;
  profile.phrases     = document.getElementById('q_phrases').value.trim();
  profile.wisdom      = document.getElementById('q_wisdom').value.trim();

  // Transcribe uploaded audio
  if (uploadedAudioFile) {
    const status = document.getElementById('transcribeStatus');
    status.textContent = t('toast_learning');
    status.style.display = 'block';
    try {
      const fd = new FormData();
      fd.append('audio', uploadedAudioFile, uploadedAudioFile.name);
      fd.append('language_code', profile.language);
      const res = await fetch('/api/transcribe_profile_audio', { method: 'POST', body: fd });
      const data = await res.json();
      if (data.ok) {
        profileVoiceId = data.profile_voice_id || '';
        updateCloneBadge(profileVoiceId ? 'warming' : 'off');
        if (data.transcript) audioTranscript = data.transcript;
        status.textContent = '✓ ' + (uiLang === 'hi' ? 'Voice sample save ho gaya!' : 'Voice sample saved!');
        await sleep(900);
      }
    } catch (err) {
      console.warn('Profile audio transcription failed', err);
    }
    status.style.display = 'none';
  }

  buildSystemPrompt();

  // Create companion from onboarding details before entering chat.
  try {
    const style = personalityToStyle(profile.personality);
    const langPref = uiCodeToDbLanguage(profile.language);
    const createRes = await fetch('/api/companions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name: profile.name,
        style,
        language: langPref,
        voice_type: profile.voiceType || 'female',
        profile_voice_id: profileVoiceId || null,
      }),
    });
    const createData = await createRes.json().catch(() => ({}));
    if (!createRes.ok || !createData.ok || !createData.companion) {
      showToast(createData.error || 'Could not create companion');
      btn.disabled = false;
      document.querySelector('#startChatBtn span').textContent = t('btn_start');
      return;
    }
    currentCompanionId = createData.companion.id;
  } catch (_) {
    showToast('Could not create companion');
    btn.disabled = false;
    document.querySelector('#startChatBtn span').textContent = t('btn_start');
    return;
  }

  isCompanionOnboarding = false;
  setupChatUI();
  showScreen('chatScreen');

  btn.disabled = false;
  document.querySelector('#startChatBtn span').textContent = t('btn_start');
}

// ══════════════════════════════
// SYSTEM PROMPT BUILDER
// ══════════════════════════════
function buildSystemPrompt() {
  const langCode = profile.language || 'hi-IN';
  const langMap = {
    'hi-IN':'Hindi','bn-IN':'Bangla','ta-IN':'Tamil','te-IN':'Telugu',
    'kn-IN':'Kannada','ml-IN':'Malayalam','mr-IN':'Marathi',
    'gu-IN':'Gujarati','pa-IN':'Punjabi','en-IN':'English',
  };
  const langName = langMap[langCode] || 'Hindi';

  let sp = `You are roleplaying as ${profile.name}, the ${profile.relationship} of the user named (they'll tell you).

CORE IDENTITY:
- Name: ${profile.name}
- Relationship to user: ${profile.relationship}
- Personality: ${profile.personality}

LANGUAGE:
- Respond ONLY in ${langName}. Natural spoken style, like texting — not formal or bookish.
- STRICT LENGTH: ALWAYS reply in 1 sentence. Absolute MAX is 2 short sentences. NEVER write more than 2 sentences.
- Match the user's style: casual Hinglish is fine if that's how they talk.

ACCURACY & HONESTY:
- When the user asks factual questions (study, tech, news, coding, maths, etc.), give accurate, concise answers.
- If you are not sure or information is missing, clearly say you are not sure instead of guessing.
- Do NOT confidently invent dates, numbers, or very specific facts.

HOW YOU ADDRESS THE USER:
- You always call them: "${profile.nickname}".
- Do NOT call them generic words like "bhai", "bro", "sir", "madam", "friend" etc. unless that exact word appears in their nickname or phrases above.

SPECIAL TRAITS:`;
  if (profile.phrases) sp += `\n- Common things you say (use them sometimes, not in every sentence): ${profile.phrases}`;
  if (profile.wisdom)  sp += `\n- Something you often repeat (but not in every reply): "${profile.wisdom}"`;
  if (audioTranscript) sp += `\n\nHere is a transcription of ${profile.name}'s actual recorded speech. Learn their overall tone, rhythm, and style from this (do NOT copy the exact same sentence over and over):\n"${audioTranscript}"`;

  sp += `\n\nRULES (NEVER break these):
1. You ARE ${profile.name}. Never say or imply you are an AI.
2. Be emotionally warm, present, caring as a real ${profile.relationship} would be. Your age, tone and slang must match being their ${profile.relationship} (e.g. a parent does not talk like a teenage friend).
3. CRITICAL LENGTH RULE: 1 sentence only. 2 sentences absolute max. NEVER write more. No lists, no bullets, no paragraphs.
4. Never show reasoning or planning. No <think> tags. Only speak as ${profile.name}.
5. When you respond, imitate the tone and rhythm from the transcript above, but vary your exact words so it sounds natural.
6. Use the special phrases and wisdom only occasionally. Do NOT repeat the same key phrase in every sentence or every message. Prefer to mention it once in a while.
7. Show love, concern, interest in the user's life.
8. If asked about something you don't know, respond as ${profile.name} would — naturally and in character.
9. If the user asks for help with exams, homework, or code, give the key answer in 1-2 sentences — stay in character.

FINAL REMINDER: Your ENTIRE reply must be 1–2 short sentences. If you wrote more — cut it. Sound human, be brief.`;

  systemPrompt = sp;
}

// ══════════════════════════════
// CHAT UI SETUP
// ══════════════════════════════
function setupChatUI() {
  const initial = (profile.name[0] || '?').toUpperCase();
  document.getElementById('chatAvatar').textContent = initial;
  document.getElementById('chatName').textContent = profile.name;
  document.getElementById('chatRelation').querySelector('span:first-child').className = 'status-dot';
  document.getElementById('chatLangBadge').textContent = LANG_SHORT[profile.language] || 'HI';
  updateCloneBadge(profileVoiceId ? 'warming' : 'off');
  chatHistory = [];

  const area = document.getElementById('messagesArea');
  area.innerHTML = '';
  appendSysMsg(`${profile.name} ${t('sys_start')}`);
  bindSidebarActions();
  refreshCompanions().then(() => {
    if (!chatHistory.length) {
      sendBotGreeting();
    }
  });
}

function bindSidebarActions() {
  const newChatBtn = document.getElementById('newChatBtn');
  const editBtn = document.getElementById('editCompanionBtn');
  const deleteBtn = document.getElementById('deleteCompanionBtn');

  if (newChatBtn && newChatBtn.dataset.bound !== '1') {
    newChatBtn.dataset.bound = '1';
    newChatBtn.textContent = 'Add Companion';
    newChatBtn.addEventListener('click', async () => {
      await openCompanionOnboarding();
    });
  }

  if (editBtn && editBtn.dataset.bound !== '1') {
    editBtn.dataset.bound = '1';
    editBtn.addEventListener('click', openCompanionEditor);
  }

  if (deleteBtn && deleteBtn.dataset.bound !== '1') {
    deleteBtn.dataset.bound = '1';
    deleteBtn.addEventListener('click', deleteCurrentCompanion);
  }

  const cancelBtn = document.getElementById('cancelCompanionEditBtn');
  const saveBtn = document.getElementById('saveCompanionEditBtn');
  const backdrop = document.getElementById('companionModalBackdrop');

  if (cancelBtn && cancelBtn.dataset.bound !== '1') {
    cancelBtn.dataset.bound = '1';
    cancelBtn.addEventListener('click', closeCompanionEditor);
  }
  if (saveBtn && saveBtn.dataset.bound !== '1') {
    saveBtn.dataset.bound = '1';
    saveBtn.addEventListener('click', saveCompanionEdits);
  }
  if (backdrop && backdrop.dataset.bound !== '1') {
    backdrop.dataset.bound = '1';
    backdrop.addEventListener('click', (e) => {
      if (e.target === backdrop) closeCompanionEditor();
    });
  }
}

async function refreshCompanions() {
  try {
    const res = await fetch('/api/companions');
    if (!res.ok) {
      companions = [];
      currentCompanionId = null;
      renderCompanionsSidebar();
      return;
    }

    const data = await res.json().catch(() => ({}));
    companions = Array.isArray(data.companions) ? data.companions : [];

    if (!companions.length) {
      renderCompanionsSidebar();
      return;
    }

    if (!currentCompanionId || !companions.some((c) => c.id === currentCompanionId)) {
      currentCompanionId = companions[0].id;
    }

    await loadCompanionMessages(currentCompanionId);
  } catch (_) {
    companions = [];
    currentCompanionId = null;
    renderCompanionsSidebar();
  }
}

function renderCompanionsSidebar() {
  const listEl = document.getElementById('historyList');
  if (!listEl) return;
  listEl.innerHTML = '';

  if (!companions.length) {
    listEl.innerHTML = '<div class="history-empty">No companions yet</div>';
    return;
  }

  companions.forEach((c) => {
    const item = document.createElement('button');
    item.className = `history-item${c.id === currentCompanionId ? ' active' : ''}`;
    item.type = 'button';
    item.textContent = c.name || `Companion ${c.id}`;
    item.addEventListener('click', async () => {
      await loadCompanionMessages(c.id);
    });
    listEl.appendChild(item);
  });
}

function openCompanionEditor() {
  if (!currentCompanionId) {
    showToast('Select a companion first');
    return;
  }

  const row = companions.find((c) => c.id === currentCompanionId);
  if (!row) {
    showToast('Companion not found');
    return;
  }

  document.getElementById('companionEditName').value = row.name || '';
  document.getElementById('companionEditStyle').value = row.style || 'casual';
  document.getElementById('companionEditLanguage').value = row.language || 'hinglish';
  document.getElementById('companionEditVoiceType').value = row.voice_type || 'female';
  document.getElementById('companionEditAudio').value = '';

  const err = document.getElementById('companionModalError');
  err.style.display = 'none';
  err.textContent = '';

  document.getElementById('companionModalBackdrop').style.display = 'flex';
}

function closeCompanionEditor() {
  const backdrop = document.getElementById('companionModalBackdrop');
  if (backdrop) backdrop.style.display = 'none';
}

async function saveCompanionEdits() {
  if (!currentCompanionId) return;

  const name = document.getElementById('companionEditName').value.trim();
  const style = document.getElementById('companionEditStyle').value;
  const language = document.getElementById('companionEditLanguage').value;
  const voiceType = document.getElementById('companionEditVoiceType').value;
  const file = document.getElementById('companionEditAudio').files[0] || null;
  const err = document.getElementById('companionModalError');

  err.style.display = 'none';
  err.textContent = '';

  if (!name) {
    err.textContent = 'Name is required';
    err.style.display = 'block';
    return;
  }

  const saveBtn = document.getElementById('saveCompanionEditBtn');
  saveBtn.disabled = true;

  try {
    let uploadedVoiceId = null;
    if (file) {
      const fd = new FormData();
      fd.append('audio', file, file.name);
      fd.append('language_code', dbLanguageToUiCode(language));
      const voiceRes = await fetch(`/api/companions/${currentCompanionId}/voice`, {
        method: 'POST',
        body: fd,
      });
      const voiceData = await voiceRes.json().catch(() => ({}));
      if (!voiceRes.ok || !voiceData.ok) {
        err.textContent = voiceData.error || 'Could not upload voice sample';
        err.style.display = 'block';
        saveBtn.disabled = false;
        return;
      }
      uploadedVoiceId = voiceData.profile_voice_id || null;
    }

    const existing = companions.find((c) => c.id === currentCompanionId) || {};
    const res = await fetch(`/api/companions/${currentCompanionId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name,
        style,
        language,
        voice_type: voiceType,
        profile_voice_id: uploadedVoiceId || existing.profile_voice_id || null,
      }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok || !data.ok) {
      err.textContent = data.error || 'Could not save companion';
      err.style.display = 'block';
      saveBtn.disabled = false;
      return;
    }

    closeCompanionEditor();
    await refreshCompanions();
    await loadCompanionMessages(currentCompanionId);
    showToast('Companion updated');
  } catch (_) {
    err.textContent = 'Server error while saving companion';
    err.style.display = 'block';
  } finally {
    saveBtn.disabled = false;
  }
}

async function deleteCurrentCompanion() {
  if (!currentCompanionId) {
    showToast('Select a companion first');
    return;
  }
  if (!confirm('Delete this companion and all linked chat?')) return;

  try {
    const res = await fetch(`/api/companions/${currentCompanionId}`, { method: 'DELETE' });
    const data = await res.json().catch(() => ({}));
    if (!res.ok || !data.ok) {
      showToast(data.error || 'Could not delete companion');
      return;
    }

    currentCompanionId = null;
    profileVoiceId = '';
    await refreshCompanions();

    if (companions.length) {
      currentCompanionId = companions[0].id;
      await loadCompanionMessages(currentCompanionId);
    } else {
      chatHistory = [];
      const area = document.getElementById('messagesArea');
      if (area) area.innerHTML = '';
      appendSysMsg('No companions left. Add one to continue.');
    }
    showToast('Companion deleted');
  } catch (_) {
    showToast('Server error while deleting companion');
  }
}

async function loadCompanionMessages(companionId) {
  currentCompanionId = companionId;

  const activeCompanion = companions.find((c) => c.id === currentCompanionId);
  if (activeCompanion) {
    profile.name = activeCompanion.name || profile.name || 'Companion';
    profile.language = dbLanguageToUiCode(activeCompanion.language);
    profile.voiceType = activeCompanion.voice_type || profile.voiceType || 'female';
    profileVoiceId = activeCompanion.profile_voice_id || '';
    document.getElementById('chatName').textContent = profile.name;
    document.getElementById('chatAvatar').textContent = (profile.name[0] || '?').toUpperCase();
    document.getElementById('chatLangBadge').textContent = LANG_SHORT[profile.language] || 'HI';
  }

  const area = document.getElementById('messagesArea');
  if (!area) return;
  area.innerHTML = '';

  try {
    const res = await fetch(`/api/messages/${companionId}`);
    if (!res.ok) {
      chatHistory = [];
      appendSysMsg(`${profile.name} ${t('sys_start')}`);
      renderCompanionsSidebar();
      return;
    }

    const data = await res.json().catch(() => ({}));
    const msgs = Array.isArray(data.messages) ? data.messages : [];

    chatHistory = [];
    if (!msgs.length) {
      appendSysMsg(`${profile.name} ${t('sys_start')}`);
    }

    msgs.forEach((m) => {
      if (m.role === 'user') {
        chatHistory.push({ role: 'user', content: m.message || '' });
        appendMessage('user', m.message || '');
      } else if (m.role === 'assistant') {
        chatHistory.push({ role: 'assistant', content: m.message || '' });
        appendMessage('bot', m.message || '', true);
      }
    });
  } catch (_) {
    chatHistory = [];
    appendSysMsg(`${profile.name} ${t('sys_start')}`);
  }

  renderCompanionsSidebar();
}

async function sendBotGreeting() {
  const greetings = {
    'hi-IN': `Arre, ${profile.nickname}! Aa gaye aakhir. Bahut yaad aa rahi thi tumhari…`,
    'bn-IN': `Arre, ${profile.nickname}! Ele aakhere. Tomar jonyo onek miss korchilam…`,
    'ta-IN': `Enda, ${profile.nickname}! Vanduttae! Romba neram kaanalaaye…`,
    'te-IN': `Arre, ${profile.nickname}! Vachavu! Chala naalugaa chusala ledu…`,
    'kn-IN': `Arre, ${profile.nickname}! Bandhe! Thumba dinagala nanthara noduthiddene…`,
    'ml-IN': `Eda, ${profile.nickname}! Vannu! Kure naalaayi kaanam kaathu irunnillu…`,
    'mr-IN': `Arre, ${profile.nickname}! Aalas tu! Kitikhel yewaytoy tula…`,
    'gu-IN': `Are, ${profile.nickname}! Aavyo tu! Kitiyo samay thi raha hato…`,
    'pa-IN': `Are, ${profile.nickname}! Aa gaye tu! Bahut wait ki teri…`,
    'en-IN': `Oh ${profile.nickname}, you're here! I've missed you so much…`,
  };
  const greet = greetings[profile.language] || greetings['hi-IN'];
  chatHistory.push({ role: 'assistant', content: greet });
  appendMessage('bot', greet, true);
}

// ══════════════════════════════
// SEND MESSAGE
// ══════════════════════════════
async function sendMessage() {
  if (!currentCompanionId) {
    await refreshCompanions();
    if (!currentCompanionId) {
      showToast('Create a companion first');
      await openCompanionOnboarding();
      return;
    }
  }

  if (!currentCompanionId) {
    showToast('Create a companion first');
    return;
  }

  const input = document.getElementById('chatInput');
  const text = input.value.trim();
  if (!text) return;
  input.value = '';
  appendMessage('user', text);
  chatHistory.push({ role: 'user', content: text });
  await getBotReply();
}

async function getBotReply() {
  const typingId = showTyping();
  try {
    const lastUser = [...chatHistory].reverse().find((m) => m.role === 'user');
    if (!lastUser || !lastUser.content) {
      removeTyping(typingId);
      return;
    }

    const res = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        system: systemPrompt,
        message: lastUser.content,
        companion_id: currentCompanionId,
      }),
    });
    removeTyping(typingId);

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      console.error('Chat API error:', err);
      const fallback = getFallbackMsg();
      chatHistory.push({ role: 'assistant', content: fallback });
      appendMessage('bot', fallback, true);
      showToast(t('err_api'));
      return;
    }

    const data = await res.json();
    const reply = data.reply || getFallbackMsg();
    chatHistory.push({ role: 'assistant', content: reply });
    appendMessage('bot', reply, true);
  } catch (err) {
    removeTyping(typingId);
    console.error('Network error:', err);
    const fallback = getFallbackMsg();
    chatHistory.push({ role: 'assistant', content: fallback });
    appendMessage('bot', fallback, true);
    showToast('Server se connect nahi ho saka. Python server chal raha hai?');
  }
}

async function ensureAuthenticated() {
  try {
    const res = await fetch('/api/me');
    if (!res.ok) {
      window.location.href = '/login';
      return false;
    }
    const data = await res.json().catch(() => ({}));
    if (!data.ok || !data.authenticated) {
      window.location.href = '/login';
      return false;
    }
    currentUser = data.user || null;
    return true;
  } catch (_) {
    window.location.href = '/login';
    return false;
  }
}

function bindTopbarNavActions() {
  const logoutBtn = document.getElementById('logoutNavBtn');

  if (logoutBtn && logoutBtn.dataset.bound !== '1') {
    logoutBtn.dataset.bound = '1';
    logoutBtn.addEventListener('click', async () => {
      try {
        await fetch('/api/logout', { method: 'POST' });
      } catch (_) {
        // ignore network errors, continue redirect
      }
      window.location.href = '/login';
    });
  }
}

function getFallbackMsg() {
  const msgs = {
    'hi-IN': ['Haan, sun raha/rahi hoon beta…', 'Theek ho na tum?', 'Sochta/sochti hoon tumhare baare mein hamesha.'],
    'en-IN': ['Yes, I hear you…', 'Are you okay?', 'I always think about you.'],
  };
  const arr = msgs[profile.language] || msgs['hi-IN'];
  return arr[Math.floor(Math.random() * arr.length)];
}

// ══════════════════════════════
// TTS — speak a bot message
// ══════════════════════════════
async function speakText(text, btnEl) {
  if (!text) return;

  // Visual loading state on the clicked button
  if (btnEl) {
    btnEl.disabled = true;
    btnEl.style.opacity = '0.6';
    btnEl.innerHTML = `<svg viewBox="0 0 24 24" fill="currentColor" style="width:11px;height:11px"><path d="M12 2a10 10 0 1 0 0 20A10 10 0 0 0 12 2zm0 18a8 8 0 1 1 0-16 8 8 0 0 1 0 16zm-1-13h2v6h-2zm0 8h2v2h-2z"/></svg> …`;
  }

  try {
    const vGender = profile.voiceType === 'male' ? 'male' : 'female';
    const speaker = (VOICE_MAP[profile.language] || VOICE_MAP['hi-IN'])[vGender];

    const res = await fetch('/api/tts', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        text: text,
        language_code: profile.language,
        speaker: speaker,
        profile_voice_id: profileVoiceId,
      }),
    });

    if (!res.ok) { showToast(t('toast_tts_fail')); return; }
    const data = await res.json();
    if (!data.ok || !data.audio) { showToast(t('toast_tts_fail')); return; }

    if (data.voice_cloned) {
      updateCloneBadge('on');
    } else if (data.profile_voice_loaded && !data.clone_ready) {
      updateCloneBadge('warming');
    } else if (data.profile_voice_loaded && data.clone_ready) {
      updateCloneBadge('off');
    } else {
      updateCloneBadge('off');
    }

    if (data.profile_voice_loaded && !data.voice_cloned && data.clone_ready) {
      showToast(uiLang === 'hi' ? 'Clone sample mila, par is reply par clone apply nahi hua.' : 'Clone sample loaded, but this reply was not cloned.');
    } else if (data.profile_voice_loaded && !data.clone_ready) {
      showToast(uiLang === 'hi' ? 'Voice clone model warm-up ho raha hai, thoda wait karo…' : 'Voice clone model is warming up, please wait...');
    }

    const audioBytes = Uint8Array.from(atob(data.audio), c => c.charCodeAt(0));
    const blob = new Blob([audioBytes], { type: 'audio/wav' });
    const url = URL.createObjectURL(blob);
    const audio = new Audio(url);
    audio.onended = () => { URL.revokeObjectURL(url); };
    try { await audio.play(); } catch (playErr) {
      // Browser may block playback after async work; queue for next user gesture.
      console.warn('Autoplay blocked:', playErr);
      pendingAudioUrl = url;
      showToast(uiLang === 'hi' ? 'Audio allow karne ke liye screen par ek baar tap/click karo.' : 'Tap/click once anywhere to allow audio playback.');
      return;
    }
  } catch (e) {
    console.error('TTS error:', e);
    showToast(t('toast_tts_fail'));
  } finally {
    // Restore button
    if (btnEl) {
      btnEl.disabled = false;
      btnEl.style.opacity = '';
      btnEl.innerHTML = `<svg viewBox="0 0 24 24" fill="currentColor" style="width:11px;height:11px"><path d="M8 5v14l11-7z"/></svg> ${uiLang === 'hi' ? 'Suno' : 'Play'}`;
    }
  }
}

// ══════════════════════════════
// STT — record voice
// ══════════════════════════════
async function toggleRecord() {
  if (isRecording) { stopRecording(); }
  else { await startRecording(); }
}

async function startRecording() {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    audioChunks = [];
    mediaRecorder = new MediaRecorder(stream);
    mediaRecorder.ondataavailable = e => { if (e.data.size > 0) audioChunks.push(e.data); };
    mediaRecorder.onstop = handleRecordingStop;
    mediaRecorder.start();
    isRecording = true;
    document.getElementById('micBtn').classList.add('recording');
    showToast(t('toast_recording'));
  } catch (e) {
    showToast(t('toast_micfail'));
  }
}

function stopRecording() {
  if (mediaRecorder && isRecording) {
    mediaRecorder.stop();
    mediaRecorder.stream.getTracks().forEach(t => t.stop());
    isRecording = false;
    document.getElementById('micBtn').classList.remove('recording');
  }
}

async function handleRecordingStop() {
  showToast(t('toast_processing'));
  const blob = new Blob(audioChunks, { type: 'audio/webm' });
  const fd = new FormData();
  fd.append('audio', blob, 'voice.webm');
  fd.append('language_code', profile.language || 'hi-IN');

  try {
    const res = await fetch('/api/stt', { method: 'POST', body: fd });
    if (!res.ok) { showToast(t('toast_nothead')); return; }
    const data = await res.json();
    if (data.ok && data.transcript) {
      document.getElementById('chatInput').value = data.transcript;
      showToast(t('toast_heard') + data.transcript.substring(0, 40) + (data.transcript.length > 40 ? '…' : ''));
    } else {
      showToast(t('toast_nothead'));
    }
  } catch (e) {
    console.error('STT error:', e);
    showToast(t('toast_nothead'));
  }
}

// ══════════════════════════════
// DOM HELPERS
// ══════════════════════════════
function appendMessage(role, text, withSpeakBtn = false) {
  const area = document.getElementById('messagesArea');
  const div = document.createElement('div');
  div.className = `msg ${role}`;

  const now = new Date().toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' });
  const initial = role === 'bot' ? (profile.name?.[0] || '?').toUpperCase() : '✦';

  // speak button only on bot
  const speakHtml = (withSpeakBtn && role === 'bot')
    ? `<div class="speak-btn">
        <svg viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>
        ${uiLang === 'hi' ? 'Suno' : 'Play'}
      </div>`
    : '';

  div.innerHTML = `
    <div class="msg-av">${initial}</div>
    <div class="msg-content">
      <div class="msg-bubble">${escapeHtml(text)}${speakHtml}</div>
      <div class="msg-time">${now}</div>
    </div>
  `;

  // Attach click handler via closure — passes button ref for loading state
  if (withSpeakBtn && role === 'bot') {
    const btn = div.querySelector('.speak-btn');
    if (btn) btn.addEventListener('click', () => speakText(text, btn));
  }

  area.appendChild(div);
  area.scrollTop = area.scrollHeight;
}

function appendSysMsg(text) {
  const area = document.getElementById('messagesArea');
  const div = document.createElement('div');
  div.className = 'sys-msg';
  div.textContent = text;
  area.appendChild(div);
}

let typingCount = 0;
function showTyping() {
  const id = 'typing-' + (++typingCount);
  const area = document.getElementById('messagesArea');
  const div = document.createElement('div');
  div.id = id;
  div.className = 'typing-wrap';
  div.innerHTML = `
    <div class="msg-av">${(profile.name?.[0] || '?').toUpperCase()}</div>
    <div class="typing-bubble">
      <div class="typing-dot"></div>
      <div class="typing-dot"></div>
      <div class="typing-dot"></div>
    </div>`;
  area.appendChild(div);
  area.scrollTop = area.scrollHeight;
  return id;
}

function removeTyping(id) {
  const el = document.getElementById(id);
  if (el) el.remove();
}

function escapeHtml(s) {
  return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

// ══════════════════════════════
// RESET
// ══════════════════════════════
function resetProfile() {
  if (!confirm(t('toast_reset'))) return;
  profile = {}; chatHistory = []; systemPrompt = '';
  uploadedAudioFile = null; audioTranscript = ''; profileVoiceId = '';
  currentCompanionId = null;
  companions = [];
  isCompanionOnboarding = false;
  updateCloneBadge('off');
  document.getElementById('lovedName').value = '';
  document.getElementById('relationship').value = '';
  document.getElementById('q_nickname').value = '';
  document.getElementById('q_phrases').value = '';
  document.getElementById('q_wisdom').value = '';
  document.getElementById('audioFileTag').style.display = 'none';
  document.querySelectorAll('.pers-chip').forEach((c, i) => {
    c.classList.toggle('selected', i === 0);
  });
  selectedPersonality = 'warm and caring';
  showScreen('landingScreen');
}

// ══════════════════════════════
// TOAST
// ══════════════════════════════
function showToast(msg) {
  const el = document.getElementById('toast');
  el.textContent = msg;
  el.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove('show'), 3200);
}

function bindAudioUnlockHandlers() {
  if (audioUnlockHandlersBound) return;
  audioUnlockHandlersBound = true;

  const tryPlayPending = async () => {
    if (!pendingAudioUrl) return;
    const url = pendingAudioUrl;
    pendingAudioUrl = null;
    const audio = new Audio(url);
    audio.onended = () => { URL.revokeObjectURL(url); };
    try {
      await audio.play();
    } catch {
      // Keep silent here; user can tap play button again if needed.
    }
  };

  ['click', 'keydown', 'touchstart'].forEach(evt => {
    document.addEventListener(evt, tryPlayPending, { passive: true });
  });
}

// ══════════════════════════════
// UTIL
// ══════════════════════════════
function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

// ══════════════════════════════
// LANDING PAGE ANIMATIONS
// ══════════════════════════════
function initLandingAnimations() {
  const landingScreen = document.getElementById('landingScreen');
  const heroCard = document.getElementById('heroCard');
  
  if (!landingScreen || !heroCard) return;
  
  // Scroll-based 3D card animation
  const handleScroll = () => {
    const scrollY = landingScreen.scrollTop;
    const maxScroll = 600;
    const progress = Math.min(scrollY / maxScroll, 1);
    
    // Calculate rotation based on scroll
    const rotateX = 12 - (progress * 15); // 12 to -3
    const rotateY = -8 + (progress * 6);  // -8 to -2
    const scale = 1 + (progress * 0.05);  // 1 to 1.05
    const translateY = progress * -30;    // 0 to -30
    
    heroCard.querySelector('.hero-card').style.transform = 
      `rotateX(${rotateX}deg) rotateY(${rotateY}deg) scale(${scale}) translateY(${translateY}px)`;
  };
  
  landingScreen.addEventListener('scroll', handleScroll);
  
  // Smooth scroll for anchor links
  landingScreen.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function(e) {
      e.preventDefault();
      const targetId = this.getAttribute('href').substring(1);
      const target = document.getElementById(targetId);
      if (target) {
        landingScreen.scrollTo({
          top: target.offsetTop - 80,
          behavior: 'smooth'
        });
      }
    });
  });
  
  // Intersection Observer for fade-in animations
  const observerOptions = {
    root: landingScreen,
    threshold: 0.1,
    rootMargin: '0px 0px -50px 0px'
  };
  
  const fadeObserver = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.classList.add('fade-in-visible');
        fadeObserver.unobserve(entry.target);
      }
    });
  }, observerOptions);
  
  // Observe feature cards, step cards, etc.
  landingScreen.querySelectorAll('.feature-card, .step-card, .about-content').forEach(el => {
    el.classList.add('fade-in-element');
    fadeObserver.observe(el);
  });
}

// ══════════════════════════════
// LANGUAGE DROPDOWN
// ══════════════════════════════
function toggleLangDropdown() {
  const dropdown = document.querySelector('.lang-dropdown');
  if (dropdown) {
    dropdown.classList.toggle('open');
  }
}

function closeLangDropdown() {
  const dropdown = document.querySelector('.lang-dropdown');
  if (dropdown) {
    dropdown.classList.remove('open');
  }
}

// ══════════════════════════════
// INIT
// ══════════════════════════════
document.addEventListener('DOMContentLoaded', async () => {
  const ok = await ensureAuthenticated();
  if (!ok) return;

  bindTopbarNavActions();

  initTheme();
  initUiLang();
  bindAudioUnlockHandlers();
  startIntroSequence();

  // Click anywhere on intro stage to skip (except the enter button)
  const introStage = document.getElementById('introStage');
  if (introStage) {
    introStage.addEventListener('click', (e) => {
      // Don't skip if clicking on the enter button
      if (e.target.closest('.intro-enter-btn')) return;
      enterFromIntro();
    });
  }

  // Close language dropdown when clicking outside
  document.addEventListener('click', (e) => {
    if (!e.target.closest('.lang-dropdown')) {
      closeLangDropdown();
    }
  });

  // Close dropdown after selecting a language
  document.querySelectorAll('.lang-options button').forEach(btn => {
    btn.addEventListener('click', () => {
      setTimeout(closeLangDropdown, 100);
    });
  });
});
