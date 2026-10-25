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

// Default 10 English High-Converting Videos
$default_videos = [
    [
        'id' => 1,
        'title' => 'Hotel Room Secret Uncut Leak Part 1',
        'category_slug' => 'viral',
        'video_url' => 'https://www.w3schools.com/html/mov_bbb.mp4',
        'thumb_url' => 'assets/img/video1.jpg',
        'duration' => '04:12',
        'views' => 58450
    ],
    [
        'id' => 2,
        'title' => 'Dhaka Couple Private Phone Chat Tape',
        'category_slug' => 'desi',
        'video_url' => 'https://www.w3schools.com/html/movie.mp4',
        'thumb_url' => 'assets/img/video2.jpg',
        'duration' => '07:45',
        'views' => 75300
    ],
    [
        'id' => 3,
        'title' => 'VIP Luxury Suite Uncensored Cam Session',
        'category_slug' => 'vip',
        'video_url' => 'https://interactive-examples.mdn.mozilla.net/media/cc0-videos/flower.mp4',
        'thumb_url' => 'assets/img/video3.jpg',
        'duration' => '05:20',
        'views' => 91200
    ],
    [
        'id' => 4,
        'title' => 'Midnight Special Live 1-on-1 Cam Show',
        'category_slug' => 'live',
        'video_url' => 'https://www.w3schools.com/html/mov_bbb.mp4',
        'thumb_url' => 'assets/img/mitu.jpg',
        'duration' => '12:15',
        'views' => 82100
    ],
    [
        'id' => 5,
        'title' => 'Hostel Room Secret Hidden Cam Exposed',
        'category_slug' => 'exclusive',
        'video_url' => 'https://www.w3schools.com/html/movie.mp4',
        'thumb_url' => 'assets/img/riya.jpg',
        'duration' => '03:50',
        'views' => 69800
    ],
    [
        'id' => 6,
        'title' => 'College Friends Private Night Party MMS',
        'category_slug' => 'desi',
        'video_url' => 'https://interactive-examples.mdn.mozilla.net/media/cc0-videos/flower.mp4',
        'thumb_url' => 'assets/img/sadia.jpg',
        'duration' => '08:35',
        'views' => 68900
    ],
    [
        'id' => 7,
        'title' => 'VIP Private Cabin Leaked Model Video',
        'category_slug' => 'vip',
        'video_url' => 'https://www.w3schools.com/html/mov_bbb.mp4',
        'thumb_url' => 'assets/img/nusrat.jpg',
        'duration' => '06:18',
        'views' => 85600
    ],
    [
        'id' => 8,
        'title' => 'Top Trending Viral MMS Clip Full 1080p',
        'category_slug' => 'viral',
        'video_url' => 'https://www.w3schools.com/html/movie.mp4',
        'thumb_url' => 'assets/img/mim.jpg',
        'duration' => '09:40',
        'views' => 112100
    ],
    [
        'id' => 9,
        'title' => 'Live Webcam Secret Bedroom Session 2',
        'category_slug' => 'live',
        'video_url' => 'https://interactive-examples.mdn.mozilla.net/media/cc0-videos/flower.mp4',
        'thumb_url' => 'assets/img/tania.jpg',
        'duration' => '14:22',
        'views' => 53700
    ],
    [
        'id' => 10,
        'title' => 'Exclusive Uncut 1-on-1 Video Call Leak',
        'category_slug' => 'exclusive',
        'video_url' => 'https://www.w3schools.com/html/mov_bbb.mp4',
        'thumb_url' => 'assets/img/video1.jpg',
        'duration' => '11:05',
        'views' => 71800
    ]
];

$default_settings = [
    'popunder_enabled' => '1',
    'popunder_url' => 'https://t.me/darkfantasyloverzone',
    'popunder_script' => '',
    'social_ad_enabled' => '1',
    'social_ad_script' => '',
    'telegram_group_url' => 'https://t.me/darkfantasyloverzone',
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

        // Check if categories contain Bengali text or are empty
        $cntCat = (int) $pdo->query("SELECT COUNT(*) FROM portal_categories")->fetchColumn();
        $hasBengaliCat = false;
        if ($cntCat > 0) {
            $catNames = $pdo->query("SELECT name FROM portal_categories")->fetchAll(PDO::FETCH_COLUMN);
            foreach ($catNames as $cn) {
                if (preg_match('/[\x{0980}-\x{09FF}]/u', $cn)) {
                    $hasBengaliCat = true;
                    break;
                }
            }
        }

        if ($cntCat === 0 || $hasBengaliCat) {
            $pdo->exec("DELETE FROM portal_categories");
            $stmtC = $pdo->prepare("INSERT INTO portal_categories (name, slug, icon, order_num) VALUES (?, ?, ?, ?)");
            foreach ($default_categories as $c) {
                if ($c['slug'] === 'all') continue;
                $stmtC->execute([$c['name'], $c['slug'], $c['icon'], $c['order_num']]);
            }
        }

        // Check if videos contain Bengali text or are empty
        $cntVid = (int) $pdo->query("SELECT COUNT(*) FROM portal_videos")->fetchColumn();
        $hasBengaliVid = false;
        if ($cntVid > 0) {
            $vidTitles = $pdo->query("SELECT title FROM portal_videos")->fetchAll(PDO::FETCH_COLUMN);
            foreach ($vidTitles as $vt) {
                if (preg_match('/[\x{0980}-\x{09FF}]/u', $vt)) {
                    $hasBengaliVid = true;
                    break;
                }
            }
        }

        if ($cntVid === 0 || $hasBengaliVid) {
            $pdo->exec("DELETE FROM portal_videos");
            $stmtV = $pdo->prepare("INSERT INTO portal_videos (title, category_slug, video_url, thumb_url, duration, views, is_active, order_num) VALUES (?, ?, ?, ?, ?, ?, 1, ?)");
            $ord = 1;
            foreach ($default_videos as $v) {
                $stmtV->execute([$v['title'], $v['category_slug'], $v['video_url'], $v['thumb_url'], $v['duration'], $v['views'], $ord++]);
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
            $db_cats = $pdo->query("SELECT id, name, slug, icon, order_num FROM portal_categories ORDER BY order_num ASC, id ASC")->fetchAll();
            if (!empty($db_cats)) {
                $cleaned_cats = [];
                foreach ($db_cats as $c) {
                    $catName = trim($c['name']);
                    if (isset($bn_cat_map[$catName])) {
                        $catName = $bn_cat_map[$catName];
                    } elseif (preg_match('/[\x{0980}-\x{09FF}]/u', $catName)) {
                        $slugMap = [
                            'all' => '🔥 All Leaks',
                            'exclusive' => '🔞 Exclusive Uncut',
                            'desi' => '💋 Hot Desi MMS',
                            'vip' => '💎 VIP Vault',
                            'live' => '🎥 Live Webcams',
                            'viral' => '⚡ Trending Viral'
                        ];
                        $catName = $slugMap[$c['slug']] ?? '🔥 All Leaks';
                    }
                    $c['name'] = $catName;
                    $cleaned_cats[] = $c;
                }

                $categories = array_merge(
                    [['id' => 0, 'name' => '🔥 All Leaks', 'slug' => 'all', 'icon' => 'fa-fire', 'order_num' => 0]],
                    $cleaned_cats
                );
            }

            // Fetch exactly latest 10 active videos
            $db_vids = $pdo->query("SELECT id, title, category_slug, video_url, thumb_url, duration, views FROM portal_videos WHERE is_active=1 ORDER BY id DESC LIMIT 10")->fetchAll();
            if (!empty($db_vids)) {
                $cleaned_vids = [];
                $vidx = 0;
                foreach ($db_vids as $v) {
                    $vtitle = trim($v['title']);
                    if (isset($bn_vid_map[$vtitle])) {
                        $vtitle = $bn_vid_map[$vtitle];
                    } elseif (preg_match('/[\x{0980}-\x{09FF}]/u', $vtitle)) {
                        $vtitle = $default_videos[$vidx % count($default_videos)]['title'];
                    }
                    $v['title'] = $vtitle;
                    $cleaned_vids[] = $v;
                    $vidx++;
                }
                $videos = $cleaned_vids;
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
