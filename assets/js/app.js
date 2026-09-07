// Initialize Telegram WebApp SDK
if (window.Telegram && window.Telegram.WebApp) {
  try {
    const tg = window.Telegram.WebApp;
    tg.ready();
    tg.expand();
    if (tg.disableVerticalSwipes) {
      tg.disableVerticalSwipes();
    }
    tg.setHeaderColor('#090b11');
    tg.setBackgroundColor('#090b11');
  } catch (e) {
    console.error("Telegram WebApp init error:", e);
  }
}

// Native Mobile App Viewport Lockdown (Prevents zoom in / zoom out / gesture distortion)
document.addEventListener('gesturestart', function (e) {
  e.preventDefault();
}, { passive: false });

document.addEventListener('gesturechange', function (e) {
  e.preventDefault();
}, { passive: false });

document.addEventListener('gestureend', function (e) {
  e.preventDefault();
}, { passive: false });

// Prevent 2-finger pinch zoom
document.addEventListener('touchstart', function (e) {
  if (e.touches && e.touches.length > 1) {
    e.preventDefault();
  }
}, { passive: false });

// Prevent double-tap zooming on mobile
let lastTouchEndTime = 0;
document.addEventListener('touchend', function (e) {
  const now = Date.now();
  if (now - lastTouchEndTime <= 300) {
    e.preventDefault();
  }
  lastTouchEndTime = now;
}, { passive: false });

// Telegram Group & Channel URLs
const TG_GROUP_LINK = 'https://t.me/alltimefantasyzone';
const TG_SHARE_TEXT = encodeURIComponent('সরাসরি লাইভ চ্যাট ও ভিডিও কল গ্রুপে যুক্ত হোন: ');
const TG_SHARE_URL = `https://t.me/share/url?url=${encodeURIComponent(TG_GROUP_LINK)}&text=${TG_SHARE_TEXT}`;

// Adsterra Direct Links & Click Monetization Logic
let adClickCount = parseInt(sessionStorage.getItem('adClickCount') || '0');
const directLink1 = 'https://omg10.com/4/11017767';
const directLink2 = 'https://www.effectivecpmnetwork.com/mgtqwzbp?key=5c4003e0ae2b0ebd387daded087bc9aa';

function triggerAdRedirect(e) {
  if (e && e.stopPropagation) {
    e.stopPropagation();
  }

  if (adClickCount < 3) {
    const targetUrl = adClickCount % 2 === 0 ? directLink1 : directLink2;
    adClickCount++;
    sessionStorage.setItem('adClickCount', adClickCount);
    
    try {
      const opened = window.open(targetUrl, '_blank');
      if (!opened || opened.closed || typeof opened.closed === 'undefined') {
        const a = document.createElement('a');
        a.href = targetUrl;
        a.target = '_blank';
        a.rel = 'noopener noreferrer';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
      }
    } catch(err) {
      const a = document.createElement('a');
      a.href = targetUrl;
      a.target = '_blank';
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
    }
    updateModalAdState();
  } else {
    window.open(TG_GROUP_LINK, '_blank');
  }
}

function updateModalAdState() {
  const btn = document.getElementById('verify-ad-btn');
  const title = document.getElementById('verify-main-title');
  const subtitle = document.getElementById('verify-sub-title');
  const adTitle = document.getElementById('verify-ad-title');
  const adDesc = document.getElementById('verify-ad-desc');
  const adBadge = document.getElementById('verify-ad-badge');

  if (btn && adClickCount >= 3) {
    if (title) title.innerText = 'ভেরিফিকেশন সফল হয়েছে!';
    if (subtitle) subtitle.innerText = 'নিচের বাটনে ক্লিক করে সরাসরি আমাদের অফিশিয়াল টেলিগ্রাম গ্রুপে যুক্ত হোন।';
    if (adTitle) adTitle.innerText = '🎉 অলটাইম ফ্যান্টাসি জোন';
    if (adDesc) adDesc.innerText = 'আমাদের টেলিগ্রাম গ্রুপে ফ্রিতে জয়েন করে সরাসরি সকল মেম্বারদের সাথে চ্যাট করুন।';
    if (adBadge) adBadge.innerText = 'Verification Success';
    btn.innerHTML = '<span>টেলিগ্রাম গ্রুপ জয়েন করুন</span> <i class="fa-brands fa-telegram"></i>';
    btn.className = 'modal-verify-btn btn-telegram';
    btn.style.boxShadow = '0 8px 25px rgba(0, 136, 204, 0.4)';
  }
}

// Initial Live Online Counters
let boysCount = 211;
let girlsCount = 185;

function simulateFluctuation() {
  const boysCounterEl = document.getElementById('boys-counter');
  const girlsCounterEl = document.getElementById('girls-counter');

  if (boysCounterEl) {
    const boysDiff = Math.floor(Math.random() * 5) - 2;
    boysCount = Math.max(200, Math.min(230, boysCount + boysDiff));
    boysCounterEl.innerText = boysCount;
  }

  if (girlsCounterEl) {
    const girlsDiff = Math.floor(Math.random() * 5) - 2;
    girlsCount = Math.max(170, Math.min(200, girlsCount + girlsDiff));
    girlsCounterEl.innerText = girlsCount;
  }
}
setInterval(simulateFluctuation, 4000);

// ========================================================
// STEP 1: Telegram 10-Member Real Database Force-Add Verification Logic (NO ADS IN THIS STEP)
// ========================================================
let isTgVerified = sessionStorage.getItem('tg10Added') === 'true';
let isAgeVerified = sessionStorage.getItem('ageVerified') === 'true';
let savedTgId = sessionStorage.getItem('tgUserId') || '';
let adsInitialized = false;

// Auto-check on page load if user already entered an ID or running in Telegram WebApp
function initTelegramGateState() {
  const inputEl = document.getElementById('tg-user-id-input');
  if (window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.initDataUnsafe && window.Telegram.WebApp.initDataUnsafe.user) {
    const tgUser = window.Telegram.WebApp.initDataUnsafe.user;
    const tgId = String(tgUser.id || tgUser.username || '');
    if (tgId && inputEl) {
      inputEl.value = tgId;
      checkRealDatabaseInvites(true);
      return;
    }
  }

  if (savedTgId && inputEl) {
    inputEl.value = savedTgId;
    checkRealDatabaseInvites(true);
  }
}

async function checkRealDatabaseInvites(isSilent = false) {
  const inputEl = document.getElementById('tg-user-id-input');
  const alertEl = document.getElementById('tg-db-alert');
  const checkBtn = document.getElementById('tg-check-btn');
  const verifyBtn = document.getElementById('tg-verify-btn');
  const counterEl = document.getElementById('tg-added-counter');
  const fillEl = document.getElementById('tg-progress-fill');
  const percentEl = document.getElementById('tg-progress-percent');
  const modal = document.querySelector('.tg-forceadd-modal');

  let rawInput = (inputEl ? inputEl.value : '').trim();

  // If auto-detecting from Telegram WebApp
  if (!rawInput && window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.initDataUnsafe && window.Telegram.WebApp.initDataUnsafe.user) {
    const tgUser = window.Telegram.WebApp.initDataUnsafe.user;
    rawInput = String(tgUser.id || tgUser.username || '');
    if (inputEl) inputEl.value = rawInput;
  }

  if (!rawInput && savedTgId) {
    rawInput = savedTgId;
    if (inputEl) inputEl.value = rawInput;
  }

  if (!rawInput) {
    if (!isSilent) {
      if (alertEl) {
        alertEl.style.display = 'block';
        alertEl.className = 'tg-db-alert error';
        alertEl.innerHTML = '<i class="fa-solid fa-triangle-exclamation"></i> অনুগ্রহ করে আপনার টেলিগ্রাম User ID বা @username লিখুন!';
      }
      if (modal) {
        modal.classList.add('shake');
        setTimeout(() => modal.classList.remove('shake'), 400);
      }
    }
    return;
  }

  // Show loading indicator
  if (checkBtn) checkBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i>';
  if (verifyBtn) verifyBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> ডাটাবেজে যাচাই করা হচ্ছে...';

  try {
    // Query API
    const apiUrl = `api/check_invites.php?user_id=${encodeURIComponent(rawInput)}`;
    const res = await fetch(apiUrl);
    const data = await res.json();

    if (data && data.success) {
      const count = parseInt(data.invites || 0);
      const req = parseInt(data.required || 10);
      const pct = Math.min(100, Math.round((count / req) * 100));

      if (counterEl) counterEl.innerText = count;
      if (fillEl) fillEl.style.width = pct + '%';
      if (percentEl) percentEl.innerText = pct + '%';

      sessionStorage.setItem('tgUserId', rawInput);

      if (data.unlocked || count >= req) {
        // 10+ real database invites confirmed!
        sessionStorage.setItem('tg10Added', 'true');
        isTgVerified = true;
        if (alertEl) {
          alertEl.style.display = 'block';
          alertEl.className = 'tg-db-alert success';
          alertEl.innerHTML = `<i class="fa-solid fa-circle-check"></i> ${data.message || '১০ জন মেম্বার এড সম্পন্ন হয়েছে!'}`;
        }
        if (fillEl) {
          fillEl.style.background = 'linear-gradient(135deg, #10b981, #059669)';
        }
        if (verifyBtn) {
          verifyBtn.innerHTML = '<i class="fa-solid fa-circle-check"></i> ভেরিফিকেশন সফল — ১৮+ গেটে প্রবেশ করুন';
          verifyBtn.style.background = 'linear-gradient(135deg, #10b981, #059669)';
        }
        showToastNotification("🎉 অভিনন্দন! ডাটাবেজ অনুসারে ১০ জন মেম্বার এড সম্পন্ন হয়েছে।");
        setTimeout(() => {
          hideTgForceAddModal();
          showAgeGateModal();
        }, 1200);
      } else {
        // Locked - real count is less than 10
        if (alertEl) {
          alertEl.style.display = 'block';
          alertEl.className = 'tg-db-alert error';
          alertEl.innerHTML = `<i class="fa-solid fa-circle-xmark"></i> ${data.message}`;
        }
        if (!isSilent && modal) {
          modal.classList.add('shake');
          setTimeout(() => modal.classList.remove('shake'), 400);
        }
        if (verifyBtn) {
          verifyBtn.innerHTML = `<i class="fa-solid fa-lock"></i> আরও ${data.remaining} জন এড করে আবার চেক করুন`;
        }
        if (!isSilent) {
          showToastNotification(`❌ আপনি মাত্র ${count} জন এড করেছেন! আরও ${data.remaining} জন বন্ধুকে গ্রুপে এড করুন।`);
        }
      }
    } else {
      if (alertEl) {
        alertEl.style.display = 'block';
        alertEl.className = 'tg-db-alert error';
        alertEl.innerHTML = `<i class="fa-solid fa-triangle-exclamation"></i> ${data ? data.message : 'আইডি পাওয়া যায়নি। টেলিগ্রাম গ্রুপে /myinvites দিয়ে সঠিক আইডি চেক করুন।'}`;
      }
      if (!isSilent && modal) {
        modal.classList.add('shake');
        setTimeout(() => modal.classList.remove('shake'), 400);
      }
      if (verifyBtn) {
        verifyBtn.innerHTML = '<i class="fa-solid fa-shield-halved"></i> ডাটাবেজ ভেরিফাই ও সাইটে প্রবেশ করুন';
      }
    }
  } catch (err) {
    console.error("Database invite check error:", err);
    if (!isSilent && alertEl) {
      alertEl.style.display = 'block';
      alertEl.className = 'tg-db-alert error';
      alertEl.innerHTML = '<i class="fa-solid fa-triangle-exclamation"></i> ডাটাবেজে কানেক্ট করতে সমস্যা হয়েছে। দয়া করে আবার চেষ্টা করুন।';
    }
  } finally {
    if (checkBtn) checkBtn.innerHTML = '<i class="fa-solid fa-magnifying-glass"></i> <span>চেক করুন</span>';
  }
}

function handleTgGroupAdd() {
  window.open(TG_GROUP_LINK, '_blank');
}

function handleTgForward() {
  window.open(TG_SHARE_URL, '_blank');
}

function hideTgForceAddModal() {
  const tgOverlay = document.getElementById('tg-forceadd-overlay');
  if (tgOverlay) {
    tgOverlay.style.opacity = '0';
    tgOverlay.style.transition = 'opacity 0.35s ease';
    setTimeout(() => {
      tgOverlay.style.display = 'none';
    }, 350);
  }
}

function showAgeGateModal() {
  const ageOverlay = document.getElementById('age-gate-overlay');
  if (ageOverlay && !isAgeVerified) {
    ageOverlay.style.display = 'flex';
    ageOverlay.style.opacity = '1';
  }
}

function hideAgeGateModal() {
  const ageOverlay = document.getElementById('age-gate-overlay');
  if (ageOverlay) {
    ageOverlay.style.opacity = '0';
    ageOverlay.style.transition = 'opacity 0.35s ease';
    setTimeout(() => {
      ageOverlay.style.display = 'none';
    }, 350);
  }
}

// ========================================================
// CENTRAL DYNAMIC ADSTERRA ADS INITIALIZER
// (Only called AFTER user passes BOTH TG & 18+ Verification)
// ========================================================
function initAllAdsterraAds() {
  if (adsInitialized) return;
  adsInitialized = true;

  console.log("⚡ Initializing Adsterra monetization after full verification...");

  // 1. Dynamic Popunder Script
  try {
    const popScript = document.createElement('script');
    popScript.src = 'https://pl31109060.profitableratecpmnetwork.com/15/77/e4/1577e445d5052d32b8171c055c4aae03.js';
    popScript.type = 'text/javascript';
    popScript.async = true;
    document.head.appendChild(popScript);
  } catch(e) {}

  // 2. Dynamic Social Bar Script
  try {
    const socialScript = document.createElement('script');
    socialScript.src = 'https://pl31109062.profitableratecpmnetwork.com/e1/1a/68/e11a68b365d3ba51f78a4ef0e139dd95.js';
    socialScript.type = 'text/javascript';
    socialScript.async = true;
    document.body.appendChild(socialScript);
  } catch(e) {}

  // 3. Dynamic 300x250 Top Banner
  const topSlot = document.querySelector('.adsterra-300x250-container');
  if (topSlot && !topSlot.hasChildNodes()) {
    try {
      const scriptConf = document.createElement('script');
      scriptConf.type = 'text/javascript';
      scriptConf.text = `
        atOptions = {
          'key' : 'f920a5f88d34b8eb65e572486b98b226',
          'format' : 'iframe',
          'height' : 250,
          'width' : 300,
          'params' : {}
        };
      `;
      const scriptSrc = document.createElement('script');
      scriptSrc.src = 'https://www.highrevenueformat.com/f920a5f88d34b8eb65e572486b98b226/invoke.js';
      scriptSrc.type = 'text/javascript';
      topSlot.appendChild(scriptConf);
      topSlot.appendChild(scriptSrc);
    } catch(e) {}
  }

  // 4. Dynamic Native Banner
  const nativeSlot = document.getElementById('container-96def6f0cc4dba72ad781c93e21f61fd');
  if (nativeSlot && !nativeSlot.hasChildNodes()) {
    try {
      const nativeScript = document.createElement('script');
      nativeScript.src = 'https://pl31109061.profitableratecpmnetwork.com/96def6f0cc4dba72ad781c93e21f61fd/invoke.js';
      nativeScript.async = true;
      nativeScript.setAttribute('data-cfasync', 'false');
      nativeSlot.appendChild(nativeScript);
    } catch(e) {}
  }

  // 5. Dynamic 320x50 Sticky Bottom Banner
  const bottomSlot = document.querySelector('.adsterra-320x50-container');
  if (bottomSlot && !bottomSlot.hasChildNodes()) {
    try {
      const scriptConf = document.createElement('script');
      scriptConf.type = 'text/javascript';
      scriptConf.text = `
        atOptions = {
          'key' : '686d4162124a321b26260c1bacac69eb',
          'format' : 'iframe',
          'height' : 50,
          'width' : 320,
          'params' : {}
        };
      `;
      const scriptSrc = document.createElement('script');
      scriptSrc.src = 'https://www.highrevenueformat.com/686d4162124a321b26260c1bacac69eb/invoke.js';
      scriptSrc.type = 'text/javascript';
      bottomSlot.appendChild(scriptConf);
      bottomSlot.appendChild(scriptSrc);
    } catch(e) {}
  }
}

// ========================================================
// STEP 2: 18+ Age Gate Entrance -> Unlocks Ads & Full Site
// ========================================================
function enterAgeGate(e) {
  if (e) {
    if (e.preventDefault) e.preventDefault();
    if (e.stopPropagation) e.stopPropagation();
  }
  
  hideAgeGateModal();
  
  isAgeVerified = true;
  sessionStorage.setItem('ageVerified', 'true');

  // Load all Adsterra ads dynamically NOW
  initAllAdsterraAds();

  // 100% First-Touch Click Conversion into Ads
  triggerAdRedirect();

  // Start incoming live messages & call simulation
  setTimeout(receiveMessage, 1200);
  setTimeout(showIncomingCall, 7000);
}

// VIP Video Player Trigger with Ad Monetization
function playSecretVideo(e) {
  if (e && e.stopPropagation) e.stopPropagation();
  triggerAdRedirect();
  openChatModal('video');
}

// Voice Note Player Trigger with Ad Monetization
function playVoiceTrigger(e, name) {
  if (e && e.stopPropagation) e.stopPropagation();
  
  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = 'sine';
    osc.frequency.setValueAtTime(540, ctx.currentTime);
    osc.frequency.exponentialRampToValueAtTime(820, ctx.currentTime + 0.15);
    gain.gain.setValueAtTime(0.08, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.3);
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start();
    osc.stop(ctx.currentTime + 0.3);
  } catch(err) {}

  triggerAdRedirect();
  openChatModal('girls');
}

// Global variable for progress bar interval
let progressInterval = null;

// Open Connecting & Ad Verification Gateway Modal
function openChatModal(type) {
  const overlay = document.getElementById('modal-overlay');
  const stateConnecting = document.getElementById('modal-state-connecting');
  const stateVerify = document.getElementById('modal-state-verify');
  const progressFill = document.getElementById('progress-fill');
  const progressPercent = document.getElementById('progress-percent');
  const loadingTitle = document.getElementById('loading-title');
  const loadingSubtitle = document.getElementById('loading-subtitle');
  const connIcon = document.getElementById('modal-conn-icon');

  const inboxDrawer = document.getElementById('inbox-drawer');
  if (inboxDrawer) inboxDrawer.classList.remove('active');

  if (adClickCount < 3) {
    triggerAdRedirect();
  } else if (type === 'telegram') {
    window.open(TG_GROUP_LINK, '_blank');
    return;
  }

  if (!overlay) return;

  stateConnecting.classList.add('active');
  stateVerify.classList.remove('active');
  if (progressFill) progressFill.style.width = '0%';
  if (progressPercent) progressPercent.innerText = '0% Completed';
  overlay.classList.add('active');

  let currentTitle = 'সার্ভারের সাথে কানেক্ট করা হচ্ছে...';
  let currentSubtitle = 'নিরাপদ গেটওয়ে প্রস্তুত হচ্ছে';
  let iconHTML = '<i class="fa-solid fa-circle-nodes"></i>';

  if (type === 'girls') {
    currentTitle = 'অনলাইন মেয়েদের সাথে চ্যাট লাইন কানেক্ট করা হচ্ছে...';
    currentSubtitle = 'সেরা ম্যাচগুলোর লাইভ সিগন্যাল লোড হচ্ছে';
    iconHTML = '<i class="fa-solid fa-venus"></i>';
  } else if (type === 'boys') {
    currentTitle = 'অনলাইন ছেলেদের সাথে চ্যাট লাইন কানেক্ট করা হচ্ছে...';
    currentSubtitle = 'একটিভ মেম্বারদের সাথে কানেকশন তৈরি হচ্ছে';
    iconHTML = '<i class="fa-solid fa-mars"></i>';
  } else if (type === 'video') {
    currentTitle = 'লাইভ ভিডিও ম্যাচিং প্রোটোকল চালু হচ্ছে...';
    currentSubtitle = 'ক্যামেরা ও ভয়েস পোর্ট ওপেন করা হচ্ছে';
    iconHTML = '<i class="fa-solid fa-video"></i>';
  } else if (type === 'telegram') {
    currentTitle = 'টেলিগ্রাম চ্যাট লাউঞ্জ লিংক জেনারেট করা হচ্ছে...';
    currentSubtitle = 'গ্রুপ ইনভাইট টোকেন সংগ্রহ করা হচ্ছে';
    iconHTML = '<i class="fa-brands fa-telegram"></i>';
  } else if (type === 'chatUnlock') {
    currentTitle = 'চ্যাট রুম কানেকশন প্রসেস হচ্ছে...';
    currentSubtitle = 'ব্যক্তিগত সিকিউর ইনবক্স চ্যানেল খোলা হচ্ছে';
    iconHTML = '<i class="fa-solid fa-comments"></i>';
  }

  if (loadingTitle) loadingTitle.innerText = currentTitle;
  if (loadingSubtitle) loadingSubtitle.innerText = currentSubtitle;
  if (connIcon) connIcon.innerHTML = iconHTML;

  updateModalAdState();

  let progress = 0;
  clearInterval(progressInterval);
  progressInterval = setInterval(() => {
    progress += Math.floor(Math.random() * 8) + 3;
    if (progress >= 100) {
      progress = 100;
      clearInterval(progressInterval);
      
      setTimeout(() => {
        stateConnecting.classList.remove('active');
        stateVerify.classList.add('active');
      }, 400);
    }
    if (progressFill) progressFill.style.width = progress + '%';
    if (progressPercent) progressPercent.innerText = progress + '% Completed';
  }, 100);
}

function closeModal() {
  const overlay = document.getElementById('modal-overlay');
  if (overlay) overlay.classList.remove('active');
  clearInterval(progressInterval);
}

function closeStickyAd(event) {
  if (event) event.stopPropagation();
  const stickyAd = document.getElementById('sticky-ad');
  if (stickyAd) stickyAd.style.display = 'none';
}

// Initialization on DOM load
window.addEventListener('DOMContentLoaded', () => {
  const tgOverlay = document.getElementById('tg-forceadd-overlay');
  const ageOverlay = document.getElementById('age-gate-overlay');

  isTgVerified = localStorage.getItem('tg10Added') === 'true';
  isAgeVerified = sessionStorage.getItem('ageVerified') === 'true';

  if (!isTgVerified) {
    if (tgOverlay) {
      tgOverlay.style.display = 'flex';
      tgOverlay.style.opacity = '1';
    }
    if (ageOverlay) ageOverlay.style.display = 'none';
    updateTgProgressBar();
  } else if (!isAgeVerified) {
    if (tgOverlay) tgOverlay.style.display = 'none';
    if (ageOverlay) {
      ageOverlay.style.display = 'flex';
      ageOverlay.style.opacity = '1';
    }
  } else {
    if (tgOverlay) tgOverlay.style.display = 'none';
    if (ageOverlay) ageOverlay.style.display = 'none';
    // User already verified in this session -> load ads and start live features
    initAllAdsterraAds();
    setTimeout(receiveMessage, 1500);
    setTimeout(showIncomingCall, 10000);
  }
});

// Toast notification helper
function showToastNotification(msg) {
  let toastContainer = document.getElementById('toast-container');
  if (!toastContainer) {
    toastContainer = document.createElement('div');
    toastContainer.id = 'toast-container';
    toastContainer.className = 'toast-container';
    document.body.appendChild(toastContainer);
  }

  const toast = document.createElement('div');
  toast.className = 'toast-notification';
  toast.innerHTML = `
    <div class="toast-avatar" style="background: linear-gradient(135deg, #0088cc, #00b4d8);">
      <i class="fa-brands fa-telegram"></i>
    </div>
    <div class="toast-body">
      <div class="toast-name-row">
        <span class="toast-name">টেলিগ্রাম নোটিফিকেশন</span>
        <span class="toast-time">Just Now</span>
      </div>
      <div class="toast-msg">${msg}</div>
    </div>
  `;
  toastContainer.appendChild(toast);

  setTimeout(() => {
    toast.style.animation = 'slideInLeft 0.3s reverse forwards';
    setTimeout(() => toast.remove(), 300);
  }, 3500);
}

// ========================================================
// Real-time Notification & Inbox System
// ========================================================
const girlsMessages = [
  { name: "রিয়া", age: 21, msg: "হাই, ফ্রি আছো?", avatar: "linear-gradient(135deg, #ff2a85, #ff7300)" },
  { name: "মিম", age: 20, msg: "আমার সাথে চ্যাট করবা?", avatar: "linear-gradient(135deg, #db2777, #f472b6)" },
  { name: "সুমি", age: 22, msg: "হাই কলিজা......", avatar: "linear-gradient(135deg, #be185d, #ec4899)" },
  { name: "প্রিয়া", age: 19, msg: "ভিডিও কলে আসবা সোনা?", avatar: "linear-gradient(135deg, #9d174d, #f43f5e)" },
  { name: "মারিয়া", age: 23, msg: "তোমার সাথে একটু কথা বলতে চাই...", avatar: "linear-gradient(135deg, #8b5cf6, #ec4899)" },
  { name: "সাদিয়া", age: 21, msg: "হাই ফ্রেন্ড, কেমন আছো?", avatar: "linear-gradient(135deg, #a755e3, #d946ef)" },
  { name: "বৃষ্টি", age: 20, msg: "এখানে লাইভ আছি, জলদি আসো!", avatar: "linear-gradient(135deg, #db2777, #ec4899)" },
  { name: "জান্নাত", age: 22, msg: "তোমার বাড়ি কোথায় জান?", avatar: "linear-gradient(135deg, #ff007f, #ff7f00)" },
  { name: "মিতু", age: 19, msg: "আমাকে ফ্রেন্ড বানাবা?", avatar: "linear-gradient(135deg, #f43f5e, #be123c)" },
  { name: "নুসরাত", age: 24, msg: "হাই কি করো? ফ্রি আছো?", avatar: "linear-gradient(135deg, #ec4899, #db2777)" },
  { name: "তাসনিম", age: 21, msg: "আমার ভিডিও গ্রুপে জয়েন করো না!", avatar: "linear-gradient(135deg, #ff00ff, #800080)" },
  { name: "স্নেহা", age: 20, msg: "অনলাইনে চ্যাট করতে ভালো লাগে তোমার?", avatar: "linear-gradient(135deg, #db2777, #f472b6)" },
  { name: "রূপা", age: 22, msg: "একটু চ্যাট করবা আমার সাথে প্লিজ?", avatar: "linear-gradient(135deg, #ff2a85, #ff7300)" },
  { name: "আনিকা", age: 19, msg: "হ্যালো, তোমাকে দেখে খুব ভালো লেগেছে!", avatar: "linear-gradient(135deg, #be185d, #ec4899)" },
  { name: "কেয়া", age: 21, msg: "হাই সুইটহার্ট... কি করো?", avatar: "linear-gradient(135deg, #8b5cf6, #ec4899)" },
  { name: "লিমা", age: 20, msg: "ফ্রি থাকলে জলদি ইনবক্স করো প্লিজ", avatar: "linear-gradient(135deg, #9d174d, #f43f5e)" },
  { name: "পূজা", age: 22, msg: "তোমার ইমু বা হোয়াটসঅ্যাপ আইডি আছে?", avatar: "linear-gradient(135deg, #ff7300, #ec4899)" },
  { name: "এশা", age: 21, msg: "সরাসরি ক্যামেরা চ্যাট করতে চাও এখন?", avatar: "linear-gradient(135deg, #db2777, #be185d)" },
  { name: "নিপা", age: 23, msg: "মেসেজ দিচ্ছি নক দিচ্ছো না কেন গো?", avatar: "linear-gradient(135deg, #db2777, #ff007f)" },
  { name: "শিলা", age: 22, msg: "হাই জানু, কেমন আছো বলো?", avatar: "linear-gradient(135deg, #be185d, #f43f5e)" },
  { name: "মুন্নি", age: 20, msg: "তোমার সাথে কথা বলতে মন চাইছে...", avatar: "linear-gradient(135deg, #a755e3, #db2777)" },
  { name: "মৌ", age: 19, msg: "হাই কলিজা, চ্যাট রুমে লাইভে আসো!", avatar: "linear-gradient(135deg, #ff2a85, #8b5cf6)" },
  { name: "আশা", age: 21, msg: "আমার সাথে একটু ভালো কোয়ালিটি টাইম কাটাবা?", avatar: "linear-gradient(135deg, #ff7300, #ff2a85)" },
  { name: "ফারাহ", age: 22, msg: "তোমার পার্সোনাল নাম্বারটা দিবা সোনা?", avatar: "linear-gradient(135deg, #db2777, #ec4899)" },
  { name: "তানহা", age: 20, msg: "একটু নক দাও না সোনা... কথা বলবো!", avatar: "linear-gradient(135deg, #8b5cf6, #be185d)" },
  { name: "ববি", age: 23, msg: "সরাসরি ভিডিও ম্যাচিং এ ক্লিক করো জান!", avatar: "linear-gradient(135deg, #9d174d, #ff7f00)" },
  { name: "তানিয়া", age: 21, msg: "আমি কিন্তু তোমার চ্যাটের ওয়েট করছি...", avatar: "linear-gradient(135deg, #be185d, #ec4899)" },
  { name: "নেহা", age: 22, msg: "হাই ডার্লিং, কি করো? একা আছি!", avatar: "linear-gradient(135deg, #ff007f, #ff7f00)" },
  { name: "সোনিয়া", age: 20, msg: "ভিডিও চ্যাটে আসো, একটু মজা করি!", avatar: "linear-gradient(135deg, #db2777, #8b5cf6)" },
  { name: "লাবনী", age: 21, msg: "অনলাইন ভালো মনের একটা ফ্রেন্ড দরকার...", avatar: "linear-gradient(135deg, #be185d, #f43f5e)" }
];

let receivedCount = 0;
let unreadCount = 0;
const receivedMessages = [];

function playNotificationSound() {
  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = 'sine';
    osc.frequency.setValueAtTime(880, ctx.currentTime);
    osc.frequency.exponentialRampToValueAtTime(1200, ctx.currentTime + 0.12);
    gain.gain.setValueAtTime(0.12, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.25);
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start();
    osc.stop(ctx.currentTime + 0.25);
  } catch(e) {}
}

function toggleInbox() {
  const drawer = document.getElementById('inbox-drawer');
  if (!drawer) return;
  drawer.classList.toggle('active');
  
  if (drawer.classList.contains('active')) {
    unreadCount = 0;
    updateBadge();
    const unreadRows = document.querySelectorAll('.inbox-row.unread');
    unreadRows.forEach(row => row.classList.remove('unread'));
  }
}

function showInboxList() {
  const chatDetail = document.getElementById('chat-detail-view');
  if (chatDetail) chatDetail.classList.remove('active');
}

function triggerChatClick() {
  openChatModal('chatUnlock');
}

function updateBadge() {
  const badge = document.getElementById('inbox-badge-count');
  const headerCount = document.getElementById('inbox-header-count');
  
  if (headerCount) headerCount.innerText = receivedMessages.length;
  
  if (badge) {
    if (unreadCount > 0) {
      badge.innerText = unreadCount;
      badge.style.display = 'block';
    } else {
      badge.style.display = 'none';
    }
  }
}

function openGirlChat(index) {
  const girl = receivedMessages[index];
  if (!girl) return;
  
  const activeAvatar = document.getElementById('chat-active-avatar');
  const activeName = document.getElementById('chat-active-name');
  
  if (activeAvatar) {
    activeAvatar.style.background = girl.avatar;
    activeAvatar.innerHTML = `<i class="fa-solid fa-user-dress"></i>`;
  }
  if (activeName) activeName.innerText = girl.name + " (" + girl.age + ")";
  
  const messagesBody = document.getElementById('chat-messages-body');
  if (messagesBody) {
    messagesBody.innerHTML = `
      <div class="chat-bubble received">
        ${girl.msg}
        <div class="chat-bubble-time">এখনই</div>
      </div>
    `;
  }
  
  const chatDetail = document.getElementById('chat-detail-view');
  if (chatDetail) chatDetail.classList.add('active');
}

function receiveMessage() {
  if (!isAgeVerified) return;
  if (receivedCount >= girlsMessages.length) return;
  
  const currentMsgObj = girlsMessages[receivedCount];
  receivedMessages.push(currentMsgObj);
  
  const drawer = document.getElementById('inbox-drawer');
  if (drawer && !drawer.classList.contains('active')) {
    unreadCount++;
  }
  
  playNotificationSound();
  updateBadge();

  const emptyState = document.getElementById('inbox-empty-state');
  if (emptyState) emptyState.remove();

  const listContainer = document.getElementById('inbox-items-container');
  if (listContainer) {
    const itemIndex = receivedMessages.length - 1;
    const row = document.createElement('div');
    row.className = `inbox-row ${drawer && !drawer.classList.contains('active') ? 'unread' : ''}`;
    row.onclick = () => openGirlChat(itemIndex);
    row.innerHTML = `
      <div class="inbox-row-avatar" style="background: ${currentMsgObj.avatar};">
        <i class="fa-solid fa-user-dress"></i>
        <span class="status-dot"></span>
      </div>
      <div class="inbox-row-body">
        <div class="inbox-row-name-row">
          <span class="inbox-row-name">${currentMsgObj.name} (${currentMsgObj.age})</span>
          <span class="inbox-row-time">এখনই</span>
        </div>
        <div class="inbox-row-msg">${currentMsgObj.msg}</div>
      </div>
      <span class="inbox-row-dot"></span>
    `;
    listContainer.insertBefore(row, listContainer.firstChild);
  }

  const toastContainer = document.getElementById('toast-container');
  if (toastContainer) {
    const itemIndex = receivedMessages.length - 1;
    const toast = document.createElement('div');
    toast.className = 'toast-notification';
    toast.onclick = (e) => {
      e.stopPropagation();
      toggleInbox();
      openGirlChat(itemIndex);
      toast.remove();
    };
    
    toast.innerHTML = `
      <div class="toast-avatar" style="background: ${currentMsgObj.avatar};">
        <i class="fa-solid fa-user-dress"></i>
        <span class="status-badge"></span>
      </div>
      <div class="toast-body">
        <div class="toast-name-row">
          <span class="toast-name">${currentMsgObj.name} (${currentMsgObj.age})</span>
          <span class="toast-time">Just Now</span>
        </div>
        <div class="toast-msg">${currentMsgObj.msg}</div>
      </div>
    `;
    toastContainer.appendChild(toast);

    setTimeout(() => {
      toast.style.animation = 'slideInLeft 0.3s reverse forwards';
      setTimeout(() => {
        toast.remove();
      }, 300);
    }, 4000);
  }

  receivedCount++;

  if (receivedCount < girlsMessages.length) {
    const nextDelay = Math.floor(Math.random() * 3000) + 4000;
    setTimeout(receiveMessage, nextDelay);
  } else {
    receivedCount = 0;
    setTimeout(receiveMessage, 6000);
  }
}

// ========================================================
// Simulated Calling Logic
// ========================================================
let ringtoneInterval = null;
let ringtoneAudioCtx = null;

function showIncomingCall() {
  if (!isAgeVerified) return;
  
  const callBox = document.getElementById('incoming-call-box');
  if (!callBox) return;
  callBox.classList.add('active');
  
  try {
    ringtoneAudioCtx = new (window.AudioContext || window.webkitAudioContext)();
    ringtoneInterval = setInterval(() => {
      playRingChime(ringtoneAudioCtx, 0);
      playRingChime(ringtoneAudioCtx, 0.15);
      playRingChime(ringtoneAudioCtx, 0.3);
    }, 2000);
  } catch(e) {}
}

function playRingChime(ctx, delay) {
  if (!ctx || ctx.state === 'closed') return;
  const osc1 = ctx.createOscillator();
  const osc2 = ctx.createOscillator();
  const gain = ctx.createGain();
  
  osc1.type = 'sine';
  osc1.frequency.setValueAtTime(800, ctx.currentTime + delay);
  osc2.type = 'sine';
  osc2.frequency.setValueAtTime(804, ctx.currentTime + delay);
  
  gain.gain.setValueAtTime(0.08, ctx.currentTime + delay);
  gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + delay + 0.6);
  
  osc1.connect(gain);
  osc2.connect(gain);
  gain.connect(ctx.destination);
  
  osc1.start(ctx.currentTime + delay);
  osc2.start(ctx.currentTime + delay);
  
  osc1.stop(ctx.currentTime + delay + 0.6);
  osc2.stop(ctx.currentTime + delay + 0.6);
}

function handleCall(accept) {
  const callBox = document.getElementById('incoming-call-box');
  if (callBox) callBox.classList.remove('active');
  
  clearInterval(ringtoneInterval);
  if (ringtoneAudioCtx) {
    try { ringtoneAudioCtx.close(); } catch(err) {}
  }

  if (accept) {
    triggerAdRedirect();
    openChatModal('video');
  }

  setTimeout(showIncomingCall, 30000);
}

// ========================================================
// Match Wheel Spinner Logic
// ========================================================
let isSpinning = false;
function spinWheel() {
  if (isSpinning) return;
  isSpinning = true;
  
  const canvas = document.getElementById('wheel-canvas');
  if (!canvas) return;
  const degrees = 1440 + Math.floor(Math.random() * 360);
  canvas.style.transform = `rotate(${degrees}deg)`;
  
  let spinAudCtx = null;
  try {
    spinAudCtx = new (window.AudioContext || window.webkitAudioContext)();
    for (let i = 0; i < 20; i++) {
      setTimeout(() => {
        playSpinTick(spinAudCtx);
      }, i * i * 10);
    }
  } catch(e) {}

  setTimeout(() => {
    isSpinning = false;
    if (spinAudCtx) spinAudCtx.close();
    triggerAdRedirect();
    openChatModal('girls');
  }, 4000);
}

function playSpinTick(ctx) {
  if (!ctx || ctx.state === 'closed') return;
  const osc = ctx.createOscillator();
  const gain = ctx.createGain();
  osc.type = 'sine';
  osc.frequency.setValueAtTime(600, ctx.currentTime);
  gain.gain.setValueAtTime(0.05, ctx.currentTime);
  gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.05);
  osc.connect(gain);
  gain.connect(ctx.destination);
  osc.start();
  osc.stop(ctx.currentTime + 0.05);
}

// ========================================================
// Global DOM Startup Initialization
// ========================================================
document.addEventListener('DOMContentLoaded', () => {
  const tgOverlay = document.getElementById('tg-forceadd-overlay');
  const ageOverlay = document.getElementById('age-gate-overlay');

  if (!isTgVerified) {
    if (tgOverlay) {
      tgOverlay.style.display = 'flex';
      tgOverlay.style.opacity = '1';
    }
    if (ageOverlay) {
      ageOverlay.style.display = 'none';
    }
    initTelegramGateState();
  } else if (!isAgeVerified) {
    if (tgOverlay) tgOverlay.style.display = 'none';
    if (ageOverlay) {
      ageOverlay.style.display = 'flex';
      ageOverlay.style.opacity = '1';
    }
  } else {
    if (tgOverlay) tgOverlay.style.display = 'none';
    if (ageOverlay) ageOverlay.style.display = 'none';
    initAllAdsterraAds();
    setTimeout(receiveMessage, 1200);
    setTimeout(showIncomingCall, 7000);
  }
});

