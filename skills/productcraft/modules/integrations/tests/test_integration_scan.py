"""Offline tests for integration_scan.py. Synthetic files only: no network, no real keys."""
import contextlib
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "integration_scan.py"
spec = importlib.util.spec_from_file_location("integration_scan", SCRIPT)
scan_mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = scan_mod
spec.loader.exec_module(scan_mod)


def write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def run(argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = scan_mod.main(argv)
    return code, out.getvalue(), err.getvalue()


class ScanCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def rules(self, **kwargs):
        result = scan_mod.scan(self.root, **kwargs)
        return [(d["rule"], d["file"], d["line"]) for d in result["leads"]]

    def rule_ids(self, **kwargs):
        return sorted({r for r, _, _ in self.rules(**kwargs)})


class WebhookTests(ScanCase):
    def test_reparsed_body_is_flagged(self):
        write(self.root, "src/webhooks/stripe.ts",
              "export async function handle(req, res) {\n"
              "  const sig = req.headers['stripe-signature'];\n"
              "  const event = stripe.webhooks.constructEvent(JSON.stringify(req.body), sig, secret);\n"
              "  await markProcessed(event.id);\n"
              "}\n")
        self.assertIn(("WEBHOOK-REPARSED-BODY", "src/webhooks/stripe.ts", 3), self.rules())

    def test_raw_body_with_dedup_is_clean(self):
        write(self.root, "src/webhooks/stripe.ts",
              "export async function handle(req, res) {\n"
              "  const sig = req.headers['stripe-signature'];\n"
              "  const event = stripe.webhooks.constructEvent(req.rawBody, sig, secret);\n"
              "  await db.query('insert into webhook_events (event_id) values ($1) on conflict do nothing', [event.id]);\n"
              "}\n")
        self.assertEqual(self.rules(), [])

    def test_unverified_handler_without_dedup(self):
        write(self.root, "app/api/webhooks/billing/route.ts",
              "export async function POST(request: Request) {\n"
              "  const payload = await request.json();\n"
              "  await grantAccess(payload.data.user);\n"
              "  return Response.json({ ok: true });\n"
              "}\n")
        self.assertEqual(self.rule_ids(), ["WEBHOOK-NO-DEDUP", "WEBHOOK-NO-VERIFY"])

    def test_route_string_marks_handler(self):
        write(self.root, "server/app.py",
              "@app.post('/hooks/webhook')\n"
              "def receive():\n"
              "    data = request.get_data()\n"
              "    if not verify_signature(data, request.headers):\n"
              "        abort(400)\n"
              "    handle(data)\n")
        self.assertEqual(self.rules(), [("WEBHOOK-NO-DEDUP", "server/app.py", 1)])

    def test_plain_compare_js(self):
        write(self.root, "lib/verify.js",
              "const crypto = require('crypto');\n"
              "function ok(body, signature, secret) {\n"
              "  if (signature == null) return false;\n"
              "  const digest = crypto.createHmac('sha256', secret).update(body).digest('hex');\n"
              "  if (digest !== signature) return false;\n"
              "  return crypto.timingSafeEqual(Buffer.from(digest), Buffer.from(signature));\n"
              "}\n")
        self.assertEqual(self.rules(), [("HMAC-PLAIN-COMPARE", "lib/verify.js", 5)])

    def test_plain_compare_python_and_length_check(self):
        write(self.root, "app/sig.py",
              "import hashlib, hmac\n"
              "def check(raw, received, secret):\n"
              "    if len(received) != 64:\n"
              "        return False\n"
              "    expected = hmac.new(secret, raw, hashlib.sha256).hexdigest()\n"
              "    return expected == received\n")
        self.assertEqual(self.rules(), [("HMAC-PLAIN-COMPARE", "app/sig.py", 6)])


class ProviderRuleTests(ScanCase):
    def test_stripe_creates(self):
        write(self.root, "billing/charge.ts",
              "import Stripe from 'stripe';\n"
              "const stripe = new Stripe(process.env.STRIPE_SECRET_KEY);\n"
              "await stripe.paymentIntents.create({ amount: 500, currency: 'usd' });\n"
              "await stripe.refunds.create(\n"
              "  { payment_intent: id },\n"
              "  { idempotencyKey: `order_${orderId}:refund` },\n"
              ");\n"
              "await stripe.customers.create({ email });\n")
        self.assertEqual(self.rules(), [("STRIPE-NO-IDEMPOTENCY", "billing/charge.ts", 3)])

    def test_python_stripe_create(self):
        write(self.root, "billing/charge.py",
              "import stripe\n"
              "stripe.PaymentIntent.create(amount=500, currency='usd', idempotency_key=key)\n"
              "stripe.Subscription.create(customer=cid, items=[{'price': price_id}])\n")
        self.assertEqual(self.rules(), [("STRIPE-NO-IDEMPOTENCY", "billing/charge.py", 3)])

    def test_secret_in_url(self):
        write(self.root, "src/rpc.ts",
              "const url = `https://rpc.example.com/?api-key=${process.env.RPC_KEY}`;\n"
              "const page = `https://api.example.com/items?page=${n}`;\n"
              "const check = BASE + '/licenses/validate?license_key=' + key;\n")
        self.assertEqual(self.rules(), [("SECRET-IN-URL", "src/rpc.ts", 1), ("SECRET-IN-URL", "src/rpc.ts", 3)])

    def test_broad_scopes_in_code_and_config(self):
        write(self.root, "auth/scopes.py",
              "SCOPES = [\n"
              "    'https://www.googleapis.com/auth/drive.file',\n"
              "    'https://www.googleapis.com/auth/drive',\n"
              "    'https://www.googleapis.com/auth/calendar.events',\n"
              "    'https://mail.google.com/',\n"
              "]\n")
        write(self.root, "config/oauth.json",
              '{"scopes": ["read:jira-work", "manage:jira-configuration"]}\n')
        self.assertEqual(self.rules(), [
            ("BROAD-OAUTH-SCOPE", "auth/scopes.py", 3),
            ("BROAD-OAUTH-SCOPE", "auth/scopes.py", 5),
            ("BROAD-OAUTH-SCOPE", "config/oauth.json", 1),
        ])

    def test_client_module_with_server_sdk(self):
        write(self.root, "components/Pay.tsx",
              "'use client';\n"
              "import { loadStripe } from '@stripe/stripe-js';\n"
              "import Stripe from 'stripe';\n"
              "const key = process.env.STRIPE_SECRET_KEY;\n")
        write(self.root, "components/Ok.tsx",
              "\"use client\";\n"
              "import { loadStripe } from '@stripe/stripe-js';\n"
              "const pk = process.env.NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY;\n")
        write(self.root, "lib/server.ts", "import Stripe from 'stripe';\n")
        self.assertEqual(self.rules(), [
            ("CLIENT-SERVER-SDK", "components/Pay.tsx", 3),
            ("CLIENT-SERVER-SDK", "components/Pay.tsx", 4),
        ])

    def test_getsession_only_in_server_code(self):
        snippet = "const { data } = await supabase.auth.getSession();\n"
        write(self.root, "app/api/profile/route.ts", snippet)
        write(self.root, "src/lib/actions.ts", "'use server';\n" + snippet)
        write(self.root, "components/Nav.tsx", snippet)
        self.assertEqual(self.rules(), [
            ("SUPABASE-GETSESSION-SERVER", "app/api/profile/route.ts", 1),
            ("SUPABASE-GETSESSION-SERVER", "src/lib/actions.ts", 2),
        ])

    def test_sheets_user_entered(self):
        write(self.root, "export/sheets.py",
              "sheets.values().update(spreadsheetId=sid, range=rng,\n"
              "    valueInputOption='USER_ENTERED', body=body).execute()\n"
              "sheets.values().update(spreadsheetId=sid, range=rng, valueInputOption='RAW', body=body)\n")
        self.assertEqual(self.rules(), [("SHEETS-USER-ENTERED", "export/sheets.py", 2)])

    def test_retired_apis(self):
        write(self.root, "src/legacy.ts",
              "const a = `${base}/rest/api/3/search?jql=${q}`;\n"
              "const b = `${base}/rest/api/3/search/jql`;\n"
              "const env = PlaidEnvironments.development;\n"
              "const redirect = 'urn:ietf:wg:oauth:2.0:oob';\n")
        self.assertEqual(self.rules(), [
            ("RETIRED-API", "src/legacy.ts", 1),
            ("RETIRED-API", "src/legacy.ts", 3),
            ("RETIRED-API", "src/legacy.ts", 4),
        ])


class BehaviourTests(ScanCase):
    def test_acknowledged_line_is_suppressed(self):
        write(self.root, "src/rpc.ts",
              "// integration-scan: ignore SECRET-IN-URL provider accepts the key only in the URL; server-side\n"
              "const url = `https://rpc.example.com/?api-key=${process.env.RPC_KEY}`;\n")
        result = scan_mod.scan(self.root)
        self.assertEqual(result["leads"], [])
        self.assertEqual(result["suppressed"], 1)

    def test_test_files_skipped_unless_requested(self):
        write(self.root, "tests/test_sig.py",
              "import hmac\nx = hmac.new(k, b, 'sha256').hexdigest()\nassert x == expected\n")
        write(self.root, "src/sig.spec.ts",
              "const d = createHmac('sha256', k).digest('hex');\nexpect(d == expected);\n")
        self.assertEqual(self.rules(), [])
        self.assertEqual(self.rule_ids(include_tests=True), ["HMAC-PLAIN-COMPARE"])

    def test_skipped_folders_and_env_files(self):
        write(self.root, "node_modules/pkg/index.js", "const s = 'https://mail.google.com/';\n")
        write(self.root, ".env.local", "SCOPE=https://mail.google.com/\n")
        self.assertEqual(self.rules(), [])

    def test_cli_exit_codes_and_output(self):
        code, out, _ = run(["--root", str(self.root)])
        self.assertEqual(code, 0)
        self.assertIn("0 lead(s)", out)
        marker = "x" * 24
        write(self.root, "src/rpc.ts", f"const url = 'https://rpc.example.com/?api_key=' + '{marker}';\n")
        code, out, _ = run(["--root", str(self.root)])
        self.assertEqual(code, 1)
        self.assertIn("SECRET-IN-URL", out)
        self.assertNotIn(marker, out, "matched source text must never be printed")
        self.assertEqual(run(["--root", str(self.root), "--fail-on", "high"])[0], 0)
        self.assertEqual(run(["--root", str(self.root), "--fail-on", "never"])[0], 0)
        code, out, _ = run(["--root", str(self.root), "--json"])
        data = json.loads(out)
        self.assertEqual(data["counts"]["medium"], 1)
        self.assertNotIn(marker, out)

    def test_usage_errors_and_help(self):
        self.assertEqual(run(["--root", str(self.root / "missing")])[0], 2)
        self.assertEqual(run(["--max-files", "0"])[0], 2)
        self.assertEqual(run(["--no-such-flag"])[0], 2)
        self.assertEqual(run(["--help"])[0], 0)
        code, out, _ = run(["--list-rules"])
        self.assertEqual(code, 0)
        for rule in scan_mod.RULES:
            self.assertIn(rule, out)

    def test_deterministic(self):
        write(self.root, "b/one.py", "S = 'https://www.googleapis.com/auth/drive'\n")
        write(self.root, "a/two.py", "S = 'https://www.googleapis.com/auth/cloud-platform'\n")
        first = run(["--root", str(self.root), "--json"])[1]
        second = run(["--root", str(self.root), "--json"])[1]
        self.assertEqual(first, second)
        files = [d["file"] for d in json.loads(first)["leads"]]
        self.assertEqual(files, sorted(files))


if __name__ == "__main__":
    unittest.main()
