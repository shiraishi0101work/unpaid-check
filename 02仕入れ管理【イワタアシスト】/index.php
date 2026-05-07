<?php
session_start();
if (!isset($_SESSION['user'])) {
    header('Location: /login.php');
    exit;
}
$ua = $_SERVER['HTTP_USER_AGENT'] ?? '';
$sp = preg_match('/iPhone|Android|Mobile/i', $ua);
header('Location: ' . ($sp ? '/purchase_management_SP.html' : '/purchase_management_PC.html'));
exit;
