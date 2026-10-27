# WordPress and WooCommerce

Read this when you build or change a WordPress plugin, theme, block, REST endpoint or WooCommerce extension, or tune a WordPress site's performance or security. General PHP practice is in `php-laravel.md` and the PHP section of `../../code-security-review/references/language-pitfalls.md`; launch-level security in `../../launchguard/GUIDE.md`.

## Versions that change the advice

| Version | What matters |
|---|---|
| 6.2 (2023) | `%i` placeholder for identifiers in `$wpdb->prepare` |
| 6.3 (2023) | `wp_enqueue_script` accepts a `strategy` of `defer` or `async` |
| 6.5 (2024) | Interactivity API, Script Modules API, Block Bindings API, plugin dependencies (`Requires Plugins` header) |
| 6.6 (2024) | `theme.json` version 3; minimum PHP 7.2.24 |
| WooCommerce 8.2 and 8.3 (2023) | High-Performance Order Storage (HPOS) and the block-based Cart and Checkout are defaults for new stores |

Read the site's version (`wp core version`, or `$wp_version`) and the `Requires at least` and `Requires PHP` headers of the plugin or theme. Code must run on the oldest versions those headers claim.

## Where code belongs

- Never edit WordPress core, a parent theme or a third-party plugin; updates erase the change. Use hooks, a child theme, or your own plugin.
- Site functionality (custom post types, integrations, business rules) goes in a plugin, so it survives a theme switch. Must-use plugins (`wp-content/mu-plugins`) hold code the site must always run.
- Themes handle presentation. Block themes (`theme.json`, HTML templates and template parts) are the default for new themes; classic PHP themes remain supported.
- Local environment: `@wordpress/env` (`wp-env`, Docker-based) or the project's own setup. WP-CLI for everything scriptable.

## Hooks

- Actions run code at a point; filters receive a value and must return it (also when they change nothing).
- Register on the right hook: post types and taxonomies on `init`, assets on `wp_enqueue_scripts` or `admin_enqueue_scripts`, REST routes on `rest_api_init`, settings on `admin_init`.
- Removing a callback needs the same hook, callable and priority. Closures cannot be removed by others; register public callbacks as named functions or static methods.
- Prefix every function, hook, option, post type and script handle (or use a namespace) to avoid collisions.
- Offer your own `do_action` and `apply_filters` points, with prefixed names, where other code should extend yours.
- Do not run queries or remote requests on hooks that fire on every request unless the result is cached.

## Plugin structure

- Main file header: name, version, `Requires at least`, `Requires PHP`, `Text Domain`, `License: GPL-2.0-or-later`. Guard every PHP file with `defined( 'ABSPATH' ) || exit;`.
- Composer autoloading for classes. In plugins you distribute, prefix bundled vendor namespaces (Strauss or PHP-Scoper) so two plugins shipping different versions of one library do not collide.
- Activation hook for one-time setup (create tables with `dbDelta`, add capabilities, flush rewrite rules once); deactivation hook to unschedule events; `uninstall.php` to remove data, honoring a "keep data" setting if the plugin offers one.
- Plugins distributed outside the WordPress.org directory need their own update channel: serve packages and update metadata over HTTPS from a server you control, and never take the update URL from an option an administrator or attacker could edit.
- Settings pages register options with `register_setting` and a `sanitize_callback`, behind a capability check, or use a REST-backed settings screen built with `@wordpress/components`.
- Large options: `autoload` false. Every autoloaded option is loaded on every request; Site Health reports when the total grows too large.

## Security: WordPress's names for the baseline controls

- **Authorization is capability checks:** `current_user_can( 'edit_post', $post_id )` before every privileged action, including reads of private data. Use meta capabilities with an object id, not role names.
- **Nonces protect against CSRF; they are not authorization.** Check both: `check_admin_referer()` for admin forms, `check_ajax_referer()` for admin-ajax, the `wp_rest` nonce for cookie-authenticated REST calls.
- **Input:** `wp_unslash()` first, then sanitize by type (`sanitize_text_field`, `sanitize_email`, `sanitize_key`, `absint`, `esc_url_raw`, `wp_kses_post` for allowed HTML). Validate against allowed values, not only sanitize.
- **Output: escape late, at the point of output,** with the function for the context: `esc_html`, `esc_attr`, `esc_url`, `wp_kses_post`, and `wp_json_encode` for data printed into scripts. Translated strings too (`esc_html__`, `esc_attr_e`).
- **SQL:** prefer `WP_Query` and the meta and options APIs. Raw queries go through `$wpdb->prepare` with `%d`, `%s`, `%f` and `%i` placeholders; table names from `$wpdb->prefix`.
- **REST routes:** every `register_rest_route` has a `permission_callback`; `__return_true` only for data that is public by design. Declare `args` with types, `validate_callback` and `sanitize_callback`.
- **admin-ajax:** `wp_ajax_nopriv_{action}` handlers are public endpoints reachable by anyone.
- **Uploads:** `wp_handle_upload` with an allowed MIME list and `wp_check_filetype_and_ext`; never execute or include uploaded files.
- **Never `unserialize()` user-controlled data** (PHP object injection); use JSON.
- Hardening outside code: `DISALLOW_FILE_EDIT` in `wp-config.php`, least-privilege roles, updates applied promptly, a WordPress vulnerability database checked for installed plugins.

```php
add_action( 'rest_api_init', function () {
	register_rest_route( 'acme/v1', '/projects/(?P<id>\d+)/notes', array(
		'methods'             => WP_REST_Server::CREATABLE,
		'permission_callback' => function ( WP_REST_Request $request ) {
			return current_user_can( 'edit_post', (int) $request['id'] ); // object-level check
		},
		'args'                => array(
			'note' => array(
				'type'              => 'string',
				'required'          => true,
				'sanitize_callback' => 'sanitize_textarea_field',
				'validate_callback' => fn( $value ) => is_string( $value ) && strlen( $value ) <= 2000,
			),
		),
		'callback'            => function ( WP_REST_Request $request ) {
			$post_id = (int) $request['id'];
			$note_id = add_post_meta( $post_id, '_acme_note', $request['note'] );
			if ( ! $note_id ) {
				return new WP_Error( 'acme_note_failed', __( 'Could not save the note.', 'acme' ), array( 'status' => 500 ) );
			}
			return new WP_REST_Response( array( 'id' => $note_id ), 201 );
		},
	) );
} );
```

## Blocks

- Scaffold with `npx @wordpress/create-block`; build with `@wordpress/scripts`. Register from `block.json` (`apiVersion` 3) with `register_block_type( __DIR__ . '/build/my-block' )`.
- **Static blocks** save HTML into post content. Changing the `save` output later invalidates existing content ("This block contains unexpected or invalid content") unless you add a `deprecated` entry for every previous version.
- **Dynamic blocks** render on the server (`render.php`) from stored attributes. Prefer them when output depends on data or will change.
- Use `useBlockProps` on the wrapper, `InnerBlocks` for nested content, and `@wordpress/data` stores for editor data.
- Front-end interactivity: the Interactivity API (`data-wp-*` directives with a store in a script module) instead of ad-hoc jQuery.
- Block patterns (PHP files in a theme's `patterns/` folder) and `theme.json` presets give editors consistent building blocks.

## Themes

- Block theme: `theme.json` for settings (palette, typography, spacing, layout widths) and styles; `templates/*.html` and `parts/*.html` for structure; style variations for alternatives. Disable editor controls the design system does not allow.
- Classic theme: the template hierarchy (`single-{post_type}.php`, `archive-{post_type}.php`, `page-{slug}.php`), `get_template_part`, `add_theme_support` in `after_setup_theme`.
- Enqueue assets with a version (the build hash or `filemtime`) and only where they are needed; use `strategy => 'defer'` for scripts that need not block rendering.
- All strings translatable with the theme's text domain.

## Performance

- **Queries:** never `posts_per_page => -1` on content that grows. Pass `no_found_rows => true` when not paginating, `fields => 'ids'` when only ids are needed, and `update_post_meta_cache => false` or `update_post_term_cache => false` when unused. `meta_query` on unindexed meta values slows down as data grows; use a taxonomy or a custom table for heavily filtered data.
- **Caching:** a persistent object cache (Redis or Memcached) makes `wp_cache_*` and transients fast. Without one, transients live in the options table and may vanish early; never rely on a transient being present.
- **WP-Cron** runs on page views and is unreliable on low-traffic sites and costly on busy ones. Set `DISABLE_WP_CRON` and run due events from a system scheduler (`wp cron event run --due-now`). Use Action Scheduler for large background job volumes.
- **Page caching** (plugin, server or CDN) for anonymous visitors; logged-in users and carts bypass it, so their paths need efficient code.
- Profile with Query Monitor on a staging copy before optimizing (`../../engineering-practices/references/performance.md`).

## WooCommerce

- Use the CRUD objects and functions (`wc_get_order()`, `$order->get_meta()`, `$order->update_meta_data()`, `$order->save()`), never direct post meta for orders: with HPOS, orders live in their own tables. Declare HPOS compatibility in the plugin.
- The block-based Cart and Checkout do not fire most classic checkout PHP hooks. Extend them through the Store API and the checkout block extensibility points, and test both checkouts if the store can use either.
- Payment and order state changes follow `../../launchguard/references/stack-playbooks.md` (payments): verify gateway webhooks, use idempotency, and never mark an order paid from the browser.

## Testing and tooling

- PHP_CodeSniffer with the WordPress Coding Standards (`phpcs --standard=WordPress`), PHPStan with the WordPress extension, and the Plugin Check plugin before directory submission.
- PHPUnit with the WordPress test suite (`wp scaffold plugin-tests`, or the `wp-env` test environment); JavaScript unit tests through `wp-scripts test-unit-js`; end-to-end tests with `@wordpress/e2e-test-utils-playwright`.
- Test with the oldest and newest WordPress and PHP versions the headers claim.

## Operations

- Never develop on production. Work on a local or staging copy; deploy code through version control.
- Moving between domains: `wp search-replace old new --all-tables --dry-run` first. Raw SQL replacement corrupts PHP-serialized data.
- Back up the database and files before core, plugin or theme updates, and update staging first. Running updates or `search-replace` on production is a production action that needs permission.
- Configuration and secrets in `wp-config.php` read from the environment, not committed.

## Licensing

Plugins and themes distributed to others are derivative of WordPress and must be GPL-compatible (the WordPress.org directory requires GPLv2 or later compatible licenses). Check the licenses of bundled libraries, fonts and images (`../../legal-ready/GUIDE.md`).

## Common breakages

| Symptom | Cause | Fix |
|---|---|---|
| "This block contains unexpected or invalid content" | Static block `save` output changed | Add a `deprecated` version, or make the block dynamic |
| Custom post type URLs return 404 | Rewrite rules not flushed | Flush once on activation (or visit Permalinks); never on every request |
| REST route notice about `permission_callback` | Missing callback | Add a real capability check |
| Filter breaks output elsewhere | Callback did not return the value | Always return the (modified) value |
| Site slow only for logged-in users | Page cache bypassed; heavy queries per request | Object cache; fix the queries Query Monitor shows |
| Serialized settings lost after a domain move | SQL find-and-replace changed string lengths | Restore the backup; use `wp search-replace` |
| WooCommerce hook does not fire at checkout | Store uses the block checkout | Store API and block extensibility |

## Done when

- [ ] PHPCS (WordPress standard) and the project's tests pass on the oldest and newest supported WordPress and PHP versions.
- [ ] Every privileged action checks a capability; every form and AJAX or REST call made with cookies checks a nonce; every REST route has a real `permission_callback`.
- [ ] All output is escaped at the point of output; all raw SQL uses `prepare`.
- [ ] No unbounded queries; expensive results cached; cron jobs unscheduled on deactivation.
- [ ] No change was made directly on a production site.
