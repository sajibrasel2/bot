// ========================================================
// 1. Direct Links, Adsterra Configuration & Click Interceptors
// ========================================================
const DIRECT_LINK_1 = 'https://omg10.com/4/11017767';
const DIRECT_LINK_2 = 'https://www.effectivecpmnetwork.com/mgtqwzbp?key=5c4003e0ae2b0ebd387daded087bc9aa';

let adClickCount = parseInt(sessionStorage.getItem('kidsAdClickCount') || '0');

/**
 * Triggers direct ad redirect to maximize publisher revenue (alternates between Link 1 & Link 2)
 */
function triggerAdRedirect(e) {
  if (e && e.stopPropagation) e.stopPropagation();

  const targetUrl = (adClickCount % 2 === 0) ? DIRECT_LINK_1 : DIRECT_LINK_2;
  adClickCount++;
  sessionStorage.setItem('kidsAdClickCount', adClickCount);

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

/**
 * Initialize all Adsterra network scripts (Popunder, Social Bar, 300x250 banners)
 */
let adsLoaded = false;
function initAdsterraMonetization() {
  if (adsLoaded) return;
  adsLoaded = true;

  // 1. Adsterra Popunder Script
  try {
    const popScript = document.createElement('script');
    popScript.src = 'https://pl31109060.profitableratecpmnetwork.com/15/77/e4/1577e445d5052d32b8171c055c4aae03.js';
    document.body.appendChild(popScript);
  } catch(e) {}

  // 2. Adsterra Native Social Bar Script
  try {
    const nativeScript = document.createElement('script');
    nativeScript.src = 'https://pl31109061.profitableratecpmnetwork.com/96def6f0cc4dba72ad781c93e21f61fd/invoke.js';
    nativeScript.async = true;
    nativeScript.setAttribute('data-cfasync', 'false');
    document.body.appendChild(nativeScript);
  } catch(e) {}

  // 3. Adsterra 300x250 Banner Slots
  initBannerSlots();
}

function initBannerSlots() {
  const containers = document.querySelectorAll('.adsterra-300x250-container');
  containers.forEach((container) => {
    if (!container.hasChildNodes() || container.children.length === 0) {
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
        console.log("Kids Banner Load Note:", e);
      }
    }
  });
}

// ========================================================
// 2. Kids Video Database
// ========================================================
const kidsVideos = [
  {
    id: 1,
    title: "টম অ্যান্ড জেরি — সেরা মজার কমেডি পর্ব (ফুল এইচডি)",
    category: "tom-jerry",
    categoryName: "🐱 টম অ্যান্ড জেরি",
    duration: "১০:৪৫",
    views: "১.৮ লক্ষ ভিউ",
    likes: "৯৯%",
    tag: "জনপ্রিয় পর্ব",
    tagType: "hd",
    youtubeId: "t0Q2otsqC4I",
    cover: "https://img.youtube.com/vi/t0Q2otsqC4I/hqdefault.jpg"
  },
  {
    id: 2,
    title: "চাঁদ উঠেছে ফুল ফুটেছে কদম তলায় কে — ছোটদের সেরা বাংলা ছড়া গান",
    category: "rhymes",
    categoryName: "🎵 ছড়া ও গান",
    duration: "০৪:২০",
    views: "২.৪ লক্ষ ভিউ",
    likes: "৯৮%",
    tag: "বাংলা ছড়া",
    tagType: "fun",
    youtubeId: "6g3A3e4wZ0s",
    cover: "https://img.youtube.com/vi/6g3A3e4wZ0s/hqdefault.jpg"
  },
  {
    id: 3,
    title: "গোপাল ভাঁড় — রাজার বুদ্ধিমান বিচার ও মিষ্টি চুরি (মজার কার্টুন)",
    category: "comedy",
    categoryName: "😂 মজার কমেডি",
    duration: "১২:১৫",
    views: "৩.৫ লক্ষ ভিউ",
    likes: "৯৯%",
    tag: "হাসির কার্টুন",
    tagType: "live-cam",
    youtubeId: "CwL1wPzGv2k",
    cover: "https://img.youtube.com/vi/CwL1wPzGv2k/hqdefault.jpg"
  },
  {
    id: 4,
    title: "মোটু পাতলু — সমুচার জাদু ও উড়ন্ত গাড়ির রোমাঞ্চকর কাণ্ড",
    category: "comedy",
    categoryName: "😂 মজার কমেডি",
    duration: "১১:৩০",
    views: "১.২ লক্ষ ভিউ",
    likes: "৯৭%",
    tag: "অ্যাকশন কমেডি",
    tagType: "hd",
    youtubeId: "YqN_z1aZ308",
    cover: "https://img.youtube.com/vi/YqN_z1aZ308/hqdefault.jpg"
  },
  {
    id: 5,
    title: "সিংহ এবং ছোট্ট ইঁদুরের বন্ধুত্ব — শিক্ষণীয় ঈশপের রূপকথা গল্প",
    category: "stories",
    categoryName: "🧙‍♂️ রূপকথার গল্প",
    duration: "০৮:৫০",
    views: "৮৫ হাজার ভিউ",
    likes: "১০০%",
    tag: "শিক্ষণীয় গল্প",
    tagType: "fun",
    youtubeId: "Gv4EfZ5r8B4",
    cover: "https://img.youtube.com/vi/Gv4EfZ5r8B4/hqdefault.jpg"
  },
  {
    id: 6,
    title: "মাশা অ্যান্ড দ্য বিয়ার — মজার বরফের স্কেটিং ও মিষ্টি দুষ্টুমি",
    category: "comedy",
    categoryName: "😂 মজার কমেডি",
    duration: "০৭:৪০",
    views: "৪.১ লক্ষ ভিউ",
    likes: "৯৯%",
    tag: "সুপারহিট",
    tagType: "live-cam",
    youtubeId: "a_80vXFp56E",
    cover: "https://img.youtube.com/vi/a_80vXFp56E/hqdefault.jpg"
  },
  {
    id: 7,
    title: "খোকন খোকন ডাক পাড়ি খোকন গেলো কার বাড়ি — মিষ্টি এনিমেশন ছড়া",
    category: "rhymes",
    categoryName: "🎵 ছড়া ও গান",
    duration: "০৩:৫০",
    views: "১.৯ লক্ষ ভিউ",
    likes: "৯৮%",
    tag: "ছোটদের গান",
    tagType: "fun",
    youtubeId: "WRVsOCh907o",
    cover: "https://img.youtube.com/vi/WRVsOCh907o/hqdefault.jpg"
  },
  {
    id: 8,
    title: "পরীর দেশের রাজকন্যা ও জাদুর কাঠির গল্প — রূপকথার রোমাঞ্চ",
    category: "stories",
    categoryName: "🧙‍♂️ রূপকথার গল্প",
    duration: "১৪:১০",
    views: "৯২ হাজার ভিউ",
    likes: "৯৭%",
    tag: "জাদুর গল্প",
    tagType: "hd",
    youtubeId: "wUqFj6jF2bA",
    cover: "https://img.youtube.com/vi/wUqFj6jF2bA/hqdefault.jpg"
  },
  {
    id: 9,
    title: "টম অ্যান্ড জেরি — পনির চুরির মহাযুদ্ধ ও কুকুরের কাণ্ড",
    category: "tom-jerry",
    categoryName: "🐱 টম অ্যান্ড জেরি",
    duration: "০৯:২৫",
    views: "২.৮ লক্ষ ভিউ",
    likes: "৯৯%",
    tag: "ক্লাসিক টম",
    tagType: "live-cam",
    youtubeId: "k_d5jWvBirU",
    cover: "https://img.youtube.com/vi/k_d5jWvBirU/hqdefault.jpg"
  },
  {
    id: 10,
    title: "বেবি শার্ক ড্যান্স ও ছোটদের রঙিন নাচের আনন্দ",
    category: "rhymes",
    categoryName: "🎵 ছড়া ও গান",
    duration: "০২:১৬",
    views: "৫.৫ লক্ষ ভিউ",
    likes: "১০০%",
    tag: "বিশ্বসেরা ছড়া",
    tagType: "fun",
    youtubeId: "XqZsoesa55w",
    cover: "https://img.youtube.com/vi/XqZsoesa55w/hqdefault.jpg"
  },
  {
    id: 11,
    title: "সহজ পদ্ধতিতে রঙিন প্রজাপতি ও পাখির ছবি আঁকা শিখুন",
    category: "learning",
    categoryName: "🎨 ড্রয়িং ও শিক্ষা",
    duration: "০৬:৩০",
    views: "৬৫ হাজার ভিউ",
    likes: "৯৯%",
    tag: "ড্রয়িং ক্লাস",
    tagType: "hd",
    youtubeId: "07d2dXHYb94",
    cover: "https://img.youtube.com/vi/07d2dXHYb94/hqdefault.jpg"
  },
  {
    id: 12,
    title: "বুদ্ধিমান তৃষ্ণার্ত কাক ও মাটির কলসির গল্প — ঈশপের কাহিনী",
    category: "stories",
    categoryName: "🧙‍♂️ রূপকথার গল্প",
    duration: "০৫:১৫",
    views: "১.১ লক্ষ ভিউ",
    likes: "৯৮%",
    tag: "নীতিশিক্ষা",
    tagType: "fun",
    youtubeId: "t0Q2otsqC4I",
    cover: "https://img.youtube.com/vi/t0Q2otsqC4I/hqdefault.jpg"
  }
];

let currentVideoIndex = 0;
let currentFilter = 'all';

// ========================================================
// 3. Render Video Grid
// ========================================================
function renderKidsGrid(list) {
  const grid = document.getElementById('kids-video-grid');
  const empty = document.getElementById('kids-empty-state');
  const countEl = document.getElementById('kids-video-count');

  if (!grid) return;

  if (countEl) {
    countEl.innerText = `${toBengaliDigits(list.length)} টি ভিডিও`;
  }

  if (list.length === 0) {
    grid.innerHTML = '';
    if (empty) empty.style.display = 'block';
    return;
  }

  if (empty) empty.style.display = 'none';

  let html = '';
  list.forEach((v, idx) => {
    // Find absolute index in kidsVideos
    const realIdx = kidsVideos.findIndex(item => item.id === v.id);

    html += `
      <div class="kids-video-card" onclick="openKidsPlayer(${realIdx})">
        <div class="kids-thumb-box">
          <img src="${v.cover}" class="kids-thumb-img" alt="${v.title}" loading="lazy" onerror="this.src='assets/img/video1.jpg'" />
          <div class="kids-tag-pill ${v.tagType}"><i class="fa-solid fa-sparkles"></i> ${v.tag}</div>
          <div class="kids-duration-badge"><i class="fa-solid fa-clock"></i> ${toBengaliDigits(v.duration)}</div>
          <div class="kids-play-overlay-btn"><i class="fa-solid fa-play"></i></div>
        </div>
        <div class="kids-video-info">
          <h3 class="kids-video-title">${v.title}</h3>
          <div class="kids-video-meta">
            <div class="kids-meta-left">
              <span class="kids-meta-item"><i class="fa-solid fa-eye" style="color:var(--kids-cyan);"></i> ${v.views}</span>
              <span class="kids-meta-item" style="color:var(--kids-pink);"><i class="fa-solid fa-heart"></i> ${v.likes}</span>
            </div>
            <div class="kids-meta-action">
              <i class="fa-solid fa-play-circle"></i> দেখুন
            </div>
          </div>
        </div>
      </div>
    `;

    // High CTR in-feed sponsored ad banner after 4th card
    if (idx === 3) {
      html += `
        <div class="kids-ad-promo-box" onclick="triggerAdRedirect(event)" style="grid-column: 1 / -1;">
          <div class="kids-ad-promo-info">
            <span class="kids-ad-badge"><i class="fa-solid fa-crown"></i> স্পন্সরড সারপ্রাইজ</span>
            <h4 class="kids-ad-title">🎁 নতুন কার্টুন ও খেলনার এক্সক্লুসিভ ভিডিও প্লে করুন</h4>
            <p class="kids-ad-subtitle">এইচডি কোয়ালিটিতে দেখতে এবং ইনস্টল করতে এখনই ট্যাপ করুন</p>
          </div>
          <button class="kids-ad-btn"><i class="fa-solid fa-bolt"></i> আনলক করুন</button>
        </div>
      `;
    }
  });

  grid.innerHTML = html;
}

// Convert numbers to Bengali digits
function toBengaliDigits(str) {
  const bn = ['০', '১', '২', '৩', '৪', '৫', '৬', '৭', '৮', '৯'];
  return String(str).replace(/[0-9]/g, d => bn[parseInt(d)]);
}

// ========================================================
// 4. Video Player Modal Logic with Smart CTR Ad Hook
// ========================================================
function openKidsPlayer(index) {
  currentVideoIndex = index;
  const v = kidsVideos[index];
  if (!v) return;

  const modal = document.getElementById('kids-player-modal');
  const titleEl = document.getElementById('kids-player-title');
  const frameEl = document.getElementById('kids-player-iframe');
  const metaViews = document.getElementById('kids-player-views');
  const metaTag = document.getElementById('kids-player-tag');

  if (titleEl) titleEl.innerText = v.title;
  if (metaViews) metaViews.innerText = `${v.views} • ${v.likes} লাইক`;
  if (metaTag) metaTag.innerText = v.categoryName;

  // Load YouTube embed with autoplay
  if (frameEl) {
    frameEl.src = `https://www.youtube-nocookie.com/embed/${v.youtubeId}?autoplay=1&rel=0&modestbranding=1`;
  }

  // Populate related list
  populateRelatedVideos(index);

  if (modal) modal.classList.add('active');

  // Trigger high-revenue smartlink on background tab
  triggerAdRedirect();

  // Re-init player banner if present
  setTimeout(initBannerSlots, 300);
}

function closeKidsPlayer() {
  const modal = document.getElementById('kids-player-modal');
  const frameEl = document.getElementById('kids-player-iframe');
  if (modal) modal.classList.remove('active');
  if (frameEl) frameEl.src = '';
}

function playNextEpisode() {
  currentVideoIndex = (currentVideoIndex + 1) % kidsVideos.length;
  openKidsPlayer(currentVideoIndex);
}

function downloadEpisodeHD() {
  triggerAdRedirect();
  alert("🎉 সম্পূর্ণ ভিডিওটি ফুল এইচডি (1080p) ডাউনলোড শুরু হচ্ছে...");
}

function populateRelatedVideos(currentIndex) {
  const container = document.getElementById('kids-related-list');
  if (!container) return;

  let html = '';
  const currentCat = kidsVideos[currentIndex].category;
  const related = kidsVideos.filter((_, i) => i !== currentIndex).slice(0, 4);

  related.forEach(item => {
    const realIdx = kidsVideos.findIndex(v => v.id === item.id);
    html += `
      <div class="kids-related-item" onclick="openKidsPlayer(${realIdx})">
        <img src="${item.cover}" class="kids-related-thumb" alt="${item.title}" onerror="this.src='assets/img/video2.jpg'" />
        <div class="kids-related-info">
          <div class="kids-related-name">${item.title}</div>
          <div class="kids-related-sub"><i class="fa-solid fa-play"></i> ${item.views}</div>
        </div>
        <div style="color:var(--kids-cyan); font-size:14px;"><i class="fa-solid fa-circle-play"></i></div>
      </div>
    `;
  });

  container.innerHTML = html;
}

// ========================================================
// 5. Interactive Kids Reactions (Balloons, Hearts, Stars)
// ========================================================
function sendKidsReaction(emoji) {
  const container = document.getElementById('kids-float-container');
  if (!container) return;

  for (let i = 0; i < 4; i++) {
    setTimeout(() => {
      const item = document.createElement('div');
      item.className = 'kids-float-item';
      item.innerText = emoji;
      item.style.right = `${10 + Math.random() * 60}px`;
      container.appendChild(item);
      setTimeout(() => item.remove(), 2100);
    }, i * 150);
  }
}

// ========================================================
// 6. Interactive Surprise Gift & Spin Wheel
// ========================================================
function openSurpriseGift() {
  const modal = document.getElementById('kids-gift-modal');
  if (modal) modal.classList.add('active');
}

function closeSurpriseGift() {
  const modal = document.getElementById('kids-gift-modal');
  if (modal) modal.classList.remove('active');
}

function claimSurpriseGift() {
  closeSurpriseGift();
  triggerAdRedirect();
  // Open random special video
  const randIdx = Math.floor(Math.random() * kidsVideos.length);
  openKidsPlayer(randIdx);
}

function spinCartoonWheel() {
  triggerAdRedirect();
  alert("🎡 হুইল ঘুরছে... আপনি জিতেছেন একটি এক্সক্লুসিভ টম অ্যান্ড জেরি স্পেশাল ভিডিও!");
  openKidsPlayer(0);
}

// ========================================================
// 7. Search & Category Filters
// ========================================================
function setupFiltersAndSearch() {
  // Category Chips
  const chips = document.querySelectorAll('.kids-chip');
  chips.forEach(chip => {
    chip.addEventListener('click', () => {
      chips.forEach(c => c.classList.remove('active'));
      chip.classList.add('active');
      currentFilter = chip.getAttribute('data-cat') || 'all';
      applyFilterAndSearch();
    });
  });

  // Search Input
  const searchInput = document.getElementById('kids-search-input');
  const clearBtn = document.getElementById('kids-search-clear');

  if (searchInput) {
    searchInput.addEventListener('input', () => {
      if (clearBtn) clearBtn.style.display = searchInput.value ? 'block' : 'none';
      applyFilterAndSearch();
    });
  }

  if (clearBtn) {
    clearBtn.addEventListener('click', () => {
      if (searchInput) {
        searchInput.value = '';
        clearBtn.style.display = 'none';
        applyFilterAndSearch();
      }
    });
  }
}

function applyFilterAndSearch() {
  const query = (document.getElementById('kids-search-input')?.value || '').trim().toLowerCase();

  let filtered = kidsVideos;

  if (currentFilter !== 'all') {
    filtered = filtered.filter(v => v.category === currentFilter);
  }

  if (query) {
    filtered = filtered.filter(v => 
      v.title.toLowerCase().includes(query) || 
      v.categoryName.toLowerCase().includes(query) ||
      v.tag.toLowerCase().includes(query)
    );
  }

  renderKidsGrid(filtered);
}

// ========================================================
// 8. Generate Floating Background Stars & Confetti
// ========================================================
function spawnBackgroundStars() {
  const container = document.getElementById('kids-bg-stars');
  if (!container) return;

  const icons = ['⭐', '🎈', '✨', '🍭', '🎨', '🌟', '🚀', '🐱', '🎵'];
  for (let i = 0; i < 16; i++) {
    const span = document.createElement('span');
    span.innerText = icons[Math.floor(Math.random() * icons.length)];
    span.style.left = `${Math.random() * 95}%`;
    span.style.animationDelay = `${Math.random() * 12}s`;
    span.style.animationDuration = `${10 + Math.random() * 8}s`;
    span.style.fontSize = `${14 + Math.random() * 14}px`;
    container.appendChild(span);
  }
}

// ========================================================
// DOM Ready Bootstrap
// ========================================================
document.addEventListener('DOMContentLoaded', () => {
  spawnBackgroundStars();
  renderKidsGrid(kidsVideos);
  setupFiltersAndSearch();
  initAdsterraMonetization();
});
