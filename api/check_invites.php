<?php
header('Content-Type: application/json; charset=utf-8');
header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Methods: GET, POST, OPTIONS');
header('Access-Control-Allow-Headers: Content-Type');

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

try {
    $pdo = new PDO("mysql:host={$db_host};dbname={$db_name};charset=utf8mb4", $db_user, $db_pass, [
        PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
        PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC
    ]);
} catch (Exception $e) {
    echo json_encode([
        'success' => false,
        'unlocked' => false,
        'invites' => 0,
        'required' => 10,
        'error' => 'Database connection failed: ' . $e->getMessage(),
        'message' => 'ডাটাবেজের সাথে সংযোগ স্থাপন করা যায়নি।'
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
        'required' => 10,
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
    // Look up user info from users table
    $stmt = $pdo->prepare("SELECT user_id, username, first_name FROM users WHERE user_id = ? LIMIT 1");
    $stmt->execute([$user_id]);
    $user = $stmt->fetch();
    if ($user) {
        $username = $user['username'] ?? '';
        $first_name = $user['first_name'] ?? '';
    }
} else {
    // Look up user by username (case-insensitive)
    $stmt = $pdo->prepare("SELECT user_id, username, first_name FROM users WHERE LOWER(username) = LOWER(?) LIMIT 1");
    $stmt->execute([$clean_input]);
    $user = $stmt->fetch();
    if ($user) {
        $user_id = (int)$user['user_id'];
        $username = $user['username'] ?? '';
        $first_name = $user['first_name'] ?? '';
    }
}

if (!$user_id) {
    echo json_encode([
        'success' => false,
        'unlocked' => false,
        'invites' => 0,
        'required' => 10,
        'remaining' => 10,
        'message' => "❌ টেলিগ্রাম আইডি '{$raw_input}' ডাটাবেজে পাওয়া যায়নি। আপনি কি গ্রুপে জয়েন বা কোনো মেম্বার এড করেছেন? টেলিগ্রাম গ্রুপে /myinvites লিখে আপনার সঠিক আইডি দেখে নিন।"
    ]);
    exit;
}

// Query real member invites from user_invites table
$stmt = $pdo->prepare("SELECT COUNT(*) as cnt FROM user_invites WHERE inviter_id = ?");
$stmt->execute([$user_id]);
$row = $stmt->fetch();
$invite_count = (int)($row['cnt'] ?? 0);

$required = 10;
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
        ? "✅ অভিনন্দন! আপনি ডাটাবেজ অনুসারে সফলভাবে {$invite_count} জন মেম্বার এড করেছেন।"
        : "❌ আপনি মাত্র {$invite_count} জন মেম্বার এড করেছেন! সাইটের কন্টেন্ট আনলক করতে আরও {$remaining} জন বন্ধুকে টেলিগ্রাম গ্রুপে এড করতে হবে।"
]);
