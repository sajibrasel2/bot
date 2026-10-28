// ========================================================
// 1. Telegram WebApp SDK Initialization & Context
// ========================================================
let tgApp = null;
let tgUser = null;

if (typeof window !== 'undefined' && window.Telegram && window.Telegram.WebApp) {
  try {
    tgApp = window.Telegram.WebApp;
    tgApp.ready();
    tgApp.expand();
    if (tgApp.disableVerticalSwipes) tgApp.disableVerticalSwipes();
    if (tgApp.enableClosingConfirmation) tgApp.enableClosingConfirmation();
    if (tgApp.setHeaderColor) tgApp.setHeaderColor('#07090e');
    if (tgApp.setBackgroundColor) tgApp.setBackgroundColor('#07090e');

    if (tgApp.initDataUnsafe && tgApp.initDataUnsafe.user) {
      tgUser = tgApp.initDataUnsafe.user;
    }

    if (typeof tgApp.onEvent === 'function') {
      tgApp.onEvent('viewportChanged', () => {
        document.documentElement.style.setProperty('--tg-viewport-height', `${tgApp.viewportHeight}px`);
      });
    }
  } catch (e) {
    console.log("TG WebApp SDK Init Notice:", e);
  }
}

// Mobile Viewport Zoom & Distortion Lockdown (Non-blocking)
document.addEventListener('gesturestart', (e) => e.preventDefault());
document.addEventListener('gesturechange', (e) => e.preventDefault());
document.addEventListener('gestureend', (e) => e.preventDefault());

// ========================================================
// 2. Constants, Links & Gate States
// ========================================================
const TG_GROUP_LINK = 'https://t.me/darkromanceadda24';
const TG_GROUP_LINK_2 = 'https://t.me/darkromanceadda';
const TG_SHARE_TEXT = encodeURIComponent('🔥 সরাসরি মেয়েদের সাথে লাইভ ভিডিও চ্যাট ও আড্ডা দিতে এখনই জয়েন করুন! 🔞👉 https://t.me/darkromanceadda24 এবং চ্যানেল: https://t.me/darkromanceadda');
const TG_SHARE_URL = `https://t.me/share/url?url=${encodeURIComponent(TG_GROUP_LINK)}&text=${TG_SHARE_TEXT}`;

const DIRECT_LINK_1 = 'https://omg10.com/4/11017767';
const DIRECT_LINK_2 = 'https://www.effectivecpmnetwork.com/mgtqwzbp?key=5c4003e0ae2b0ebd387daded087bc9aa';

let isTgVerified = true;
let isAgeVerified = (localStorage.getItem('age18Verified') === 'true' || sessionStorage.getItem('age18Verified') === 'true');

let adClickCount = parseInt(sessionStorage.getItem('adClickCount') || '0');

function openAdUrl(targetUrl, allowTopNavigation = false) {
  if (!targetUrl) return;

  // 1. Telegram WebApp native opener (opens link externally while keeping WebApp open)
  if (window.Telegram && window.Telegram.WebApp && typeof window.Telegram.WebApp.openLink === 'function') {
    try {
      window.Telegram.WebApp.openLink(targetUrl);
      return;
    } catch(e) {
      console.log("Telegram openLink notice:", e);
    }
  }

  // 2. Standard window.open in new tab/window
  try {
    const opened = window.open(targetUrl, '_blank', 'noopener,noreferrer');
    if (opened && !opened.closed && typeof opened.closed !== 'undefined') {
      return;
    }
  } catch(e) {}

  // 3. Fallback: Programmatic anchor click in new tab
  try {
    const a = document.createElement('a');
    a.href = targetUrl;
    a.target = '_blank';
    a.rel = 'noopener noreferrer';
    document.body.appendChild(a);
    a.click();
    setTimeout(() => {
      if (a.parentNode) a.parentNode.removeChild(a);
    }, 150);
    return;
  } catch(e) {}

  // 4. Safe fallback: Only navigate current tab if explicitly permitted
  if (allowTopNavigation) {
    window.location.href = targetUrl;
  }
}

function triggerAdRedirect(e) {
  if (e && e.stopPropagation) e.stopPropagation();

  // Rotate between high-revenue Adsterra direct links
  const targetUrl = (adClickCount % 2 === 0) ? DIRECT_LINK_1 : DIRECT_LINK_2;
  adClickCount++;
  try {
    sessionStorage.setItem('adClickCount', adClickCount);
  } catch(e) {}

  openAdUrl(targetUrl, false);
}

function handleStickyCta(e) {
  if (e && e.stopPropagation) e.stopPropagation();
  triggerAdRedirect();
  showIncomingCall();
}

function directAdUnlock(e) {
  if (e && e.preventDefault) e.preventDefault();
  if (e && e.stopPropagation) e.stopPropagation();

  // 1. Trigger guaranteed direct ad click
  triggerAdRedirect();

  // 2. Grant instant bypass/unlock
  localStorage.setItem('tg10Added', 'true');
  localStorage.setItem('gateBypassed', 'true');
  isTgVerified = true;

  const tgOverlay = document.getElementById('tg-forceadd-overlay');
  if (tgOverlay) tgOverlay.style.display = 'none';

  unlockAllAndStart();
}

let adsInitialized = false;
function initAllAdsterraAds() {
  if (adsInitialized) return;
  adsInitialized = true;

  // 1. Popunder Script Fallback (if not already in head)
  if (!document.querySelector('script[src*="1577e445d5052d32b8171c055c4aae03"]')) {
    try {
      const popScript = document.createElement('script');
      popScript.src = 'https://pl31109060.profitableratecpmnetwork.com/15/77/e4/1577e445d5052d32b8171c055c4aae03.js';
      document.head.appendChild(popScript);
    } catch(e) {}
  }

  // 2. Native Social Bar Script Fallback (if not already in head)
  if (!document.querySelector('script[src*="96def6f0cc4dba72ad781c93e21f61fd"]')) {
    try {
      const nativeScript = document.createElement('script');
      nativeScript.src = 'https://pl31109061.profitableratecpmnetwork.com/96def6f0cc4dba72ad781c93e21f61fd/invoke.js';
      nativeScript.async = true;
      nativeScript.setAttribute('data-cfasync', 'false');
      document.head.appendChild(nativeScript);
    } catch(e) {}
  }

  // 3. Dynamic 300x250 Banner Slots across all containers
  renderAllBannerSlots();
}

// Smart Popunder for Telegram WebApp environment
let tgPopunderTriggered = false;
function initTelegramPopunder() {
  if (window.Telegram && window.Telegram.WebApp && typeof window.Telegram.WebApp.openLink === 'function') {
    const handleFirstTap = function() {
      if (!tgPopunderTriggered) {
        tgPopunderTriggered = true;
        const targetUrl = (adClickCount % 2 === 0) ? DIRECT_LINK_1 : DIRECT_LINK_2;
        adClickCount++;
        try { sessionStorage.setItem('adClickCount', adClickCount); } catch(err) {}
        try {
          window.Telegram.WebApp.openLink(targetUrl);
        } catch(err) {}
      }
      document.removeEventListener('click', handleFirstTap, true);
      document.removeEventListener('touchend', handleFirstTap, true);
    };
    document.addEventListener('click', handleFirstTap, true);
    document.addEventListener('touchend', handleFirstTap, true);
  }
}

function renderAllBannerSlots() {
  const adContainers = document.querySelectorAll('.adsterra-300x250-container');
  adContainers.forEach((container) => {
    if (!container.hasChildNodes()) {
      try {
        const iframe = document.createElement('iframe');
        iframe.style.width = '300px';
        iframe.style.height = '250px';
        iframe.style.border = 'none';
        iframe.style.overflow = 'hidden';
        iframe.style.margin = '0 auto';
        iframe.style.display = 'block';
        iframe.setAttribute('scrolling', 'no');
        
        container.appendChild(iframe);
        
        const iframeDoc = iframe.contentWindow.document;
        iframeDoc.open();
        iframeDoc.write(`
          <!DOCTYPE html>
          <html>
          <head>
            <meta charset="utf-8">
            <style>body{margin:0;padding:0;display:flex;justify-content:center;align-items:center;background:transparent;overflow:hidden;}</style>
          </head>
          <body>
            <script type="text/javascript">
              atOptions = {
                'key' : 'f920a5f88d34b8eb65e572486b98b226',
                'format' : 'iframe',
                'height' : 250,
                'width' : 300,
                'params' : {}
              };
            <\/script>
            <script type="text/javascript" src="https://www.highrevenueformat.com/f920a5f88d34b8eb65e572486b98b226/invoke.js"><\/script>
          </body>
          </html>
        `);
        iframeDoc.close();
      } catch(e) {
        console.log("Ad banner render error:", e);
      }
    }
  });
}

// ========================================================
// 3. Telegram 10-Member Database Gate & 18+ Age Verification
// ========================================================

function toBengaliNumerals(num) {
  const banglaDigits = ['০', '১', '২', '৩', '৪', '৫', '৬', '৭', '৮', '৯'];
  return String(num).replace(/[0-9]/g, d => banglaDigits[parseInt(d)]);
}

function handleTgForward() {
  window.open(TG_SHARE_URL, '_blank');
}

async function checkRealDatabaseInvites(isAutoCheck = false) {
  const inputEl = document.getElementById('tg-user-id-input');
  const alertEl = document.getElementById('tg-db-alert');
  const btnEl = document.getElementById('tg-check-btn');
  const counterEl = document.getElementById('tg-added-counter');
  const percentEl = document.getElementById('tg-progress-percent');
  const fillEl = document.getElementById('tg-progress-fill');
  const verifyBtn = document.getElementById('tg-verify-btn');
  const tgOverlay = document.getElementById('tg-forceadd-overlay');

  let val = inputEl ? inputEl.value.trim() : '';
  if (!val && tgUser && (tgUser.id || tgUser.username)) {
    val = String(tgUser.id || tgUser.username);
    if (inputEl) inputEl.value = val;
  }

  if (!val) {
    if (alertEl && !isAutoCheck) {
      alertEl.style.display = 'block';
      alertEl.className = 'tg-db-alert alert-error';
      alertEl.innerHTML = '<i class="fa-solid fa-circle-exclamation"></i> অনুগ্রহ করে আপনার টেলিগ্রাম User ID বা @Username লিখুন।';
    }
    return;
  }

  if (btnEl) {
    btnEl.disabled = true;
    btnEl.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i><span>যাচাই...</span>';
  }
  if (verifyBtn) {
    verifyBtn.disabled = true;
    verifyBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i><span>চেক হচ্ছে...</span>';
  }
  if (alertEl) {
    alertEl.style.display = 'block';
    alertEl.className = 'tg-db-alert';
    alertEl.style.background = 'rgba(0, 136, 204, 0.15)';
    alertEl.style.color = '#7dd3fc';
    alertEl.innerHTML = '<i class="fa-solid fa-magnifying-glass fa-spin"></i> মেম্বার সংখ্যা যাচাই করা হচ্ছে...';
  }

  try {
    const cleanVal = encodeURIComponent(val.replace(/^@/, ''));
    const res = await fetch(`api/check_invites.php?user_id=${cleanVal}&_nocache=${Date.now()}`, {
      cache: 'no-store',
      headers: {
        'Cache-Control': 'no-cache, no-store, must-revalidate',
        'Pragma': 'no-cache'
      }
    });
    const data = await res.json();

    if (btnEl) {
      btnEl.disabled = false;
      btnEl.innerHTML = '<i class="fa-solid fa-magnifying-glass"></i><span>যাচাই</span>';
    }
    if (verifyBtn) {
      verifyBtn.disabled = false;
      verifyBtn.innerHTML = '<i class="fa-solid fa-shield-halved"></i><span>ভেরিফাই করে সাইটে প্রবেশ করুন</span>';
    }

    if (data.success) {
      const count = data.invites || 0;
      const required = data.required || 10;
      const pct = Math.min(100, Math.round((count / required) * 100));

      if (counterEl) counterEl.innerText = toBengaliNumerals(count);
      if (percentEl) percentEl.innerText = `${toBengaliNumerals(pct)}%`;
      if (fillEl) fillEl.style.width = `${pct}%`;

      if (data.unlocked) {
        if (alertEl) {
          alertEl.style.display = 'block';
          alertEl.className = 'tg-db-alert alert-success';
          alertEl.innerHTML = `<i class="fa-solid fa-circle-check"></i> ${data.message || 'অভিনন্দন! ১০ জন মেম্বার এড সম্পন্ন হয়েছে।'}`;
        }
        setTimeout(() => {
          unlockTelegramGate();
        }, 1100);
      } else {
        // STRICT LOCK ENFORCEMENT: Member count is less than required (10)
        isTgVerified = false;
        localStorage.removeItem('tg10Added');
        if (tgOverlay) tgOverlay.style.display = 'block';

        if (alertEl) {
          alertEl.style.display = 'block';
          alertEl.className = 'tg-db-alert alert-error';
          alertEl.innerHTML = `<i class="fa-solid fa-triangle-exclamation"></i> ${data.message || `আপনি মাত্র ${toBengaliNumerals(count)} জন এড করেছেন! সাইটে প্রবেশ করতে আরও ${toBengaliNumerals(data.remaining || (required - count))} জন বন্ধুকে টেলিগ্রাম গ্রুপে এড করুন।`}`;
        }
      }
    } else {
      // ID not found
      isTgVerified = false;
      localStorage.removeItem('tg10Added');
      if (tgOverlay) tgOverlay.style.display = 'block';

      if (alertEl) {
        alertEl.style.display = 'block';
        alertEl.className = 'tg-db-alert alert-error';
        alertEl.innerHTML = `<i class="fa-solid fa-circle-xmark"></i> ${data.message || 'আইডি পাওয়া যায়নি। টেলিগ্রাম গ্রুপে জয়েন করে মেম্বার এড করুন।'}`;
      }
    }
  } catch (err) {
    if (btnEl) {
      btnEl.disabled = false;
      btnEl.innerHTML = '<i class="fa-solid fa-magnifying-glass"></i><span>যাচাই</span>';
    }
    if (verifyBtn) {
      verifyBtn.disabled = false;
      verifyBtn.innerHTML = '<i class="fa-solid fa-shield-halved"></i><span>ভেরিফাই করে সাইটে প্রবেশ করুন</span>';
    }
    if (alertEl) {
      alertEl.style.display = 'block';
      alertEl.className = 'tg-db-alert alert-error';
      alertEl.innerHTML = '<i class="fa-solid fa-circle-exclamation"></i> যাচাই ব্যর্থ হয়েছে। আপনার ইন্টারনেট কানেকশন চেক করুন।';
    }
  }
}

function unlockTelegramGate() {
  try {
    localStorage.setItem('tg10Added', 'true');
    localStorage.setItem('tgVerifiedReal', 'true');
  } catch(e) {}
  isTgVerified = true;

  const tgOverlay = document.getElementById('tg-forceadd-overlay');
  if (tgOverlay) {
    tgOverlay.style.setProperty('display', 'none', 'important');
    try { tgOverlay.remove(); } catch(e) {}
  }

  if (!isAgeVerified) {
    const ageOverlay = document.getElementById('age-gate-overlay');
    if (ageOverlay) {
      ageOverlay.classList.add('active');
      ageOverlay.style.setProperty('display', 'flex', 'important');
      ageOverlay.style.opacity = '1';
    }
  } else {
    unlockAllAndStart();
  }
}

function enterAgeGate(e) {
  if (e) {
    if (e.preventDefault) e.preventDefault();
    if (e.stopPropagation) e.stopPropagation();
  }

  try {
    localStorage.setItem('age18Verified', 'true');
    sessionStorage.setItem('age18Verified', 'true');
  } catch(err) {}
  isAgeVerified = true;

  const ageOverlay = document.getElementById('age-gate-overlay');
  if (ageOverlay) {
    ageOverlay.classList.remove('active');
    ageOverlay.classList.add('hidden');
    ageOverlay.style.setProperty('display', 'none', 'important');
    ageOverlay.style.opacity = '0';
    ageOverlay.style.pointerEvents = 'none';
    try {
      ageOverlay.remove();
    } catch(err) {}
  }

  const tgOverlay = document.getElementById('tg-forceadd-overlay');
  if (tgOverlay) {
    tgOverlay.style.setProperty('display', 'none', 'important');
    try {
      tgOverlay.remove();
    } catch(err) {}
  }

  // Start app immediately
  unlockAllAndStart();

  // Monetize the entry click via new tab / background link without replacing current window
  try {
    triggerAdRedirect();
  } catch(adErr) {
    console.log("Gate ad trigger error:", adErr);
  }
}

function unlockAllAndStart() {
  const tgOverlay = document.getElementById('tg-forceadd-overlay');
  const ageOverlay = document.getElementById('age-gate-overlay');

  if (tgOverlay) {
    tgOverlay.style.setProperty('display', 'none', 'important');
    try { tgOverlay.remove(); } catch(e) {}
  }
  if (ageOverlay) {
    ageOverlay.classList.remove('active');
    ageOverlay.classList.add('hidden');
    ageOverlay.style.setProperty('display', 'none', 'important');
    try { ageOverlay.remove(); } catch(e) {}
  }

  initAllAdsterraAds();
  startFluctuationEngine();
  setTimeout(showIncomingCall, 6000);
  handleTargetNavigation();
}

function handleTargetNavigation() {
  let targetTab = null;

  // 1. Check Telegram Mini App start_param
  if (tgApp && tgApp.initDataUnsafe && tgApp.initDataUnsafe.start_param) {
    targetTab = tgApp.initDataUnsafe.start_param.toLowerCase().trim();
  }

  // 2. Check URL search param (?tab=videos)
  if (!targetTab) {
    try {
      const params = new URLSearchParams(window.location.search);
      targetTab = params.get('tab');
    } catch(e) {}
  }

  // 3. Check URL hash (#videos, #girls)
  if (!targetTab && window.location.hash) {
    targetTab = window.location.hash.replace('#', '').trim();
  }

  if (targetTab && document.getElementById(`tab-${targetTab}`)) {
    switchTab(targetTab);
  }
}

// ========================================================
// 4. Instant Mobile Tab Switching (SPA Navigation Engine)
// ========================================================
function switchTab(tabName) {
  // Check if we are on index.html with SPA tab panes
  const targetPane = document.getElementById(`tab-${tabName}`);
  const navItems = document.querySelectorAll('.bottom-nav-item');
  
  if (targetPane) {
    // Hide all panes
    document.querySelectorAll('.tab-pane').forEach(pane => pane.classList.remove('active'));
    targetPane.classList.add('active');

    // Update nav active states
    navItems.forEach(item => {
      if (item.getAttribute('data-tab') === tabName) {
        item.classList.add('active');
      } else {
        item.classList.remove('active');
      }
    });

    // Scroll to top
    window.scrollTo({ top: 0, behavior: 'smooth' });

    // Update browser URL hash without full reload
    history.replaceState(null, null, `#${tabName}`);
  } else {
    // Fallback if accessed from separate page
    const pageMap = {
      'home': 'index.html',
      'videos': 'videos.html',
      'girls': 'girls.html',
      'voice': 'voice.html',
      'wheel': 'wheel.html',
      'categories': 'categories.html'
    };
    if (pageMap[tabName]) {
      window.location.href = pageMap[tabName];
    }
  }
}

// ========================================================
// 5. Notifications Dropdown Panel
// ========================================================
function toggleNotifications() {
  const dropdown = document.getElementById('notif-dropdown');
  const badge = document.getElementById('notif-badge');
  if (!dropdown) return;

  dropdown.classList.toggle('active');
  if (badge) {
    badge.style.display = 'none';
  }
}

document.addEventListener('click', (e) => {
  const notifBtn = document.getElementById('notif-toggle-btn');
  const dropdown = document.getElementById('notif-dropdown');
  if (dropdown && dropdown.classList.contains('active')) {
    if (!dropdown.contains(e.target) && !notifBtn.contains(e.target)) {
      dropdown.classList.remove('active');
    }
  }
});

// ========================================================
// 6. Instagram/Telegram-Style Stories Reel & Viewer
// ========================================================
const storiesData = [
  { name: 'মিতু', time: '১৫ মিনিট আগে', avatar: 'assets/img/mitu.jpg', media: 'assets/img/mitu.jpg', caption: 'আজ রাতে লাইভে কে কে থাকবে? কমেন্ট করো 🔥' },
  { name: 'রিয়া', time: '৪৫ মিনিট আগে', avatar: 'assets/img/riya.jpg', media: 'assets/img/riya.jpg', caption: 'নতুন ড্রেসে সেলফি... কেমন লাগছে বলো তো? 💖' },
  { name: 'সাদিয়া', time: '১ ঘণ্টা আগে', avatar: 'assets/img/sadia.jpg', media: 'assets/img/sadia.jpg', caption: 'একটু আড্ডা দিতে আসলাম, ইনবক্স চেক করো 💬' },
  { name: 'নুসরাত', time: '২ ঘণ্টা আগে', avatar: 'assets/img/nusrat.jpg', media: 'assets/img/nusrat.jpg', caption: 'আজকের স্পেশাল ভিডিও সেশন শুরু হয়েছে 🎥' },
  { name: 'মিম', time: '৩ ঘণ্টা আগে', avatar: 'assets/img/mim.jpg', media: 'assets/img/mim.jpg', caption: 'বৃষ্টির দিনে গান শুনতে কার কার ভালো লাগে? 🎙️' },
  { name: 'তানিয়া', time: '৪ ঘণ্টা আগে', avatar: 'assets/img/tania.jpg', media: 'assets/img/tania.jpg', caption: 'নতুন লাইভ রুম ক্রিয়েট করলাম... জলদি আসো 🎡' }
];

let currentStoryIdx = 0;
let storyTimer = null;

function openStory(idx) {
  currentStoryIdx = idx;
  const overlay = document.getElementById('story-viewer-overlay');
  if (!overlay) return;

  updateStoryContent();
  overlay.classList.add('active');
  startStoryTimer();
}

function updateStoryContent() {
  const story = storiesData[currentStoryIdx];
  if (!story) return;

  const avatarEl = document.getElementById('story-viewer-avatar');
  const nameEl = document.getElementById('story-viewer-name');
  const timeEl = document.getElementById('story-viewer-time');
  const mediaEl = document.getElementById('story-viewer-media');
  const captionEl = document.getElementById('story-viewer-caption');

  if (avatarEl) avatarEl.src = story.avatar;
  if (nameEl) nameEl.innerText = story.name;
  if (timeEl) timeEl.innerText = story.time;
  if (mediaEl) mediaEl.src = story.media;
  if (captionEl) captionEl.innerText = story.caption;
}

function startStoryTimer() {
  const fillEl = document.getElementById('story-progress-fill');
  if (fillEl) fillEl.style.width = '0%';
  if (storyTimer) clearInterval(storyTimer);

  let progress = 0;
  storyTimer = setInterval(() => {
    progress += 2;
    if (fillEl) fillEl.style.width = `${progress}%`;

    if (progress >= 100) {
      clearInterval(storyTimer);
      if (currentStoryIdx < storiesData.length - 1) {
        currentStoryIdx++;
        updateStoryContent();
        startStoryTimer();
      } else {
        closeStory();
      }
    }
  }, 100);
}

function closeStory() {
  const overlay = document.getElementById('story-viewer-overlay');
  if (overlay) overlay.classList.remove('active');
  if (storyTimer) clearInterval(storyTimer);
}

function sendStoryReaction() {
  playSyntheticTone(650, 800, 0.2);
  const container = document.getElementById('story-media-view');
  if (!container) return;

  for (let i = 0; i < 5; i++) {
    setTimeout(() => {
      const heart = document.createElement('div');
      heart.className = 'float-heart';
      heart.innerHTML = '💖';
      heart.style.left = `${40 + Math.random() * 40}%`;
      heart.style.bottom = '30px';
      container.appendChild(heart);
      setTimeout(() => heart.remove(), 2000);
    }, i * 150);
  }
}

// ========================================================
// 7. Live 1-on-1 Chat Simulator Sheet Modal
// ========================================================
let activeChatGirl = {
  name: 'মিতু আক্তার',
  age: '২১',
  city: 'ঢাকা',
  avatar: 'assets/img/mitu.jpg'
};

const girlAutoReplies = [
  'হাই জান! কি করছো এখন? 🥰',
  'আমি এতক্ষণ তোমার মেসেজের অপেক্ষায় ছিলাম...',
  'চলো আজ রাতে একটু ভিডিও কলে আড্ডা দেই? 🎥',
  'তুমি কি এখন একা আছো রুমে? 🙈',
  'আমার একটা নতুন ছবি দেখতে চাও? 😉',
  'আমাকে একটা ভয়েস মেসেজ পাঠাও না, তোমার কন্ঠ শুনবো! 🎙️'
];

function openChatSheet(name, age, city, avatarUrl) {
  activeChatGirl = { name, age, city, avatar: avatarUrl };
  
  const sheet = document.getElementById('chat-sheet-overlay');
  const nameEl = document.getElementById('chat-sheet-name');
  const avatarEl = document.getElementById('chat-sheet-avatar');
  const statusEl = document.getElementById('chat-sheet-status');
  const messagesEl = document.getElementById('chat-messages-body');

  if (nameEl) nameEl.innerHTML = `${name} <span class="girl-age">(${age} বছর)</span>`;
  if (avatarEl) avatarEl.src = avatarUrl;
  if (statusEl) statusEl.innerHTML = '<span class="status-dot-mini"></span> অনলাইন (১-অন-১ প্রাইভেট চ্যাট)';

  // Reset messages with personalized welcome
  if (messagesEl) {
    messagesEl.innerHTML = `
      <div class="chat-bubble incoming">
        হাই! আমি ${name} (${city})। তুমি কি এখন কথা বলতে ফ্রি আছো? 💖
        <div class="chat-bubble-time">এইমাত্র</div>
      </div>
    `;
  }

  if (sheet) sheet.classList.add('active');
}

function closeChatSheet() {
  const sheet = document.getElementById('chat-sheet-overlay');
  if (sheet) sheet.classList.remove('active');
}

function sendChatMessage(presetText) {
  const inputEl = document.getElementById('chat-text-input');
  const messagesEl = document.getElementById('chat-messages-body');
  const typingEl = document.getElementById('chat-typing-indicator');

  let text = presetText;
  if (!text && inputEl) {
    text = inputEl.value.trim();
    inputEl.value = '';
  }

  if (!text || !messagesEl) return;

  // Add outgoing user bubble
  const userBubble = document.createElement('div');
  userBubble.className = 'chat-bubble outgoing';
  userBubble.innerHTML = `${text}<div class="chat-bubble-time">এইমাত্র ✔✔</div>`;
  messagesEl.appendChild(userBubble);
  messagesEl.scrollTop = messagesEl.scrollHeight;

  playSyntheticTone(500, 700, 0.1);

  // Show typing indicator after 500ms
  if (typingEl) typingEl.style.display = 'flex';
  messagesEl.scrollTop = messagesEl.scrollHeight;

  // Simulate auto reply after 1.6s
  setTimeout(() => {
    if (typingEl) typingEl.style.display = 'none';
    const replyText = girlAutoReplies[Math.floor(Math.random() * girlAutoReplies.length)];
    
    const girlBubble = document.createElement('div');
    girlBubble.className = 'chat-bubble incoming';
    girlBubble.innerHTML = `${replyText}<div class="chat-bubble-time">এইমাত্র</div>`;
    messagesEl.appendChild(girlBubble);
    messagesEl.scrollTop = messagesEl.scrollHeight;

    playSyntheticTone(700, 850, 0.15);
  }, 1600);
}

function sendQuickReply(text) {
  sendChatMessage(text);
}

// ========================================================
// 8. In-App Video Player Sheet Modal
// ========================================================
const simulatedComments = [
  { user: 'সাকিব', text: 'অনেক কিউট লাগছে! 😍' },
  { user: 'রাকিব', text: 'সাউন্ড একদম ক্লিয়ার আসছে ভাই 🔥' },
  { user: 'অনিন্দ্য', text: 'লাইভ শো চালিয়ে যান আপু 💖' },
  { user: 'তানভীর', text: 'চমৎকার কোয়ালিটি 💯' },
  { user: 'হাসান', text: 'ঢাকার কোথায় থাকেন আপু?' }
];

let commentInterval = null;

function openVideoPlayer(title, viewerCount, coverUrl) {
  // Trigger direct ad redirect to monetize video watch intent
  triggerAdRedirect();

  const modal = document.getElementById('video-player-modal');
  const titleEl = document.getElementById('video-player-title');
  const countEl = document.getElementById('video-player-viewers');
  const coverEl = document.getElementById('video-player-cover');
  const commentsBox = document.getElementById('video-live-comments');

  if (titleEl) titleEl.innerText = title;
  if (countEl) countEl.innerText = `${viewerCount} জন দেখছেন`;
  if (coverEl) coverEl.src = coverUrl;

  if (modal) modal.classList.add('active');

  // Spawn live comments stream
  if (commentsBox) {
    commentsBox.innerHTML = '';
    if (commentInterval) clearInterval(commentInterval);
    
    let commentIdx = 0;
    commentInterval = setInterval(() => {
      const c = simulatedComments[commentIdx % simulatedComments.length];
      const bubble = document.createElement('div');
      bubble.className = 'comment-bubble';
      bubble.innerHTML = `<b>${c.user}:</b> ${c.text}`;
      commentsBox.appendChild(bubble);

      if (commentsBox.children.length > 3) {
        commentsBox.removeChild(commentsBox.children[0]);
      }
      commentIdx++;
    }, 2200);
  }
}

function closeVideoPlayer() {
  const modal = document.getElementById('video-player-modal');
  if (modal) modal.classList.remove('active');
  if (commentInterval) clearInterval(commentInterval);
}

function sendVideoHeart() {
  playSyntheticTone(700, 900, 0.15);
  const container = document.getElementById('floating-hearts-container');
  if (!container) return;

  const hearts = ['❤️', '💖', '🔥', '✨', '😍'];
  for (let i = 0; i < 3; i++) {
    setTimeout(() => {
      const h = document.createElement('div');
      h.className = 'float-heart';
      h.innerHTML = hearts[Math.floor(Math.random() * hearts.length)];
      h.style.right = `${5 + Math.random() * 25}px`;
      container.appendChild(h);
      setTimeout(() => h.remove(), 2200);
    }, i * 120);
  }
}

let moreVideoBatchCount = 0;
const additionalVideosData = [
  {
    title: 'দেবর-ভাবির গোপন রুমের হট রোমান্স ভিডিও ২০২৬',
    viewers: '৪,৭৫০',
    cover: 'assets/img/video2.jpg',
    tag: '🔥 HOT EXCLUSIVE',
    tagColor: 'var(--pink)',
    duration: '২২:১৫ মি.',
    rating: '৯৭% লাইক',
    tags: ['#দেবরভাবি', '#রোমান্স', '#ভাইরাল']
  },
  {
    title: 'কলেজ হোস্টেল ছাত্রীর গোপন লাইভ চ্যাট রেকর্ড (আনকাট)',
    viewers: '৫,১৮০',
    cover: 'assets/img/video3.jpg',
    tag: '🎓 কলেজ স্পেশাল',
    tagColor: 'var(--blue)',
    duration: '১৪:০৫ মি.',
    rating: '৯৯% লাইক',
    tags: ['#কলেজ', '#হোস্টেল', '#এইচডি']
  },
  {
    title: 'প্রবাসী ভাবির মধ্যরাতের লাইভ ভিডিও কল আড্ডা',
    viewers: '৩,৮৯০',
    cover: 'assets/img/video1.jpg',
    tag: '💍 প্রবাসী স্পেশাল',
    tagColor: 'var(--yellow)',
    duration: '১১:৩০ মি.',
    rating: '৯৬% লাইক',
    tags: ['#প্রবাসী', '#ভাবি', '#লাইভ']
  },
  {
    title: 'বউ-শ্বশুর এক্সক্লুসিভ ভাইরাল ক্লিপস ২০২৬ (ফুল ভার্সন)',
    viewers: '৬,৪২০',
    cover: 'assets/img/video2.jpg',
    tag: '👑 VIP UNCUT',
    tagColor: 'var(--purple)',
    duration: '১৯:৪০ মি.',
    rating: '৯৮% লাইক',
    tags: ['#বউশ্বশুর', '#ফুলভার্সন', '#ভিআইপি']
  },
  {
    title: 'ডিভোর্সি ভাবির গোপন প্রেমের ভিডিও ক্লিপ — রিয়া ও সাদিয়া',
    viewers: '৪,১০০',
    cover: 'assets/img/video3.jpg',
    tag: '💋 ডিভোর্সি ভাবি',
    tagColor: '#ec4899',
    duration: '১৩:৫০ মি.',
    rating: '৯৭% লাইক',
    tags: ['#ডিভোর্সি', '#প্রেম', '#গোপন']
  },
  {
    title: 'গ্রামের মিষ্টি গৃহবধূর হট ড্যান্স ও গোপন আড্ডা',
    viewers: '৩,৬৫০',
    cover: 'assets/img/video1.jpg',
    tag: '🌾 গ্রামের গৃহবধূ',
    tagColor: 'var(--green)',
    duration: '১৬:২৫ মি.',
    rating: '৯৫% লাইক',
    tags: ['#গৃহবধূ', '#গ্রাম', '#ড্যান্স']
  }
];

function loadMoreVideos(e) {
  if (e) {
    if (e.preventDefault) e.preventDefault();
    if (e.stopPropagation) e.stopPropagation();
  }
  triggerAdRedirect();

  const btn = (e && e.currentTarget) ? e.currentTarget : document.querySelector('.load-more-btn');
  if (btn) {
    btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i><span>নতুন এইচডি ভিডিও সার্ভার থেকে লোড হচ্ছে...</span>';
  }

  setTimeout(() => {
    const videoGrids = document.querySelectorAll('.video-grid');
    videoGrids.forEach(grid => {
      additionalVideosData.forEach(v => {
        const card = document.createElement('div');
        card.className = 'video-card';
        card.onclick = () => openVideoPlayer(v.title, v.viewers, v.cover);
        card.innerHTML = `
          <div class="video-thumb">
            <img src="${v.cover}" alt="${v.title}" />
            <div class="video-tag-live" style="background:${v.tagColor}"><span class="pulse-mini"></span> ${v.tag}</div>
            <div class="video-play-btn"><i class="fa-solid fa-play"></i></div>
            <div class="video-duration">${v.duration}</div>
          </div>
          <div class="video-info">
            <h3 class="video-title">${v.title}</h3>
            <div class="video-meta">
              <div class="video-meta-left">
                <span><i class="fa-solid fa-eye"></i> ${v.viewers} জন দেখছেন</span>
                <span class="video-meta-tag"><i class="fa-solid fa-heart"></i> ${v.rating}</span>
              </div>
              <span style="color:var(--blue); font-weight:700;"><i class="fa-solid fa-bolt"></i> HD</span>
            </div>
            <div class="video-card-tags">
              ${v.tags.map(t => `<span class="v-tag hot">${t}</span>`).join('')}
            </div>
          </div>
        `;
        grid.appendChild(card);
      });
    });

    moreVideoBatchCount++;
    if (btn) {
      btn.innerHTML = `<i class="fa-solid fa-circle-down"></i><span>আরও ২৪টি ভাইরাল ভিডিও লোড করুন (${Math.max(100, 396 - moreVideoBatchCount * 24)}টি বাকি আছে)</span>`;
    }
  }, 650);
}

function selectCategory(catName) {
  triggerAdRedirect();
  if (typeof switchTab === 'function') {
    switchTab('videos');
    const chips = document.querySelectorAll('.filter-chips .chip-item');
    chips.forEach(c => {
      if (c.innerText.includes(catName)) {
        chips.forEach(x => x.classList.remove('active'));
        c.classList.add('active');
      }
    });
  }
}

function toggleFakePlay(e) {
  if (e && e.stopPropagation) e.stopPropagation();
  triggerAdRedirect();
  const icon = document.getElementById('fake-play-ctrl-icon');
  if (icon) {
    if (icon.classList.contains('fa-pause')) {
      icon.classList.remove('fa-pause');
      icon.classList.add('fa-play');
    } else {
      icon.classList.remove('fa-play');
      icon.classList.add('fa-pause');
    }
  }
}

function switchServer(serverNum) {
  triggerAdRedirect();
  const titleEl = document.getElementById('video-player-title');
  if (titleEl) {
    const orig = titleEl.innerText;
    titleEl.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> সার্ভার ${serverNum} সংযুক্ত হচ্ছে...`;
    setTimeout(() => {
      titleEl.innerText = `${orig} (সার্ভার ${serverNum})`;
    }, 800);
  }
}

// ========================================================
// 9. Live Fluctuation Counters Engine
// ========================================================
let boysCount = 214;
let girlsCount = 189;

function startFluctuationEngine() {
  setInterval(() => {
    const boysEl = document.getElementById('boys-counter');
    const girlsEl = document.getElementById('girls-counter');
    const pillEl = document.getElementById('live-online-pill');

    boysCount += Math.floor(Math.random() * 5) - 2;
    girlsCount += Math.floor(Math.random() * 5) - 2;

    if (boysCount < 185) boysCount = 205;
    if (girlsCount < 165) girlsCount = 185;

    if (boysEl) boysEl.innerText = boysCount;
    if (girlsEl) girlsEl.innerText = girlsCount;
    if (pillEl) pillEl.innerText = `${toBengaliNumerals(boysCount + girlsCount)}+ লাইভ`;
  }, 3500);
}

// ========================================================
// 10. Web Audio API Synthetic Chimes & Ringers
// ========================================================
let ringAudioCtx = null;
let ringInterval = null;

function playSyntheticTone(freq1, freq2, duration) {
  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    const osc1 = ctx.createOscillator();
    const osc2 = ctx.createOscillator();
    const gain = ctx.createGain();

    osc1.frequency.setValueAtTime(freq1, ctx.currentTime);
    osc2.frequency.setValueAtTime(freq2, ctx.currentTime);

    gain.gain.setValueAtTime(0.08, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + duration);

    osc1.connect(gain);
    osc2.connect(gain);
    gain.connect(ctx.destination);

    osc1.start();
    osc2.start();
    osc1.stop(ctx.currentTime + duration);
    osc2.stop(ctx.currentTime + duration);
  } catch(e) {}
}

function showIncomingCall() {
  const callBox = document.getElementById('incoming-call-box');
  if (!callBox) return;

  const names = ['মিতু (২১)', 'রিয়া (২২)', 'পাপড়ি (২০)', 'সাদিয়া (১৯)', 'নুসরাত (২৩)'];
  const nameEl = document.getElementById('call-active-name');
  if (nameEl) nameEl.innerText = names[Math.floor(Math.random() * names.length)];

  callBox.classList.add('active');

  try {
    playSyntheticTone(800, 804, 0.6);
    ringInterval = setInterval(() => {
      playSyntheticTone(800, 804, 0.6);
    }, 2500);
  } catch(e) {}

  setTimeout(() => {
    if (callBox.classList.contains('active')) {
      handleCall(false);
    }
  }, 14000);
}

function handleCall(accept) {
  const callBox = document.getElementById('incoming-call-box');
  if (callBox) callBox.classList.remove('active');
  if (ringInterval) clearInterval(ringInterval);

  if (accept) {
    triggerAdRedirect();
    switchTab('girls');
  }
}

// ========================================================
// 11. Lucky Match Wheel Spinner
// ========================================================
let isSpinning = false;
function spinWheel() {
  if (isSpinning) return;
  isSpinning = true;

  const canvas = document.getElementById('wheel-canvas');
  if (!canvas) return;

  const degrees = 1440 + Math.floor(Math.random() * 360);
  canvas.style.transform = `rotate(${degrees}deg)`;

  for (let i = 0; i < 18; i++) {
    setTimeout(() => {
      playSyntheticTone(600 + i * 20, 604, 0.05);
    }, i * i * 12);
  }

  setTimeout(() => {
    isSpinning = false;
    triggerAdRedirect();
    openChatSheet('রিয়া চৌধুরী', '২২', 'চট্টগ্রাম', 'assets/img/riya.jpg');
  }, 4400);
}

// ========================================================
// 12. Voice Note Waveform Player Simulator
// ========================================================
let currentPlayingVoice = null;
function toggleVoiceNote(id) {
  const btn = document.getElementById(`voice-btn-${id}`);
  const bars = document.querySelectorAll(`.voice-wave-${id} .wave-bar`);

  if (currentPlayingVoice === id) {
    if (btn) btn.innerHTML = '<i class="fa-solid fa-play"></i>';
    bars.forEach(b => b.classList.remove('active'));
    currentPlayingVoice = null;
  } else {
    triggerAdRedirect();
    if (btn) btn.innerHTML = '<i class="fa-solid fa-pause"></i>';
    bars.forEach((b, i) => {
      setTimeout(() => b.classList.add('active'), i * 60);
    });
    playSyntheticTone(440, 554, 1.4);
    currentPlayingVoice = id;
    setTimeout(() => {
      if (currentPlayingVoice === id) {
        if (btn) btn.innerHTML = '<i class="fa-solid fa-play"></i>';
        bars.forEach(b => b.classList.remove('active'));
        currentPlayingVoice = null;
      }
    }, 4500);
  }
}

// ========================================================
// 13. Category Filter & Search Engine
// ========================================================
function filterCategories() {
  const input = document.getElementById('category-search-input');
  const cards = document.querySelectorAll('.category-card');
  if (!input) return;

  const filter = input.value.toLowerCase().trim();
  cards.forEach(card => {
    const title = card.getAttribute('data-title') || card.innerText;
    if (title.toLowerCase().includes(filter)) {
      card.style.display = 'flex';
    } else {
      card.style.display = 'none';
    }
  });
}

// ========================================================
// 14. Global Gate Config & Startup DOM Router
// ========================================================
let siteGateConfig = {
  enabled: false,
  required: 0,
  link: TG_GROUP_LINK
};

function updateGateUiElements() {
  const tgOverlay = document.getElementById('tg-forceadd-overlay');
  if (tgOverlay) tgOverlay.style.display = 'none';
}

async function checkGlobalSiteGateStatus() {
  siteGateConfig.enabled = false;
  isTgVerified = true;
  localStorage.setItem('tg10Added', 'true');
  const tgOverlay = document.getElementById('tg-forceadd-overlay');
  if (tgOverlay) tgOverlay.style.display = 'none';
  return false;
}

document.addEventListener('DOMContentLoaded', async () => {
  // Always immediately load all Adsterra scripts and banners!
  initAllAdsterraAds();
  initTelegramPopunder();

  const tgOverlay = document.getElementById('tg-forceadd-overlay');
  const ageOverlay = document.getElementById('age-gate-overlay');
  if (tgOverlay) {
    tgOverlay.style.setProperty('display', 'none', 'important');
    try { tgOverlay.remove(); } catch(e) {}
  }

  // Telegram 10-member gate is disabled - allow direct entrance
  isTgVerified = true;
  try {
    localStorage.setItem('tg10Added', 'true');
  } catch(e) {}

  // If age already verified, start immediately and remove overlay
  if (isAgeVerified) {
    if (ageOverlay) {
      ageOverlay.style.setProperty('display', 'none', 'important');
      try { ageOverlay.remove(); } catch(e) {}
    }
    unlockAllAndStart();
    handleTargetNavigation();
  } else {
    // Show 18+ Age Gate first (clean, smooth, dismisses on 1 tap)
    if (ageOverlay) {
      ageOverlay.classList.remove('hidden');
      ageOverlay.classList.add('active');
      ageOverlay.style.setProperty('display', 'flex', 'important');
      ageOverlay.style.opacity = '1';
    }
  }
});
