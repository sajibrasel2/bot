/**
 * bKash & Nagad 500 TK Campaign - High-Conversion Viral Engine
 * Handles Referral Tracking, Ad Click Verification, Live Timers, and Claims
 */

// ============================================================================
// ১. আপনার বিজ্ঞাপন ও ক্যাম্পেইন কনফিগারেশন (এখানে আপনার লিংকগুলো বসাবেন)
// ============================================================================
const CAMPAIGN_CONFIG = {
  // আপনার ১ম বিজ্ঞাপন / ডিরেক্ট লিংক (Adsterra / Monetag / Sponsor URL)
  adLink1: "https://www.google.com", 
  
  // আপনার ২য় বিজ্ঞাপন লিংক (অথবা অন্য এড নেটওয়ার্কের লিংক)
  adLink2: "https://www.google.com", 
  
  // অফারের মূল শর্তাবলী
  requiredReferrals: 20, // ২০ জনকে রেফার বা সাইট ভিজিট করাতে হবে
  rewardAmount: 500,     // ৫০০ টাকা
  totalWinners: 20,      // সর্বোচ্চ ২০ জন
  adTimerSeconds: 15,    // এডে ন্যূনতম ১৫ সেকেন্ড ভিজিট থাকতে হবে
  
  // ব্যাকএন্ড এপিআই পাথ
  apiUrl: "api/campaign.php"
};

// State
let currentUser = null;
let currentRefCode = null;
let currentReferrals = 0;
let tasksCompleted = { ad1: false, ad2: false };
let isClaimed = false;

// DOM Ready
document.addEventListener("DOMContentLoaded", () => {
  initUrlParams();
  loadSavedUser();
  initCountdownTimer();
  startLiveWinnerToasts();
  initFaqAccordion();
  checkApiInit();
});

// ============================================================================
// ২. URL প্যারামিটার ও ভিজিটর ট্র্যাকিং (?ref=...)
// ============================================================================
function initUrlParams() {
  const urlParams = new URLSearchParams(window.location.search);
  const ref = urlParams.get('ref');
  
  if (ref) {
    // Record visit via backend API
    fetch(`${CAMPAIGN_CONFIG.apiUrl}?action=init&ref=${encodeURIComponent(ref)}`)
      .then(res => res.json())
      .then(data => {
        if (data.status === 'success' && data.visit_registered) {
          console.log(`[Referral Recorded] Ref: ${ref}`);
        }
      })
      .catch(() => {
        // Fallback to local storage if API unreachable
        recordLocalReferral(ref);
      });
  }
}

// Fallback offline / static storage for referrals
function recordLocalReferral(ref) {
  try {
    const visitedKey = `campaign_visited_${ref}`;
    if (!localStorage.getItem(visitedKey)) {
      localStorage.setItem(visitedKey, "1");
      let count = parseInt(localStorage.getItem(`ref_count_${ref}`) || "0", 10);
      count += 1;
      localStorage.setItem(`ref_count_${ref}`, count.toString());
    }
  } catch (e) {
    console.warn("Storage error", e);
  }
}

// ============================================================================
// ৩. ইউজার স্টেট লোড ও ইন্টারফেস আপডেট
// ============================================================================
function loadSavedUser() {
  const saved = localStorage.getItem("my_bk_campaign_user");
  if (saved) {
    try {
      currentUser = JSON.parse(saved);
      currentRefCode = currentUser.phone;
      tasksCompleted = currentUser.tasksCompleted || { ad1: false, ad2: false };
      isClaimed = currentUser.isClaimed || false;
      renderRegisteredView();
      fetchReferralStatus();
    } catch (e) {
      localStorage.removeItem("my_bk_campaign_user");
    }
  }
}

function checkApiInit() {
  fetch(`${CAMPAIGN_CONFIG.apiUrl}?action=init`)
    .then(r => r.json())
    .then(data => {
      if (data && data.stats) {
        updateStatsUI(data.stats);
      }
    })
    .catch(() => {
      // Offline fallback stats
      updateStatsUI({
        claimed_count: 14,
        slots_remaining: 6,
        total_participants: 685
      });
    });
}

function updateStatsUI(stats) {
  const slotsRemainingEl = document.getElementById("slots-remaining-num");
  const slotsFillEl = document.getElementById("slots-progress-fill");
  const participantsEl = document.getElementById("total-participants-num");
  
  if (slotsRemainingEl) slotsRemainingEl.textContent = stats.slots_remaining;
  if (participantsEl) participantsEl.textContent = stats.total_participants;
  if (slotsFillEl) {
    const claimedPercent = Math.min(100, Math.round((stats.claimed_count / 20) * 100));
    slotsFillEl.style.width = `${claimedPercent}%`;
  }
}

// ============================================================================
// ৪. রেজিস্ট্রেশন ও রেফারেল লিংক তৈরি (ধাপ ১)
// ============================================================================
function handleRegister(e) {
  if (e) e.preventDefault();
  const phoneInput = document.getElementById("user-phone-input");
  const phone = phoneInput ? phoneInput.value.trim() : "";
  const methodRadios = document.getElementsByName("wallet-method");
  let selectedMethod = "bKash";
  for (const r of methodRadios) {
    if (r.checked) selectedMethod = r.value;
  }

  // Validate Bangladeshi 11-digit mobile number
  const cleanPhone = phone.replace(/\D/g, "");
  if (cleanPhone.length !== 11 || !cleanPhone.startsWith("01")) {
    alert("❌ অনুগ্রহ করে সঠিক ১১ ডিজিটের মোবাইল নম্বর দিন (যেমন: 01712345678)");
    if (phoneInput) phoneInput.focus();
    return;
  }

  // Call API or setup locally
  fetch(`${CAMPAIGN_CONFIG.apiUrl}?action=register&phone=${cleanPhone}&method=${selectedMethod}`)
    .then(res => res.json())
    .then(data => {
      processRegistrationSuccess(cleanPhone, selectedMethod, data.referral_count || 0);
    })
    .catch(() => {
      // Local fallback
      processRegistrationSuccess(cleanPhone, selectedMethod, 0);
    });
}

function processRegistrationSuccess(phone, method, initialCount) {
  currentUser = {
    phone: phone,
    method: method,
    tasksCompleted: { ad1: false, ad2: false },
    isClaimed: false
  };
  currentRefCode = phone;
  currentReferrals = initialCount;
  localStorage.setItem("my_bk_campaign_user", JSON.stringify(currentUser));

  renderRegisteredView();
  fetchReferralStatus();

  // Smooth scroll to Tasks
  const step2 = document.getElementById("step-tasks-card");
  if (step2) {
    step2.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }
}

function renderRegisteredView() {
  if (!currentUser) return;

  const regForm = document.getElementById("registration-form-box");
  const refDisplay = document.getElementById("referral-box-container");
  const refLinkInput = document.getElementById("my-referral-link");
  const step1Card = document.getElementById("step-1-card");
  const stepTasksCard = document.getElementById("step-tasks-card");

  if (regForm) regForm.style.display = "none";
  if (refDisplay) refDisplay.style.display = "block";

  // Build clean absolute referral link
  const currentUrl = window.location.origin + window.location.pathname;
  const fullRefLink = `${currentUrl}?ref=${encodeURIComponent(currentRefCode)}`;
  if (refLinkInput) refLinkInput.value = fullRefLink;

  if (step1Card) {
    step1Card.classList.remove("active-step");
    step1Card.classList.add("completed-step");
  }
  if (stepTasksCard) {
    stepTasksCard.classList.add("active-step");
  }

  updateTaskStatusUI();
}

// ============================================================================
// ৫. বিজ্ঞাপন ভিজিট ও ক্লিক টাস্ক (Core Ads Trigger)
// ============================================================================
let adTimerInterval = null;

function handleAdTask1() {
  if (!currentUser) {
    alert("⚠️ আগে উপরে আপনার মোবাইল নম্বর দিয়ে রেজিস্ট্রেশন করুন!");
    document.getElementById("user-phone-input")?.focus();
    return;
  }

  // 1. Open User's Direct Ad Link in new tab
  window.open(CAMPAIGN_CONFIG.adLink1, "_blank");

  // 2. Start Countdown Timer on this page
  const timerBox = document.getElementById("ad-timer-box-1");
  const timerSecondsEl = document.getElementById("ad-timer-count-1");
  const adBtn = document.getElementById("btn-ad-task-1");

  if (timerBox) timerBox.style.display = "flex";
  if (adBtn) {
    adBtn.disabled = true;
    adBtn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i><span>এড ভিজিট হচ্ছে...</span>`;
  }

  let timeLeft = CAMPAIGN_CONFIG.adTimerSeconds;
  if (timerSecondsEl) timerSecondsEl.textContent = timeLeft;

  if (adTimerInterval) clearInterval(adTimerInterval);
  adTimerInterval = setInterval(() => {
    timeLeft--;
    if (timerSecondsEl) timerSecondsEl.textContent = timeLeft;

    if (timeLeft <= 0) {
      clearInterval(adTimerInterval);
      tasksCompleted.ad1 = true;
      saveUserTasks();

      if (timerBox) {
        timerBox.style.display = "none";
      }
      if (adBtn) {
        adBtn.className = "ad-task-btn btn-ad-done";
        adBtn.innerHTML = `<i class="fa-solid fa-circle-check"></i><span>ভিজিট সম্পন্ন ✅</span>`;
      }

      // Sync with API
      fetch(`${CAMPAIGN_CONFIG.apiUrl}?action=record_task&ref=${encodeURIComponent(currentRefCode)}&task_id=ad1`).catch(()=>{});

      checkUnlockEligibility();
      alert("🎉 চমৎকার! স্পন্সর এড ১ ভিজিট সফলভাবে সম্পন্ন হয়েছে!");
    }
  }, 1000);
}

function handleAdTask2() {
  if (!currentUser) {
    alert("⚠️ আগে উপরে আপনার মোবাইল নম্বর দিয়ে রেজিস্ট্রেশন করুন!");
    return;
  }

  // Open Ad Link 2
  window.open(CAMPAIGN_CONFIG.adLink2, "_blank");

  const adBtn = document.getElementById("btn-ad-task-2");
  tasksCompleted.ad2 = true;
  saveUserTasks();

  if (adBtn) {
    adBtn.className = "ad-task-btn btn-ad-done";
    adBtn.innerHTML = `<i class="fa-solid fa-circle-check"></i><span>ক্লিক সম্পন্ন ✅</span>`;
  }

  // Sync with API
  fetch(`${CAMPAIGN_CONFIG.apiUrl}?action=record_task&ref=${encodeURIComponent(currentRefCode)}&task_id=ad2`).catch(()=>{});

  checkUnlockEligibility();
}

function saveUserTasks() {
  if (currentUser) {
    currentUser.tasksCompleted = tasksCompleted;
    localStorage.setItem("my_bk_campaign_user", JSON.stringify(currentUser));
  }
}

function updateTaskStatusUI() {
  if (tasksCompleted.ad1) {
    const adBtn1 = document.getElementById("btn-ad-task-1");
    if (adBtn1) {
      adBtn1.className = "ad-task-btn btn-ad-done";
      adBtn1.innerHTML = `<i class="fa-solid fa-circle-check"></i><span>ভিজিট সম্পন্ন ✅</span>`;
    }
    document.getElementById("ad-task-item-1")?.classList.add("task-done");
  }
  if (tasksCompleted.ad2) {
    const adBtn2 = document.getElementById("btn-ad-task-2");
    if (adBtn2) {
      adBtn2.className = "ad-task-btn btn-ad-done";
      adBtn2.innerHTML = `<i class="fa-solid fa-circle-check"></i><span>ক্লিক সম্পন্ন ✅</span>`;
    }
    document.getElementById("ad-task-item-2")?.classList.add("task-done");
  }
}

// ============================================================================
// ৬. রেফারেল স্ট্যাটাস চেক ও ২০ জন প্রগ্রেস বার
// ============================================================================
function fetchReferralStatus(isManual = false) {
  if (!currentRefCode) return;

  const btnRefresh = document.getElementById("btn-refresh-referrals");
  if (btnRefresh && isManual) {
    btnRefresh.innerHTML = `<i class="fa-solid fa-rotate fa-spin"></i><span>চেক করা হচ্ছে...</span>`;
  }

  fetch(`${CAMPAIGN_CONFIG.apiUrl}?action=check_status&ref=${encodeURIComponent(currentRefCode)}`)
    .then(r => r.json())
    .then(data => {
      if (data.status === 'success') {
        currentReferrals = data.referrals || 0;
        if (data.has_claimed) isClaimed = true;
        renderReferralProgress();
      }
    })
    .catch(() => {
      // Fallback: check local storage count
      const localCount = parseInt(localStorage.getItem(`ref_count_${currentRefCode}`) || "0", 10);
      currentReferrals = localCount;
      renderReferralProgress();
    })
    .finally(() => {
      if (btnRefresh && isManual) {
        setTimeout(() => {
          btnRefresh.innerHTML = `<i class="fa-solid fa-rotate"></i><span>রিফ্রেশ</span>`;
        }, 500);
      }
    });
}

function renderReferralProgress() {
  const countEl = document.getElementById("current-ref-count");
  const percentEl = document.getElementById("current-ref-percent");
  const fillEl = document.getElementById("ref-progress-fill");

  const target = CAMPAIGN_CONFIG.requiredReferrals;
  const percent = Math.min(100, Math.round((currentReferrals / target) * 100));

  if (countEl) countEl.textContent = currentReferrals;
  if (percentEl) percentEl.textContent = `${percent}%`;
  if (fillEl) fillEl.style.width = `${percent}%`;

  checkUnlockEligibility();
}

function checkUnlockEligibility() {
  const lockedCard = document.getElementById("claim-card-locked");
  const unlockedCard = document.getElementById("claim-card-unlocked");

  const has20Refs = currentReferrals >= CAMPAIGN_CONFIG.requiredReferrals;
  const hasAdsDone = tasksCompleted.ad1 && tasksCompleted.ad2;

  if (has20Refs && hasAdsDone && !isClaimed) {
    if (lockedCard) lockedCard.style.display = "none";
    if (unlockedCard) unlockedCard.style.display = "block";
    
    // Auto fill claim number
    const claimInput = document.getElementById("claim-phone-input");
    if (claimInput && currentUser && !claimInput.value) {
      claimInput.value = currentUser.phone;
    }
  } else {
    if (lockedCard) lockedCard.style.display = "block";
    if (unlockedCard) unlockedCard.style.display = "none";
  }
}

// ============================================================================
// ৭. ওয়ান-ক্লিক কপি ও সোশ্যাল শেয়ার (WhatsApp, FB, TG, Messenger)
// ============================================================================
function copyReferralLink() {
  const refLinkInput = document.getElementById("my-referral-link");
  if (!refLinkInput || !refLinkInput.value) return;

  refLinkInput.select();
  refLinkInput.setSelectionRange(0, 99999);

  navigator.clipboard.writeText(refLinkInput.value).then(() => {
    const copyBtn = document.getElementById("btn-copy-ref");
    if (copyBtn) {
      const orig = copyBtn.innerHTML;
      copyBtn.innerHTML = `<i class="fa-solid fa-check"></i><span>কপি হয়েছে!</span>`;
      copyBtn.style.background = "#10b981";
      setTimeout(() => {
        copyBtn.innerHTML = orig;
        copyBtn.style.background = "";
      }, 2000);
    }
  }).catch(() => {
    alert("লিংকটি কপি করুন:\n" + refLinkInput.value);
  });
}

function shareOnWhatsApp() {
  if (!currentUser) return alert("⚠️ আগে মোবাইল নম্বর দিয়ে লিংক তৈরি করুন!");
  const link = document.getElementById("my-referral-link")?.value || window.location.href;
  const msg = `🎉 বিকাশ ও নগদ ৫০০ টাকা ফ্রি মোবাইল রিচার্জ ক্যাম্পেইন দিচ্ছে!\nআমি অলরেডি রেজিস্ট্রেশন করেছি। আপনিও ৫০০ টাকা রিচার্জ বা ক্যাশ পেতে এখনই নিচের লিংকে ক্লিক করুন 👉\n${link}`;
  window.open(`https://api.whatsapp.com/send?text=${encodeURIComponent(msg)}`, '_blank');
}

function shareOnFacebook() {
  if (!currentUser) return alert("⚠️ আগে মোবাইল নম্বর দিয়ে লিংক তৈরি করুন!");
  const link = document.getElementById("my-referral-link")?.value || window.location.href;
  window.open(`https://www.facebook.com/sharer/sharer.php?u=${encodeURIComponent(link)}`, '_blank');
}

function shareOnTelegram() {
  if (!currentUser) return alert("⚠️ আগে মোবাইল নম্বর দিয়ে লিংক তৈরি করুন!");
  const link = document.getElementById("my-referral-link")?.value || window.location.href;
  const msg = `🔥 বিকাশ ও নগদ ৫০০ টাকা ফ্রি মোবাইল রিচার্জ অফার! ক্লেইম করুন: ${link}`;
  window.open(`https://t.me/share/url?url=${encodeURIComponent(link)}&text=${encodeURIComponent(msg)}`, '_blank');
}

function shareOnMessenger() {
  if (!currentUser) return alert("⚠️ আগে মোবাইল নম্বর দিয়ে লিংক তৈরি করুন!");
  const link = document.getElementById("my-referral-link")?.value || window.location.href;
  window.open(`fb-messenger://share/?link=${encodeURIComponent(link)}`, '_blank');
}

// ============================================================================
// ৮. ৫০০ টাকা রিচার্জ দাবি সাবমিশন (Claim Reward)
// ============================================================================
function handleClaimSubmit(e) {
  if (e) e.preventDefault();

  if (currentReferrals < CAMPAIGN_CONFIG.requiredReferrals) {
    alert(`❌ আপনার এখনও ২০ জন রেফারেল সম্পন্ন হয়নি! বর্তমান রেফারেল: ${currentReferrals}/${CAMPAIGN_CONFIG.requiredReferrals}`);
    return;
  }
  if (!tasksCompleted.ad1 || !tasksCompleted.ad2) {
    alert("❌ অনুগ্রহ করে দুটি স্পন্সর এড টাস্ক সম্পন্ন করুন!");
    return;
  }

  const claimPhone = document.getElementById("claim-phone-input")?.value.trim();
  const paymentMethod = document.getElementById("claim-payment-method")?.value || "bKash";
  const simType = document.getElementById("claim-sim-type")?.value || "Prepaid";

  if (!claimPhone || claimPhone.length !== 11 || !claimPhone.startsWith("01")) {
    alert("❌ সঠিক ১১ ডিজিটের মোবাইল নম্বর দিন");
    return;
  }

  const claimBtn = document.getElementById("btn-claim-submit");
  if (claimBtn) {
    claimBtn.disabled = true;
    claimBtn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i><span>আবেদন পাঠানো হচ্ছে...</span>`;
  }

  fetch(`${CAMPAIGN_CONFIG.apiUrl}?action=submit_claim&ref=${encodeURIComponent(currentRefCode)}&claim_phone=${claimPhone}&payment_method=${paymentMethod}&sim_type=${simType}`)
    .then(res => res.json())
    .then(data => {
      if (data.status === 'success' || data.status === 'info') {
        const claimInfo = data.claim || {
          claim_id: "BK500-" + Math.floor(100000 + Math.random() * 900000),
          claim_phone: claimPhone,
          payment_method: paymentMethod,
          amount: 500,
          submitted_at: new Date().toLocaleTimeString('bn-BD')
        };

        isClaimed = true;
        if (currentUser) {
          currentUser.isClaimed = true;
          localStorage.setItem("my_bk_campaign_user", JSON.stringify(currentUser));
        }

        showSuccessModal(claimInfo);
      } else {
        alert(data.message || "কোনো সমস্যা হয়েছে! আবার চেষ্টা করুন।");
      }
    })
    .catch(() => {
      // Fallback offline claim display
      const fallbackClaim = {
        claim_id: "BK500-" + Math.floor(100000 + Math.random() * 900000),
        claim_phone: claimPhone,
        payment_method: paymentMethod,
        amount: 500,
        submitted_at: new Date().toLocaleTimeString('bn-BD')
      };
      isClaimed = true;
      showSuccessModal(fallbackClaim);
    })
    .finally(() => {
      if (claimBtn) {
        claimBtn.disabled = false;
        claimBtn.innerHTML = `<i class="fa-solid fa-paper-plane"></i><span>৫০০ টাকা রিচার্জ গ্রহণ করুন</span>`;
      }
    });
}

function showSuccessModal(claim) {
  const modal = document.getElementById("success-modal-overlay");
  const modalId = document.getElementById("receipt-claim-id");
  const modalPhone = document.getElementById("receipt-phone");
  const modalMethod = document.getElementById("receipt-method");
  const modalTime = document.getElementById("receipt-time");

  if (modalId) modalId.textContent = claim.claim_id;
  if (modalPhone) modalPhone.textContent = claim.claim_phone;
  if (modalMethod) modalMethod.textContent = claim.payment_method;
  if (modalTime) modalTime.textContent = claim.submitted_at;

  if (modal) modal.classList.add("open");
}

function closeModal() {
  document.getElementById("success-modal-overlay")?.classList.remove("open");
}

// ============================================================================
// ৯. কাউন্টডাউন টাইমার (FOMO & Urgency)
// ============================================================================
function initCountdownTimer() {
  const hoursEl = document.getElementById("timer-hours");
  const minsEl = document.getElementById("timer-mins");
  const secsEl = document.getElementById("timer-secs");

  // Fixed 14h 45m countdown from today midnight
  let totalSeconds = 14 * 3600 + 45 * 60 + 20;

  setInterval(() => {
    totalSeconds--;
    if (totalSeconds <= 0) totalSeconds = 24 * 3600;

    const h = Math.floor(totalSeconds / 3600);
    const m = Math.floor((totalSeconds % 3600) / 60);
    const s = totalSeconds % 60;

    if (hoursEl) hoursEl.textContent = String(h).padStart(2, '0');
    if (minsEl) minsEl.textContent = String(m).padStart(2, '0');
    if (secsEl) secsEl.textContent = String(s).padStart(2, '0');
  }, 1000);
}

// ============================================================================
// ১০. ভাসমান লাইভ উইনার্স নোটিফিকেশন ফিড (Viral Social Proof)
// ============================================================================
const sampleWinners = [
  { name: "মো: আরিফুল ইসলাম", phone: "০১৭১***৪৫২", method: "বিকাশ ক্যাশ", time: "১ মিনিট আগে" },
  { name: "সাদিয়া আক্তার", phone: "০১৮২***৭৮৯", method: "নগদ রিচার্জ", time: "২ মিনিট আগে" },
  { name: "তানজিল আহমেদ", phone: "০১৯১***১২০", method: "বিকাশ ক্যাশ", time: "৩ মিনিট আগে" },
  { name: "সুমাইয়া খাতুন", phone: "০১৭৮***৯০১", method: "নগদ রিচার্জ", time: "৫ মিনিট আগে" },
  { name: "রাকিবুল হাসান", phone: "০১৬৪***২৩৩", method: "গ্রামীণফোন রিচার্জ", time: "৬ মিনিট আগে" },
  { name: "ফারহানা জাহান", phone: "০১৮১***৭৭৪", method: "বিকাশ ক্যাশ", time: "৮ মিনিট আগে" },
  { name: "মিজানুর রহমান", phone: "০১৭২***৮১০", method: "নগদ রিচার্জ", time: "১০ মিনিট আগে" }
];

let winnerIndex = 0;
function startLiveWinnerToasts() {
  const toast = document.getElementById("floating-winner-toast");
  const nameEl = document.getElementById("toast-winner-name");
  const detailEl = document.getElementById("toast-winner-detail");

  if (!toast) return;

  function showNextToast() {
    const winner = sampleWinners[winnerIndex];
    winnerIndex = (winnerIndex + 1) % sampleWinners.length;

    if (nameEl) nameEl.textContent = `${winner.name} (${winner.phone})`;
    if (detailEl) detailEl.textContent = `🎉 ৫০০ টাকা ${winner.method} পেয়েছেন (${winner.time})`;

    toast.classList.add("show");

    setTimeout(() => {
      toast.classList.remove("show");
    }, 4500);
  }

  // First trigger after 3s, then every 9s
  setTimeout(showNextToast, 3000);
  setInterval(showNextToast, 9500);
}

// ============================================================================
// ১১. FAQ অ্যাকর্ডিয়ন টগল
// ============================================================================
function initFaqAccordion() {
  const items = document.querySelectorAll(".faq-item");
  items.forEach(item => {
    const q = item.querySelector(".faq-question");
    if (q) {
      q.addEventListener("click", () => {
        item.classList.toggle("open");
      });
    }
  });
}
