<?php
/**
 * Count a Register click, then send the browser to the real destination.
 * Only the named targets are allowed, so this cannot redirect anywhere else.
 */
define('UTM_LIBRARY', true);
require __DIR__ . '/utm-live.php';

$name = isset($_GET['to']) ? strtolower(trim((string) $_GET['to'])) : '';
$targets = utm_click_targets();

header('Cache-Control: no-store');

if (!isset($targets[$name])) {
    header('Location: index.php', true, 302);
    exit;
}

$method = isset($_SERVER['REQUEST_METHOD']) ? strtoupper($_SERVER['REQUEST_METHOD']) : 'GET';
if ($method === 'GET') {
    utm_track_click($name);
} elseif ($method !== 'HEAD') {
    header('Allow: GET, HEAD');
    http_response_code(405);
    header('Content-Type: text/plain; charset=utf-8');
    echo "Method Not Allowed\n";
    exit;
}

header('Location: ' . $targets[$name]['url'], true, 302);
exit;
