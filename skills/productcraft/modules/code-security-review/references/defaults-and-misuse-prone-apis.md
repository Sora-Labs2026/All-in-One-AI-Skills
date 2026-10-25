# Insecure defaults and misuse-prone APIs

Two related questions. Part 1: what does the application do when nobody configured it, or configured it wrong? Part 2: when the project exposes or wraps an API, library or configuration format, is the easy way to use it also the safe way? Generated-code versions of several defaults (fallback secrets, permissive CORS, debug mode, leftover routes, fail-open handlers, scaffolding) are in [AI-generated code bugs](ai-generated-code-bugs.md) as `AIG-05`, `AIG-06`, `AIG-12`, `AIG-18`, `AIG-19` and `AIG-26`; this file gives the method and the cases those entries do not cover.

## Part 1. Defaults in the application

### Two shapes of insecure default

| Shape | Example | When it is a finding |
|---|---|---|
| **Fallback**: a configuration lookup with a default | `os.getenv("SESSION_SECRET", "dev")`, `process.env.CORS_ORIGIN ?? "*"`, `ENV.fetch("REQUIRE_MFA", "false")`, Spring `@Value("${auth.enabled:false}")`, `${ADMIN_PASSWORD:-admin}` in compose files | Only if the application actually starts and serves with the default in an environment that matters. Reading `os.environ["SESSION_SECRET"]` crashes when unset, which is safe |
| **Fixed**: insecure as written, no configuration involved | `verify=False` on a shared HTTP client, `Access-Control-Allow-Origin` reflected with credentials, `DEBUG = True` in the production settings module | Always, wherever production can reach it. A missing environment variable is no defense because nothing reads one |

About half of real cases are the fixed kind. Do not dismiss one because "production sets the variable": there is no variable.

### Method

1. **Find where configuration enters**: settings modules, config schemas (Zod, Pydantic settings, `@ConfigurationProperties`), the project's own wrappers (`getConfig("x", default)`, `settings.get`), `.env.example`, Helm `values.yaml`, compose files, Terraform variables, Kubernetes manifests, Dockerfile `ENV` lines. Wrappers hide fallbacks from generic searches; read them.
2. **List the settings that change security**: secrets and keys; authentication or MFA on and off; CSRF; CORS origins; cookie flags; TLS verification; debug, tracing and error detail; admin, debug and seed routes; rate limits and lockouts; session and token lifetimes; upload size and type limits; log level and what gets logged; allowed hosts and redirect targets; the role given to new users; storage visibility; bind address; feature flags that skip a check.
3. **For each one, answer four questions**: what runs when it is unset, when it is an empty string, when it is malformed (`"flase"`, `"0 "`), and which deploy manifests set it. Check every environment that serves real users, not just production: staging with real data and preview deployments count.
4. **Sweep for fallback syntax** to catch what the list missed (adapt to the stack; the hits are leads):

```bash
rg -n -e 'getenv\([^)]*,\s*["\x27]' -e 'environ\.get\([^)]*,\s*["\x27]' -e 'process\.env\.\w+\s*(\|\||\?\?)' \
  -e 'ENV\.fetch\([^)]*,' -e '\$\{\w+:-[^}]*\}' -e '@Value\("\$\{[^}:]+:[^}]*\}"\)' \
  -e 'GetValue<[^>]+>\([^)]*,' -e 'os\.LookupEnv' .
```

5. **Decide with this table**:

| What happens when the setting is absent | Verdict |
|---|---|
| Startup fails with a clear message | Safe (fail-secure) |
| A secure value is used | Safe |
| An insecure value is used, but every manifest for every serving environment sets it | Hardening note; becomes a finding the day one manifest forgets |
| An insecure value is used and some serving environment does not set it (or you cannot tell) | Finding (`LIKELY` with the unverified manifest as the condition when the deploy config is outside the repository) |
| Insecure fixed value on a path production runs | Finding |

6. **Fix**: no defaults for secrets and security switches; validate the whole settings object at startup and refuse to start when a required value is missing or invalid; make the secure value the default for everything else; put development conveniences in an explicit, untracked development file. The regression test starts the application with the variable unset (and with it empty) and expects a refusal.

### Defaults worth a specific look

| Default | Signals | Safer form |
|---|---|---|
| Seeded or default accounts | Migrations or seed scripts that create `admin` users and run at deploy; compose files with `POSTGRES_PASSWORD: postgres`; dashboards and brokers left on vendor default credentials | Seeds only in development; first admin created by a one-time, expiring invitation; generated passwords from a secrets store |
| Default-allow authorization | Policy files with a default of allow (`default allow := true` in a policy language, an `else: return True` in a permission function), route groups whose guard list is empty by default, database or storage rules that start open | Deny by default; every allow rule names its condition; a test that a route with no explicit rule is refused |
| File and directory modes | `0o666`, `0o777`, `chmod 777`, `umask(0)`, key files written with default permissions, `tempfile.mktemp` (predictable name) | `0o600` for secrets and `0o700` for private directories; `mkstemp` or `NamedTemporaryFile`; create files with the mode instead of fixing it afterwards |
| Storage visibility | `ACL="public-read"`, `allUsers` grants, public access blocks turned off, signed URLs with lifetimes of days | Private buckets; short-lived signed URLs for specific objects |
| Bind address and exposure | Admin, metrics, debugger or database ports bound to `0.0.0.0`; dev servers started with `--host 0.0.0.0` in containers whose ports are published | Bind internal services to localhost or an internal network; publish only the public port |
| Lifetimes | Tokens without `exp`, sessions with no idle or absolute timeout, reset links valid for days, `0` or `-1` meaning "never expires" | Explicit, short lifetimes; reject non-positive values instead of treating them as infinite |
| Error detail and tracing | `AIG-12`, plus tracing or profiling endpoints enabled by a default flag | Off unless explicitly enabled per environment |

### Infrastructure defaults

| Area | Look for | Tools if installed |
|---|---|---|
| Terraform and cloud | Security groups open to `0.0.0.0/0` on SSH, RDP or database ports; `publicly_accessible = true` databases; missing public access blocks on buckets; unencrypted volumes and snapshots; IAM policies with `*` actions and resources | `checkov -d .`, `trivy config .` |
| Kubernetes | `privileged: true`, `hostNetwork`, `hostPath` mounts, no `runAsNonRoot`, `allowPrivilegeEscalation` not set to false, service account tokens mounted where not needed, no NetworkPolicy (everything can talk to everything), `cluster-admin` bindings for applications | `kube-linter lint .`, `trivy config .` |
| Containers and compose | Root user, published database and cache ports, default passwords, secrets in `ENV` or build arguments | `trivy config .`, `hadolint Dockerfile` |

Scanner output here is a lead like any other. Cloud account settings outside the repository are `NOT_VERIFIED` and go to the owner's list ([LaunchGuard](../../launchguard/GUIDE.md) covers provider settings for launches).

## Part 2. Misuse-prone APIs and configuration formats

Use this when the project offers an API, SDK, library, plugin interface or configuration schema to others, or wraps a dangerous primitive in a helper that the rest of the code calls. The test is simple: if the obvious call, the first example in the docs or a slightly wrong value produces an insecure result, the design invites the mistake, and some caller will eventually make it.

### Probe every choice point

For each parameter, setting or flag that affects security, try the values below in a small test, and ask three questions: is the first example in the documentation safe? What happens if two arguments are swapped or one is left out? What can someone who controls this value (a request field, a config file in a pull request, a tenant's settings) do with it?

| Misuse pattern | Probe | Safer design |
|---|---|---|
| The caller, or the input, picks the algorithm or mode | `verify(token)` that trusts the token's own `alg` header; `hash(name, data)` accepting `md5` or `crc32`; a `cipher=` parameter | Fix the algorithm in code or check it against a short allowlist; offer one function per purpose instead of a mode switch |
| Zero, empty or null means "off" or "everything" | `ttl=0`, `max_attempts=0`, `allowed_origins=[]`, `api_key=""`, `required_role=None`, `-1` | Reject invalid values loudly; make "disabled" a separate, explicit flag; an empty allowlist denies everything |
| A boolean switches protection off | `verify=False`, `skip_auth=True`, `trust_proxy=True`, `sanitize=False` reachable from requests or tenant settings | Keep such switches out of request-controlled paths, give them alarming names, refuse them in production mode and log when they are used |
| Failure is silent | A verify function that returns `False` and callers that ignore it; exceptions swallowed inside the library; parse errors replaced with defaults | Raise on failure, or return a result type the compiler forces callers to inspect (`#[must_use]`, Go's error return, checked exceptions); test malformed input |
| Different things share one type | Keys, nonces, ciphertexts and signatures all plain bytes; user ID and tenant ID both strings; positional arguments of the same type | Distinct wrapper types; keyword-only or named parameters |
| Comparisons that lie | `==` on MACs and tokens (timing); PHP loose comparison, where `"0e1" == "0e2"` is true; JavaScript `==`; culture-sensitive string comparison of identifiers | Constant-time comparison for secrets (class 3); strict comparison; ordinal comparison for identifiers |
| Security values as free text | Roles as comma-separated strings that can be appended to; permissions built by string concatenation; URLs built by joining strings | Enums and sets; URL builders that encode each part |
| Configuration that accepts nonsense | A YAML 1.1 parser reading `no`, `off` and the country code `NO` as false; a typo such as `fasle` read as a truthy string; misspelled keys (`requre_auth`) silently ignored | A strict schema: reject unknown keys (`additionalProperties: false`, Pydantic `extra="forbid"`, Zod `.strict()`), check types and enums, fail on the first error |
| Dangerous combinations accepted | `auth_required: true` together with a bypass list that contains `/`; credentials allowed with a wildcard origin; `SameSite=None` without `Secure` | Validate combinations when the configuration loads and refuse to start |
| Silent truncation or normalization | bcrypt using only the first 72 bytes of a password; Unicode or case normalization applied to one side of a comparison; hostnames with a trailing dot | Document and enforce limits (reject over-long input instead of truncating); normalize both sides the same way before comparing |
| Good default, unchecked override | A constructor defaulting to SHA-256 and 120 seconds that also accepts `"md5"` and `0` | Validate overrides as strictly as the default |
| An unsafe twin next to the safe call | `render` and `render_raw`, `query` and `query_unsafe`, a raw-HTML prop | Make the unsafe twin long, obviously named and easy to search for; add a lint or Semgrep rule that flags it |

### Turn the probe into evidence

1. Write the misuse as a minimal test: `verify(token_with_alg_none)` must raise; `RateLimiter(max_attempts=0)` must raise instead of allowing everything.
2. Decide whether a real caller misuses it today. If a caller in scope does, that caller has a finding and the API change is its root-cause fix. If none does, it is a hardening note with the probe as evidence.
3. Rate by how easy the misuse is: unsafe by default or in the obvious usage is serious; unsafe after an easy, plausible mistake is moderate; unsafe only through deliberate misuse is minor. Documentation of the danger lowers likelihood but does not excuse the design.

## Done when

- Every security-relevant setting has a recorded answer for unset, empty and malformed values and for each serving environment's manifest (or `NOT_VERIFIED` where the manifest lives outside the repository).
- Each fixed insecure value on a production path is a finding; each fallback is a finding, a hardening note or safe, with the reason.
- For an exposed API or configuration format, every choice point was probed, the misuse tests exist, and callers that misuse it today are findings.
