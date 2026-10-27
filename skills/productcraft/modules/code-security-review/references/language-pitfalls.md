# Language and framework pitfalls

Reference for the `code-security-review` module. Read only the section for the stack under review. Entries are traps specific to that language or framework; the general classes are in `vulnerability-classes.md` (cited as "class N") and generated-code patterns in `ai-generated-code-bugs.md` (cited as `AIG-nn`). Tools named here are optional: run them only if already installed, treat their output as advisory, and record anything that did not run as `NOT_VERIFIED`.

**Contents:** [JavaScript and TypeScript](#javascript-and-typescript) · [Python](#python) · [Go](#go) · [Java and Spring](#java-and-spring) · [PHP](#php) · [Ruby and Rails](#ruby-and-rails) · [C# and .NET](#c-and-net) · [Solidity basics](#solidity-basics)

**Separate guides:** [C and C++](c-and-cpp.md), [Rust](rust.md), [smart contracts in depth](smart-contracts.md), [mobile apps and their backends](mobile-apps.md).


Writing idiomatic code in these stacks (toolchains, versions, framework behavior such as ORM loading and transactions) is in `../../stacks/GUIDE.md`; this file covers only the security traps.

## JavaScript and TypeScript

### Node.js and TypeScript
- **Types vanish at runtime.** `req.body as CreateUser` checks nothing; parse request data with a schema (Zod, Valibot, Ajv) at every boundary (AIG-13).
- **Query and body values are not always strings.** `?id=1&id=2` yields an array, and Express 4's default parser turns `?a[b]=1` into an object. Check types before comparing or querying (class 1.2), and use `===`.
- **`child_process.exec` runs a shell;** `execFile` and `spawn` do not unless `shell: true` is set (class 1.3).
- **`vm` is not a sandbox,** as Node's own documentation states. Run untrusted code in a separate process or container.
- **Prototype pollution** through deep merges and path setters (class 14).
- **One event loop serves everyone.** A catastrophic regex (`new RegExp(input)`, nested quantifiers) or a large synchronous `JSON.parse` blocks all requests (class 16).
- **`crypto.timingSafeEqual` throws on unequal lengths;** compare fixed-length digests (class 3).
- **Unhandled promise rejections terminate the process** in current Node versions; an attacker who can trigger one can crash the server. Handle errors at route level.
- **Outbound calls need explicit timeouts** (`AbortSignal.timeout(ms)` with `fetch`); the defaults are minutes long.
- **Tools:** `npm audit --omit=dev` (or the pnpm/yarn equivalent), ESLint with `eslint-plugin-security` if the project uses ESLint, Semgrep or CodeQL if configured.

### Express
- **Middleware order is the security model.** `app.use(auth)` protects only routes registered after it (AIG-02).
- **`app.set("trust proxy", true)` trusts every `X-Forwarded-For`,** so clients can spoof their IP and defeat IP-based limits and logs. Set it to the real hop count or proxy addresses.
- **Body limits:** `express.json()` defaults to 100 kB. Raise limits per route, not globally.
- **No security headers by default:** use `helmet` and tune its CSP (LaunchGuard control 18).
- **`res.sendFile` with user-influenced names** needs the `root` option (class 6).
- **The default error handler includes stack traces unless `NODE_ENV=production`;** set it in every deployment and install a custom error handler (AIG-12).
- **Sessions:** `express-session`'s default `MemoryStore` is not meant for production; set `secret` from the environment and cookie flags `httpOnly`, `secure`, `sameSite` (LaunchGuard control 9).
- **`csurf` is deprecated;** use a maintained CSRF approach (class 8).

### React
- **JSX escapes text only.** `dangerouslySetInnerHTML`, user-supplied `href`/`src` with `javascript:` URLs, and `ref.current.innerHTML` are not protected (class 7).
- **Everything in the bundle and in props is public:** no secrets, no authorization decisions (AIG-01, AIG-04).
- **Markdown from users or models:** `react-markdown` does not render raw HTML by default; adding `rehype-raw` requires `rehype-sanitize` after it.
- **Server-rendered state** embedded in the page needs an escaping serializer (class 7).

### Next.js (App Router)
- **Server Actions are public POST endpoints.** Authenticate, authorize and validate arguments inside every action, even when the button is hidden.
- **Route handlers (`app/**/route.ts`) and Pages Router API routes need their own checks;** middleware is not a sufficient boundary (AIG-02, including CVE-2025-29927).
- **Props from Server to Client Components are serialized to the browser.** Pass DTOs with only the fields the client needs; mark server-only modules with `import "server-only"` so an accidental client import fails the build.
- **Environment variables:** only `NEXT_PUBLIC_*` reaches the browser, inlined at build time; the `next.config` `env` block also inlines values (LaunchGuard control 1).
- **Caching:** per-user data must never be cached under a shared key (data caches such as `unstable_cache` or the `use cache` directive, `fetch` caching, CDN caching of authenticated pages). Key by user or opt out.
- **Redirects and images:** `redirect()` with user input is an open redirect (class 12); wildcard `images.remotePatterns` and `dangerouslyAllowSVG` widen SSRF and XSS exposure (classes 4, 7).
- **CSRF:** Server Actions check `Origin` against `Host`; cookie-authenticated route handlers do not and need their own protection (class 8).
- **Stay on a patched release:** check the installed version (`npm ls next`) against the framework's security advisories.

## Python

### Language and standard library
- **Code-running loaders:** `pickle`, `yaml.load`, `eval`/`exec`, `subprocess` with `shell=True` (classes 1, 5).
- **`os.path.join(base, name)` discards `base` when `name` is absolute** (class 6).
- **`assert` disappears under `python -O`;** never use it for security checks.
- **User-controlled format strings leak data:** `user_template.format(obj)` lets `{0.__init__.__globals__}` walk attributes. Templates are constants; user data goes in arguments.
- **`random` is predictable;** use `secrets` for anything security-relevant (class 9).
- **`tempfile.mktemp` is racy;** use `mkstemp` or `NamedTemporaryFile` (class 10).
- **Archives:** `tarfile.extractall` needs `filter="data"` before Python 3.14; `zipfile` strips `..` from names but does nothing about size (class 6).
- **`requests` has no default timeout;** always pass `timeout=`.
- **Standard-library XML on untrusted input:** use `defusedxml` (class 13).
- **Tools:** `pip-audit`, `bandit -r <package>`, Semgrep if configured.

### Django
- **Defaults that help:** template auto-escaping, CSRF middleware, ORM parameterization, clickjacking middleware, strong password hashers. Findings usually come from switching them off.
- **Production settings:** `DEBUG = True`, `ALLOWED_HOSTS = ["*"]`, a committed `SECRET_KEY` (the generated `django-insecure-` prefix is a giveaway), insecure cookie settings. Run `python manage.py check --deploy`.
- **Escaping opt-outs:** `mark_safe`, `|safe`, `{% autoescape off %}`; `format_html` is safe only when user data is passed as arguments.
- **Raw SQL:** `.raw()`, `.extra()`, `RawSQL` with string formatting (class 1.1); `.raw()` accepts a `params` argument.
- **Lookup injection:** `Model.objects.filter(**request.GET.dict())` lets users choose lookups such as `password__startswith` and probe hidden fields. Map allowed filters explicitly.
- **Forms and serializers:** `ModelForm` or `ModelSerializer` with `fields = "__all__"` or `exclude` lets new model fields become writable (class 11).
- **Django REST Framework:** the default permission is `AllowAny` unless `DEFAULT_PERMISSION_CLASSES` is set; scope `get_queryset()` by `request.user` so detail views inherit it (class 2).
- **Redirects:** use `url_has_allowed_host_and_scheme` for `next` parameters (class 12).
- **User uploads** served from `MEDIA_URL` on the main domain can carry HTML or SVG; serve them from a separate domain or as attachments.

### Flask
- **No CSRF protection by default:** add Flask-WTF `CSRFProtect` for cookie sessions (class 8).
- **Sessions are signed, not encrypted:** users can read their contents, and a weak `SECRET_KEY` can be brute-forced to forge sessions. Use a long random key from the environment.
- **`debug=True` or `FLASK_DEBUG=1`** exposes the Werkzeug debugger, which can execute code; never on a reachable host (AIG-12).
- **Templates:** `render_template_string` with user text is template injection (class 1.5); `Markup()` and `|safe` skip escaping; Flask auto-escapes `.html`/`.htm`/`.xml` templates rendered through `render_template`, but a standalone Jinja2 `Environment` does not escape by default.
- **Files:** `send_file(user_path)` is traversal; use `send_from_directory(directory, name)`.

### FastAPI
- **Authentication is opt-in per route** through dependencies; attach it at router level (`APIRouter(dependencies=[Depends(...)])`) so new routes inherit it.
- **`OAuth2PasswordBearer` only extracts the bearer token;** your dependency still has to verify it (class 3).
- **Separate input models** with `model_config = ConfigDict(extra="forbid")`, and `response_model` (or explicit response schemas) so ORM objects do not leak fields (class 11, AIG-22).
- **Raw SQL:** `text(f"...")` is injectable; bind with `text("... WHERE id = :id")` and pass parameters to `execute` (class 1.1).
- **CORS:** `allow_origins=["*"]` with `allow_credentials=True` (AIG-06).
- **Docs endpoints** (`/docs`, `/redoc`, `/openapi.json`) are public by default; disable them (`docs_url=None`, `redoc_url=None`, `openapi_url=None`) or protect them for internal APIs.
- **Blocking calls inside `async def` handlers** stall the event loop for everyone; use `def` handlers or async libraries.

## Go
- **Templates:** `html/template` escapes by context, `text/template` does not; converting user data to `template.HTML`, `template.JS` or `template.URL` disables escaping (class 7).
- **SQL:** use placeholders (`?` for MySQL and SQLite, `$1` for Postgres); `fmt.Sprintf` into SQL is injection (class 1.1).
- **Commands:** `exec.Command` does not use a shell unless you call `sh -c`; argument injection still applies (class 1.3).
- **Paths:** `filepath.Join` and `filepath.Clean` do not confine; use `filepath.IsLocal` (Go 1.20+) or `os.Root` (Go 1.24+) (class 6).
- **Timeouts and sizes:** the zero-value `http.Server` and `http.Client` have no timeouts. Set `ReadHeaderTimeout`, `ReadTimeout`, `WriteTimeout`, `IdleTimeout` and a client `Timeout`, and wrap request bodies in `http.MaxBytesReader`.
- **Concurrency:** concurrent map writes crash the process and data races corrupt state; protect shared state with `sync.Mutex` or channels and run `go test -race ./...` (class 10).
- **Ignored errors:** `_ =` on `Scan`, `json.Unmarshal`, `rows.Err()` or verification calls lets zero values flow into security decisions.
- **Integer conversions wrap silently:** `int32(n)` after `strconv.Atoi` can overflow; parse with the target size (`strconv.ParseInt(s, 10, 32)`) and check ranges.
- **JWT:** with golang-jwt, pass `jwt.WithValidMethods([]string{"RS256"})` (or your algorithm) and validate claims (class 3).
- **Strict JSON input:** decoding straight into database structs is mass assignment (class 11); use request DTOs and `Decoder.DisallowUnknownFields()`.
- **Crypto:** `crypto/rand`, not `math/rand`; never `InsecureSkipVerify: true` (class 9).
- **Tools:** `govulncheck ./...` (reports vulnerabilities in code paths you actually call), `go vet ./...`, `gosec ./...` and `staticcheck ./...` if installed.

## Java and Spring
- **Rule order in Spring Security:** request matchers are evaluated in order. Put specific rules first and end with `anyRequest().authenticated()` (or `denyAll()`); an early, broad `permitAll()` opens everything it matches.
- **Method security must be switched on:** `@PreAuthorize` and `@Secured` do nothing without `@EnableMethodSecurity` (older versions: `@EnableGlobalMethodSecurity(prePostEnabled = true)`), and calls from within the same class bypass the proxy.
- **CSRF:** `csrf.disable()` is fine for stateless bearer-token APIs and wrong for session or cookie login (class 8).
- **Actuator:** exposing `env`, `heapdump`, `threaddump`, `configprops` or `loggers` over HTTP leaks secrets (a heap dump contains credentials). Expose `health` (and `info` if needed) and protect the rest.
- **Binding to entities:** `@RequestBody` or `@ModelAttribute` bound to `@Entity` classes is mass assignment; use DTOs, or `@InitBinder` with `setAllowedFields` for form binding (class 11).
- **JPQL and native queries:** `createQuery("..." + x)` is injectable like SQL; use named parameters and `setParameter`. Spring Data derived queries and `@Query` with `:param` are bound; `nativeQuery = true` with concatenation is not (class 1.1).
- **Expressions and views:** never evaluate user strings with SpEL's `StandardEvaluationContext`; never build Thymeleaf view names or fragment expressions from input; `th:utext` skips escaping (classes 1.4, 1.5, 7).
- **Deserialization and XML:** `ObjectInputStream`, Jackson default typing, XStream and SnakeYAML 1.x (class 5); XML factories need explicit XXE hardening (class 13).
- **Logging library:** `log4j-core` older than 2.17.1 on Java 8+ is affected by the Log4Shell family (CVE-2021-44228 and follow-ups); check the resolved tree (`mvn dependency:tree`, `gradle dependencies`).
- **Errors:** `server.error.include-stacktrace` and `include-message` must not be `always` in production (AIG-12).
- **Crypto:** `SecureRandom`, not `Random`; `Cipher.getInstance("AES")` means ECB (class 9).
- **Tools:** OWASP Dependency-Check or the build's SCA plugin, SpotBugs with Find Security Bugs, Semgrep or CodeQL if configured.

## PHP
- **Loose comparison:** `==` juggles types. `"0e123" == "0e456"` is true because both read as zero in scientific notation, so comparing hashes with `==` fails open; in PHP 7, `0 == "anything"` is also true. Use `===`, `hash_equals`, `password_verify`, `in_array($x, $list, true)`, and `match` (strict) rather than `switch` (loose).
- **`strcmp($input, $secret) == 0`** passes in PHP 7 when `$input` is an array (`strcmp` returns null); PHP 8 throws a `TypeError` instead.
- **File inclusion:** `include`/`require` with request data is local file inclusion, and remote inclusion if `allow_url_include` is on (class 1.4).
- **Object injection:** `unserialize` on input triggers magic methods (`__wakeup`, `__destruct`, `__toString`) in available classes; use JSON (class 5).
- **Variable overwrite:** `extract($_POST)`, variable variables (`$$name`) and one-argument `parse_str` (removed in PHP 8) overwrite local variables.
- **SQL:** PDO or mysqli prepared statements; `real_escape_string` does not protect unquoted numbers or identifiers (class 1.1).
- **Output:** `htmlspecialchars($s, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8')`, or the template engine's escaping (Twig, Blade `{{ }}`) (class 7).
- **Uploads:** `$_FILES[...]['type']` and the original name are client-controlled; check content, generate names, and never store uploads where PHP executes (`.php`, `.phtml`, `.phar` under the web root).
- **Sessions:** `session_regenerate_id(true)` after login; `session.use_strict_mode=1`, `session.cookie_httponly`, `session.cookie_secure`, `session.cookie_samesite`.
- **Production config:** `display_errors=Off`; log errors instead (AIG-12).
- **Laravel:** `{!! !!}` prints raw HTML; `$guarded = []` with `$request->all()` is mass assignment, use `$fillable` and `$request->validated()`; `DB::raw` and `whereRaw` with variables; `APP_DEBUG=true` in production exposes environment details; a leaked `APP_KEY` lets attackers forge encrypted cookies and signed URLs; review CSRF exclusions; authorize with Policies or Gates (`$this->authorize()`), not only route middleware; keep private files off the `public` disk.
- **WordPress:** every admin-ajax and REST handler needs `current_user_can()` plus a nonce check (`check_ajax_referer`, `wp_verify_nonce`); `wp_ajax_nopriv_*` hooks run for anonymous visitors; REST routes need a real `permission_callback` (`__return_true` makes them public); queries go through `$wpdb->prepare`; output through `esc_html`, `esc_attr`, `esc_url`.
- **Tools:** `composer audit`, Psalm taint analysis (`psalm --taint-analysis`) or PHPStan if configured.

## Ruby and Rails
- **Strong parameters:** never `permit!`; never permit `role`, `admin`, `user_id` or `account_id` from user-facing forms; permit nested attributes (`accepts_nested_attributes_for`) key by key (class 11).
- **SQL:** use hash conditions or `?` placeholders. Interpolation in `where`, `order`, `group`, `pluck`, `joins` or `find_by_sql` is injectable. Rails 6+ rejects raw SQL in `order` and `pluck` unless wrapped in `Arel.sql`, so `Arel.sql(params[...])` is a red flag; allowlist sort columns (class 1.1).
- **Output:** ERB escapes `<%= %>`; `raw`, `html_safe`, `<%==`, `render html:` and `render inline:` do not; `link_to` accepts `javascript:` URLs, so validate schemes; use `sanitize` for intended HTML (class 7).
- **Dynamic dispatch:** `send`, `public_send`, `constantize` and `safe_constantize` with parameters call arbitrary methods or classes; allowlist names (class 1.4).
- **Regex anchors:** `^` and `$` match at every line break, so `"ok\n<script>"` passes `/^ok$/`. Validate with `\A` and `\z`. Rails format validators reject multiline anchors unless `multiline: true` is set, which catches many cases.
- **Deserialization and secrets:** `Marshal.load`, `YAML.unsafe_load` (class 5); use the `:json` cookie serializer, not `:marshal`; protect `secret_key_base` and `config/master.key`, since a leak allows forged sessions.
- **Redirects:** keep `raise_on_open_redirects` on and avoid `allow_other_host: true` with user input (class 12).
- **Pipes in file APIs:** `Kernel#open`, `IO.read` and `IO.readlines` with user input can run commands when the value starts with `|` (on Ruby versions that still allow it); use `File.open`/`File.read`. `URI.open` is also an SSRF sink (class 4).
- **CSRF:** `ActionController::Base` protects by default; `ActionController::API` controllers have no CSRF protection, which is fine for token authentication and wrong if they read cookies (class 8).
- **Tools:** Brakeman (`brakeman -q`), bundler-audit (`bundle audit check`; refreshing its advisory database needs network access).

## C# and .NET
- **Deserialization:** `BinaryFormatter` (obsolete, and removed from .NET 9), `SoapFormatter`, `NetDataContractSerializer`, `LosFormatter`, `ObjectStateFormatter`, Json.NET with `TypeNameHandling` other than `None` on untrusted input, and `JavaScriptSerializer` with a type resolver. Use `System.Text.Json` and never let the input choose the type (class 5).
- **SQL:** Entity Framework `FromSqlRaw` or `ExecuteSqlRaw` with interpolated or concatenated strings, and `SqlCommand` text built from input. Use `FromSql` or `FromSqlInterpolated`, which turn interpolations into parameters, or explicit `SqlParameter`s (class 1.1).
- **XML:** `XmlDocument` or `XmlTextReader` with a non-null `XmlResolver`, or `XmlReaderSettings.DtdProcessing = DtdProcessing.Parse`. Old .NET Framework versions resolve external entities by default; keep `DtdProcessing.Prohibit` and a null resolver (class 13).
- **Processes:** `Process.Start` with `UseShellExecute = true`, or `cmd.exe /c` and `powershell -Command` with input in the command line; pass arguments through `ProcessStartInfo.ArgumentList` (class 1.3).
- **Authorization:** controllers and endpoints without `[Authorize]` when no fallback policy is set, `[AllowAnonymous]` overriding a controller-level policy, and minimal-API endpoints registered outside the group that carries `RequireAuthorization()` (class 2).
- **Forms and redirects:** MVC controllers handling cookie-authenticated form posts without antiforgery validation (Razor Pages validate by default; MVC needs `[ValidateAntiForgeryToken]` or the global `AutoValidateAntiforgeryTokenAttribute`), `[IgnoreAntiforgeryToken]`, `Redirect(returnUrl)` instead of `LocalRedirect` or a `Url.IsLocalUrl` check, and `Html.Raw` on user content (classes 7, 8 and 12).
- **Over-posting:** model binding straight into entity classes; bind to request DTOs (class 11).
- **Randomness and passwords:** `System.Random` for tokens (use `RandomNumberGenerator`); `MD5` or `SHA1` for passwords (use ASP.NET Core Identity's password hasher, or `Rfc2898DeriveBytes.Pbkdf2` with a high iteration count) (class 9).
- **Comparisons:** culture-sensitive `string.Compare`, `ToLower()` or `ToUpper()` on identifiers (the Turkish dotless i); use `StringComparison.Ordinal` or `OrdinalIgnoreCase`.
- **Tools:** `dotnet list package --vulnerable --include-transitive`, the built-in analyzers with `<AnalysisLevel>latest-all</AnalysisLevel>`, and CodeQL for C#.

## Solidity basics

Contracts hold value and cannot be patched in place once deployed, so treat findings as high stakes. Work only against local chains or forks (Foundry Anvil, Hardhat Network); never sign or send mainnet transactions, never handle real private keys or seed phrases, and recommend an independent audit before value-bearing contracts are deployed. OWASP's web categories fit contracts poorly; describe findings by name and impact, and use the OWASP Smart Contract Top 10 when a list is wanted.

- **Reentrancy:** an external call (ETH transfer, token transfer, callbacks such as `onERC721Received` or ERC-777 hooks) before state is updated. Follow checks-effects-interactions, add `nonReentrant` (OpenZeppelin `ReentrancyGuard`), and consider cross-function and read-only reentrancy (view functions read half-updated state).
- **Access control:** privileged functions (`mint`, `withdraw`, `setOwner`, `upgradeTo`, `pause`) without `onlyOwner` or role checks; unprotected `initialize` in upgradeable contracts (use the `initializer` modifier and call `_disableInitializers()` in the implementation's constructor).
- **`tx.origin` for authorization:** a malicious contract the user calls can act as the user; use `msg.sender`.
- **Arithmetic:** Solidity 0.8+ reverts on overflow, except inside `unchecked { }` and for explicit downcasts (`uint8(x)` truncates silently; use `SafeCast`); older code needs SafeMath; dividing before multiplying loses precision; check the rounding direction in share and price math.
- **Unchecked calls and tokens:** a low-level `call` returns a success flag that must be checked; non-standard ERC-20 tokens may not return a bool, so use `SafeERC20`; fee-on-transfer and rebasing tokens break balance assumptions.
- **`delegatecall`** to a user-supplied or upgradeable target runs foreign code against your storage; check proxy storage layouts for collisions.
- **Oracle manipulation:** a spot price from one AMM pool can be moved within a single transaction (flash loans); use time-weighted or decentralized oracles with staleness and deviation checks.
- **Front-running:** require slippage limits and deadlines on swaps; use commit-reveal for secret choices.
- **Signatures:** include a nonce, the chain ID and the contract address (EIP-712); reject `ecrecover` results of `address(0)`; use OpenZeppelin `ECDSA`, which rejects malleable signatures; mark signatures as used.
- **Randomness:** `block.timestamp`, `blockhash` and `block.prevrandao` are predictable or influenceable; use a verifiable randomness service.
- **Denial of service:** unbounded loops over growing arrays; paying many recipients in one transaction (one reverting recipient blocks all), so use pull payments.
- **Tools:** Foundry `forge test` with fuzz and invariant tests, plus a Solidity static analyzer (for example Mythril) if one is installed. Pin an exact compiler version and build on OpenZeppelin Contracts instead of hand-written tokens and access control.

Scoping a contract review, writing invariants, token integration, upgradeable contracts, Foundry fuzz, invariant and fork tests, and other chains: `smart-contracts.md`.
