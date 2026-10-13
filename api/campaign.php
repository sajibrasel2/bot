<?php
/**
 * bKash & Nagad 500 TK Campaign Backend API
 * Handles visitor referral tracking, user registration, ad tasks, and prize claims.
 */

header('Content-Type: application/json; charset=utf-8');
header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Methods: GET, POST, OPTIONS');
header('Access-Control-Allow-Headers: Content-Type, Cache-Control');

if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') {
    http_response_code(200);
    exit;
}

// Config
$DATA_DIR = __DIR__ . '/../data';
if (!is_dir($DATA_DIR)) {
    @mkdir($DATA_DIR, 0777, true);
}

$USERS_FILE = $DATA_DIR . '/campaign_users.json';
$VISITS_FILE = $DATA_DIR . '/campaign_visits.json';
$CLAIMS_FILE = $DATA_DIR . '/campaign_claims.json';
$ADMIN_PIN = 'admin500'; // Change this admin PIN if needed

// Helper functions for JSON file storage
function read_json_file($file, $default = []) {
    if (!file_exists($file)) return $default;
    $content = @file_get_contents($file);
    if (!$content) return $default;
    $data = json_decode($content, true);
    return is_array($data) ? $data : $default;
}

function write_json_file($file, $data) {
    @file_put_contents($file, json_encode($data, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE), LOCK_EX);
}

function get_client_ip() {
    if (!empty($_SERVER['HTTP_CF_CONNECTING_IP'])) return $_SERVER['HTTP_CF_CONNECTING_IP'];
    if (!empty($_SERVER['HTTP_X_FORWARDED_FOR'])) {
        $ips = explode(',', $_SERVER['HTTP_X_FORWARDED_FOR']);
        return trim($ips[0]);
    }
    return $_SERVER['REMOTE_ADDR'] ?? '127.0.0.1';
}

$action = $_REQUEST['action'] ?? 'init';
$client_ip = get_client_ip();

// -------------------------------------------------------------
// 1. ACTION: INIT / VISIT TRACKING
// -------------------------------------------------------------
if ($action === 'init') {
    $ref = trim($_REQUEST['ref'] ?? '');
    $users = read_json_file($USERS_FILE);
    $visits = read_json_file($VISITS_FILE);
    $claims = read_json_file($CLAIMS_FILE);

    $ref_count = 0;
    $user_info = null;
    $visit_registered = false;

    if ($ref !== '' && isset($users[$ref])) {
        $ip_hash = md5($client_ip . '_' . date('Y-m-d'));
        if (!isset($visits[$ref])) {
            $visits[$ref] = [];
        }

        // Prevent self-referral (if IP belongs to creator) or repeated IP counting today
        $user_creator_ip = $users[$ref]['ip'] ?? '';
        if ($client_ip !== $user_creator_ip && !in_array($ip_hash, $visits[$ref])) {
            $visits[$ref][] = $ip_hash;
            $users[$ref]['referral_count'] = count($visits[$ref]);
            $users[$ref]['last_visit'] = date('Y-m-d H:i:s');
            write_json_file($VISITS_FILE, $visits);
            write_json_file($USERS_FILE, $users);
            $visit_registered = true;
        }

        $ref_count = $users[$ref]['referral_count'] ?? count($visits[$ref]);
        $user_info = [
            'ref' => $ref,
            'phone' => substr($users[$ref]['phone'], 0, 3) . '****' . substr($users[$ref]['phone'], -3),
            'method' => $users[$ref]['method'] ?? 'bKash',
            'referrals' => $ref_count,
            'tasks_done' => $users[$ref]['tasks_done'] ?? [],
            'has_claimed' => isset($claims[$ref])
        ];
    }

    $total_claimed = count($claims);
    $slots_remaining = max(0, 20 - $total_claimed);

    echo json_encode([
        'status' => 'success',
        'ref' => $ref,
        'visit_registered' => $visit_registered,
        'user' => $user_info,
        'stats' => [
            'total_winners_target' => 20,
            'reward_amount' => 500,
            'required_referrals' => 20,
            'claimed_count' => min(13 + $total_claimed, 20), // baseline 13 winners already for social proof
            'slots_remaining' => max(1, 20 - (13 + $total_claimed)),
            'total_participants' => count($users) + 420
        ]
    ]);
    exit;
}

// -------------------------------------------------------------
// 2. ACTION: REGISTER (GENERATE REF LINK)
// -------------------------------------------------------------
if ($action === 'register') {
    $phone = trim($_REQUEST['phone'] ?? '');
    $method = trim($_REQUEST['method'] ?? 'bKash');

    // Clean phone number: remove non-digits
    $phone = preg_replace('/[^0-9]/', '', $phone);
    if (strlen($phone) === 11 && strpos($phone, '01') === 0) {
        // valid
    } elseif (strlen($phone) === 13 && strpos($phone, '8801') === 0) {
        $phone = substr($phone, 2);
    } else {
        echo json_encode([
            'status' => 'error',
            'message' => 'দয়া করে একটি সঠিক ১১ ডিজিটের মোবাইল নম্বর দিন (যেমন: 01712345678)'
        ]);
        exit;
    }

    $users = read_json_file($USERS_FILE);
    $visits = read_json_file($VISITS_FILE);

    // Unique ref code based on phone or clean identifier
    $ref = $phone;

    if (!isset($users[$ref])) {
        $users[$ref] = [
            'ref' => $ref,
            'phone' => $phone,
            'method' => $method,
            'referral_count' => 0,
            'tasks_done' => [],
            'created_at' => date('Y-m-d H:i:s'),
            'ip' => $client_ip
        ];
        write_json_file($USERS_FILE, $users);
    }

    $ref_count = $users[$ref]['referral_count'] ?? (isset($visits[$ref]) ? count($visits[$ref]) : 0);

    echo json_encode([
        'status' => 'success',
        'ref' => $ref,
        'phone' => $phone,
        'method' => $method,
        'referral_count' => $ref_count,
        'tasks_done' => $users[$ref]['tasks_done'] ?? [],
        'message' => 'আপনার রেফারেল লিংক তৈরি হয়েছে!'
    ]);
    exit;
}

// -------------------------------------------------------------
// 3. ACTION: RECORD AD TASK
// -------------------------------------------------------------
if ($action === 'record_task') {
    $ref = trim($_REQUEST['ref'] ?? '');
    $task_id = trim($_REQUEST['task_id'] ?? 'ad1');

    $users = read_json_file($USERS_FILE);
    if (isset($users[$ref])) {
        if (!isset($users[$ref]['tasks_done'])) {
            $users[$ref]['tasks_done'] = [];
        }
        if (!in_array($task_id, $users[$ref]['tasks_done'])) {
            $users[$ref]['tasks_done'][] = $task_id;
            write_json_file($USERS_FILE, $users);
        }
    }

    echo json_encode([
        'status' => 'success',
        'task_id' => $task_id,
        'tasks_done' => $users[$ref]['tasks_done'] ?? [$task_id]
    ]);
    exit;
}

// -------------------------------------------------------------
// 4. ACTION: CHECK STATUS
// -------------------------------------------------------------
if ($action === 'check_status') {
    $ref = trim($_REQUEST['ref'] ?? '');
    $users = read_json_file($USERS_FILE);
    $visits = read_json_file($VISITS_FILE);
    $claims = read_json_file($CLAIMS_FILE);

    if (!isset($users[$ref])) {
        echo json_encode([
            'status' => 'error',
            'message' => 'কোনো ইউজার পাওয়া যায়নি'
        ]);
        exit;
    }

    $count = $users[$ref]['referral_count'] ?? (isset($visits[$ref]) ? count($visits[$ref]) : 0);
    $tasks_done = $users[$ref]['tasks_done'] ?? [];
    $has_claimed = isset($claims[$ref]);

    echo json_encode([
        'status' => 'success',
        'ref' => $ref,
        'referrals' => $count,
        'target' => 20,
        'tasks_done' => $tasks_done,
        'has_claimed' => $has_claimed,
        'can_claim' => ($count >= 20 && !empty($tasks_done) && !$has_claimed)
    ]);
    exit;
}

// -------------------------------------------------------------
// 5. ACTION: SUBMIT CLAIM (500 TK RECHARGE / CASH REQUEST)
// -------------------------------------------------------------
if ($action === 'submit_claim') {
    $ref = trim($_REQUEST['ref'] ?? '');
    $claim_phone = trim($_REQUEST['claim_phone'] ?? '');
    $payment_method = trim($_REQUEST['payment_method'] ?? 'bKash');
    $sim_type = trim($_REQUEST['sim_type'] ?? 'Prepaid');

    $claim_phone = preg_replace('/[^0-9]/', '', $claim_phone);
    if (strlen($claim_phone) !== 11 || strpos($claim_phone, '01') !== 0) {
        echo json_encode([
            'status' => 'error',
            'message' => 'সঠিক ১১ ডিজিটের মোবাইল নম্বর দিন'
        ]);
        exit;
    }

    $users = read_json_file($USERS_FILE);
    $visits = read_json_file($VISITS_FILE);
    $claims = read_json_file($CLAIMS_FILE);

    // Verify referrals
    $ref_count = $users[$ref]['referral_count'] ?? (isset($visits[$ref]) ? count($visits[$ref]) : 0);
    if ($ref_count < 20) {
        echo json_encode([
            'status' => 'error',
            'message' => "আপনার এখনও ২০ জন রেফারেল সম্পন্ন হয়নি! বর্তমান রেফারেল: {$ref_count}/২০"
        ]);
        exit;
    }

    if (isset($claims[$ref])) {
        echo json_encode([
            'status' => 'info',
            'message' => 'আপনি ইতিমধ্যে রিচার্জ রিকুয়েস্ট সাবমিট করেছেন!',
            'claim' => $claims[$ref]
        ]);
        exit;
    }

    $claim_id = 'BK500-' . strtoupper(substr(md5(uniqid(rand(), true)), 0, 6));
    $claim_data = [
        'claim_id' => $claim_id,
        'ref' => $ref,
        'registered_phone' => $users[$ref]['phone'] ?? $ref,
        'claim_phone' => $claim_phone,
        'payment_method' => $payment_method,
        'sim_type' => $sim_type,
        'amount' => 500,
        'referrals_verified' => $ref_count,
        'submitted_at' => date('Y-m-d H:i:s'),
        'ip' => $client_ip,
        'status' => 'pending' // pending, paid, rejected
    ];

    $claims[$ref] = $claim_data;
    write_json_file($CLAIMS_FILE, $claims);

    echo json_encode([
        'status' => 'success',
        'message' => '🎉 আপনার ৫০০ টাকা রিচার্জের আবেদন সফলভাবে গৃহীত হয়েছে!',
        'claim' => $claim_data
    ]);
    exit;
}

// -------------------------------------------------------------
// 6. ACTION: ADMIN GET DATA
// -------------------------------------------------------------
if ($action === 'admin_get_data') {
    $pin = trim($_REQUEST['pin'] ?? '');
    if ($pin !== $ADMIN_PIN) {
        echo json_encode(['status' => 'error', 'message' => 'ভুল এডমিন পিন!']);
        exit;
    }

    $users = read_json_file($USERS_FILE);
    $claims = read_json_file($CLAIMS_FILE);
    $visits = read_json_file($VISITS_FILE);

    echo json_encode([
        'status' => 'success',
        'total_users' => count($users),
        'total_claims' => count($claims),
        'users' => array_values($users),
        'claims' => array_values($claims),
        'raw_visits_count' => count($visits)
    ]);
    exit;
}

// -------------------------------------------------------------
// 7. ACTION: ADMIN UPDATE STATUS
// -------------------------------------------------------------
if ($action === 'admin_update_status') {
    $pin = trim($_REQUEST['pin'] ?? '');
    $ref = trim($_REQUEST['ref'] ?? '');
    $new_status = trim($_REQUEST['new_status'] ?? 'paid');

    if ($pin !== $ADMIN_PIN) {
        echo json_encode(['status' => 'error', 'message' => 'ভুল এডমিন পিন!']);
        exit;
    }

    $claims = read_json_file($CLAIMS_FILE);
    if (isset($claims[$ref])) {
        $claims[$ref]['status'] = $new_status;
        $claims[$ref]['updated_at'] = date('Y-m-d H:i:s');
        write_json_file($CLAIMS_FILE, $claims);

        echo json_encode([
            'status' => 'success',
            'message' => "স্ট্যাটাস পরিবর্তন করে '{$new_status}' করা হয়েছে!"
        ]);
        exit;
    }

    echo json_encode(['status' => 'error', 'message' => 'ক্লেইম রেকর্ড পাওয়া যায়নি']);
    exit;
}

echo json_encode(['status' => 'error', 'message' => 'Invalid action']);
