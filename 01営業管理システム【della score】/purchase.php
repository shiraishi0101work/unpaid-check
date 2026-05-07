<?php
$ua = $_SERVER['HTTP_USER_AGENT'] ?? '';
$isMobile = preg_match('/iPhone|Android|Mobile|iPad/', $ua);
header('Location: ' . ($isMobile ? '/purchase_management_SP.html' : '/purchase_management_PC.html'));
exit;
