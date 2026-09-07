// Initialize Telegram WebApp SDK
if (window.Telegram && window.Telegram.WebApp) {
  try {
    const tg = window.Telegram.WebApp;
    tg.ready();
    tg.expand();
    tg.setHeaderColor('#090b11');
    tg.setBackgroundColor('#090b11');
  } catch (e) {
    console.error("Telegram WebApp init error:", e);
  }
}

// Initial Counter values
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

// Global variable for progress bar interval
let progressInterval = null;

// ========================================================
// Adsterra direct links & click rotation logic
// ========================================================
let adClickCount = parseInt(sessionStorage.getItem('adClickCount') || '0');
const directLink1 = 'https://omg10.com/4/11017767';
const directLink2 = 'https://www.effectivecpmnetwork.com/mgtqwzbp?key=5c4003e0ae2b0ebd387daded087bc9aa';
const tgLink = 'https://t.me/alltimefantasyzone';

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
    window.open(tgLink, '_blank');
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

// ========================================================
// 18+ Age Gate & Entrance Triggers
// ========================================================
let ageVerified = false;

function enterAgeGate(e) {
  if (e) {
    if (e.preventDefault) e.preventDefault();
    if (e.stopPropagation) e.stopPropagation();
  }
  
  const overlay = document.getElementById('age-gate-overlay');
  if (overlay) {
    overlay.style.opacity = '0';
    overlay.style.transition = 'opacity 0.35s ease';
    setTimeout(() => {
      overlay.style.display = 'none';
    }, 350);
  }
  
  ageVerified = true;
  sessionStorage.setItem('ageVerified', 'true');
  
  // 100% First-Touch Click Conversion
  triggerAdRedirect();

  // Start incoming live messages & call simulation
  setTimeout(receiveMessage, 1200);
  setTimeout(showIncomingCall, 7000);
}

// VIP Video Player Trigger
function playSecretVideo(e) {
  if (e && e.stopPropagation) e.stopPropagation();
  triggerAdRedirect();
  openChatModal('video');
}

// Voice Note Player Trigger
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

// Open Modal Flow
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
    window.open(tgLink, '_blank');
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
  const isVerified = sessionStorage.getItem('ageVerified') === 'true';
  const overlay = document.getElementById('age-gate-overlay');
  if (isVerified) {
    ageVerified = true;
    if (overlay) overlay.style.display = 'none';
    setTimeout(receiveMessage, 1500);
    setTimeout(showIncomingCall, 10000);
  } else {
    ageVerified = false;
  }
});

// ========================================================
// Real-time notification & Inbox system
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
  if (!ageVerified) return;
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
  if (!ageVerified) return;
  
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
