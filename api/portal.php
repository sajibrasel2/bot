<?php
/**
 * Video Portal API — Public API for Category & Video & Ads Delivery
 * Always maintains and delivers the 10 freshest collected videos (FIFO rotation).
 */

header('Content-Type: application/json; charset=utf-8');
header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Methods: GET, POST, OPTIONS');
header('Access-Control-Allow-Headers: Content-Type, Cache-Control, Pragma');
header('Cache-Control: no-store, no-cache, must-revalidate, max-age=0, post-check=0, pre-check=0');
header('Pragma: no-cache');
header('Expires: 0');
header('Surrogate-Control: no-store');
header('Clear-Site-Data: "cache"');

if (isset($_SERVER['REQUEST_METHOD']) && $_SERVER['REQUEST_METHOD'] === 'OPTIONS') {
    http_response_code(200);
    exit;
}

// Default English Categories (High-Converting)
$default_categories = [
    ['id' => 1, 'name' => '🔥 All Leaks', 'slug' => 'all', 'icon' => 'fa-fire', 'order_num' => 0],
    ['id' => 2, 'name' => '🔞 Exclusive Uncut', 'slug' => 'exclusive', 'icon' => 'fa-star', 'order_num' => 1],
    ['id' => 3, 'name' => '💋 Hot Desi MMS', 'slug' => 'desi', 'icon' => 'fa-heart', 'order_num' => 2],
    ['id' => 4, 'name' => '💎 VIP Vault', 'slug' => 'vip', 'icon' => 'fa-gem', 'order_num' => 3],
    ['id' => 5, 'name' => '🎥 Live Webcams', 'slug' => 'live', 'icon' => 'fa-video', 'order_num' => 4],
    ['id' => 6, 'name' => '⚡ Trending Viral', 'slug' => 'viral', 'icon' => 'fa-bolt', 'order_num' => 5]
];

// Default 10 English High-Converting Videos with SEO Keywords
$default_videos = [
    [
        'id' => 1,
        'title' => 'Hotel Room Secret Uncut Leak Part 1',
        'category_slug' => 'viral',
        'video_url' => 'https://www.w3schools.com/html/mov_bbb.mp4',
        'thumb_url' => 'assets/img/video1.jpg',
        'duration' => '04:12',
        'views' => 58450,
        'keywords' => 'hotel room leak, secret recording, viral mms, uncut 1080p, telegram link'
    ],
    [
        'id' => 2,
        'title' => 'Dhaka Couple Private Phone Chat Tape',
        'category_slug' => 'desi',
        'video_url' => 'https://www.w3schools.com/html/movie.mp4',
        'thumb_url' => 'assets/img/video2.jpg',
        'duration' => '07:45',
        'views' => 75300,
        'keywords' => 'dhaka couple leak, private phone chat, hot desi mms, bangla viral video, telegram link'
    ],
    [
        'id' => 3,
        'title' => 'VIP Luxury Suite Uncensored Cam Session',
        'category_slug' => 'vip',
        'video_url' => 'https://interactive-examples.mdn.mozilla.net/media/cc0-videos/flower.mp4',
        'thumb_url' => 'assets/img/video3.jpg',
        'duration' => '05:20',
        'views' => 91200,
        'keywords' => 'vip luxury suite, uncensored cam show, private vault leak, 4k hd stream'
    ],
    [
        'id' => 4,
        'title' => 'Midnight Special Live 1-on-1 Cam Show',
        'category_slug' => 'live',
        'video_url' => 'https://www.w3schools.com/html/mov_bbb.mp4',
        'thumb_url' => 'assets/img/mitu.jpg',
        'duration' => '12:15',
        'views' => 82100,
        'keywords' => 'midnight special cam, 1 on 1 live webcam, webcam leaked video, private session'
    ],
    [
        'id' => 5,
        'title' => 'Hostel Room Secret Hidden Cam Exposed',
        'category_slug' => 'exclusive',
        'video_url' => 'https://www.w3schools.com/html/movie.mp4',
        'thumb_url' => 'assets/img/riya.jpg',
        'duration' => '03:50',
        'views' => 69800,
        'keywords' => 'hostel room secret, hidden cam exposed, exclusive uncut, viral mms 2026'
    ],
    [
        'id' => 6,
        'title' => 'College Friends Private Night Party MMS',
        'category_slug' => 'desi',
        'video_url' => 'https://interactive-examples.mdn.mozilla.net/media/cc0-videos/flower.mp4',
        'thumb_url' => 'assets/img/sadia.jpg',
        'duration' => '08:35',
        'views' => 68900,
        'keywords' => 'college friends night party, desi mms leak, private party video, uncut telegram'
    ],
    [
        'id' => 7,
        'title' => 'VIP Private Cabin Leaked Model Video',
        'category_slug' => 'vip',
        'video_url' => 'https://www.w3schools.com/html/mov_bbb.mp4',
        'thumb_url' => 'assets/img/nusrat.jpg',
        'duration' => '06:18',
        'views' => 85600,
        'keywords' => 'vip private cabin, leaked model video, uncut private tape, telegram full link'
    ],
    [
        'id' => 8,
        'title' => 'Top Trending Viral MMS Clip Full 1080p',
        'category_slug' => 'viral',
        'video_url' => 'https://www.w3schools.com/html/movie.mp4',
        'thumb_url' => 'assets/img/mim.jpg',
        'duration' => '09:40',
        'views' => 112100,
        'keywords' => 'top trending viral clip, mms full 1080p, viral telegram video, direct stream'
    ],
    [
        'id' => 9,
        'title' => 'Live Webcam Secret Bedroom Session 2',
        'category_slug' => 'live',
        'video_url' => 'https://interactive-examples.mdn.mozilla.net/media/cc0-videos/flower.mp4',
        'thumb_url' => 'assets/img/tania.jpg',
        'duration' => '14:22',
        'views' => 53700,
        'keywords' => 'live webcam secret, bedroom session part 2, web show leak, 1080p hd'
    ],
    [
        'id' => 10,
        'title' => 'Exclusive Uncut 1-on-1 Video Call Leak',
        'category_slug' => 'exclusive',
        'video_url' => 'https://www.w3schools.com/html/mov_bbb.mp4',
        'thumb_url' => 'assets/img/video1.jpg',
        'duration' => '11:05',
        'views' => 71800,
        'keywords' => 'exclusive uncut, 1 on 1 video call leak, leaked phone call mms, telegram'
    ]
];

$default_settings = [
    'popunder_enabled' => '1',
    'popunder_url' => 'https://t.me/darkromanceadda24',
    'popunder_script' => '',
    'social_ad_enabled' => '1',
    'social_ad_script' => '',
    'telegram_group_url' => 'https://t.me/darkromanceadda24',
    'portal_title' => 'ADULT HUB LIVE — VIP PRIVATE LEAKS & WEBCAMS',
    'portal_blur' => '14'
];

// Database configuration
$db_host = 'localhost';
$db_name = 'techandc_tlbot';
$db_user = 'techandc_bot';
$db_pass = '12345Sajibs6@';

$env_file = __DIR__ . '/../.env';
if (file_exists($env_file)) {
    $lines = file($env_file, FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES);
    foreach ($lines as $line) {
        if (strpos(trim($line), '#') === 0) continue;
        if (strpos($line, '=') !== false) {
            list($key, $val) = explode('=', $line, 2);
            $key = trim($key);
            $val = trim($val, " \t\n\r\0\x0B\"'");
            if ($key === 'MYSQL_HOST') $db_host = $val;
            if ($key === 'MYSQL_DB') $db_name = $val;
            if ($key === 'MYSQL_USER') $db_user = $val;
            if ($key === 'MYSQL_PASSWORD') $db_pass = $val;
        }
    }
}

$pdo = null;
try {
    $pdo = new PDO("mysql:host={$db_host};dbname={$db_name};charset=utf8mb4", $db_user, $db_pass, [
        PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
        PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC
    ]);
} catch (Exception $e) {}

// Ensure schema and auto-clean
if ($pdo) {
    try {
        $pdo->exec("
            CREATE TABLE IF NOT EXISTS portal_categories (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                slug VARCHAR(100) NOT NULL UNIQUE,
                icon VARCHAR(50) DEFAULT 'fa-fire',
                order_num INT DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        ");

        $pdo->exec("
            CREATE TABLE IF NOT EXISTS portal_videos (
                id INT AUTO_INCREMENT PRIMARY KEY,
                title VARCHAR(255) NOT NULL,
                category_slug VARCHAR(100) NOT NULL,
                video_url VARCHAR(500) NOT NULL,
                thumb_url VARCHAR(500) DEFAULT '',
                duration VARCHAR(50) DEFAULT '04:15',
                views INT DEFAULT 1200,
                is_active TINYINT(1) DEFAULT 1,
                order_num INT DEFAULT 0,
                keywords TEXT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_cat (category_slug),
                INDEX idx_active (is_active)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        ");

        try {
            $pdo->exec("ALTER TABLE portal_videos ADD COLUMN keywords TEXT NULL");
        } catch (Exception $e) {}

        $pdo->exec("
            CREATE TABLE IF NOT EXISTS portal_settings (
                setting_key VARCHAR(100) PRIMARY KEY,
                setting_val TEXT
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        ");

        // Seed default categories ONLY if table is completely empty
        $cntCat = (int) $pdo->query("SELECT COUNT(*) FROM portal_categories")->fetchColumn();
        if ($cntCat === 0) {
            $stmtC = $pdo->prepare("INSERT INTO portal_categories (name, slug, icon, order_num) VALUES (?, ?, ?, ?)");
            foreach ($default_categories as $c) {
                if ($c['slug'] === 'all') continue;
                $stmtC->execute([$c['name'], $c['slug'], $c['icon'], $c['order_num']]);
            }
        }

        // Seed default videos ONLY if table is completely empty
        $cntVid = (int) $pdo->query("SELECT COUNT(*) FROM portal_videos")->fetchColumn();
        if ($cntVid === 0) {
            $stmtV = $pdo->prepare("INSERT INTO portal_videos (title, category_slug, video_url, thumb_url, duration, views, is_active, order_num, keywords) VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)");
            $ord = 1;
            foreach ($default_videos as $v) {
                $kw = $v['keywords'] ?? ($v['title'] . ', viral leak, telegram link');
                $stmtV->execute([$v['title'], $v['category_slug'], $v['video_url'], $v['thumb_url'], $v['duration'], $v['views'], $ord++, $kw]);
            }
        }

        // Maintain exact 10 latest videos (FIFO limit)
        $pdo->exec("
            DELETE FROM portal_videos 
            WHERE id NOT IN (
                SELECT id FROM (
                    SELECT id FROM portal_videos ORDER BY id DESC LIMIT 10
                ) AS keep_rows
            )
        ");

        // Seed settings if none
        $cntSet = (int) $pdo->query("SELECT COUNT(*) FROM portal_settings")->fetchColumn();
        if ($cntSet === 0) {
            $stmtS = $pdo->prepare("INSERT IGNORE INTO portal_settings (setting_key, setting_val) VALUES (?, ?)");
            foreach ($default_settings as $k => $v) {
                $stmtS->execute([$k, $v]);
            }
        }
    } catch (Exception $e) {}
}

$action = $_GET['action'] ?? $_POST['action'] ?? 'get_data';

if ($action === 'get_data') {
    $categories = $default_categories;
    $videos = $default_videos;
    $settings = $default_settings;

    // Translation dictionary for fallback
    $bn_cat_map = [
        'সব ভিডিও' => '🔥 All Leaks',
        'ভাইরাল ভাইরাল' => '⚡ Trending Viral',
        'দেশি হট' => '💋 Hot Desi MMS',
        'এক্সক্লুসিভ' => '🔞 Exclusive Uncut',
        'ভিআইপি লিকস' => '💎 VIP Vault',
        'লাইভ ক্যামেরা' => '🎥 Live Webcams'
    ];
    $bn_vid_map = [
        'আনলকড ফুল এইচডি এক্সক্লুসিভ শো' => 'Unlocked Full HD 4K Exclusive Leak',
        'মধ্যরাতের হট চ্যাট ভাইরাল ক্লিপ' => 'Midnight Secret Hot Chat Viral Leak',
        'ভিআইপি মেম্বার্স অনলি আনকাট লিক' => 'VIP Members Only Uncut Tape',
        'অফিস ট্যুরের গোপন রেকর্ড ভাইরাল' => 'Office Tour Hidden Record Viral Clip',
        '১-অন-১ সিক্রেট চ্যাট পার্টনার শো' => '1-on-1 Private Live Cam Partner Show',
        'লাইভ ক্যামেরা প্রাইভেট শো ২' => 'Live Webcam Private Bedroom Session 2',
        'টপ ট্রেন্ডিং ভাইরাল ক্লিপ এইচডি' => 'Top Trending Viral MMS Tape 1080p',
        'ভিআইপি প্রাইভেট ক্যাবিন ভিডিও লিক' => 'VIP Private Cabin Leaked Model Video',
        'চট্টগ্রাম কলেজ ফ্রেন্ডস নাইট পার্টি' => 'College Friends Secret Night Party MMS',
        'হোস্টেল রুমের গোপন ভিডিও ফাঁস' => 'Hostel Room Secret Hidden Cam Exposed'
    ];

    if ($pdo) {
        try {
            // Fetch DB categories
            // Fetch DB categories
            $db_cats = $pdo->query("SELECT id, name, slug, icon, order_num FROM portal_categories ORDER BY order_num ASC, id ASC")->fetchAll();
            if (!empty($db_cats)) {
                $categories = array_merge(
                    [['id' => 0, 'name' => '🔥 All', 'slug' => 'all', 'icon' => 'fa-fire', 'order_num' => 0]],
                    $db_cats
                );
            }

            // Fetch exactly latest 10 active videos with SEO keywords
            $db_vids = $pdo->query("SELECT id, title, category_slug, video_url, thumb_url, duration, views, keywords, created_at FROM portal_videos WHERE is_active=1 ORDER BY id DESC LIMIT 10")->fetchAll();
            if (!empty($db_vids)) {
                $videos = $db_vids;
            }

            // Fetch DB settings
            $db_sets = $pdo->query("SELECT setting_key, setting_val FROM portal_settings")->fetchAll();
            foreach ($db_sets as $r) {
                $settings[$r['setting_key']] = $r['setting_val'];
            }
        } catch (Exception $e) {}
    }

    echo json_encode([
        'status' => 'success',
        'categories' => $categories,
        'videos' => $videos,
        'settings' => $settings,
        'total' => count($videos)
    ], JSON_UNESCAPED_UNICODE);
    exit;
}

if ($action === 'sitemap') {
    header('Content-Type: application/xml; charset=utf-8');
    $site_url = 'https://techandclick.site/bot/';
    echo '<?xml version="1.0" encoding="UTF-8"?>' . "\n";
    echo '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:video="http://www.google.com/schemas/sitemap-video/1.1">' . "\n";
    echo '  <url>' . "\n";
    echo '    <loc>' . htmlspecialchars($site_url) . '</loc>' . "\n";
    echo '    <changefreq>hourly</changefreq>' . "\n";
    echo '    <priority>1.0</priority>' . "\n";
    
    $s_vids = $default_videos;
    if ($pdo) {
        try {
            $db_s = $pdo->query("SELECT id, title, category_slug, video_url, thumb_url, duration, views, keywords, created_at FROM portal_videos WHERE is_active=1 ORDER BY id DESC LIMIT 10")->fetchAll();
            if (!empty($db_s)) $s_vids = $db_s;
        } catch (Exception $e) {}
    }
    
    foreach ($s_vids as $sv) {
        $th = (strpos($sv['thumb_url'], 'http') === 0) ? $sv['thumb_url'] : $site_url . ltrim($sv['thumb_url'], '/');
        $kw = !empty($sv['keywords']) ? $sv['keywords'] : ($sv['title'] . ', viral leak, telegram link');
        $dt = !empty($sv['created_at']) ? date('c', strtotime($sv['created_at'])) : date('c');
        echo '    <video:video>' . "\n";
        echo '      <video:thumbnail_loc>' . htmlspecialchars($th) . '</video:thumbnail_loc>' . "\n";
        echo '      <video:title>' . htmlspecialchars($sv['title']) . '</video:title>' . "\n";
        echo '      <video:description>' . htmlspecialchars("Watch " . $sv['title'] . " full uncut 1080p private leak on Telegram & Web.") . '</video:description>' . "\n";
        echo '      <video:content_loc>' . htmlspecialchars($sv['video_url']) . '</video:content_loc>' . "\n";
        echo '      <video:publication_date>' . htmlspecialchars($dt) . '</video:publication_date>' . "\n";
        echo '      <video:family_friendly>no</video:family_friendly>' . "\n";
        echo '      <video:tag>' . htmlspecialchars($kw) . '</video:tag>' . "\n";
        echo '    </video:video>' . "\n";
    }
    
    echo '  </url>' . "\n";
    echo '</urlset>';
    exit;
}

if ($action === 'view') {
    $vid = (int) ($_POST['video_id'] ?? $_GET['video_id'] ?? 0);
    if ($pdo && $vid > 0) {
        try {
            $pdo->prepare("UPDATE portal_videos SET views = views + 1 WHERE id=?")->execute([$vid]);
        } catch (Exception $e) {}
    }
    echo json_encode(['status' => 'success']);
    exit;
}

echo json_encode(['status' => 'error', 'message' => 'Invalid action']);
