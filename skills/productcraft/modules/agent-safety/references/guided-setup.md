# Guided setup scripts: steps only the user can do

Read this when a setup, key rotation or cutover needs several things only a person can do: sign in to a provider's dashboard, create a key, paste a secret, approve a change, or carry out a step that cannot be undone. Instead of asking for secrets in the chat, or walking the user through it over many messages, write a short script that they run in their own terminal.

What it buys: secret values go from the user's clipboard into `.env` or the CI secret store without passing through the conversation; every step is numbered and can stop safely; and the next person can repeat the setup.

## 1. Plan the steps with the user

Read what the project expects first: `.env.example`, the configuration loader, the README and the CI workflows. Workflows name the secrets and variables they expect (`secrets.NAME`, `vars.NAME`), and each one needs a step that supplies it:

```bash
grep -ohE '(secrets|vars)\.[A-Za-z0-9_]+' .github/workflows/*.yml | sort -u
```

Then fill in one row per value:

| Value | Where the person finds it | Stored in | Secret? |
|---|---|---|---|
| `PAYMENTS_API_KEY` | Provider dashboard: Developers > API keys > restricted key | `.env` and CI secret | yes |
| `PAYMENTS_WEBHOOK_URL` | Our staging URL plus `/webhooks/payments` | provider dashboard only | no |

For a cutover, add the current state, the target state and each step between them that cannot be undone. If you do not know a provider's current interface, write the page address and what to look for, and say you have not verified the path; never make up menu names.

Show the table and the order of steps to the user and let them correct it before you write the script.

## 2. Write the script

Keep the helper functions at the top as they are and write one `step` per task below the marker. Save it outside the repository, or under `scripts/` if the user wants to keep it, with no values in it.

```bash
#!/usr/bin/env bash
# Guided setup: steps only a person can do. Run it yourself:  bash setup-payments.sh
# Pasted values go straight into ENV_FILE and the CI secret store; they are never printed.
set -euo pipefail
umask 077                       # files this script creates are readable by you only
ENV_FILE="${ENV_FILE:-.env}"
DRY_RUN="${DRY_RUN:-0}"         # DRY_RUN=1 asks everything but writes only to ENV_FILE
TOTAL=3
STEP=0

step() { STEP=$((STEP + 1)); printf '\n[%d/%d] %s\n' "$STEP" "$TOTAL" "$1"; }
note() { printf '  %s\n' "$@"; }
show_page() {
  note "Open: $1"
  [ "$DRY_RUN" = 1 ] && return 0
  if command -v xdg-open >/dev/null 2>&1; then xdg-open "$1" >/dev/null 2>&1 || true
  elif command -v open >/dev/null 2>&1; then open "$1" || true
  fi
}
ask_yes() {                     # ask_yes "question": succeeds only on y or yes
  local answer
  read -r -p "  $1 [y/N] " answer || answer=""
  case "$answer" in [yY] | [yY][eE][sS]) return 0 ;; *) return 1 ;; esac
}
read_hidden() {                 # value=$(read_hidden NAME): no echo, stops on empty input
  local value
  read -r -s -p "  Paste $1 (input hidden): " value || value=""
  printf '\n' >&2
  if [ -z "$value" ]; then note "$1 is empty; stopping. Nothing else was written." >&2; exit 1; fi
  printf '%s' "$value"
}
save_env() {                    # save_env NAME VALUE: add or replace NAME in ENV_FILE
  local tmp
  touch "$ENV_FILE"
  tmp="$(mktemp "${ENV_FILE}.XXXXXX")"
  grep -v "^$1=" "$ENV_FILE" > "$tmp" || true
  printf '%s=%s\n' "$1" "$2" >> "$tmp"
  mv "$tmp" "$ENV_FILE"
  note "Saved $1 to $ENV_FILE"
}
store_ci_secret() {             # store_ci_secret NAME VALUE: the CI tool reads the value on stdin
  if [ "$DRY_RUN" = 1 ]; then note "Dry run: would store CI secret $1"; return 0; fi
  printf '%s' "$2" | gh secret set "$1"
  note "Stored CI secret $1"
}

# ---- steps: edit below this line ----
step "Create a restricted API key"
show_page "https://dashboard.payments.example/apikeys"
note "Developers > API keys > Create restricted key, with write access to Charges and Refunds only."
key="$(read_hidden PAYMENTS_API_KEY)"
save_env PAYMENTS_API_KEY "$key"

step "Give the key to CI"
store_ci_secret PAYMENTS_API_KEY "$key"
unset key

step "Register the webhook endpoint"
note "Endpoint: https://staging.app.example/webhooks/payments   Events: charge.succeeded, charge.refunded"
ask_yes "Have you saved the endpoint in the dashboard?" || { note "Stopped here. Re-run when ready; finished steps are safe to repeat."; exit 1; }

printf '\nDone: %d of %d steps. Tell the agent "setup finished"; it never needs the values.\n' "$STEP" "$TOTAL"
```

Keep to these rules when you write the steps:
- One task per step, in the order the table needs, with `TOTAL` equal to the number of steps.
- Show the page address first, then ask for the value found there. Secrets only through `read_hidden`; a public value may use a plain `read`.
- Values travel in variables, files and standard input, never as arguments of external programs, which show up in process lists and shell history. `printf` and `read` are shell builtins, so the helpers above do not expose values. With a CI provider other than GitHub, use its CLI's standard-input option.
- Before anything that cannot be undone (deleting the old key, moving production traffic, dropping data), say what will happen and what is permanent, then `ask_yes`. Stopping at any point must leave a state the next run can continue from.
- No `set -x`, no `echo` or logging of a value, and writes only to the files named at the top.

## 3. Check it without running it for real

The script waits for a person and receives real secrets, so you do not run it against the real environment. Check it like this instead:

```bash
bash -n setup-payments.sh                                  # syntax
command -v shellcheck >/dev/null && shellcheck setup-payments.sh
T="$(mktemp -d)"                                           # dry run with a fake value into a temporary file
printf 'fake-key-for-test\ny\n' | ENV_FILE="$T/.env" DRY_RUN=1 bash setup-payments.sh
cut -d= -f1 "$T/.env"                                      # names only: PAYMENTS_API_KEY
```

Then read the script against the table from step 1: every row has a step that reads the value and a call that stores it where the row says, and every CI secret name is spelled exactly as the workflows spell it.

## 4. Hand it over and confirm

- Give the user the path, the command, the number of steps, and the reassurance that values stay out of the chat.
- When they report back, confirm by name only: `cut -d= -f1 .env`, `gh secret list` (names and dates, never values), or the app's own set-or-missing check (`secrets.md`).
- Delete the script afterwards, unless the user wants to keep it as the documented setup path; then commit it without values and point to it from the README.
