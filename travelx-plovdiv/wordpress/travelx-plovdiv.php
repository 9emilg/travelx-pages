<?php
/**
 * Plugin Name:       TravelX Plovdiv
 * Description:       Publishes the TravelX Conference 2027 page (Plovdiv, 13–15 January 2027) as a static page at /plovdiv/ (Bulgarian at /plovdiv/bg/) and prerenders it when a visitor hovers a link to it.
 * Version:           1.0.0
 * Requires at least: 6.8
 * Requires PHP:      7.4
 * Author:            URBO Studio
 *
 * How it works
 * ------------
 * The page lives in site/ inside this plugin. On activation, and after every
 * update, it is copied to <site root>/plovdiv/, where LiteSpeed serves it as a
 * plain file — WordPress, the theme and the other plugins never run for it.
 * If the site root isn't writable, WordPress serves the same file from the
 * plugin folder instead (slower, but it works).
 *
 * Deactivating the plugin removes /plovdiv/. It only ever deletes a folder that
 * carries its own marker file, never one it didn't create.
 *
 * To update the page: edit it, bump TXPV_VERSION, run `python tools/build.py`,
 * then upload the zip under Plugins → Add New → Upload Plugin and choose
 * "Replace current with uploaded".
 */

defined( 'ABSPATH' ) || exit;

const TXPV_VERSION = '1.0.6';
const TXPV_SLUG    = 'plovdiv';
const TXPV_MARKER  = '.travelx-plovdiv';

function txpv_source() {
	return __DIR__ . '/site';
}

function txpv_target() {
	return untrailingslashit( ABSPATH ) . '/' . TXPV_SLUG;
}

/** True if $dir holds a file at any depth. Empty sub-folders don't count. */
function txpv_has_files( $dir ) {
	$files = new RecursiveIteratorIterator( new RecursiveDirectoryIterator( $dir, FilesystemIterator::SKIP_DOTS ) );
	foreach ( $files as $file ) {
		return true;
	}
	return false;
}

/**
 * Ours to replace: nothing there yet, a folder this plugin published, or an
 * empty folder someone else left behind (a hosting-panel subdomain root, say)
 * — there is nothing in it to lose.
 */
function txpv_owns_target() {
	$target = txpv_target();
	return ! file_exists( $target )
		|| is_file( $target . '/' . TXPV_MARKER )
		|| ( is_dir( $target ) && ! txpv_has_files( $target ) );
}

function txpv_rmdir( $dir ) {
	if ( ! is_dir( $dir ) ) {
		return;
	}
	$items = new RecursiveIteratorIterator(
		new RecursiveDirectoryIterator( $dir, FilesystemIterator::SKIP_DOTS ),
		RecursiveIteratorIterator::CHILD_FIRST
	);
	foreach ( $items as $item ) {
		$item->isDir() ? rmdir( $item->getPathname() ) : unlink( $item->getPathname() );
	}
	rmdir( $dir );
}

/**
 * Copy site/ to <root>/plovdiv/. The copy is built beside the live folder and
 * swapped in, so nobody ever loads a half-copied page.
 */
function txpv_publish() {
	if ( ! txpv_owns_target() ) {
		return false;
	}
	$target = txpv_target();
	$tmp    = $target . '.tmp-' . uniqid();
	// Modes are set explicitly: wp_mkdir_p() copies the parent folder's mode,
	// and where the site root is 0750 (the web server gets in through the
	// group) the new folders end up unreadable to the web server.
	if ( ! wp_mkdir_p( $tmp ) || ! chmod( $tmp, 0755 ) ) {
		return false;
	}
	$items = new RecursiveIteratorIterator(
		new RecursiveDirectoryIterator( txpv_source(), FilesystemIterator::SKIP_DOTS ),
		RecursiveIteratorIterator::SELF_FIRST
	);
	foreach ( $items as $item ) {
		$to = $tmp . '/' . $items->getSubPathname();
		$ok = $item->isDir()
			? wp_mkdir_p( $to ) && chmod( $to, 0755 )
			: copy( $item->getPathname(), $to ) && chmod( $to, 0644 );
		if ( ! $ok ) {
			txpv_rmdir( $tmp );
			return false;
		}
	}
	file_put_contents( $tmp . '/' . TXPV_MARKER, TXPV_VERSION );
	if ( is_dir( $target ) && ! is_file( $target . '/' . TXPV_MARKER ) ) {
		update_option( 'txpv_adopted', 1, false ); // an empty folder was already here — put it back on deactivation
	}
	txpv_rmdir( $target );
	return rename( $tmp, $target );
}

function txpv_sync() {
	update_option( 'txpv_state', txpv_publish() ? TXPV_VERSION : 'failed-' . TXPV_VERSION, false );
}
register_activation_hook( __FILE__, 'txpv_sync' );

// "Replace current with uploaded" doesn't re-run activation, so republish on
// the first admin page load after the version changes.
add_action( 'admin_init', function () {
	$state = get_option( 'txpv_state' );
	if ( TXPV_VERSION !== $state && 'failed-' . TXPV_VERSION !== $state ) {
		txpv_sync();
	}
} );

register_deactivation_hook( __FILE__, function () {
	if ( is_file( txpv_target() . '/' . TXPV_MARKER ) ) {
		txpv_rmdir( txpv_target() );
		if ( get_option( 'txpv_adopted' ) ) {
			wp_mkdir_p( txpv_target() ); // leave it as we found it
		}
	}
	delete_option( 'txpv_state' );
	delete_option( 'txpv_adopted' );
} );

add_action( 'admin_notices', function () {
	if ( 'failed-' . TXPV_VERSION !== get_option( 'txpv_state' ) || ! current_user_can( 'activate_plugins' ) ) {
		return;
	}
	if ( txpv_owns_target() ) {
		$why = 'WordPress could not write the <code>/plovdiv/</code> folder to the site root, so the page is being served through WordPress from the plugin folder instead. It works, just a little slower.';
	} else {
		$found = array_slice( array_values( array_diff( scandir( txpv_target() ), array( '.', '..' ) ) ), 0, 8 );
		$why   = 'A <code>/plovdiv/</code> folder this plugin did not create already exists in the site root and holds files, so it was left alone — and the server shows it instead of this page. It contains: <code>' . esc_html( implode( ', ', $found ) ) . '</code>. Move those files elsewhere, then deactivate and reactivate the plugin.';
	}
	echo '<div class="notice notice-warning"><p><strong>TravelX Plovdiv:</strong> ' . $why . '</p></div>'; // phpcs:ignore WordPress.Security.EscapeOutput -- fixed strings
} );

// Fallback: only reached when the static folder isn't there — when it is,
// LiteSpeed answers /plovdiv/ and /plovdiv/bg/ before WordPress ever loads.
// The Bulgarian page sits one folder down, so its asset URLs read ../assets/.
add_action( 'template_redirect', function () {
	$path  = trim( (string) wp_parse_url( $_SERVER['REQUEST_URI'] ?? '', PHP_URL_PATH ), '/' );
	$pages = array(
		TXPV_SLUG         => '/index.html',
		TXPV_SLUG . '/bg' => '/bg/index.html',
	);
	if ( ! isset( $pages[ $path ] ) || ! is_file( txpv_source() . $pages[ $path ] ) ) {
		return;
	}
	// the language switch links are relative (bg/, ../), so they need the slash
	$uri = (string) wp_parse_url( $_SERVER['REQUEST_URI'] ?? '', PHP_URL_PATH );
	if ( '/' !== substr( $uri, -1 ) ) {
		$query = (string) wp_parse_url( $_SERVER['REQUEST_URI'] ?? '', PHP_URL_QUERY );
		wp_safe_redirect( home_url( '/' . $path . '/' ) . ( '' !== $query ? '?' . $query : '' ), 301 );
		exit;
	}
	$html = file_get_contents( txpv_source() . $pages[ $path ] );
	$html = preg_replace( '#(?<=["\'\s(,])(?:\.\./)?assets/#', plugins_url( 'site/assets/', __FILE__ ), $html );
	status_header( 200 );
	header( 'Content-Type: text/html; charset=utf-8' );
	echo $html; // phpcs:ignore WordPress.Security.EscapeOutput -- our own static page
	exit;
}, 0 );

// Prerender /plovdiv/ while a visitor hovers a link to it, so the click lands
// instantly. WordPress core already prefetches internal links on click; this
// adds a prerender for this one page only.
add_action( 'wp_load_speculation_rules', function ( $rules ) {
	$rules->add_rule( 'prerender', 'travelx-plovdiv', array(
		'source'    => 'document',
		'where'     => array( 'href_matches' => '/' . TXPV_SLUG . '/*' ),
		'eagerness' => 'moderate',
	) );
} );

// No cross-fade here: TravelX Sliven already scopes WordPress's view
// transitions to /sliven/, and a second scope script would cancel it.

// ── Diagnostics: Tools → TravelX Plovdiv ─────────────────────────────
// A read-only report of where the page was published and what the web
// server actually returns for it, plus a button to republish without
// re-uploading the plugin.

add_action( 'admin_menu', function () {
	add_management_page( 'TravelX Plovdiv', 'TravelX Plovdiv', 'manage_options', 'travelx-plovdiv', 'txpv_diagnostics_page' );
} );

add_filter( 'plugin_action_links_' . plugin_basename( __FILE__ ), function ( $links ) {
	$links[] = '<a href="' . esc_url( admin_url( 'tools.php?page=travelx-plovdiv' ) ) . '">Diagnostics</a>';
	return $links;
} );

function txpv_listing( $dir ) {
	if ( ! is_dir( $dir ) ) {
		return file_exists( $dir ) ? '(exists, but is not a folder)' : '(does not exist)';
	}
	$lines = array();
	foreach ( array_diff( scandir( $dir ), array( '.', '..' ) ) as $name ) {
		$path    = $dir . '/' . $name;
		$lines[] = sprintf( '%s  %s%s', substr( sprintf( '%o', fileperms( $path ) ), -4 ), $name, is_dir( $path ) ? '/' : '  (' . filesize( $path ) . ' B)' );
	}
	return $lines ? implode( "\n", $lines ) : '(empty folder)';
}

/** "0755  owner:group" for a path. */
function txpv_mode( $path ) {
	if ( ! file_exists( $path ) ) {
		return '(missing)';
	}
	$stat  = stat( $path );
	$owner = $stat['uid'];
	$group = $stat['gid'];
	if ( function_exists( 'posix_getpwuid' ) && ( $pw = posix_getpwuid( $owner ) ) ) {
		$owner = $pw['name'];
	}
	if ( function_exists( 'posix_getgrgid' ) && ( $gr = posix_getgrgid( $group ) ) ) {
		$group = $gr['name'];
	}
	return substr( sprintf( '%o', $stat['mode'] ), -4 ) . '  ' . $owner . ':' . $group;
}

function txpv_diagnostics_page() {
	if ( ! current_user_can( 'manage_options' ) ) {
		return;
	}
	if ( isset( $_POST['txpv_republish'] ) && check_admin_referer( 'txpv_republish' ) ) {
		txpv_sync();
		echo '<div class="notice notice-info"><p>Republished. State is now <code>' . esc_html( (string) get_option( 'txpv_state' ) ) . '</code>.</p></div>';
	}

	$target  = txpv_target();
	$docroot = untrailingslashit( isset( $_SERVER['DOCUMENT_ROOT'] ) ? (string) $_SERVER['DOCUMENT_ROOT'] : '' );
	$user    = get_current_user();
	if ( function_exists( 'posix_geteuid' ) && function_exists( 'posix_getpwuid' ) ) {
		$pw   = posix_getpwuid( posix_geteuid() );
		$user = $pw ? $pw['name'] : (string) posix_geteuid();
	}
	$rows = array(
		'Plugin version'          => TXPV_VERSION,
		'Publish state'           => var_export( get_option( 'txpv_state' ), true ),
		'Adopted an empty folder' => get_option( 'txpv_adopted' ) ? 'yes' : 'no',
		'ABSPATH'                 => ABSPATH . '  →  ' . var_export( realpath( ABSPATH ), true ),
		'DOCUMENT_ROOT'           => $docroot . '  →  ' . var_export( realpath( $docroot ), true ),
		'Publish target'          => $target . '  →  ' . var_export( realpath( $target ), true ),
		'Target is a symlink'     => is_link( $target ) ? 'yes → ' . readlink( $target ) : 'no',
		'Site root mode'          => txpv_mode( ABSPATH ),
		'Target mode'             => txpv_mode( $target ),
		'Target assets/ mode'     => txpv_mode( $target . '/assets' ),
		'Site root writable'      => is_writable( ABSPATH ) ? 'yes' : 'no',
		'PHP runs as'             => $user,
		'open_basedir'            => ini_get( 'open_basedir' ) ? ini_get( 'open_basedir' ) : '(none)',
		'Server software'         => isset( $_SERVER['SERVER_SOFTWARE'] ) ? (string) $_SERVER['SERVER_SOFTWARE'] : '',
	);

	echo '<div class="wrap"><h1>TravelX Plovdiv — diagnostics</h1><table class="widefat striped" style="max-width:1100px"><tbody>';
	foreach ( $rows as $label => $value ) {
		echo '<tr><th style="width:220px">' . esc_html( $label ) . '</th><td><code>' . esc_html( (string) $value ) . '</code></td></tr>';
	}
	echo '</tbody></table>';

	echo '<h2>Contents of ' . esc_html( $target ) . '</h2><pre>' . esc_html( txpv_listing( $target ) ) . '</pre>';
	if ( $docroot && realpath( $docroot ) !== realpath( ABSPATH ) ) {
		echo '<h2>Contents of ' . esc_html( $docroot . '/' . TXPV_SLUG ) . '</h2><pre>' . esc_html( txpv_listing( $docroot . '/' . TXPV_SLUG ) ) . '</pre>';
	}

	echo '<h2>What the web server returns</h2><pre>';
	foreach ( array( '/plovdiv/', '/plovdiv/index.html', '/plovdiv/bg/', '/plovdiv/assets/og.jpg', '/wp-content/plugins/travelx-plovdiv/site/index.html' ) as $path ) {
		$r = wp_remote_get( home_url( $path ), array( 'timeout' => 10, 'redirection' => 0, 'sslverify' => false ) );
		$result = is_wp_error( $r ) ? 'error: ' . $r->get_error_message() : wp_remote_retrieve_response_code( $r ) . '  ' . strlen( wp_remote_retrieve_body( $r ) ) . ' B';
		echo esc_html( str_pad( $path, 56 ) . $result ) . "\n";
	}
	echo '</pre>';

	$htaccess = array_unique( array_filter( array( realpath( ABSPATH . '.htaccess' ), realpath( $docroot . '/.htaccess' ) ) ) );
	foreach ( $htaccess as $file ) {
		echo '<h2>' . esc_html( $file ) . '</h2><pre style="max-height:420px;overflow:auto;background:#fff;padding:8px;border:1px solid #ccd0d4">' . esc_html( (string) file_get_contents( $file ) ) . '</pre>';
	}

	echo '<form method="post">';
	wp_nonce_field( 'txpv_republish' );
	submit_button( 'Republish /plovdiv/ now', 'secondary', 'txpv_republish' );
	echo '</form></div>';
}
