# Secrets: doing the work without seeing the values

Anything printed in a session is stored in the transcript and may be logged, synced or shared. The agent therefore treats secret values as something it never needs to see, and works with names, presence checks and lengths.

## What counts as secret

| Class | Examples | Agent behavior | Guard |
|---|---|---|---|
| Private keys and credential stores | SSH private keys in `~/.ssh/` (anything except `*.pub`, `known_hosts`, `authorized_keys`, `config`); `*.key`, private-key `*.pem`, `*.p12`, `*.pfx`, Java keystores, `*.kdbx`; `~/.gnupg/`; cloud CLI credentials (`~/.aws/`, `~/.config/gcloud/`, `~/.azure/`); `~/.kube/config`; `~/.docker/config.json`; `~/.netrc`; `~/.git-credentials`; `~/.pgpass`; the GitHub CLI's `hosts.yml`; OS keychains; browser profiles (saved passwords, cookies); wallet files; the coding agent's own login files | Never read, print, copy or upload. Using a key through its normal program (`ssh -i KEY`, `ssh-add`, `git` over SSH) is fine | Reading denied, copying asked, uploading denied |
| Dotenv-style and config secrets | `.env`, `.env.local`, `.env.production`, `*.env`, `.envrc`, `.dev.vars`, `local.settings.json`, `secrets.json` or `.yaml`, `credentials.json`, service-account and OAuth client JSON, `.npmrc` and `.pypirc` (often hold registry tokens), `.htpasswd`, Terraform `*.tfstate` and `*.tfvars` | Names and presence only. Read values only when the user asked and the task needs them; never repeat them | Reading asked, uploading denied, `git add` asked |
| Environment and history | Environment variables, shell history files, CI logs, crash dumps | Print one non-secret variable at a time; never dump the whole environment | `env`, `printenv`, `set`, `export -p` asked |

Templates are not secret: `.env.example`, `.env.sample`, `.env.template`, `*.pub` keys and certificates without private keys.

## Rules

1. **Need to know.** Most tasks only need to know that a variable exists and where the app reads it.
2. **Names, not values.** Never echo, paste, summarize or partially reveal a value, including "the first few characters".
3. **Keep values off the command line.** Arguments end up in shell history, in process listings (`ps`) and in the session log. Prefer the tool's own login flow, a credential helper, an environment file, or a stdin option such as `docker login --password-stdin`.
4. **Keep values out of artifacts.** No secrets in code, tests, fixtures, commit messages, pull requests, issues, logs or screenshots. Use obvious placeholders such as `sk_test_REPLACE_ME`.
5. **Never send values to third parties:** paste sites, online formatters or decoders, other AI tools, chat webhooks, or URL query strings.
6. **Ignore before create.** Add `.env` to `.gitignore` before creating it, and commit a `.env.example` with placeholder values.

## Common tasks without the values

```bash
test -f .env && echo present                                  # does the file exist?
git check-ignore -v .env                                      # is it ignored, and by which rule?
git ls-files --error-unmatch .env                             # exit status 0 means it is tracked (bad)
git log --all --oneline -- .env                               # was it ever committed?
grep -v '^[[:space:]]*#' .env | cut -d= -f1                   # which variables are defined?
diff <(cut -d= -f1 .env.example | sort) <(cut -d= -f1 .env | sort)   # missing or extra names
grep -c '^STRIPE_SECRET_KEY=' .env                            # is one variable defined? (count only)
echo "${STRIPE_SECRET_KEY:+set}"                              # is it set in this shell?
echo "${#STRIPE_SECRET_KEY}"                                  # length only
ls -l ~/.ssh                                                  # which key files exist, and their modes
ssh-keygen -lf ~/.ssh/id_ed25519.pub                          # fingerprint from the public key
aws sts get-caller-identity                                   # which account is active (no secret shown)
gh auth status                                                # logged in? (token stays masked)
```

To check that the app sees a variable, add a temporary check that prints only `set` or `missing`, and remove it afterwards.

## When the user provides a secret

- Prefer that the user writes it into `.env` or the secret store themselves.
- If they paste a value into the chat, use it only for the step they asked for, do not repeat it, and mention that it now exists in the conversation history.
- Create secret files with restrictive permissions: `umask 077` before creating, or `chmod 600 .env` afterwards.
- For CI secrets, let the tool prompt for the value (`gh secret set NAME` reads it interactively or from stdin) instead of putting it in a command argument.

## When a secret has been exposed

1. Stop. Do not print it again.
2. Tell the user what was exposed and where (file and line, or command), the kind of secret, and the channels it may have reached. Never repeat the value.
3. Follow LaunchGuard's leak response in `../../launchguard/references/safe-operations.md`: rotate or revoke at the provider first; removing the text does not make it safe.
4. Rewriting git history is optional and needs coordination; see `destructive-commands.md`, section 3.

## Native controls worth suggesting

Claude Code permission rules can stop the agent's file tools from reading secret files. They do not cover shell commands such as `cat`, which is why the optional command guard also checks those.

```json
{
  "permissions": {
    "deny": [
      "Read(./.env)",
      "Read(./.env.*)",
      "Read(./secrets/**)",
      "Read(~/.ssh/**)",
      "Read(~/.aws/**)"
    ]
  }
}
```

Propose such rules to the user and add them only with their OK. Rules in `.claude/settings.json` are shared with the team; personal ones belong in `.claude/settings.local.json` or `~/.claude/settings.json`.
