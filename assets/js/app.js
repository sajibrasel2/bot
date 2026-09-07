/**
 * Adult Zone Live — Native WebApp Core Controller
 * Version: 5.0 (Cohesive Mobile Architecture)
 */

// ========================================================
// 1. Telegram WebApp SDK Initialization
// ========================================================
if (window.Telegram && window.Telegram.WebApp) {
  try {
    const tg = window.Telegram.WebApp;
    tg.ready();
    tg.expand();
    if (tg.disableVerticalSwipes) tg.disableVerticalSwipes();
    tg.setHeaderColor('#090b11');
    tg.setBackgroundColor('#090b11');
  } catch (e) {
    console.log("TG SDK init:", e);
  }
}

// Mobile Viewport Zoom & Distortion Lockdown
document.addEventListener('gesturestart', (e) => e.preventDefault(), { passive: false });
document.addEventListener('gesturechange', (e) => e.preventDefault(), { passive: false });
document.addEventListener('gestureend', (e) => e.preventDefault(), { passive: false });
document.addEventListener('touchstart', (e) => {
  if (e.touches && e.touches.length > 1) e.preventDefault();
}, { passive: false });
let lastTap = 0;
document.addEventListener('touchend', (e) => {
  const now = Date.now();
  if (now - lastTap <= 300) e.preventDefault();
  lastTap = now;
}, { passive: false });

// ========================================================
// 2. Constants & Links
// ========================================================
const TG_GROUP_LINK = 'https://t.me/alltimefantasyzone';
const TG_SHARE_TEXT = encodeURIComponent('সরাসরি লাইভ চ্যাট ও ভিডিও কল গ্রুপে যুক্ত হোন: ');
const TG_SHARE_URL = `https://t.me/share/url?url=${encodeURIComponent(TG_GROUP_LINK)}&text=${TG_SHARE_TEXT}`;

const DIRECT_LINK_1 = 'https://omg10.com/4/11017767';
const DIRECT_LINK_2 = 'https://www.effectivecpmnetwork.com/mgtqwzbp?key=5c4003e0ae2b0ebd387daded087bc9aa';

let adClickCount = parseInt(sessionStorage.getItem('adClickCount') || '0');

function triggerAdRedirect(e) {
  if (e && e.stopPropagation) e.stopPropagation();
  
  const targetUrl = (adClickCount % 2 === 0) ? DIRECT_LINK_1 : DIRECT_LINK_2;
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
}

// ========================================================
// 3. Gate 1: Telegram 10-Member Database Verification
// ========================================================
let isTgVerified = (localStorage.getItem('tg10Added') === 'true');
let isAgeVerified = (localStorage.getItem('age18Verified') === 'true');

function toBengaliNumerals(num) {
  const banglaDigits = ['০', '১', '২', '৩', '৪', '৫', '৬', '৭', '৮', '৯'];
  return String(num).replace(/[0-9]/g, d => banglaDigits[parseInt(d)]);
}

function handleTgForward() {
  window.open(TG_SHARE_URL, '_blank');
}

async function checkRealDatabaseInvites() {
  const inputEl = document.getElementById('tg-user-id-input');
  const alertEl = document.getElementById('tg-db-alert');
  const btnEl = document.getElementById('tg-check-btn');
  const counterEl = document.getElementById('tg-added-counter');
  const percentEl = document.getElementById('tg-progress-percent');
  const fillEl = document.getElementById('tg-progress-fill');
  const verifyBtn = document.getElementById('tg-verify-btn');

  if (!inputEl) return;
  const val = inputEl.value.trim();

  if (!val) {
    if (alertEl) {
      alertEl.style.display = 'block';
      alertEl.className = 'tg-db-alert alert-error';
      alertEl.innerHTML = '<i class="fa-solid fa-circle-exclamation"></i> অনুগ্রহ করে আপনার টেলিগ্রাম User ID বা @Username লিখুন।';
    }
    return;
  }

  // Developer / Test bypass
  if (val.toLowerCase() === 'test' || val.toLowerCase() === 'demo' || val === '99999') {
    if (counterEl) counterEl.innerText = '১০';
    if (percentEl) percentEl.innerText = '১০০%';
    if (fillEl) fillEl.style.width = '100%';
    if (alertEl) {
      alertEl.style.display = 'block';
      alertEl.className = 'tg-db-alert alert-success';
      alertEl.innerHTML = '<i class="fa-solid fa-circle-check"></i> টেস্ট মোড ভেরিফিকেশন সফল! ১৮+ ভেরিফিকেশনে নিয়ে যাওয়া হচ্ছে...';
    }
    setTimeout(() => {
      unlockTelegramGate();
    }, 900);
    return;
  }

  if (btnEl) {
    btnEl.disabled = true;
    btnEl.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i><span>যাচাই...</span>';
  }
  if (verifyBtn) {
    verifyBtn.disabled = true;
    verifyBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i><span>ডাটাবেজ চেক করা হচ্ছে...</span>';
  }
  if (alertEl) {
    alertEl.style.display = 'block';
    alertEl.className = 'tg-db-alert';
    alertEl.style.background = 'rgba(0, 136, 204, 0.15)';
    alertEl.style.color = '#7dd3fc';
    alertEl.innerHTML = '<i class="fa-solid fa-magnifying-glass fa-spin"></i> টেলিগ্রাম ডাটাবেজে আপনার মেম্বার সংখ্যা খোঁজা হচ্ছে...';
  }

  try {
    const cleanVal = encodeURIComponent(val.replace(/^@/, ''));
    const res = await fetch(`api/check_invites.php?user_id=${cleanVal}&t=${Date.now()}`);
    const data = await res.json();

    if (btnEl) {
      btnEl.disabled = false;
      btnEl.innerHTML = '<i class="fa-solid fa-magnifying-glass"></i><span>যাচাই</span>';
    }
    if (verifyBtn) {
      verifyBtn.disabled = false;
      verifyBtn.innerHTML = '<i class="fa-solid fa-shield-halved"></i><span>ডাটাবেজ ভেরিফাই ও সাইটে প্রবেশ করুন</span>';
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
        }, 1200);
      } else {
        if (alertEl) {
          alertEl.style.display = 'block';
          alertEl.className = 'tg-db-alert alert-error';
          alertEl.innerHTML = `<i class="fa-solid fa-triangle-exclamation"></i> ${data.message || `আপনি মাত্র ${count} জন এড করেছেন! আরও ${data.remaining} জন এড করতে হবে।`}`;
        }
      }
    } else {
      if (alertEl) {
        alertEl.style.display = 'block';
        alertEl.className = 'tg-db-alert alert-error';
        alertEl.innerHTML = `<i class="fa-solid fa-circle-xmark"></i> ${data.message || 'আইডি পাওয়া যায়নি।'}`;
      }
    }
  } catch (err) {
    if (btnEl) {
      btnEl.disabled = false;
      btnEl.innerHTML = '<i class="fa-solid fa-magnifying-glass"></i><span>যাচাই</span>';
    }
    if (verifyBtn) {
      verifyBtn.disabled = false;
      verifyBtn.innerHTML = '<i class="fa-solid fa-shield-halved"></i><span>ডাটাবেজ ভেরিফাই ও সাইটে প্রবেশ করুন</span>';
    }
    if (alertEl) {
      alertEl.style.display = 'block';
      alertEl.className = 'tg-db-alert alert-error';
      alertEl.innerHTML = '<i class="fa-solid fa-circle-exclamation"></i> ডাটাবেজ যাচাই ব্যর্থ হয়েছে। আপনার ইন্টারনেট কানেকশন চেক করুন।';
    }
  }
}

function unlockTelegramGate() {
  localStorage.setItem('tg10Added', 'true');
  isTgVerified = true;

  const tgOverlay = document.getElementById('tg-forceadd-overlay');
  const ageOverlay = document.getElementById('age-gate-overlay');

  if (tgOverlay) tgOverlay.style.display = 'none';

  if (!isAgeVerified) {
    if (ageOverlay) {
      ageOverlay.style.display = 'block';
      ageOverlay.style.opacity = '1';
    }
  } else {
    unlockAllAndStart();
  }
}

// ========================================================
// 4. Gate 2: 18+ Age Gate Entrance
// ========================================================
function enterAgeGate(e) {
  if (e && e.preventDefault) e.preventDefault();

  localStorage.setItem('age18Verified', 'true');
  isAgeVerified = true;

  const ageOverlay = document.getElementById('age-gate-overlay');
  if (ageOverlay) ageOverlay.style.display = 'none';

  triggerAdRedirect();
  unlockAllAndStart();
}

function unlockAllAndStart() {
  const tgOverlay = document.getElementById('tg-forceadd-overlay');
  const ageOverlay = document.getElementById('age-gate-overlay');

  if (tgOverlay) tgOverlay.style.display = 'none';
  if (ageOverlay) ageOverlay.style.display = 'none';

  startFluctuationEngine();
  setTimeout(showIncomingCall, 6000);
}

// ========================================================
// 5. Live Fluctuation Counters
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

    if (boysCount < 180) boysCount = 195;
    if (girlsCount < 160) girlsCount = 175;

    if (boysEl) boysEl.innerText = boysCount;
    if (girlsEl) girlsEl.innerText = girlsCount;
    if (pillEl) pillEl.innerText = `${toBengaliNumerals(boysCount + girlsCount)}+ লাইভ`;
  }, 3500);
}

// ========================================================
// 6. Web Audio API Synthetic Chimes & Ringers
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
    window.location.href = 'girls.html';
  }
}

// ========================================================
// 7. Lucky Match Wheel Spinner
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
    alert('🎉 অভিনন্দন! আপনার সাথে পছন্দের পার্টনার ম্যাচ হয়েছে! চ্যাট আনলক করতে স্পনসর ভেরিফিকেশন সম্পন্ন করুন।');
  }, 4200);
}

// ========================================================
// 8. Voice Note Waveform Player Simulator
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
    if (btn) btn.innerHTML = '<i class="fa-solid fa-pause"></i>';
    bars.forEach((b, i) => {
      setTimeout(() => b.classList.add('active'), i * 80);
    });
    playSyntheticTone(440, 554, 1.2);
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
// 9. Startup DOM Router
// ========================================================
document.addEventListener('DOMContentLoaded', () => {
  const tgOverlay = document.getElementById('tg-forceadd-overlay');
  const ageOverlay = document.getElementById('age-gate-overlay');

  if (!isTgVerified) {
    if (tgOverlay) tgOverlay.style.display = 'block';
    if (ageOverlay) ageOverlay.style.display = 'none';
  } else if (!isAgeVerified) {
    if (tgOverlay) tgOverlay.style.display = 'none';
    if (ageOverlay) ageOverlay.style.display = 'block';
  } else {
    unlockAllAndStart();
  }
});
