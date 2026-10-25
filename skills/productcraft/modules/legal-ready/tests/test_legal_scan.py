"""Offline tests for legal_scan.py using small synthetic fixtures in temporary folders."""
import contextlib
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "legal_scan.py"
spec = importlib.util.spec_from_file_location("legal_scan", SCRIPT)
legal_scan = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = legal_scan
spec.loader.exec_module(legal_scan)


def build(files: dict) -> tempfile.TemporaryDirectory:
    tmp = tempfile.TemporaryDirectory()
    for rel, content in files.items():
        path = Path(tmp.name) / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            path.write_bytes(content)
        else:
            path.write_text(content, encoding="utf-8")
    return tmp


def run(files: dict, **kwargs) -> dict:
    with build(files) as root:
        report = legal_scan.scan(Path(root), **kwargs)
    return {c["id"]: c for c in report["checks"]} | {"_report": report}


def details(check: dict) -> list:
    return [e["detail"] for e in check["evidence"]]


class PolicyPageTests(unittest.TestCase):
    def test_pages_found_in_common_layouts(self):
        r = run({
            "app/privacy/page.tsx": "export default () => <h1>Privacy policy</h1>",
            "src/pages/TermsOfService.vue": "<template><h1>Terms</h1></template>",
            "content/legal/refund-policy.md": "# Refunds",
            "public/cookie-policy.html": "<h1>Cookies</h1>",
        })
        for cid in ("PRIVACY_POLICY", "TERMS_OF_SERVICE", "REFUND_POLICY", "COOKIE_POLICY"):
            self.assertEqual(r[cid]["status"], "PASS", cid)

    def test_utility_module_is_not_a_policy_page(self):
        r = run({"src/lib/cookies.ts": "export const read = () => document.cookie;"})
        self.assertEqual(r["COOKIE_POLICY"]["status"], "NOT_FOUND")

    def test_link_without_page_needs_review(self):
        r = run({"app/footer.tsx": '<a href="/privacy">Privacy</a><a href="/terms-of-service">Terms</a>'})
        self.assertEqual(r["PRIVACY_POLICY"]["status"], "NEEDS_REVIEW")
        self.assertEqual(r["TERMS_OF_SERVICE"]["status"], "NEEDS_REVIEW")

    def test_placeholders_block_a_pass(self):
        r = run({"app/privacy/page.tsx": "<p>Controller: [[LEGAL: registered company name]]</p>"})
        self.assertEqual(r["PRIVACY_POLICY"]["status"], "NEEDS_REVIEW")
        self.assertEqual(r["UNRESOLVED_PLACEHOLDERS"]["status"], "NEEDS_REVIEW")
        self.assertIn("[[LEGAL: registered company name]]", details(r["UNRESOLVED_PLACEHOLDERS"]))

    def test_refund_note_mentions_payment_code(self):
        r = run({"package.json": json.dumps({"dependencies": {"@stripe/stripe-js": "1"}})})
        self.assertEqual(r["REFUND_POLICY"]["status"], "NOT_FOUND")
        self.assertTrue(any("Payment code detected" in n for n in r["REFUND_POLICY"]["notes"]))

    def test_business_details_need_page_and_identity(self):
        r = run({"app/contact/page.tsx": "<footer>© 2026 Example Widgets Ltd. VAT number GB000</footer>"})
        self.assertEqual(r["BUSINESS_DETAILS"]["status"], "PASS")
        r = run({"app/contact/page.tsx": "<p>Write to us</p>"})
        self.assertEqual(r["BUSINESS_DETAILS"]["status"], "NEEDS_REVIEW")


class ConsentTests(unittest.TestCase):
    BANNER = """export function CookieBanner() {
  const gpc = navigator.globalPrivacyControl === true;
  return <div><button>Reject all</button><button>Accept all</button></div>;
}"""

    def test_banner_with_reject_and_gpc_passes(self):
        r = run({"components/CookieBanner.tsx": self.BANNER})
        self.assertEqual(r["COOKIE_CONSENT"]["status"], "PASS")

    def test_banner_without_reject_or_gpc_needs_review(self):
        r = run({"components/CookieBanner.tsx": "export const CookieBanner = () => <button>Accept all</button>;"})
        c = r["COOKIE_CONSENT"]
        self.assertEqual(c["status"], "NEEDS_REVIEW")
        self.assertTrue(any("no reject" in d for d in details(c)))
        self.assertTrue(any("Global Privacy Control" in d for d in details(c)))

    def test_trackers_without_banner(self):
        r = run({"index.html": '<script src="https://connect.facebook.net/en_US/fbevents.js"></script>'})
        c = r["COOKIE_CONSENT"]
        self.assertEqual(c["status"], "NOT_FOUND")
        self.assertTrue(any("need prior consent" in n for n in c["notes"]))

    def test_consent_mode_granted_by_default(self):
        bad = "gtag('consent', 'default', {'ad_storage': 'granted', 'analytics_storage': 'granted'});"
        regional = "gtag('consent', 'default', {'ad_storage': 'granted', 'region': ['US']});"
        r = run({"components/CookieBanner.tsx": self.BANNER, "head.js": bad})
        self.assertTrue(any("granted" in d for d in details(r["COOKIE_CONSENT"])))
        r = run({"components/CookieBanner.tsx": self.BANNER, "head.js": regional})
        self.assertFalse(any("granted" in d for d in details(r["COOKIE_CONSENT"])))


class ThirdPartyTests(unittest.TestCase):
    def test_inventory_from_scripts_manifests_and_calls(self):
        r = run({
            "index.html": '<script src="https://www.googletagmanager.com/gtag/js?id=X"></script>',
            "package.json": json.dumps({"dependencies": {"posthog-js": "1"}, "devDependencies": {"@sentry/node": "7"}}),
            "ios/Podfile": "pod 'FBSDKCoreKit'\n",
            "android/app/build.gradle": "implementation 'com.google.firebase:firebase-analytics:21.0.0'\n",
            "src/track.js": "fbq('track', 'Purchase');",
        })
        matched = {m for t in r["_report"]["third_parties"] for m in t["matched"]}
        for ident in ("googletagmanager.com", "posthog-js", "@sentry/node", "FBSDKCoreKit", "firebase-analytics", "fbq("):
            self.assertIn(ident, matched)
        self.assertEqual(r["THIRD_PARTY_SCRIPTS"]["status"], "NEEDS_REVIEW")

    def test_lockfiles_and_docs_are_ignored(self):
        r = run({
            "package-lock.json": '{"packages": {"node_modules/mixpanel-browser": {}}}',
            "README.md": "We used to load https://static.hotjar.com/c/hotjar.js",
        })
        self.assertEqual(r["_report"]["third_parties"], [])
        self.assertEqual(r["THIRD_PARTY_SCRIPTS"]["status"], "NOT_FOUND")


class ImageAltTests(unittest.TestCase):
    def test_missing_alt_is_reported_with_line(self):
        r = run({"src/Hero.tsx": 'export const Hero = () => (\n  <div>\n    <img src="/hero.png" />\n  </div>\n);'})
        c = r["IMG_ALT"]
        self.assertEqual(c["status"], "NEEDS_REVIEW")
        self.assertEqual(c["evidence"][0]["line"], 3)

    def test_alt_variants_and_non_images(self):
        r = run({"src/Gallery.tsx": """
<img src="a.png" alt="Invoice list" />
<img src={b} alt="" />
<img src={c} onLoad={() => setReady(x > 1)} alt={t("chart")} />
<Img src="styled-component.png" />
{/* <img src="commented-out.png"> */}
"""})
        c = r["IMG_ALT"]
        self.assertEqual(c["status"], "PASS")
        self.assertIn("All 3 image(s)", c["summary"])
        self.assertTrue(any("empty alt" in n for n in c["notes"]))

    def test_no_images(self):
        self.assertEqual(run({"index.html": "<p>Text only</p>"})["IMG_ALT"]["status"], "NOT_FOUND")


class PrecheckedConsentTests(unittest.TestCase):
    def test_prechecked_marketing_box_flagged(self):
        r = run({"signup.html": """
<label><input type="checkbox" name="newsletter" checked> Send me offers</label>
<label><input type="checkbox" checked> Remember me</label>
"""})
        c = r["PRECHECKED_CONSENT"]
        self.assertEqual(c["status"], "NEEDS_REVIEW")
        self.assertEqual(c["evidence_count"], 1)
        self.assertEqual(c["evidence"][0]["line"], 2)

    def test_unticked_box_passes(self):
        r = run({"signup.html": '<label><input type="checkbox" name="marketing"> Email me product news</label>'})
        self.assertEqual(r["PRECHECKED_CONSENT"]["status"], "PASS")

    def test_default_true_in_state_and_data_model(self):
        r = run({
            "src/Signup.tsx": "const [marketingOptIn, setMarketingOptIn] = useState(true);\n"
                              "const form = useForm({ defaultValues: { email: '', newsletter: true } });",
            "schema.prisma": "model User {\n  marketingConsent Boolean @default(true)\n}",
            "users/models.py": "newsletter = models.BooleanField(default=True)",
            "flags.ts": "export const requireConsent = true;",
        })
        files = sorted({e["file"] for e in r["PRECHECKED_CONSENT"]["evidence"]})
        self.assertEqual(files, ["schema.prisma", "src/Signup.tsx", "users/models.py"])


class EmailTests(unittest.TestCase):
    def test_marketing_template_without_unsubscribe(self):
        r = run({
            "emails/spring-sale.html": "<h1>Sale</h1>",
            "emails/weekly-digest.html": '<a href="*|UNSUB|*">Unsubscribe</a>',
            "emails/password-reset.html": "<p>Reset</p>",
        })
        c = r["EMAIL_UNSUBSCRIBE_LINK"]
        self.assertEqual(c["status"], "NEEDS_REVIEW")
        self.assertEqual([e["file"] for e in c["evidence"]], ["emails/spring-sale.html"])

    def test_transactional_only(self):
        r = run({"emails/password-reset.html": "<p>Reset</p>"})
        self.assertEqual(r["EMAIL_UNSUBSCRIBE_LINK"]["status"], "NOT_FOUND")
        self.assertIn("transactional", r["EMAIL_UNSUBSCRIBE_LINK"]["summary"])

    def test_one_click_headers(self):
        both = {"mail.ts": 'headers: {"List-Unsubscribe": "<https://x/u>", "List-Unsubscribe-Post": "List-Unsubscribe=One-Click"}'}
        self.assertEqual(run(both)["EMAIL_ONE_CLICK_HEADERS"]["status"], "PASS")
        only = {"mail.ts": 'headers: {"List-Unsubscribe": "<mailto:u@example.com>"}'}
        self.assertEqual(run(only)["EMAIL_ONE_CLICK_HEADERS"]["status"], "NEEDS_REVIEW")
        sender = {"package.json": json.dumps({"dependencies": {"nodemailer": "6"}})}
        self.assertEqual(run(sender)["EMAIL_ONE_CLICK_HEADERS"]["status"], "NEEDS_REVIEW")
        self.assertEqual(run({"a.py": "print(1)"})["EMAIL_ONE_CLICK_HEADERS"]["status"], "NOT_FOUND")


class DataRightsAndAssetTests(unittest.TestCase):
    def test_deletion_routes(self):
        r = run({"server/routes.js": "router.delete('/api/me', auth, deleteSelf);"})
        self.assertEqual(r["DATA_DELETION"]["status"], "PASS")
        r = run({"app/api/account/route.ts": "export async function DELETE(req) {}"})
        self.assertEqual(r["DATA_DELETION"]["status"], "PASS")
        r = run({"app.py": "@app.route('/account', methods=['GET', 'DELETE'])\ndef account(): pass"})
        self.assertEqual(r["DATA_DELETION"]["status"], "PASS")

    def test_policy_text_is_not_a_deletion_route(self):
        r = run({"app/privacy/page.tsx": "<p>Send data deletion requests to [[LEGAL: privacy email]]</p>"})
        self.assertEqual(r["DATA_DELETION"]["status"], "NOT_FOUND")

    def test_fonts_need_licence_evidence(self):
        r = run({"public/fonts/Brand-Bold.woff2": b"\x00font"})
        self.assertEqual(r["ASSET_LICENSES"]["status"], "NEEDS_REVIEW")
        r = run({"public/fonts/inter/Inter-Regular.woff2": b"\x00font", "public/fonts/inter/OFL.txt": "SIL Open Font License 1.1"})
        self.assertEqual(r["ASSET_LICENSES"]["status"], "PASS")
        r = run({"public/fonts/Brand-Bold.woff2": b"\x00font", "ASSET-LICENSES.md": "| Brand | font | licence on file |"})
        self.assertEqual(r["ASSET_LICENSES"]["status"], "PASS")


class CopyTests(unittest.TestCase):
    def test_claims_and_testimonials(self):
        r = run({"src/Landing.tsx": """
const testimonials = [{ name: "Sam", quote: "Great" }];
<h1>AI-powered invoicing, 10x faster than spreadsheets</h1>
<p>Trusted by 10,000+ happy customers. Clinically proven calm.</p>
"""})
        self.assertEqual(r["CLAIMS_TO_SUBSTANTIATE"]["status"], "NEEDS_REVIEW")
        labels = {d.split(":")[0] for d in details(r["CLAIMS_TO_SUBSTANTIATE"])}
        self.assertTrue({"AI capability claim", "performance or savings figure", "health claim",
                         "customer-count or social-proof figure"} <= labels)
        self.assertEqual(r["REVIEWS_TESTIMONIALS"]["status"], "NEEDS_REVIEW")

    def test_plain_copy_passes(self):
        r = run({"src/Landing.tsx": "<h1>Send invoices and get paid</h1>"})
        self.assertEqual(r["CLAIMS_TO_SUBSTANTIATE"]["status"], "PASS")
        self.assertEqual(r["REVIEWS_TESTIMONIALS"]["status"], "PASS")


class ScopeAndCliTests(unittest.TestCase):
    def test_test_folders_skipped_unless_asked(self):
        files = {"tests/fixtures/page.html": '<img src="x.png">', "src/ok.html": '<img src="y.png" alt="Logo">'}
        self.assertEqual(run(files)["IMG_ALT"]["status"], "PASS")
        self.assertEqual(run(files, include_tests=True)["IMG_ALT"]["status"], "NEEDS_REVIEW")

    def test_deterministic_and_json(self):
        files = {"index.html": '<img src="a.png"><a href="/privacy">Privacy</a>', "emails/promo.html": "<p>Deal</p>"}
        with build(files) as root:
            first = legal_scan.scan(Path(root))
            second = legal_scan.scan(Path(root))
            self.assertEqual(first, second)
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                code = legal_scan.main(["--root", root, "--json"])
            self.assertEqual(code, 0)
            data = json.loads(buf.getvalue())
            self.assertEqual(len(data["checks"]), 16)
            self.assertTrue({c["status"] for c in data["checks"]} <= {"PASS", "NEEDS_REVIEW", "NOT_FOUND"})
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                strict = legal_scan.main(["--root", root, "--strict"])
            self.assertEqual(strict, 1)
            self.assertIn("not legal advice", buf.getvalue())
            self.assertIn("| PRIVACY_POLICY | 1 | NEEDS_REVIEW |", buf.getvalue())

    def test_bad_root(self):
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(legal_scan.main(["--root", "/nonexistent/legal-ready-root"]), 2)


if __name__ == "__main__":
    unittest.main()
