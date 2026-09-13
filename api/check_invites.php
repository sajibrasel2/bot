<?php
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

// Read database configuration
$db_host = 'localhost';
$db_name = 'techandc_tlbot';
$db_user = 'techandc_bot';
$db_pass = '12345Sajibs6@';

// Parse .env if exists for dynamic config
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

// Fallback to local xampp root if testing on localhost
$is_local = (isset($_SERVER['HTTP_HOST']) && (strpos($_SERVER['HTTP_HOST'], 'localhost') !== false || strpos($_SERVER['HTTP_HOST'], '127.0.0.1') !== false));
if ($is_local && $db_user === 'techandc_bot') {
    $db_user = 'root';
    $db_pass = '';
}

$pdo = null;
$db_type = 'mysql';

// 1. Try Primary MySQL Connection
try {
    $pdo = new PDO("mysql:host={$db_host};dbname={$db_name};charset=utf8mb4", $db_user, $db_pass, [
        PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
        PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC
    ]);
} catch (Exception $e1) {
    // 2. Try Fallback MySQL db name 'sweetnikita_bot' on local
    if ($is_local) {
        try {
            $pdo = new PDO("mysql:host={$db_host};dbname=sweetnikita_bot;charset=utf8mb4", $db_user, $db_pass, [
                PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
                PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC
            ]);
        } catch (Exception $e2) {}
    }
    
    // 3. Try Fallback SQLite database
    if (!$pdo) {
        $sqlite_file = __DIR__ . '/../data/bot.db';
        if (file_exists($sqlite_file)) {
            try {
                $pdo = new PDO("sqlite:" . $sqlite_file, null, null, [
                    PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
                    PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC
                ]);
                $db_type = 'sqlite';
            } catch (Exception $e3) {}
        }
    }
}

if (!$pdo) {
    echo json_encode([
        'success' => false,
        'unlocked' => false,
        'invites' => 0,
        'required' => 10,
        'error' => 'Database connection failed',
        'message' => 'সার্ভারের সাথে সংযোগ স্থাপন করা যায়নি। অনুগ্রহ করে কিছুক্ষণ পর চেষ্টা করুন।'
    ]);
    exit;
}

// Fetch Global Settings
$site_gate_enabled = 1;
$required = 10;
$custom_link = 'https://t.me/alltimefantasyzone';

try {
    $stmt = $pdo->query("SELECT setting_key, setting_val FROM global_settings");
    if ($stmt) {
        $rows = $stmt->fetchAll();
        foreach ($rows as $r) {
            if ($r['setting_key'] === 'site_gate_enabled') $site_gate_enabled = (int)$r['setting_val'];
            if ($r['setting_key'] === 'site_gate_required_invites') $required = max(1, (int)$r['setting_val']);
            if ($r['setting_key'] === 'site_gate_custom_link') $custom_link = trim($r['setting_val']);
        }
    }
} catch (Exception $e) {}

// Check action parameter for gate_status
$action = trim($_GET['action'] ?? $_POST['action'] ?? '');
if ($action === 'gate_status') {
    echo json_encode([
        'success' => true,
        'gate_enabled' => ($site_gate_enabled === 1),
        'site_gate_enabled' => $site_gate_enabled,
        'required' => $required,
        'custom_link' => $custom_link
    ]);
    exit;
}

// If gate is disabled globally by Admin, bypass/unlock immediately
if ($site_gate_enabled === 0) {
    echo json_encode([
        'success' => true,
        'unlocked' => true,
        'gate_enabled' => false,
        'site_gate_enabled' => 0,
        'invites' => 0,
        'required' => 0,
        'remaining' => 0,
        'message' => 'টেলিগ্রাম ভেরিফিকেশন গেট বর্তমানে বন্ধ রয়েছে, সরাসরি আনলক করা হয়েছে।'
    ]);
    exit;
}

// Read input parameter: user_id or username
$raw_input = trim($_GET['user_id'] ?? $_GET['username'] ?? $_POST['user_id'] ?? $_POST['username'] ?? '');

if (empty($raw_input)) {
    echo json_encode([
        'success' => false,
        'unlocked' => false,
        'invites' => 0,
        'required' => $required,
        'message' => 'অনুগ্রহ করে আপনার টেলিগ্রাম ইউজার আইডি বা @ইউজারনেম লিখুন।'
    ]);
    exit;
}

// Clean input
$clean_input = ltrim($raw_input, '@');
$user_id = null;
$username = '';
$first_name = '';

if (is_numeric($clean_input)) {
    $user_id = (int)$clean_input;
    // Look up user info from users table if available
    try {
        $stmt = $pdo->prepare("SELECT user_id, username, first_name FROM users WHERE user_id = ? LIMIT 1");
        $stmt->execute([$user_id]);
        $user = $stmt->fetch();
        if ($user) {
            $username = $user['username'] ?? '';
            $first_name = $user['first_name'] ?? '';
        }
    } catch (Exception $e) {}
} else {
    // Look up user by username (case-insensitive)
    try {
        $stmt = $pdo->prepare("SELECT user_id, username, first_name FROM users WHERE LOWER(username) = LOWER(?) LIMIT 1");
        $stmt->execute([$clean_input]);
        $user = $stmt->fetch();
        if ($user) {
            $user_id = (int)$user['user_id'];
            $username = $user['username'] ?? '';
            $first_name = $user['first_name'] ?? '';
        }
    } catch (Exception $e) {}
}

if (!$user_id) {
    echo json_encode([
        'success' => false,
        'unlocked' => false,
        'invites' => 0,
        'required' => $required,
        'remaining' => $required,
        'message' => "❌ টেলিগ্রাম ইউজার '{$raw_input}' পাওয়া যায়নি। আপনি কি টেলিগ্রাম গ্রুপে জয়েন বা মেম্বার এড করেছেন? সঠিক আইডি জানতে টেলিগ্রাম গ্রুপে /myinvites লিখুন।"
    ]);
    exit;
}

// Query real member invites from user_invites table
$invite_count = 0;
try {
    $stmt = $pdo->prepare("SELECT COUNT(*) as cnt FROM user_invites WHERE inviter_id = ?");
    $stmt->execute([$user_id]);
    $row = $stmt->fetch();
    $invite_count = (int)($row['cnt'] ?? 0);
} catch (Exception $e) {
    $invite_count = 0;
}

$unlocked = ($invite_count >= $required);
$remaining = max(0, $required - $invite_count);

echo json_encode([
    'success' => true,
    'user_id' => $user_id,
    'username' => $username,
    'first_name' => $first_name,
    'invites' => $invite_count,
    'required' => $required,
    'remaining' => $remaining,
    'unlocked' => $unlocked,
    'message' => $unlocked 
        ? "✅ অভিনন্দন! আপনি সফলভাবে {$invite_count} জন মেম্বার এড করেছেন।"
        : "❌ আপনি মাত্র {$invite_count} জন মেম্বার এড করেছেন! সাইটে প্রবেশ করতে আরও {$remaining} জন বন্ধুকে টেলিগ্রাম গ্রুপে এড করুন।"
]);
