<?php
/**
 * Video Portal API — Public API for Category & Video & Ads Delivery
 */

header('Content-Type: application/json; charset=utf-8');
header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Methods: GET, POST, OPTIONS');
header('Access-Control-Allow-Headers: Content-Type, Cache-Control, Pragma');
header('Cache-Control: no-store, no-cache, must-revalidate, max-age=0, post-check=0, pre-check=0');
header('Pragma: no-cache');
header('Expires: 0');

if (isset($_SERVER['REQUEST_METHOD']) && $_SERVER['REQUEST_METHOD'] === 'OPTIONS') {
    http_response_code(200);
    exit;
}

// Default Fallback Data (Always available even if DB is offline)
$default_categories = [
    ['id' => 1, 'name' => '🔥 সব ভিডিও (All)', 'slug' => 'all', 'icon' => 'fa-fire', 'order_num' => 0],
    ['id' => 2, 'name' => '🔞 এক্সক্লুসিভ (Exclusive)', 'slug' => 'exclusive', 'icon' => 'fa-star', 'order_num' => 1],
    ['id' => 3, 'name' => '🇧🇩 দেশি হট (Desi)', 'slug' => 'desi', 'icon' => 'fa-heart', 'order_num' => 2],
    ['id' => 4, 'name' => '💎 ভিআইপি লিকস (VIP)', 'slug' => 'vip', 'icon' => 'fa-gem', 'order_num' => 3],
    ['id' => 5, 'name' => '🎥 লাইভ ক্যামেরা (Live)', 'slug' => 'live', 'icon' => 'fa-video', 'order_num' => 4],
    ['id' => 6, 'name' => '⚡ ভাইরাল কালেকশন (Viral)', 'slug' => 'viral', 'icon' => 'fa-bolt', 'order_num' => 5]
];

$default_videos = [
    [
        'id' => 1,
        'title' => 'হোটেল রুমের এক্সক্লুসিভ ভাইরাল পার্ট ১',
        'category_slug' => 'viral',
        'video_url' => 'https://www.w3schools.com/html/mov_bbb.mp4',
        'thumb_url' => 'assets/img/video1.jpg',
        'duration' => '04:12',
        'views' => 28450
    ],
    [
        'id' => 2,
        'title' => 'ঢাকা কাপল প্রাইভেট ফোন চ্যাট রেকর্ড',
        'category_slug' => 'desi',
        'video_url' => 'https://www.w3schools.com/html/movie.mp4',
        'thumb_url' => 'assets/img/video2.jpg',
        'duration' => '07:45',
        'views' => 35300
    ],
    [
        'id' => 3,
        'title' => 'ভিআইপি রুম আনকাট লিকস ক্লিপ',
        'category_slug' => 'vip',
        'video_url' => 'https://interactive-examples.mdn.mozilla.net/media/cc0-videos/flower.mp4',
        'thumb_url' => 'assets/img/video3.jpg',
        'duration' => '05:20',
        'views' => 41200
    ],
    [
        'id' => 4,
        'title' => 'মাঝরাতের স্পেশাল লাইভ ওয়েবক্যাম শো',
        'category_slug' => 'live',
        'video_url' => 'https://www.w3schools.com/html/mov_bbb.mp4',
        'thumb_url' => 'assets/img/mitu.jpg',
        'duration' => '12:15',
        'views' => 52100
    ],
    [
        'id' => 5,
        'title' => 'হোস্টেল রুমের গোপন ভিডিও ফাঁস',
        'category_slug' => 'exclusive',
        'video_url' => 'https://www.w3schools.com/html/movie.mp4',
        'thumb_url' => 'assets/img/riya.jpg',
        'duration' => '03:50',
        'views' => 39800
    ],
    [
        'id' => 6,
        'title' => 'চট্টগ্রাম কলেজ ফ্রেন্ডস নাইট পার্টি',
        'category_slug' => 'desi',
        'video_url' => 'https://interactive-examples.mdn.mozilla.net/media/cc0-videos/flower.mp4',
        'thumb_url' => 'assets/img/sadia.jpg',
        'duration' => '08:35',
        'views' => 48900
    ],
    [
        'id' => 7,
        'title' => 'ভিআইপি প্রাইভেট ক্যাবিন ভিডিও লিক',
        'category_slug' => 'vip',
        'video_url' => 'https://www.w3schools.com/html/mov_bbb.mp4',
        'thumb_url' => 'assets/img/nusrat.jpg',
        'duration' => '06:18',
        'views' => 55600
    ],
    [
        'id' => 8,
        'title' => 'টপ ট্রেন্ডিং ভাইরাল ক্লিপ এইচডি',
        'category_slug' => 'viral',
        'video_url' => 'https://www.w3schools.com/html/movie.mp4',
        'thumb_url' => 'assets/img/mim.jpg',
        'duration' => '09:40',
        'views' => 62100
    ],
    [
        'id' => 9,
        'title' => 'লাইভ ক্যামেরা প্রাইভেট শো ২',
        'category_slug' => 'live',
        'video_url' => 'https://interactive-examples.mdn.mozilla.net/media/cc0-videos/flower.mp4',
        'thumb_url' => 'assets/img/tania.jpg',
        'duration' => '14:22',
        'views' => 33700
    ],
    [
        'id' => 10,
        'title' => '১-অন-১ সিক্রেট চ্যাট পার্টনার শো',
        'category_slug' => 'exclusive',
        'video_url' => 'https://www.w3schools.com/html/mov_bbb.mp4',
        'thumb_url' => 'assets/img/video1.jpg',
        'duration' => '11:05',
        'views' => 51800
    ],
    [
        'id' => 11,
        'title' => 'অফিস ট্যুরের গোপন রেকর্ড ভাইরাল',
        'category_slug' => 'desi',
        'video_url' => 'https://www.w3schools.com/html/movie.mp4',
        'thumb_url' => 'assets/img/video2.jpg',
        'duration' => '04:55',
        'views' => 26900
    ],
    [
        'id' => 12,
        'title' => 'ভিআইপি মেম্বার্স অনলি আনকাট লিক',
        'category_slug' => 'vip',
        'video_url' => 'https://interactive-examples.mdn.mozilla.net/media/cc0-videos/flower.mp4',
        'thumb_url' => 'assets/img/video3.jpg',
        'duration' => '15:30',
        'views' => 74500
    ],
    [
        'id' => 13,
        'title' => 'মধ্যরাতের হট চ্যাট ভাইরাল ক্লিপ',
        'category_slug' => 'viral',
        'video_url' => 'https://www.w3schools.com/html/mov_bbb.mp4',
        'thumb_url' => 'assets/img/mitu.jpg',
        'duration' => '06:40',
        'views' => 47800
    ],
    [
        'id' => 14,
        'title' => 'আনলকড ফুল এইচডি এক্সক্লুসিভ শো',
        'category_slug' => 'exclusive',
        'video_url' => 'https://www.w3schools.com/html/movie.mp4',
        'thumb_url' => 'assets/img/riya.jpg',
        'duration' => '08:15',
        'views' => 59200
    ]
];

$default_settings = [
    'popunder_enabled' => '1',
    'popunder_url' => 'https://t.me/darkfantasyloverzone',
    'popunder_script' => '',
    'social_ad_enabled' => '1',
    'social_ad_script' => '',
    'telegram_group_url' => 'https://t.me/darkfantasyloverzone',
    'portal_title' => 'EXCLUSIVE DESI & VIRAL VAULT',
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
} catch (Exception $e) {
    // If remote or local fails, $pdo remains null and fallbacks are used
}

// Ensure database tables exist if DB is connected
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
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_cat (category_slug),
                INDEX idx_active (is_active)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        ");

        $pdo->exec("
            CREATE TABLE IF NOT EXISTS portal_settings (
                setting_key VARCHAR(100) PRIMARY KEY,
                setting_val TEXT
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        ");

        // Seed default categories if empty
        $cntCat = (int) $pdo->query("SELECT COUNT(*) FROM portal_categories")->fetchColumn();
        if ($cntCat === 0) {
            $stmtC = $pdo->prepare("INSERT IGNORE INTO portal_categories (name, slug, icon, order_num) VALUES (?, ?, ?, ?)");
            foreach ($default_categories as $c) {
                if ($c['slug'] === 'all') continue;
                $stmtC->execute([$c['name'], $c['slug'], $c['icon'], $c['order_num']]);
            }
        }

        // Seed default videos if empty
        $cntVid = (int) $pdo->query("SELECT COUNT(*) FROM portal_videos")->fetchColumn();
        if ($cntVid === 0) {
            $stmtV = $pdo->prepare("INSERT INTO portal_videos (title, category_slug, video_url, thumb_url, duration, views, is_active, order_num) VALUES (?, ?, ?, ?, ?, ?, 1, ?)");
            $ord = 1;
            foreach ($default_videos as $v) {
                $stmtV->execute([$v['title'], $v['category_slug'], $v['video_url'], $v['thumb_url'], $v['duration'], $v['views'], $ord++]);
            }
        }

        // Seed default settings if empty
        $cntSet = (int) $pdo->query("SELECT COUNT(*) FROM portal_settings")->fetchColumn();
        if ($cntSet === 0) {
            $stmtS = $pdo->prepare("INSERT IGNORE INTO portal_settings (setting_key, setting_val) VALUES (?, ?)");
            foreach ($default_settings as $k => $v) {
                $stmtS->execute([$k, $v]);
            }
        }
    } catch (Exception $e) {
        // Table creation warning ignored
    }
}

$action = $_GET['action'] ?? $_POST['action'] ?? 'get_data';

if ($action === 'get_data') {
    $categories = $default_categories;
    $videos = $default_videos;
    $settings = $default_settings;

    if ($pdo) {
        try {
            // Fetch DB categories
            $db_cats = $pdo->query("SELECT id, name, slug, icon, order_num FROM portal_categories ORDER BY order_num ASC, id ASC")->fetchAll();
            if (!empty($db_cats)) {
                // Ensure 'all' is at front
                $categories = array_merge(
                    [['id' => 0, 'name' => '🔥 সব ভিডিও (All)', 'slug' => 'all', 'icon' => 'fa-fire', 'order_num' => 0]],
                    $db_cats
                );
            }

            // Fetch DB videos
            $db_vids = $pdo->query("SELECT id, title, category_slug, video_url, thumb_url, duration, views FROM portal_videos WHERE is_active=1 ORDER BY order_num ASC, id DESC LIMIT 25")->fetchAll();
            if (!empty($db_vids)) {
                $videos = $db_vids;
            }

            // Fetch DB settings
            $db_sets = $pdo->query("SELECT setting_key, setting_val FROM portal_settings")->fetchAll();
            foreach ($db_sets as $r) {
                $settings[$r['setting_key']] = $r['setting_val'];
            }
        } catch (Exception $e) {
            // Use defaults on error
        }
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
