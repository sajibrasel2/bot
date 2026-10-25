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

if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') {
    http_response_code(200);
    exit;
}

// 1. Database Configuration
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

// Local testing fallback
$is_local = (isset($_SERVER['HTTP_HOST']) && (strpos($_SERVER['HTTP_HOST'], 'localhost') !== false || strpos($_SERVER['HTTP_HOST'], '127.0.0.1') !== false));
if ($is_local && $db_user === 'techandc_bot') {
    $db_user = 'root';
    $db_pass = '';
}

$pdo = null;
try {
    $pdo = new PDO("mysql:host={$db_host};dbname={$db_name};charset=utf8mb4", $db_user, $db_pass, [
        PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
        PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC
    ]);
} catch (Exception $e) {
    if ($is_local) {
        try {
            $pdo = new PDO("mysql:host={$db_host};dbname=sweetnikita_bot;charset=utf8mb4", $db_user, $db_pass, [
                PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
                PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC
            ]);
        } catch (Exception $e2) {
            // Error connecting to DB
        }
    }
}

// Ensure schema and tables exist
function ensure_portal_tables($pdo) {
    if (!$pdo) return;
    try {
        $pdo->exec("
            CREATE TABLE IF NOT EXISTS portal_categories (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                slug VARCHAR(100) NOT NULL UNIQUE,
                icon VARCHAR(50) DEFAULT 'fa-fire',
                sort_order INT DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        ");

        $pdo->exec("
            CREATE TABLE IF NOT EXISTS portal_videos (
                id INT AUTO_INCREMENT PRIMARY KEY,
                title VARCHAR(255) NOT NULL,
                category_id INT DEFAULT NULL,
                video_url TEXT NOT NULL,
                thumbnail_url TEXT,
                is_active TINYINT DEFAULT 1,
                views INT DEFAULT 0,
                sort_order INT DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_cat (category_id),
                INDEX idx_active (is_active)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        ");

        $pdo->exec("
            CREATE TABLE IF NOT EXISTS portal_settings (
                setting_key VARCHAR(100) PRIMARY KEY,
                setting_val LONGTEXT
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        ");

        // Seed default categories if none
        $stmt = $pdo->query("SELECT COUNT(*) as c FROM portal_categories");
        if ($stmt->fetch()['c'] == 0) {
            $cats = [
                ['🔥 ভাইরাল (Viral)', 'viral', 'fa-fire', 1],
                ['🇧🇩 দেশি স্পেশাল (Desi)', 'desi', 'fa-heart', 2],
                ['🔞 এক্সক্লুসিভ (Exclusive)', 'exclusive', 'fa-star', 3],
                ['💎 ভিআইপি ভল্ট (VIP Vault)', 'vip', 'fa-gem', 4],
                ['🎥 লাইভ শো (Live Cam)', 'live', 'fa-video', 5]
            ];
            $ins = $pdo->prepare("INSERT IGNORE INTO portal_categories (name, slug, icon, sort_order) VALUES (?, ?, ?, ?)");
            foreach ($cats as $c) {
                $ins->execute($c);
            }
        }

        // Seed default 14 CDN teaser videos if none
        $stmtV = $pdo->query("SELECT COUNT(*) as c FROM portal_videos");
        if ($stmtV->fetch()['c'] == 0) {
            $catMap = [];
            $res = $pdo->query("SELECT id, slug FROM portal_categories")->fetchAll();
            foreach ($res as $r) {
                $catMap[$r['slug']] = $r['id'];
            }

            $cdn_samples = [
                ["হোটেল রুমের এক্সক্লুসিভ ভাইরাল পার্ট ১", $catMap['viral'] ?? 1, "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerBlazes.mp4", "assets/img/video1.jpg", 18450],
                ["ঢাকা কাপল প্রাইভেট ফোন চ্যাট রেকর্ড", $catMap['desi'] ?? 2, "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerEscapes.mp4", "assets/img/video2.jpg", 25300],
                ["ভিআইপি রুম আনকাট লিকস ক্লিপ", $catMap['vip'] ?? 4, "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerFun.mp4", "assets/img/video3.jpg", 31200],
                ["মাঝরাতের স্পেশাল লাইভ ওয়েবক্যাম শো", $catMap['live'] ?? 5, "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerJoyBlazes.mp4", "assets/img/mitu.jpg", 42100],
                ["হোস্টেল রুমের গোপন ভিডিও ফাঁস", $catMap['exclusive'] ?? 3, "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerMeltdowns.mp4", "assets/img/riya.jpg", 19800],
                ["চট্টগ্রাম কলেজ ফ্রেন্ডস নাইট পার্টি", $catMap['desi'] ?? 2, "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/Sintel.mp4", "assets/img/sadia.jpg", 28900],
                ["ভিআইপি প্রাইভেট ক্যাবিন ভিডিও লিক", $catMap['vip'] ?? 4, "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/SubaruOutbackSeeTheWorld.mp4", "assets/img/nusrat.jpg", 35600],
                ["টপ ট্রেন্ডিং ভাইরাল ক্লিপ এইচডি", $catMap['viral'] ?? 1, "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/TearsOfSteel.mp4", "assets/img/mim.jpg", 52100],
                ["লাইভ ক্যামেরা প্রাইভেট শো ২", $catMap['live'] ?? 5, "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/WeAreGoingOnBullrun.mp4", "assets/img/tania.jpg", 23700],
                ["১-অন-১ সিক্রেট চ্যাট পার্টনার শো", $catMap['exclusive'] ?? 3, "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/WhatCarCanYouGetForAGrand.mp4", "assets/img/video1.jpg", 41800],
                ["অফিস ট্যুরের গোপন রেকর্ড ভাইরাল", $catMap['desi'] ?? 2, "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ElephantsDream.mp4", "assets/img/video2.jpg", 16900],
                ["ভিআইপি মেম্বার্স অনলি আনকাট লিক", $catMap['vip'] ?? 4, "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4", "assets/img/video3.jpg", 64500],
                ["মধ্যরাতের হট চ্যাট ভাইরাল ক্লিপ", $catMap['viral'] ?? 1, "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerBlazes.mp4", "assets/img/mitu.jpg", 37800],
                ["আনলকড ফুল এইচডি এক্সক্লুসিভ শো", $catMap['exclusive'] ?? 3, "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerEscapes.mp4", "assets/img/riya.jpg", 49200]
            ];

            $insV = $pdo->prepare("INSERT INTO portal_videos (title, category_id, video_url, thumbnail_url, views, sort_order) VALUES (?, ?, ?, ?, ?, ?)");
            $ord = 1;
            foreach ($cdn_samples as $v) {
                $insV->execute([$v[0], $v[1], $v[2], $v[3], $v[4], $ord++]);
            }
        }

        // Seed default settings if empty
        $def_settings = [
            'popunder_enabled' => '1',
            'popunder_url' => 'https://t.me/darkfantasyloverzone',
            'popunder_script' => '',
            'social_bar_enabled' => '1',
            'social_bar_script' => '',
            'telegram_target_url' => 'https://t.me/darkfantasyloverzone',
            'blur_level' => '10',
            'overlay_title' => '🔞 এক্সক্লুসিভ ফুল এইচডি ভিডিও পোর্টাল',
            'overlay_desc' => 'ভিডিও স্পষ্ট দেখতে ও লাইভ চ্যাট রুমে প্রবেশ করতে নিচের বাটনে চাপ দিন',
            'overlay_button_text' => '⚡ আনলক করে ফুল ভিডিও দেখুন (Unlock Full HD)'
        ];
        $insS = $pdo->prepare("INSERT IGNORE INTO portal_settings (setting_key, setting_val) VALUES (?, ?)");
        foreach ($def_settings as $k => $v) {
            $insS->execute([$k, $v]);
        }
    } catch (Exception $e) {
        // Table init error
    }
}

if ($pdo) {
    ensure_portal_tables($pdo);
}

$action = $_GET['action'] ?? $_POST['action'] ?? 'get_data';

if ($action === 'get_data') {
    $categories = [];
    $videos = [];
    $settings = [
        'popunder_enabled' => '1',
        'popunder_url' => 'https://t.me/darkfantasyloverzone',
        'popunder_script' => '',
        'social_bar_enabled' => '1',
        'social_bar_script' => '',
        'telegram_target_url' => 'https://t.me/darkfantasyloverzone',
        'blur_level' => '10',
        'overlay_title' => '🔞 এক্সক্লুসিভ ফুল এইচডি ভিডিও পোর্টাল',
        'overlay_desc' => 'ভিডিও স্পষ্ট দেখতে ও লাইভ চ্যাট রুমে প্রবেশ করতে নিচের বাটনে চাপ দিন',
        'overlay_button_text' => '⚡ আনলক করে ফুল ভিডিও দেখুন (Unlock Full HD)'
    ];

    if ($pdo) {
        try {
            // Load Categories
            $stmt = $pdo->query("SELECT id, name, slug, icon, sort_order FROM portal_categories ORDER BY sort_order ASC, id ASC");
            $categories = $stmt->fetchAll();

            // Load Videos
            $category_filter = isset($_GET['category']) ? trim($_GET['category']) : '';
            if ($category_filter && $category_filter !== 'all') {
                $stmtV = $pdo->prepare("
                    SELECT v.id, v.title, v.category_id, v.video_url, v.thumbnail_url, v.views, c.name as category_name, c.slug as category_slug
                    FROM portal_videos v
                    LEFT JOIN portal_categories c ON c.id = v.category_id
                    WHERE v.is_active = 1 AND c.slug = ?
                    ORDER BY v.sort_order ASC, v.id DESC
                    LIMIT 20
                ");
                $stmtV->execute([$category_filter]);
                $videos = $stmtV->fetchAll();
            } else {
                $stmtV = $pdo->query("
                    SELECT v.id, v.title, v.category_id, v.video_url, v.thumbnail_url, v.views, c.name as category_name, c.slug as category_slug
                    FROM portal_videos v
                    LEFT JOIN portal_categories c ON c.id = v.category_id
                    WHERE v.is_active = 1
                    ORDER BY v.sort_order ASC, v.id DESC
                    LIMIT 20
                ");
                $videos = $stmtV->fetchAll();
            }

            // Load Settings
            $stmtS = $pdo->query("SELECT setting_key, setting_val FROM portal_settings");
            $rows = $stmtS->fetchAll();
            foreach ($rows as $r) {
                $settings[$r['setting_key']] = $r['setting_val'];
            }
        } catch (Exception $e) {
            // Failover
        }
    }

    echo json_encode([
        'status' => 'success',
        'categories' => $categories,
        'videos' => $videos,
        'settings' => $settings,
        'total_videos' => count($videos)
    ], JSON_UNESCAPED_UNICODE | JSON_PRETTY_PRINT);
    exit;
}

if ($action === 'increment_view') {
    $video_id = intval($_GET['video_id'] ?? $_POST['video_id'] ?? 0);
    if ($pdo && $video_id > 0) {
        $stmt = $pdo->prepare("UPDATE portal_videos SET views = views + 1 WHERE id = ?");
        $stmt->execute([$video_id]);
    }
    echo json_encode(['status' => 'ok']);
    exit;
}

echo json_encode(['status' => 'error', 'message' => 'Invalid action']);
