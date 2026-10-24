<?php
/**
 * UTM tracking — one file, two jobs:
 *   - include from index.php → record visit UTMs
 *   - open this URL directly → live results table
 *
 * Storage: SQLite file (utm.sqlite) beside this script. No server DB required.
 *
 * Optional password for viewing results (tracking itself is never passworded):
 *   Create a sibling file named utm-password.php containing only:
 *     <?php return 'your-secret-here';
 *   While that file exists, utm-live.php asks for the password before
 *   showing the table. Delete the file to leave viewing wide open again.
 *   Do not commit utm-password.php.
 */

define('UTM_DB_FILE', __DIR__ . '/utm.sqlite');
define('UTM_PASSWORD_FILE', __DIR__ . '/utm-password.php');
define('UTM_MAX_CODES', 250);
define('UTM_NONE', '(none)');

function utm_db() {
    static $db = null;
    if ($db instanceof SQLite3) {
        return $db;
    }

    $db = new SQLite3(UTM_DB_FILE);
    $db->busyTimeout(3000);
    $db->exec('PRAGMA journal_mode=WAL');
    $db->exec(
        'CREATE TABLE IF NOT EXISTS utm (
            utm_string TEXT PRIMARY KEY NOT NULL,
            count INTEGER NOT NULL DEFAULT 0,
            first_use TEXT NOT NULL,
            last_use TEXT NOT NULL
        )'
    );
    return $db;
}

function utm_normalize_string(array $params) {
    // Fold query keys/values to lowercase so UTM_SOURCE=Email matches utm_source=email.
    $lower = array();
    foreach ($params as $name => $value) {
        $lower[strtolower((string) $name)] = $value;
    }

    // Bare ?utm=qr is an alias for utm_source (matches GA after the page-side rewrite).
    if (isset($lower['utm']) && !isset($lower['utm_source'])) {
        $lower['utm_source'] = $lower['utm'];
    }

    $keys = array('utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content');
    $parts = array();
    foreach ($keys as $key) {
        if (!isset($lower[$key])) {
            continue;
        }
        $value = strtolower(trim((string) $lower[$key]));
        if ($value === '') {
            continue;
        }
        // Keep values short so the table cannot be stuffed with huge strings.
        if (strlen($value) > 200) {
            $value = substr($value, 0, 200);
        }
        $parts[] = $key . '=' . $value;
    }
    return implode('&', $parts);
}

function utm_prune(SQLite3 $db) {
    // Cap applies to real UTM codes only; the (none) counter is never pruned.
    $stmt = $db->prepare(
        'SELECT COUNT(*) FROM utm WHERE utm_string != :none'
    );
    $stmt->bindValue(':none', UTM_NONE, SQLITE3_TEXT);
    $count = (int) $stmt->execute()->fetchArray(SQLITE3_NUM)[0];
    if ($count <= UTM_MAX_CODES) {
        return;
    }

    $extra = $count - UTM_MAX_CODES;
    $stmt = $db->prepare(
        'DELETE FROM utm WHERE utm_string IN (
            SELECT utm_string FROM utm
            WHERE utm_string != :none
            ORDER BY last_use ASC, utm_string ASC
            LIMIT :limit
        )'
    );
    $stmt->bindValue(':none', UTM_NONE, SQLITE3_TEXT);
    $stmt->bindValue(':limit', $extra, SQLITE3_INTEGER);
    $stmt->execute();
}

function utm_track() {
    $utm = utm_normalize_string($_GET);
    if ($utm === '') {
        $utm = UTM_NONE;
    }

    $now = gmdate('Y-m-d H:i:s');
    $db = utm_db();
    $db->exec('BEGIN IMMEDIATE');

    try {
        $stmt = $db->prepare('SELECT count FROM utm WHERE utm_string = :utm');
        $stmt->bindValue(':utm', $utm, SQLITE3_TEXT);
        $row = $stmt->execute()->fetchArray(SQLITE3_ASSOC);

        if ($row) {
            $upd = $db->prepare(
                'UPDATE utm SET count = count + 1, last_use = :now WHERE utm_string = :utm'
            );
            $upd->bindValue(':now', $now, SQLITE3_TEXT);
            $upd->bindValue(':utm', $utm, SQLITE3_TEXT);
            $upd->execute();
        } else {
            $ins = $db->prepare(
                'INSERT INTO utm (utm_string, count, first_use, last_use)
                 VALUES (:utm, 1, :now, :now)'
            );
            $ins->bindValue(':utm', $utm, SQLITE3_TEXT);
            $ins->bindValue(':now', $now, SQLITE3_TEXT);
            $ins->execute();
            if ($utm !== UTM_NONE) {
                utm_prune($db);
            }
        }

        $db->exec('COMMIT');
    } catch (Exception $e) {
        $db->exec('ROLLBACK');
    }
}

function utm_h($value) {
    return htmlspecialchars((string) $value, ENT_QUOTES, 'UTF-8');
}

function utm_expected_password() {
    if (!is_readable(UTM_PASSWORD_FILE)) {
        return null;
    }
    $password = include UTM_PASSWORD_FILE;
    if (!is_string($password)) {
        return null;
    }
    $password = trim($password);
    return $password === '' ? null : $password;
}

function utm_require_password() {
    $expected = utm_expected_password();
    if ($expected === null) {
        return true;
    }

    if (session_status() !== PHP_SESSION_ACTIVE) {
        session_start();
    }

    if (!empty($_SESSION['utm_live_ok'])) {
        return true;
    }

    $error = '';
    if ($_SERVER['REQUEST_METHOD'] === 'POST') {
        $got = isset($_POST['password']) ? (string) $_POST['password'] : '';
        if (hash_equals($expected, $got)) {
            $_SESSION['utm_live_ok'] = true;
            header('Location: ' . strtok($_SERVER['REQUEST_URI'], '?'));
            exit;
        }
        $error = 'Wrong password.';
    }

    header('Content-Type: text/html; charset=utf-8');
    header('Cache-Control: no-store');
    ?>
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="robots" content="noindex,nofollow">
  <title>UTM Live</title>
</head>
<body>
  <p><a href="./">Home</a></p>
  <h1>UTM Live</h1>
  <?php if ($error !== ''): ?>
    <p><?php echo utm_h($error); ?></p>
  <?php endif; ?>
  <form method="post" action="">
    <label>Password <input type="password" name="password" autofocus></label>
    <button type="submit">View</button>
  </form>
</body>
</html>
    <?php
    exit;
}

function utm_show_dashboard() {
    utm_require_password();

    $db = utm_db();
    $stmt = $db->prepare(
        'SELECT COUNT(*) FROM utm WHERE utm_string != :none'
    );
    $stmt->bindValue(':none', UTM_NONE, SQLITE3_TEXT);
    $total_codes = (int) $stmt->execute()->fetchArray(SQLITE3_NUM)[0];
    $total_hits = (int) $db->querySingle('SELECT COALESCE(SUM(count), 0) FROM utm');
    $stmt = $db->prepare(
        'SELECT count FROM utm WHERE utm_string = :none'
    );
    $stmt->bindValue(':none', UTM_NONE, SQLITE3_TEXT);
    $none_row = $stmt->execute()->fetchArray(SQLITE3_ASSOC);
    $none_hits = $none_row ? (int) $none_row['count'] : 0;
    $stmt = $db->prepare(
        'SELECT utm_string, count, first_use, last_use
         FROM utm
         ORDER BY CASE WHEN utm_string = :none THEN 0 ELSE 1 END,
                  last_use DESC, count DESC'
    );
    $stmt->bindValue(':none', UTM_NONE, SQLITE3_TEXT);
    $result = $stmt->execute();
    $row_count = (int) $db->querySingle('SELECT COUNT(*) FROM utm');

    header('Content-Type: text/html; charset=utf-8');
    header('Cache-Control: no-store');
    ?>
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="robots" content="noindex,nofollow">
  <title>UTM Live</title>
</head>
<body>
  <p><a href="./">Home</a></p>
  <h1>UTM Live</h1>
  <p>
    <?php echo (int) $total_codes; ?> / <?php echo (int) UTM_MAX_CODES; ?> codes,
    <?php echo (int) $total_hits; ?> hits
    (<?php echo (int) $none_hits; ?> with no UTM).
    Times UTC. Cap drops oldest last_use; (none) is never pruned.
  </p>

  <?php if ($row_count === 0): ?>
    <p>No visits yet.</p>
  <?php else: ?>
    <table border="1" cellpadding="4" cellspacing="0">
      <tr>
        <th>utm_string</th>
        <th>count</th>
        <th>first_use</th>
        <th>last_use</th>
      </tr>
      <?php while ($row = $result->fetchArray(SQLITE3_ASSOC)): ?>
        <tr>
          <td><code><?php echo utm_h($row['utm_string']); ?></code></td>
          <td><?php echo (int) $row['count']; ?></td>
          <td><?php echo utm_h($row['first_use']); ?></td>
          <td><?php echo utm_h($row['last_use']); ?></td>
        </tr>
      <?php endwhile; ?>
    </table>
  <?php endif; ?>
</body>
</html>
    <?php
}

// Included from another page → track. Opened directly → show live results.
if (realpath($_SERVER['SCRIPT_FILENAME']) === realpath(__FILE__)) {
    utm_show_dashboard();
} else {
    utm_track();
}
