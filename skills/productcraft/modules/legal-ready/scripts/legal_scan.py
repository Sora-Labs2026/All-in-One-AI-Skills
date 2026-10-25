#!/usr/bin/env python3
"""ProductCraft Legal Ready: read-only scan for launch-readiness signals.

Looks through a local project for policy pages, a cookie consent mechanism,
third-party scripts and SDKs, images without alt text, pre-ticked consent
boxes, marketing email templates without an unsubscribe link, one-click
unsubscribe headers, a data deletion route, asset licence notes, unfilled
[[LEGAL: ...]] placeholders, claims that need evidence and hard-coded
testimonials.

General guidance, not legal advice. A PASS only means a signal was found in
source. It never means the product complies with a law. The scan does not
run the app, load pages or contact the network. Have a qualified lawyer
review the result.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from bisect import bisect_right
from pathlib import Path, PurePosixPath

VERSION = "1.0.0"
PASS, REVIEW, MISSING = "PASS", "NEEDS_REVIEW", "NOT_FOUND"

MAX_SIZE = 1024 * 1024
MAX_FILES = 20000
MAX_EVIDENCE_JSON = 50

SKIP_DIRS = {
    ".git", ".hg", ".svn", ".agents", ".claude", ".venv", "venv", "env",
    "node_modules", "bower_components", ".next", ".nuxt", ".svelte-kit", ".astro",
    "dist", "build", "out", "coverage", "__pycache__", ".pytest_cache", ".mypy_cache",
    "vendor", "target", ".turbo", ".cache", ".angular", ".idea", ".vscode", ".expo",
    "Pods", ".gradle", ".dart_tool", ".terraform", "storybook-static", ".output",
}
TEST_DIRS = {"test", "tests", "__tests__", "spec", "specs", "e2e", "cypress",
             "__mocks__", "fixtures", "__fixtures__", "testdata"}
TEST_FILE = re.compile(r"\.(?:test|spec|stories)\.[a-z0-9]+$", re.I)
LOCKFILES = {"package-lock.json", "yarn.lock", "pnpm-lock.yaml", "npm-shrinkwrap.json",
             "Podfile.lock", "pubspec.lock", "poetry.lock", "Gemfile.lock", "composer.lock",
             "Cargo.lock", "go.sum", "Pipfile.lock", "uv.lock"}
OWN_OUTPUT = {"legal-scan.json"}

MARKUP = {".html", ".htm", ".jsx", ".tsx", ".vue", ".svelte", ".astro", ".php", ".erb",
          ".hbs", ".handlebars", ".njk", ".liquid", ".twig", ".jinja", ".jinja2", ".j2",
          ".ejs", ".pug", ".cshtml", ".razor", ".mdx", ".mjml"}
CONTENT = MARKUP - {".jsx", ".tsx"} | {".md", ".markdown"}
SCRIPT = {".js", ".mjs", ".cjs", ".ts", ".mts", ".cts"}
BACKEND = {".py", ".rb", ".go", ".java", ".kt", ".kts", ".swift", ".dart", ".rs", ".cs",
           ".ex", ".exs", ".scala", ".m", ".mm", ".gradle"}
DATA = {".json", ".jsonc", ".yaml", ".yml", ".toml", ".xml", ".plist", ".txt", ".sql",
        ".prisma", ".graphql", ".env", ".ini", ".cfg", ".properties", ".xcprivacy"}
TEXT_SUFFIXES = MARKUP | CONTENT | SCRIPT | BACKEND | DATA | {".css", ".scss"}
CODE = MARKUP | SCRIPT | BACKEND
FONT_SUFFIXES = {".woff", ".woff2", ".ttf", ".otf", ".eot"}
EXTENSIONLESS = {"Podfile", "Gemfile", "Cartfile", "Pipfile", "Dockerfile", "CREDITS",
                 "NOTICE", "LICENSE", "LICENCE", "COPYING", "ATTRIBUTION", "ATTRIBUTIONS",
                 "THIRD_PARTY_NOTICES", "OFL"}
MANIFESTS = re.compile(r"^(?:package\.json|requirements[\w.-]*\.txt|pyproject\.toml|Pipfile|"
                       r"Gemfile|Podfile|Cartfile|Package\.swift|pubspec\.yaml|composer\.json|"
                       r"go\.mod|build\.gradle(?:\.kts)?|libs\.versions\.toml)$")
I18N_DIRS = {"locales", "locale", "i18n", "lang", "langs", "messages", "translations", "intl"}
DOC_NAMES = re.compile(r"^(?:readme|changelog|contributing|license|licence|code_of_conduct|security)\b", re.I)

# --------------------------------------------------------------------------- vendors
# Detection data: (category, script or API domains, package names, call patterns).
# The report keys each entry by its first domain, or its first package when it has no domain.
VENDORS = [
    ("analytics", ["google-analytics.com", "analytics.google.com"],
     ["react-ga", "react-ga4", "vue-gtag", "ngx-google-analytics", "@react-native-firebase/analytics",
      "firebase_analytics", "FirebaseAnalytics", "firebase-analytics"], [r"firebase/analytics"]),
    ("tag-manager", ["googletagmanager.com"], ["react-gtm-module", "@next/third-parties"],
     [r"\bgtag\s*\(", r"\bdataLayer\.push\s*\("]),
    ("advertising", ["googleadservices.com", "doubleclick.net", "googlesyndication.com", "adservice.google.com"],
     ["react-native-google-mobile-ads", "google_mobile_ads", "Google-Mobile-Ads-SDK", "play-services-ads"], []),
    ("advertising", ["connect.facebook.net", "facebook.com/tr"],
     ["react-facebook-pixel", "react-native-fbsdk-next", "facebook_app_events", "FBSDKCoreKit", "FacebookCore",
      "facebook-android-sdk"], [r"\bfbq\s*\("]),
    ("advertising", ["analytics.tiktok.com"], [], [r"\bttq\.(?:track|page|load)\s*\("]),
    ("advertising", ["snap.licdn.com", "px.ads.linkedin.com"], [], [r"\blintrk\s*\("]),
    ("advertising", ["static.ads-twitter.com", "analytics.twitter.com"], [], [r"\btwq\s*\("]),
    ("advertising", ["sc-static.net", "tr.snapchat.com"], [], [r"\bsnaptr\s*\("]),
    ("advertising", ["s.pinimg.com/ct", "ct.pinterest.com"], [], [r"\bpintrk\s*\("]),
    ("advertising", ["bat.bing.com"], [], [r"\buetq\b"]),
    ("advertising", ["redditstatic.com/ads", "alb.reddit.com"], [], [r"\brdt\s*\("]),
    ("advertising", ["amazon-adsystem.com"], [], []),
    ("advertising", ["static.criteo.net"], [], []),
    ("session-replay", ["clarity.ms"], ["@microsoft/clarity"], []),
    ("session-replay", ["static.hotjar.com", "script.hotjar.com"], ["@hotjar/browser", "react-hotjar"], []),
    ("session-replay", ["edge.fullstory.com"], ["@fullstory/browser", "@fullstory/react-native"], []),
    ("session-replay", ["cdn.logrocket.io", "cdn.lr-ingest.io"], ["logrocket"], []),
    ("session-replay", ["cdn.mouseflow.com"], [], []),
    ("analytics", ["cdn.segment.com", "api.segment.io"],
     ["@segment/analytics-next", "@segment/analytics-node", "analytics-node", "@segment/analytics-react-native"], []),
    ("analytics", ["cdn.mxpnl.com", "api-js.mixpanel.com", "api.mixpanel.com"],
     ["mixpanel-browser", "mixpanel", "mixpanel-react-native", "mixpanel_flutter", "Mixpanel-swift",
      "mixpanel-android"], []),
    ("analytics", ["cdn.amplitude.com", "api2.amplitude.com"],
     ["@amplitude/analytics-browser", "@amplitude/analytics-react-native", "amplitude-js", "amplitude_flutter"], []),
    ("analytics", ["app.posthog.com", "us.i.posthog.com", "eu.i.posthog.com"],
     ["posthog-js", "posthog-node", "posthog-react-native", "posthog"], []),
    ("analytics", ["cdn.heapanalytics.com"], [], []),
    ("analytics", ["plausible.io"], [], []),
    ("analytics", ["cdn.usefathom.com"], ["fathom-client"], []),
    ("analytics", [], ["@vercel/analytics", "@vercel/speed-insights"], []),
    ("analytics", ["matomo.cloud"], [], [r"\b_paq\.push\s*\("]),
    ("attribution", ["appsflyer.com"], ["react-native-appsflyer", "appsflyer_sdk", "AppsFlyerFramework", "af-android-sdk"], []),
    ("attribution", ["adjust.com"], ["react-native-adjust", "adjust_sdk", "com.adjust.sdk"], []),
    ("attribution", ["branch.io"], ["react-native-branch", "flutter_branch_sdk", "io.branch.sdk.android"], []),
    ("chat", ["widget.intercom.io", "js.intercomcdn.com"],
     ["@intercom/messenger-js-sdk", "react-use-intercom", "@intercom/intercom-react-native"], []),
    ("chat", ["client.crisp.chat"], [], []),
    ("chat", ["embed.tawk.to"], [], []),
    ("chat", ["js.driftt.com"], [], []),
    ("chat", ["static.zdassets.com"], [], []),
    ("marketing-automation", ["js.hs-scripts.com", "js.hsforms.net", "js.hs-analytics.net"], ["@hubspot/api-client"],
     [r"\b_hsq\b"]),
    ("marketing-automation", ["chimpstatic.com", "list-manage.com"], ["@mailchimp/mailchimp_marketing"], []),
    ("marketing-automation", ["static.klaviyo.com"], [], []),
    ("marketing-automation", [], ["@braze/web-sdk", "@braze/react-native-sdk"], []),
    ("push-messaging", ["cdn.onesignal.com"], ["react-onesignal", "react-native-onesignal", "onesignal_flutter", "com.onesignal"], []),
    ("ab-testing", ["cdn.optimizely.com"], ["@optimizely/optimizely-sdk", "@optimizely/react-sdk"], []),
    ("ab-testing", ["visualwebsiteoptimizer.com"], [], []),
    ("feature-flags", [], ["launchdarkly-js-client-sdk", "launchdarkly-react-client-sdk"], []),
    ("error-monitoring", ["browser.sentry-cdn.com", "ingest.sentry.io"],
     ["@sentry/browser", "@sentry/react", "@sentry/nextjs", "@sentry/vue", "@sentry/node", "@sentry/react-native",
      "sentry-sdk", "sentry_flutter"], []),
    ("error-monitoring", ["datadoghq-browser-agent.com"],
     ["@datadog/browser-rum", "@datadog/browser-logs", "@datadog/mobile-react-native"], []),
    ("error-monitoring", ["js-agent.newrelic.com"], [], []),
    ("error-monitoring", [], ["@bugsnag/js", "@bugsnag/react-native"], []),
    ("fonts-cdn", ["fonts.googleapis.com", "fonts.gstatic.com"], [], []),
    ("fonts-cdn", ["use.typekit.net"], [], []),
    ("embed", ["youtube.com/embed", "youtube.com/iframe_api"], ["react-youtube"], []),
    ("embed", ["youtube-nocookie.com"], [], []),
    ("embed", ["player.vimeo.com"], [], []),
    ("embed", ["maps.googleapis.com", "google.com/maps/embed"], ["@react-google-maps/api"], []),
    ("social", ["platform.twitter.com"], [], []),
    ("security", ["google.com/recaptcha", "gstatic.com/recaptcha", "recaptcha.net"],
     ["react-google-recaptcha", "react-google-recaptcha-v3"], []),
    ("security", ["hcaptcha.com"], ["@hcaptcha/react-hcaptcha"], []),
    ("security", ["challenges.cloudflare.com"], [], []),
    ("payments", ["js.stripe.com", "checkout.stripe.com"],
     ["@stripe/stripe-js", "@stripe/react-stripe-js", "stripe", "@stripe/stripe-react-native", "flutter_stripe"], []),
    ("payments", ["paypal.com/sdk", "paypalobjects.com"], ["@paypal/react-paypal-js", "@paypal/paypal-js"], []),
    ("payments", ["cdn.paddle.com"], ["@paddle/paddle-js", "@paddle/paddle-node-sdk"], []),
    ("payments", ["app.lemonsqueezy.com", "assets.lemonsqueezy.com"], ["@lemonsqueezy/lemonsqueezy.js"], []),
    ("payments", ["js.braintreegateway.com"], ["braintree", "braintree-web"], []),
    ("payments", ["checkout.razorpay.com"], ["razorpay", "react-native-razorpay"], []),
    ("payments", [],
     ["react-native-iap", "expo-in-app-purchases", "react-native-purchases", "purchases_flutter", "in_app_purchase",
      "com.android.billingclient"], [r"\bimport\s+StoreKit\b"]),
    ("consent", ["cdn.cookielaw.org"], [], [r"\bOptanon\w*", r"\bOneTrust\."]),
    ("consent", ["consent.cookiebot.com", "consent.cookiebot.eu"], [], [r"\bCookiebot\."]),
    ("consent", ["usercentrics.eu"], ["@usercentrics/cmp-browser-sdk"], []),
    ("consent", ["sdk.privacy-center.org"], ["@didomi/react"], []),
    ("consent", ["cdn.iubenda.com"], [], []),
    ("consent", ["app.termly.io"], [], []),
    ("consent", ["cmp.osano.com"], [], []),
    ("consent", ["consentmanager.net"], [], []),
    ("consent", ["cmp.quantcast.com"], [], []),
    ("consent", ["cdn-cookieyes.com"], [], []),
    ("consent", [], ["vanilla-cookieconsent", "cookieconsent", "react-cookie-consent", "klaro", "tarteaucitronjs"], []),
    ("consent", [], ["user-messaging-platform", "GoogleUserMessagingPlatform"],
     [r"\bUserMessagingPlatform\b", r"\bAdsConsent\b"]),
]
NON_ESSENTIAL = {"analytics", "tag-manager", "advertising", "session-replay", "attribution", "chat",
                 "marketing-automation", "ab-testing", "embed", "social", "push-messaging"}

_domain_owner = {}
_package_owner = {}
_calls = []
VENDOR_CATEGORY = {}
for _cat, _domains, _packages, _patterns in VENDORS:
    _key = (_domains or _packages)[0]
    VENDOR_CATEGORY[_key] = _cat
    for _d in _domains:
        _domain_owner[_d.lower()] = _key
    for _p in _packages:
        _package_owner[_p.lower()] = _key
    for _pat in _patterns:
        _anchor = max(re.findall(r"[A-Za-z]{3,}", re.sub(r"\\[A-Za-z]", " ", _pat)), key=len).lower()
        _calls.append((_key, _anchor, re.compile(_pat)))
DOMAIN_RE = re.compile(r"(?<![\w-])(" + "|".join(
    re.escape(d) for d in sorted(_domain_owner, key=len, reverse=True)) + r")(?![\w-])", re.I)
DOMAIN_ANCHORS = tuple(sorted(_domain_owner))
PACKAGE_TEXT_RE = re.compile(r"(?<![\w.@/-])(" + "|".join(
    re.escape(p) for p in sorted(_package_owner, key=len, reverse=True)) + r")(?![\w-])", re.I)

# --------------------------------------------------------------------------- page families
PAGE_DIRS = {"pages", "app", "routes", "views", "templates", "screens", "content", "legal",
             "policies", "policy", "public", "static", "site", "www", "docs"}
NON_PAGE_PARENTS = {"lib", "libs", "utils", "util", "helpers", "hooks", "services", "middleware",
                    "store", "stores", "models", "schemas", "types", "config", "controllers", "server"}
HARD_EXCLUDE = {"api", "migrations"}

FAMILIES = {
    "privacy": (
        r"privacy-(?:policy|notice|statement)|datenschutz\w*",
        r"privacy",
        r"privacy(?:[-_]?(?:policy|notice|statement))?|datenschutz\w*",
    ),
    "terms": (
        r"terms-of-(?:service|use)|terms-and-conditions|terms-conditions|eula|user-agreement|agb|conditions-of-use",
        r"terms|tos|legal-terms|conditions",
        r"terms(?:[-_]?(?:of[-_]?(?:service|use)|and[-_]?conditions|conditions))?|tos|eula|agb",
    ),
    "refund": (
        r"(?:refunds?|returns?|cancellations?)-policy|refunds?-and-(?:returns?|cancellations?)|"
        r"returns?-and-refunds?|cancellations?-and-refunds?|widerruf\w*",
        r"refunds?|returns?|cancellations?|money-back",
        r"(?:refunds?|returns?|cancellations?)(?:[-_]?policy)?|refunds?[-_]and[-_](?:returns?|cancellations?)|"
        r"returns?[-_]and[-_]refunds?|widerruf\w*",
    ),
    "cookie": (
        r"cookies?-(?:policy|notice|statement|declaration)",
        r"cookies?",
        r"cookies?(?:[-_]?(?:policy|notice|statement|declaration))?",
    ),
    "contact": (
        r"imprint|impressum|legal-notice|contact-us|mentions-legales|aviso-legal",
        r"contact|support",
        r"contact(?:[-_]?us)?|imprint|impressum|legal[-_]?notice",
    ),
}
FAMILY_ANCHORS = {
    "privacy": ("privacy", "datenschutz"),
    "terms": ("terms", "tos", "eula", "agb"),
    "refund": ("refund", "return", "cancel", "widerruf", "money-back"),
    "cookie": ("cookie",),
    "contact": ("contact", "imprint", "impressum", "legal", "support"),
}
FAMILY_RES = {}
for _fam, (_strong, _weak, _route) in FAMILIES.items():
    FAMILY_RES[_fam] = (
        re.compile(rf"(?:{_strong})"),
        re.compile(rf"(?:{_weak})"),
        re.compile(rf"""["'`](?:/(?:[\w.\[\]:-]+/){{0,3}}(?:{_route})/?|(?:[\w.-]+/){{0,2}}(?:{_route})/)"""
                   rf"""(?:\.html?)?(?:[?#][^"'`\s]*)?["'`]""", re.I),
        re.compile(rf"""["'`(](https?://[^"'`\s)]*?(?<![a-z])(?:{_route})(?![a-z])[^"'`\s)]*)["'`)]""", re.I),
    )

LEGAL_PLACEHOLDER = re.compile(r"\[\[\s*LEGAL\s*:[^\]\n]{0,200}\]\]")
GENERIC_PLACEHOLDER = re.compile(
    r"lorem ipsum|\bTBD\b|\bTODO\b|\[\s*(?:insert|enter|your company|company name|business name|"
    r"company|address|effective date|date|email|jurisdiction|country|state)\b[^\]\n]{0,40}\](?!\()", re.I)

# --------------------------------------------------------------------------- other patterns
CONSENT_EXTRA = [
    ("TCF consent API (__tcfapi)", re.compile(r"__tcfapi")),
    ("GPP consent API (__gpp)", re.compile(r"__gpp\b")),
    ("tag consent-mode call", re.compile(r"gtag\(\s*['\"]consent['\"]")),
    ("Consent component", re.compile(
        r"\b(?:Cookie|Consent)(?:Consent|Banner|Notice|Manager|Preferences|Modal|Dialog|Bar|Settings)\b|"
        r"\bcookie[-_](?:consent|banner|notice|preferences)\b|\bconsent[-_](?:banner|manager|preferences|modal|dialog)\b")),
]
CONSENT_FILE = re.compile(r"(?:^|-)(?:cookie|consent)-(?:consent|banner|notice|manager|preferences|modal|dialog|bar|settings)(?:$|-)")
REJECT_WORDS = re.compile(r"reject|decline|deny|refuse|necessary only|only necessary|essential only|"
                          r"only essential|ablehnen|refuser|rechazar", re.I)
GPC_RE = re.compile(r"globalPrivacyControl|sec-gpc|\.well-known/gpc\.json", re.I)
CONSENT_LOG_RE = re.compile(r"consent[-_]?(?:log|record|receipt|event|history)s?", re.I)
CONSENT_DEFAULT_RE = re.compile(r"gtag\(\s*['\"]consent['\"]\s*,\s*['\"]default['\"]\s*,\s*\{([^}]{0,800})\}", re.S)
GRANTED_RE = re.compile(r"(?:ad_storage|analytics_storage|ad_user_data|ad_personalization)['\"]?\s*:\s*['\"]granted['\"]")

CHECKBOX_TAG = re.compile(r"<(input|Checkbox|Switch|Toggle|ToggleSwitch|Form\.Check)(?=[\s/>])")
TYPE_CHECKBOX = re.compile(r"""type\s*=\s*\{?\s*["'`](?:checkbox|switch)["'`]""", re.I)
CHECKED_BARE = re.compile(r"(?<![\w:.-])(?:checked|defaultChecked|isChecked|defaultIsChecked|isSelected|defaultSelected)(?=\s|/|>|$)")
CHECKED_VALUE = re.compile(r"(?<![\w:.-])(?:checked|defaultChecked|isChecked|defaultIsChecked|isSelected|defaultSelected)"
                           r"\s*=\s*(?:\"(?:checked|true)?\"|'(?:checked|true)?'|\{\s*true\s*\})")
CONSENT_WORDS = re.compile(
    r"consent|newsletter|marketing|subscribe|opt[-_ ]?in|offers|promotion|partners|third[- ]part|"
    r"send me|email me|keep me (?:posted|updated|informed)|share my|personali[sz]ed|terms|privacy|agree|"
    r"analytics|cookies?\b|tracking|advertis|statistic", re.I)
NOT_CONSENT = re.compile(r"remember me|keep me (?:signed|logged) in|stay (?:signed|logged) in|show password", re.I)
ATTR_TEXT = re.compile(r"""(?:name|id|aria-label|label|value)\s*=\s*(?:"([^"]*)"|'([^']*)'|\{\s*["'`]([^"'`]*)["'`]\s*\})""")
# Field names that hold a consent choice; flags such as requireConsent or showConsentBanner are excluded.
NAMES = (r"(?!(?:require|requires|needs|show|has|is|enable|enabled|ask|collect)(?-i:[A-Z_]))"
         r"\w*(?:marketing|newsletter|opt_?in|promo\w*|consent)\w*")
STATE_DEFAULTS = [
    re.compile(rf"\[\s*{NAMES}\s*,\s*\w+\s*\]\s*=\s*(?:React\.)?useState(?:<[^>]*>)?\(\s*(true|false)\s*\)", re.I),
    re.compile(rf"\b{NAMES}\b[^\n]*BooleanField\([^)\n]*default\s*=\s*(True|False)", re.I),
    re.compile(rf"^\s*{NAMES}\s+Boolean\b[^\n]*@default\(\s*(true|false)\s*\)", re.I | re.M),
    re.compile(rf"\b{NAMES}\s+(?:BOOLEAN|BOOL|TINYINT\(1\))\b[^\n,]*\bDEFAULT\s+(TRUE|FALSE|1|0)\b", re.I),
    re.compile(rf"(?:@State\s+(?:private\s+)?var|\bvar|\blet|\bconst|\bbool|\bfinal\s+bool)\s+_?{NAMES}\s*(?::\s*\w+\s*)?=\s*(true|false)\b", re.I),
    re.compile(rf"\b{NAMES}\b[^\n]*mutableStateOf\(\s*(true|false)\s*\)", re.I),
    re.compile(rf"\b{NAMES}\b[^\n]{{0,80}}\b(?:checked|defaultChecked|default|initial|selected)\s*[:=]\s*(true|false)\b", re.I),
]
STATE_ANCHORS = ("marketing", "newsletter", "optin", "opt_in", "promo", "consent")
FORM_DEFAULTS_BLOCK = re.compile(r"(?:defaultValues|initialValues|initialState)\s*[:=]\s*\{([^{}]{0,800})\}")
FORM_DEFAULT_FIELD = re.compile(rf"\b({NAMES})\s*:\s*(true|false)\b", re.I)

EMAIL_DIR = re.compile(r"(?:^|-)(?:e?mails?|mailers?|newsletters?|campaigns?|email-templates)(?:$|-)")
EMAIL_NAME = re.compile(r"(?:^|-)(?:e?mail|newsletter|campaign)(?:$|-)")
EMAIL_TEMPLATE_SUFFIXES = {".html", ".htm", ".mjml", ".hbs", ".handlebars", ".njk", ".liquid", ".twig",
                           ".ejs", ".erb", ".jinja", ".jinja2", ".j2", ".pug", ".tsx", ".jsx", ".vue", ".txt"}
EMAIL_LIB_IMPORT = re.compile(r"""from\s+["']@react-email/|require\(\s*["']@react-email/|<mjml\b""")
MARKETING_NAME = re.compile(r"(?:^|[-/])(?:newsletters?|marketing|promo\w*|campaigns?|digest|announce\w*|offers?|"
                            r"deals?|sales?|weekly|monthly|product-updates?|news|win-?back|re-?engage\w*|drip|"
                            r"nurture|abandon\w*|cart|referral\w*|upsell|launch)(?:$|[-/])")
TRANSACTIONAL_NAME = re.compile(r"(?:^|[-/])(?:reset|password|verify|verification|confirm\w*|receipt|invoice|"
                                r"orders?|shipping|shipment|delivery|otp|code|magic|login|sign-?in|signin|security|"
                                r"alert|2fa|mfa|billing|payment|refund|account|invite|invitation)(?:$|[-/])")
UNSUBSCRIBE_RE = re.compile(
    r"unsubscribe|opt[- ]?out|email preferences|manage (?:your )?(?:email )?(?:preferences|subscriptions?)|"
    r"\*\|UNSUB\|\*|%unsubscribe\w*%|<%\s*asm_|abmelden|d[ée]sinscri|d[ée]sabonn|darse de baja", re.I)
EMAIL_SENDERS = {"nodemailer", "@sendgrid/mail", "postmark", "resend", "@aws-sdk/client-ses",
                 "@aws-sdk/client-sesv2", "mailgun.js", "mailgun-js", "@mailchimp/mailchimp_transactional",
                 "@getbrevo/brevo", "sib-api-v3-sdk", "@react-email/components", "react-email", "mjml",
                 "django-anymail", "sendgrid", "postmarker", "mailjet", "node-mailjet", "@sendgrid/client"}
EMAIL_CODE = re.compile(r"\bimport\s+smtplib\b|\bActionMailer\b|\bMail::(?:to|send)\b|\bPHPMailer\b|"
                        r"\bsend_mail\s*\(|\bEmailMessage\s*\(")
LIST_UNSUB = re.compile(r"List-Unsubscribe(?!-Post)", re.I)
LIST_UNSUB_POST = re.compile(r"List-Unsubscribe-Post|List-Unsubscribe=One-Click", re.I)

DELETION_RE = re.compile(
    r"(?i)\b(?:delete[-_ ]?(?:my[-_ ]?)?account|account[-_/ ]?delet(?:e|ion)|close[-_ ]?(?:my[-_ ]?)?account|"
    r"data[-_ ]?deletion|deletion[-_ ]?request|erase[-_ ]?(?:my[-_ ]?)?(?:data|account)|"
    r"right[-_ ]to[-_ ](?:be[-_ ]forgotten|erasure)|forget[-_ ]?me|dsar|data[-_ ]?subject[-_ ]?(?:access[-_ ]?)?request|"
    r"privacy[-_ ]?request)")
# Route declarations whose path is checked against SELF_PATH: `.delete("/path")`,
# `.route("/path", methods=[... "DELETE" ...])` and a routes-file line `delete "/path"`.
DELETE_ROUTE = re.compile(
    r"""\.delete\(\s*["'`]([^"'`\n]+)["'`]|"""
    r"""\.route\(\s*["']([^"'\n]+)["'][^\n]*methods\s*=\s*[\[(][^\])\n]*["']DELETE["']|"""
    r"""^\s*delete\s+["']([^"'\n]+)["']""", re.M)
NEXT_DELETE_HANDLER = re.compile(r"export\s+(?:async\s+)?function\s+DELETE\b|export\s+const\s+DELETE\b")
SELF_PATH = re.compile(r"(?:^|/)(?:me|account|accounts|profile|user|users)(?:/|$)")
ENTITY_RE = re.compile(r"(?:©|&copy;|\([cC]\))[^<>\n]{0,80}?\b(?:Inc|LLC|L\.L\.C|Ltd|Limited|GmbH|UG|AG|SAS|SARL|"
                       r"S\.A|S\.L|B\.V|N\.V|Pty|PLC|LLP|Oy|ApS|S\.r\.l|Pvt)\b")
ENTITY_ANCHORS = ("©", "&copy;", "(c)")
REG_ANCHORS = ("vat", "ust-idnr", "company", "registered", "registration", "handelsregister", "hrb", "sire",
               "abn", "gstin", "cin")
REG_RE = re.compile(r"\b(?:VAT(?: (?:no|number|ID|reg(?:istration)?))?|USt-IdNr|[Cc]ompany (?:no|number|registration)|"
                    r"[Rr]egistered (?:office|in|number)|[Rr]egistration (?:no|number)|Handelsregister|HRB|"
                    r"SIRE[NT]|ABN|GSTIN|CIN)\b")
EXPORT_RE = re.compile(
    r"(?i)\b(?:export[-_ ]?(?:my[-_ ]?)?(?:data|account)|data[-_ ]?export|download[-_ ]?(?:my[-_ ]?|your[-_ ]?)?data|"
    r"data[-_ ]?portability|takeout)\b")

LICENSE_NEAR_FONT = re.compile(r"^(?:ofl|license|licence|copying|notice|readme|fontlog)(?:[-_.].*)?$", re.I)
ASSET_INVENTORY = re.compile(
    r"^(?:third[-_ ]?party[-_ ]?(?:notices?|licen[cs]es?)|credits|attributions?|"
    r"asset[-_ ]?(?:licen[cs]es?|inventory|credits|sources)|acknowledg(?:e)?ments)(?:\.\w+)?$", re.I)

CLAIM_PATTERNS = [
    ("performance or savings figure", ("%", "x ", "×", "x faster", "x more"), re.compile(
        r"\b\d+(?:\.\d+)?\s?(?:%|x\b|×)\s*(?:faster|quicker|better|more|less|cheaper|higher|lower|increase|"
        r"improvement|boost|growth|savings?|reduction|fewer|accura\w+|conversions?|productiv\w+|roi)\b", re.I)),
    ("performance or savings figure", ("save", "cut", "reduce", "boost", "increase", "grow", "double", "triple"), re.compile(
        r"\b(?:save|saves|saving|cut|cuts|reduce|reduces|boost|boosts|increase|increases|grow|grows|"
        r"double|doubles|triple|triples)\b[^.<>\n]{0,30}?\b\d[\d,.]*\s?(?:%|x\b|×|hours?\b|minutes?\b)", re.I)),
    ("superlative", ("#1", "no.", "number one", "best", "world", "industry", "the fastest", "the cheapest",
                     "the most", "the leading"), re.compile(
        r"#1\b|\bno\.\s?1\b|\bnumber one\b|\bbest[- ]in[- ]class\b|\bworld'?s (?:best|leading|first|fastest|most)\b|"
        r"\bindustry[- ]leading\b|\bthe (?:fastest|cheapest|most accurate|most secure|leading) \w+", re.I)),
    ("absolute or security promise", ("guarantee", "risk", "100%", "unhackable", "bulletproof", "military",
                                      "bank", "zero"), re.compile(
        r"\bguaranteed?\b|\brisk[- ]free\b|\b100%\s+(?:secure|safe|private|accurate|uptime|guaranteed|"
        r"satisfaction|natural|effective)\b|\bunhackable\b|\bbulletproof\b|\bmilitary[- ]grade\b|"
        r"\bbank[- ](?:level|grade)\b|\bzero (?:risk|downtime|errors?|bugs?)\b", re.I)),
    ("health claim", ("clinically", "scientifically", "medically", "doctor", "cure", "treat", "heal",
                      "prevent", "diagnos", "fda"), re.compile(
        r"\b(?:clinically|scientifically|medically)[- ](?:proven|tested|validated)\b|\bdoctor[- ](?:approved|recommended)\b|"
        r"\b(?:cures?|treats?|heals?|prevents?|diagnos(?:e|es|is))\s+(?:\w+\s+){0,2}(?:disease|cancer|diabetes|"
        r"depression|anxiety|adhd|covid|illness|infection|insomnia|pain)\b|\bfda[- ](?:approved|cleared)\b", re.I)),
    ("compliance or certification claim", ("compliant", "certified", "approved", "ready"), re.compile(
        r"\b(?:gdpr|ccpa|cpra|hipaa|soc\s?2|iso\s?27001|pci(?:[- ]dss)?|wcag|ada|coppa)[- ](?:compliant|certified|"
        r"approved|ready)\b|\bfully compliant\b|\bcertified secure\b", re.I)),
    ("AI capability claim", ("ai", "artificial", "machine learning", "accura", "hallucination", "replace"), re.compile(
        r"\b(?:ai|artificial intelligence|machine learning)[- ](?:powered|driven|based)\b|"
        r"\b(?:99(?:\.\d+)?|100)%\s+accura(?:te|cy)\b|\bhallucination[- ]free\b|"
        r"\breplaces? (?:your |a |an )?(?:lawyer|doctor|accountant|therapist|developer|engineer|designer)s?\b", re.I)),
    ("customer-count or social-proof figure", ("trusted", "loved", "used by", "join", "+"), re.compile(
        r"\b(?:trusted by|loved by|used by|join(?:ed)?)\s+(?:over\s+|more than\s+)?\d[\d,.]*\s?(?:k|m)?\+?\s+"
        r"(?:\w+\s+)?(?:customers|users|teams|companies|businesses|developers|people|creators|brands)\b|"
        r"\b\d[\d,.]*\s?(?:k|m)?\+\s+(?:happy |satisfied )?(?:customers|users|teams|companies|businesses|"
        r"downloads|reviews)\b", re.I)),
    ("environmental claim", ("eco", "carbon", "climate", "net", "environment", "biodegradable", "sustainable"), re.compile(
        r"\b(?:eco[- ]friendly|carbon[- ]neutral|climate[- ]neutral|net[- ]zero|environmentally friendly|"
        r"biodegradable|sustainable)\b", re.I)),
]
TESTIMONIAL_ARRAY = re.compile(
    r"\b(?:const|let|var)\s+\w*(?:testimonials?|reviews?|quotes|endorsements)\w*\s*(?::[^=\n]{0,60})?=\s*\[(?!\s*\])", re.I)
TESTIMONIAL_FILE = re.compile(r"^(?:(?:customer-|user-|product-)?(?:testimonials?|reviews?)|endorsements)$")
RATING_LITERAL = re.compile(r"""["']?(?:ratingValue|reviewCount)["']?\s*:\s*["']?\d""")


# --------------------------------------------------------------------------- project model
class SourceFile:
    __slots__ = ("rel", "text", "suffix", "name", "parts", "_starts", "_low")

    def __init__(self, rel: str, text: str):
        self.rel = rel
        self.text = text
        p = PurePosixPath(rel)
        self.suffix = p.suffix.lower()
        self.name = p.name
        self.parts = p.parts
        self._starts = None
        self._low = None

    @property
    def low(self) -> str:
        if self._low is None:
            self._low = self.text.lower()
        return self._low

    def line_of(self, pos: int) -> int:
        if self._starts is None:
            self._starts = [0] + [m.end() for m in re.finditer(r"\n", self.text)]
        return bisect_right(self._starts, pos)


def find_lines(f: SourceFile, rx: re.Pattern, anchors):
    """Yield matches of `rx`, running it only on lines that contain a lowercase anchor.

    Substring search runs at C speed, so this keeps the scan fast on large
    projects. Every line-based pattern below needs one of its anchors to match."""
    low = f.low
    if len(low) != len(f.text):  # lowercasing changed offsets (rare Unicode); scan everything
        yield from rx.finditer(f.text)
        return
    spans = set()
    for a in anchors:
        i = low.find(a)
        while i != -1:
            start = low.rfind("\n", 0, i) + 1
            end = low.find("\n", i)
            end = len(low) if end == -1 else end
            spans.add((start, end))
            i = low.find(a, end)
    for start, end in sorted(spans):
        yield from rx.finditer(f.text, start, end)


def has_any(f: SourceFile, words) -> bool:
    return any(w in f.low for w in words)


def norm(token: str, strip_suffix: bool = True) -> str:
    """Lower-case kebab form: PrivacyPolicyScreen -> privacy-policy (suffix stripped)."""
    token = re.sub(r"([a-z0-9])([A-Z])", r"\1-\2", token)
    token = re.sub(r"[^a-z0-9]+", "-", token.lower()).strip("-")
    return re.sub(r"-(?:page|screen|view|route|component|template)$", "", token) if strip_suffix else token


COMMENT_RE = re.compile(r"<!--[\s\S]{0,20000}?-->|/\*[\s\S]{0,5000}?\*/")


def without_comments(text: str) -> str:
    """Blank out HTML and block comments, keeping offsets and line numbers intact."""
    return COMMENT_RE.sub(lambda m: re.sub(r"[^\n]", " ", m.group(0)), text)


def is_test_path(parts: tuple, name: str) -> bool:
    return any(p.lower() in TEST_DIRS for p in parts[:-1]) or bool(TEST_FILE.search(name))


def load_project(root: Path, include_tests: bool) -> dict:
    files, fonts, paths = [], [], []
    stats = {"files_scanned": 0, "files_skipped_too_large": 0, "truncated": False}
    for current, dirs, names in os.walk(root, followlinks=False):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS and not (Path(current) / d).is_symlink()
                         and (include_tests or d.lower() not in TEST_DIRS))
        for name in sorted(names):
            path = Path(current) / name
            if path.is_symlink() or not path.is_file():
                continue
            rel = path.relative_to(root).as_posix()
            parts = PurePosixPath(rel).parts
            if not include_tests and is_test_path(parts, name):
                continue
            paths.append(rel)
            suffix = path.suffix.lower()
            if suffix in FONT_SUFFIXES:
                fonts.append(rel)
                continue
            if name in LOCKFILES or name in OWN_OUTPUT or name.endswith(".map"):
                continue
            if suffix not in TEXT_SUFFIXES and name not in EXTENSIONLESS:
                continue
            if stats["files_scanned"] >= MAX_FILES:
                stats["truncated"] = True
                continue
            try:
                if path.stat().st_size > MAX_SIZE:
                    stats["files_skipped_too_large"] += 1
                    continue
                data = path.read_bytes()
            except OSError:
                continue
            if b"\x00" in data[:4096]:
                continue
            files.append(SourceFile(rel, data.decode("utf-8", errors="replace")))
            stats["files_scanned"] += 1
    return {"files": files, "fonts": sorted(fonts), "paths": sorted(paths), "stats": stats}


# --------------------------------------------------------------------------- helpers
def ev(f: SourceFile | str, line: int | None, detail: str) -> dict:
    return {"file": f.rel if isinstance(f, SourceFile) else f, "line": line, "detail": detail[:120]}


def result(cid, title, items, status, summary, evidence=(), notes=()):
    seen, unique = set(), []
    for e in sorted(evidence, key=lambda e: (e["file"], e["line"] or 0, e["detail"])):
        key = (e["file"], e["line"], e["detail"])
        if key not in seen:
            seen.add(key)
            unique.append(e)
    return {"id": cid, "title": title, "items": items, "status": status, "summary": summary,
            "evidence_count": len(unique), "evidence": unique[:MAX_EVIDENCE_JSON], "notes": list(notes)}


def iter_tags(text: str, opener: re.Pattern):
    """Yield (start, tag_text, tag_name) for tags whose opening matches `opener`.

    Walks to the closing '>' while skipping quoted strings and {...} expressions,
    so JSX arrow functions inside attributes do not end the tag early."""
    for m in opener.finditer(text):
        i, depth, quote, end = m.end(), 0, "", None
        limit = min(len(text), m.start() + 3000)
        while i < limit:
            c = text[i]
            if quote:
                if c == quote:
                    quote = ""
            elif c in "\"'`":
                quote = c
            elif c == "{":
                depth += 1
            elif c == "}":
                depth = max(0, depth - 1)
            elif c == ">" and depth == 0:
                end = i + 1
                break
            i += 1
        if end:
            yield m.start(), text[m.start():end], m.group(1) if m.groups() else ""


def strip_values(tag: str) -> str:
    out = re.sub(r'"[^"]*"|\'[^\']*\'|`[^`]*`', '""', tag)
    for _ in range(3):
        out = re.sub(r"\{[^{}]*\}", "{}", out)
    return out


def page_match(rel: str, family: str) -> bool:
    strong, weak = FAMILY_RES[family][0], FAMILY_RES[family][1]
    p = PurePosixPath(rel)
    suffix = p.suffix.lower()
    if suffix not in CONTENT | CODE:
        return False
    dirs = [d.lower() for d in p.parts[:-1]]
    if any(d in HARD_EXCLUDE for d in dirs):
        return False
    stem = p.name.split(".")[0]
    tokens = [norm(d) for d in p.parts[:-1]] + [norm(stem)]
    if any(strong.fullmatch(t) for t in tokens):
        return True
    if any(weak.fullmatch(t) for t in tokens):
        if dirs and dirs[-1] in NON_PAGE_PARENTS:
            return False
        if suffix in CONTENT:
            return True
        if any(d in PAGE_DIRS for d in dirs) or re.search(r"(?:page|screen|view)$", stem, re.I):
            return True
    return False


def is_copy_file(f: SourceFile) -> bool:
    if DOC_NAMES.match(f.name):
        return False
    if f.suffix in MARKUP or f.suffix in {".md", ".markdown"}:
        return True
    return f.suffix in {".json", ".yaml", ".yml"} and any(p.lower() in I18N_DIRS for p in f.parts[:-1])


# --------------------------------------------------------------------------- third parties
def package_json_deps(f: SourceFile):
    try:
        data = json.loads(f.text)
    except ValueError:
        return
    if not isinstance(data, dict):
        return
    for section in ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies"):
        deps = data.get(section)
        if isinstance(deps, dict):
            for dep in sorted(deps):
                yield section, str(dep)


def inventory(project: dict) -> list:
    hits: dict[str, list] = {}
    matched: dict[str, set] = {}

    def add(key, e, ident):
        hits.setdefault(key, []).append(e)
        matched.setdefault(key, set()).add(ident)

    for f in project["files"]:
        if MANIFESTS.match(f.name):
            if f.name == "package.json":
                for section, dep in package_json_deps(f):
                    key = _package_owner.get(dep.lower())
                    if key:
                        add(key, ev(f, None, f"package {dep} ({section})"), dep)
            else:
                for m in PACKAGE_TEXT_RE.finditer(f.text):
                    add(_package_owner[m.group(1).lower()], ev(f, f.line_of(m.start()), f"package {m.group(1)}"), m.group(1))
            continue
        if f.suffix in {".md", ".markdown", ".txt"}:
            continue
        for m in find_lines(f, DOMAIN_RE, DOMAIN_ANCHORS):
            domain = m.group(1).lower()
            add(_domain_owner[domain], ev(f, f.line_of(m.start()), f"domain {domain}"), domain)
        if f.suffix in CODE:
            for key, anchor, rx in _calls:
                for m in find_lines(f, rx, (anchor,)):
                    call = re.sub(r"\s+", "", m.group(0))[:40]
                    add(key, ev(f, f.line_of(m.start()), f"code {call}"), call)
    out = []
    for key in sorted(hits, key=lambda k: (VENDOR_CATEGORY[k], k)):
        items = sorted(hits[key], key=lambda e: (e["file"], e["line"] or 0, e["detail"]))
        out.append({"vendor_key": key, "matched": sorted(matched[key]), "category": VENDOR_CATEGORY[key],
                    "non_essential": VENDOR_CATEGORY[key] in NON_ESSENTIAL,
                    "signal_count": len(items), "locations": items[:10]})
    return out


# --------------------------------------------------------------------------- checks
def find_pages(project, family):
    route_re, external_re = FAMILY_RES[family][2], FAMILY_RES[family][3]
    anchors = FAMILY_ANCHORS[family]
    pages = [f for f in project["files"] if page_match(f.rel, family)]
    placeholders, routes, external = [], [], []
    for f in pages:
        for rx in (LEGAL_PLACEHOLDER, GENERIC_PLACEHOLDER):
            for m in rx.finditer(f.text):
                placeholders.append(ev(f, f.line_of(m.start()), f"placeholder {m.group(0)[:60]}"))
    for f in project["files"]:
        if f.suffix not in CODE | CONTENT | {".json"}:
            continue
        for m in find_lines(f, route_re, anchors):
            routes.append(ev(f, f.line_of(m.start()), f"route or link {m.group(0)[:60]}"))
        for m in find_lines(f, external_re, anchors):
            if not DOMAIN_RE.search(m.group(1)):  # a vendor script URL is not a policy link
                external.append(ev(f, f.line_of(m.start()), "external policy link"))
    return pages, placeholders, routes, external


def check_page(project, family, cid, title, items, extra_notes=()):
    pages, placeholders, routes, external = find_pages(project, family)
    notes = list(extra_notes)
    evidence = [ev(f, None, f"{family} page file") for f in pages]
    if pages and placeholders:
        return result(cid, title, items, REVIEW, f"Page found but {len(placeholders)} placeholder(s) are unfilled",
                      evidence + placeholders, notes)
    if pages:
        return result(cid, title, items, PASS, f"Page found ({len(pages)} file(s))", evidence + routes[:5], notes)
    if routes:
        notes.append("A route or link exists but no page file was found; confirm it renders real content (CMS or hosted page).")
        return result(cid, title, items, REVIEW, "Linked or routed, but no page file found", routes, notes)
    if external:
        notes.append("Only external links found; confirm the hosted page is current and covers this product.")
        return result(cid, title, items, REVIEW, "Only an external link found", external, notes)
    return result(cid, title, items, MISSING, "No page, route or link found", (), notes)


def check_business(project):
    cid, title, items = "BUSINESS_DETAILS", "Business identity and contact details", [16]
    pages, placeholders, routes, external = find_pages(project, "contact")
    identity = []
    for f in project["files"]:
        if not is_copy_file(f):
            continue
        for rx, anchors, label in ((ENTITY_RE, ENTITY_ANCHORS, "legal entity name near a copyright line"),
                                   (REG_RE, REG_ANCHORS, "registration or tax identifier label")):
            m = next(find_lines(f, rx, anchors), None)
            if m:
                identity.append(ev(f, f.line_of(m.start()), label))
    evidence = [ev(f, None, "contact or imprint page file") for f in pages] + identity
    notes = ["The scan cannot tell whether the name, address or numbers are correct; they must come from the owner."]
    if placeholders:
        return result(cid, title, items, REVIEW, f"{len(placeholders)} unfilled placeholder(s) on contact pages",
                      evidence + placeholders, notes)
    if pages and identity:
        return result(cid, title, items, PASS, "Contact page and legal identity text found", evidence, notes)
    if pages or identity or routes:
        missing = "legal entity or registration text" if (pages or routes) else "a contact or imprint page"
        return result(cid, title, items, REVIEW, f"Partial: no {missing} found", evidence + routes[:5], notes)
    return result(cid, title, items, MISSING, "No contact page or legal identity text found", (), notes)


def check_consent(project, third):
    title = "Cookie consent mechanism"
    evidence, problems, gpc, logs, custom_files = [], [], [], [], []
    for t in third:
        if t["category"] == "consent":
            evidence.extend(dict(e, detail=f"consent platform: {e['detail']}") for e in t["locations"][:3])
    for f in project["files"]:
        if f.suffix not in CODE | {".json"}:
            continue
        if CONSENT_FILE.search(norm(f.name.split(".")[0])):
            custom_files.append(f)
            evidence.append(ev(f, None, "consent component file"))
        if not has_any(f, ("consent", "cookie", "__tcfapi", "__gpp", "gpc")):
            continue
        for label, rx in CONSENT_EXTRA:
            m = rx.search(f.text)
            if m:
                evidence.append(ev(f, f.line_of(m.start()), label))
        for m in find_lines(f, GPC_RE, ("globalprivacycontrol", "sec-gpc", "gpc.json")):
            gpc.append(ev(f, f.line_of(m.start()), "Global Privacy Control handling"))
        m = next(find_lines(f, CONSENT_LOG_RE, ("consent",)), None)
        if m:
            logs.append(ev(f, f.line_of(m.start()), "consent record"))
        for m in (CONSENT_DEFAULT_RE.finditer(f.text) if "gtag" in f.low else ()):
            block = m.group(1)
            if GRANTED_RE.search(block) and "region" not in block:
                problems.append(ev(f, f.line_of(m.start()), "consent mode default is 'granted' for every region"))
    if custom_files and not any(REJECT_WORDS.search(f.text) for f in custom_files):
        problems.append(ev(custom_files[0], None, "no reject/decline option found in the consent component files"))
    trackers = sorted({t["matched"][0] for t in third if t["non_essential"]})
    notes = [("Consent records appear to be stored; check they hold time, choice, categories and versions."
              if logs else "No consent-record storage detected; you need to be able to show what each visitor chose.")]
    if not evidence:
        if trackers:
            notes.append("Non-essential third parties detected (" + ", ".join(trackers[:8]) +
                         "); where ePrivacy or PECR rules apply they need prior consent.")
        else:
            notes.append("No non-essential third parties detected; a banner may be unnecessary if only strictly necessary storage is used.")
        return result("COOKIE_CONSENT", title, [5], MISSING, "No consent mechanism found", gpc + problems, notes)
    if not gpc:
        problems.append(ev("(project)", None, "Global Privacy Control signal not handled"))
    if problems:
        return result("COOKIE_CONSENT", title, [5], REVIEW, f"Consent mechanism found; {len(problems)} issue(s) to review",
                      evidence + problems + gpc, notes)
    notes.append("Static signals only: check in a fresh browser profile that nothing non-essential loads before consent.")
    return result("COOKIE_CONSENT", title, [5], PASS, "Consent mechanism and GPC handling found", evidence + gpc + logs, notes)


def check_third_parties(third):
    title = "Third-party scripts and SDKs"
    if not third:
        return result("THIRD_PARTY_SCRIPTS", title, [8], MISSING, "No known third-party scripts or SDKs detected",
                      notes=["Tag managers and server-side tags can add vendors the source does not show; check the network panel."])
    evidence = [dict(t["locations"][0], detail=f"{', '.join(t['matched'][:3])} [{t['category']}]") for t in third]
    cats = sorted({t["category"] for t in third})
    return result("THIRD_PARTY_SCRIPTS", title, [8], REVIEW, f"{len(third)} vendor(s) detected ({', '.join(cats)})",
                  evidence, ["Never PASS: record what each vendor receives, its purpose and whether it waits for consent."])


IMG_HTML = re.compile(r"<(img)(?=[\s/>])", re.I)
IMG_JSX = re.compile(r"<(img)(?=[\s/>])")
IMG_COMPONENT = re.compile(r"<(Image|NuxtImg|NuxtPicture|nuxt-img)(?=[\s/>])")
IMG_COMPONENT_IMPORT = re.compile(r"""["']next/image["']|["']astro:assets["']""")
ALT_ATTR = re.compile(r"(?:^|[\s\"'}])(?::|v-bind:)?alt\s*(?==|\s|/|>|$)")
EMPTY_ALT = re.compile(r"""alt\s*=\s*(?:""|''|\{\s*(?:""|'')\s*\})""")
NAMED_OTHERWISE = re.compile(r"aria-label(?:ledby)?\s*=|role\s*=\s*[\"'](?:presentation|none)[\"']")


def check_img_alt(project):
    total, missing, decorative, unknown = 0, [], 0, 0
    for f in project["files"]:
        if f.suffix not in MARKUP | SCRIPT:
            continue
        openers = [IMG_JSX if f.suffix in {".jsx", ".tsx"} | SCRIPT else IMG_HTML]
        if f.suffix == ".vue" or IMG_COMPONENT_IMPORT.search(f.text):
            openers.append(IMG_COMPONENT)
        text = without_comments(f.text)
        for opener in openers:
            for start, tag, _ in iter_tags(text, opener):
                total += 1
                if ALT_ATTR.search(strip_values(tag)) or re.search(r"\{\s*alt\s*\}", tag):
                    decorative += bool(EMPTY_ALT.search(tag))
                    continue
                if NAMED_OTHERWISE.search(tag):
                    continue
                if re.search(r"\{\s*\.\.\.|v-bind\s*=", tag):
                    unknown += 1
                    continue
                missing.append(ev(f, f.line_of(start), "image without alt attribute"))
    notes = []
    if decorative:
        notes.append(f"{decorative} image(s) use empty alt (correct only for purely decorative images).")
    if unknown:
        notes.append(f"{unknown} image(s) take props from a spread; check them by hand.")
    notes.append("Presence only: the scan cannot judge whether alt text is meaningful.")
    title = "Images have alt text"
    if not total:
        return result("IMG_ALT", title, [13], MISSING, "No <img> or image components found", (), notes)
    if missing:
        return result("IMG_ALT", title, [13], REVIEW, f"{len(missing)} of {total} image(s) lack an alt attribute", missing, notes)
    return result("IMG_ALT", title, [13], PASS, f"All {total} image(s) have alt text or a role", (), notes)


def consent_context(text: str, start: int, tag: str) -> bool:
    attrs = " ".join("".join(groups) for groups in ATTR_TEXT.findall(tag))
    if CONSENT_WORDS.search(attrs):
        return True
    end = start + len(tag)
    after = text[end:end + 160]
    cut = re.search(r"<(?:input|Checkbox|Switch|button)\b", after)
    after = after[:cut.start()] if cut else after
    before = text[max(0, start - 160):start]
    cuts = list(re.finditer(r"<input\b|<button\b|</li>|</p>", before))
    before = before[cuts[-1].end():] if cuts else before
    near = before + " " + after
    if NOT_CONSENT.search(near):
        return False
    return bool(CONSENT_WORDS.search(near))


def check_prechecked(project):
    relevant, flagged = 0, []
    for f in project["files"]:
        if f.suffix not in CODE | {".sql", ".prisma"}:
            continue
        if f.suffix in MARKUP | SCRIPT:
            text = without_comments(f.text)
            for start, tag, name in iter_tags(text, CHECKBOX_TAG):
                if name == "input" and not TYPE_CHECKBOX.search(tag):
                    continue
                if not consent_context(text, start, tag):
                    continue
                relevant += 1
                if CHECKED_BARE.search(strip_values(tag)) or CHECKED_VALUE.search(tag):
                    flagged.append(ev(f, f.line_of(start), "consent-like checkbox is pre-checked"))
        if not has_any(f, STATE_ANCHORS):
            continue
        for rx in STATE_DEFAULTS:
            for m in find_lines(f, rx, STATE_ANCHORS):
                relevant += 1
                if m.group(1).lower() in {"true", "1"}:
                    flagged.append(ev(f, f.line_of(m.start()), "consent-like field defaults to true"))
        blocks = FORM_DEFAULTS_BLOCK.finditer(f.text) if has_any(f, ("defaultvalues", "initialvalues", "initialstate")) else ()
        for block in blocks:
            for m in FORM_DEFAULT_FIELD.finditer(block.group(1)):
                relevant += 1
                if m.group(2).lower() == "true":
                    flagged.append(ev(f, f.line_of(block.start(1) + m.start()), f"form default {m.group(1)}: true"))
    title = "Consent boxes start unticked"
    if flagged:
        return result("PRECHECKED_CONSENT", title, [6], REVIEW, f"{len(flagged)} pre-ticked or default-true consent field(s)",
                      flagged, ["Marketing, sharing and terms boxes must start unticked; a default of true in the data model counts too."])
    if relevant:
        return result("PRECHECKED_CONSENT", title, [6], PASS, f"{relevant} consent-like field(s), none pre-ticked")
    return result("PRECHECKED_CONSENT", title, [6], MISSING, "No consent checkboxes or consent fields found",
                  notes=["Consent fields built from a component library or a form schema may not be visible to the scan."])


def email_templates(project):
    out = []
    for f in project["files"]:
        if f.suffix not in EMAIL_TEMPLATE_SUFFIXES:
            continue
        dir_tokens = [norm(d) for d in f.parts[:-1]]
        stem = norm(f.name.split(".")[0])
        in_dir = any(EMAIL_DIR.search(t) for t in dir_tokens)
        lib = bool(EMAIL_LIB_IMPORT.search(f.text)) or f.suffix == ".mjml"
        if f.suffix in {".tsx", ".jsx", ".vue"}:
            if not (lib or "emails" in dir_tokens):
                continue
        elif f.suffix == ".txt":
            if not in_dir:
                continue
        elif not (in_dir or lib or EMAIL_NAME.search(stem)):
            continue
        label = "/".join(dir_tokens[-1:] + [stem])
        if MARKETING_NAME.search(label):
            kind = "marketing"
        elif TRANSACTIONAL_NAME.search(label):
            kind = "transactional"
        else:
            kind = "unclassified"
        out.append((f, kind))
    return out


def check_unsubscribe(project, templates):
    title = "Unsubscribe link in marketing email"
    scoped = [(f, k) for f, k in templates if k != "transactional"]
    transactional = len(templates) - len(scoped)
    if not scoped:
        summary = f"Only transactional templates found ({transactional})" if transactional else "No email templates found"
        return result("EMAIL_UNSUBSCRIBE_LINK", title, [18], MISSING, summary,
                      notes=["Templates kept in an email provider's dashboard are not visible to this scan."])
    missing = [ev(f, None, f"{k} template without unsubscribe link") for f, k in scoped if not UNSUBSCRIBE_RE.search(f.text)]
    notes = ["Transactional templates were skipped; keep promotions out of them."] if transactional else []
    if any(k == "unclassified" for _, k in scoped):
        notes.append("Some templates could not be classified by name; treat them as marketing unless they are purely transactional.")
    if missing:
        return result("EMAIL_UNSUBSCRIBE_LINK", title, [18], REVIEW,
                      f"{len(missing)} of {len(scoped)} template(s) lack an unsubscribe link", missing, notes)
    return result("EMAIL_UNSUBSCRIBE_LINK", title, [18], PASS,
                  f"All {len(scoped)} marketing or unclassified template(s) contain an unsubscribe link", (), notes)


def check_one_click(project, templates):
    title = "One-click List-Unsubscribe headers"
    header, post, senders = [], [], []
    for f in project["files"]:
        if f.name == "package.json":
            senders.extend(ev(f, None, f"email package {dep}") for _, dep in package_json_deps(f) if dep in EMAIL_SENDERS)
            continue
        if MANIFESTS.match(f.name):
            for dep in sorted(EMAIL_SENDERS):
                if re.search(rf"(?<![\w@/.-]){re.escape(dep)}(?![\w-])", f.text):
                    senders.append(ev(f, None, f"email package {dep}"))
            continue
        if f.suffix not in CODE | DATA:
            continue
        if "list-unsubscribe" in f.low:
            header.extend(ev(f, f.line_of(m.start()), "List-Unsubscribe header") for m in LIST_UNSUB.finditer(f.text))
            post.extend(ev(f, f.line_of(m.start()), "List-Unsubscribe-Post one-click") for m in LIST_UNSUB_POST.finditer(f.text))
        m = next(find_lines(f, EMAIL_CODE, ("smtplib", "actionmailer", "mail::", "phpmailer", "send_mail", "emailmessage")), None)
        if m:
            senders.append(ev(f, f.line_of(m.start()), "email sending code"))
    if header and post:
        return result("EMAIL_ONE_CLICK_HEADERS", title, [18], PASS, "List-Unsubscribe and List-Unsubscribe-Post found",
                      header + post, ["Check a received message: both headers must be present and covered by the DKIM signature."])
    if header:
        return result("EMAIL_ONE_CLICK_HEADERS", title, [18], REVIEW,
                      "List-Unsubscribe found without the one-click POST header (RFC 8058)", header)
    if senders or templates:
        notes = ["Marketing or bulk mail needs these headers; some email providers add them, so check a received message."]
        if not any(k != "transactional" for _, k in templates):
            notes.append("If the product sends only transactional email, record this item as NOT_APPLICABLE in the report.")
        return result("EMAIL_ONE_CLICK_HEADERS", title, [18], REVIEW, "Email is sent but no List-Unsubscribe headers found in code",
                      senders, notes)
    return result("EMAIL_ONE_CLICK_HEADERS", title, [18], MISSING, "No email sending detected")


def check_deletion(project):
    policy_pages = {f.rel for f in project["files"]
                    if any(page_match(f.rel, fam) for fam in ("privacy", "terms", "cookie", "refund"))}
    deletion, export = [], []
    for f in project["files"]:
        if f.suffix not in CODE or f.rel in policy_pages:
            continue
        for m in find_lines(f, DELETION_RE, ("delet", "close", "erase", "right", "forget", "dsar", "subject", "privacy")):
            deletion.append(ev(f, f.line_of(m.start()), f"deletion signal {m.group(0)[:40]}"))
        for m in find_lines(f, DELETE_ROUTE, ("delete",)):
            route = next(g for g in m.groups() if g)
            if SELF_PATH.search(route.lower()):
                deletion.append(ev(f, f.line_of(m.start()), f"DELETE route {route[:40]}"))
        if SELF_PATH.search(f.rel.lower()):
            m = NEXT_DELETE_HANDLER.search(f.text)
            if m:
                deletion.append(ev(f, f.line_of(m.start()), "DELETE handler on an account path"))
        for m in find_lines(f, EXPORT_RE, ("export", "download", "portability", "takeout")):
            export.append(ev(f, f.line_of(m.start()), f"export signal {m.group(0)[:40]}"))
    notes = ["Access/export route: " + ("found" if export else "not found") + ".",
             "Presence only: verify identity checks, every data store, processors and deadlines by test."]
    title = "Data deletion (and export) route"
    if deletion:
        return result("DATA_DELETION", title, [20], PASS, "Account or data deletion route found", deletion + export[:5], notes)
    return result("DATA_DELETION", title, [20], MISSING, "No account or data deletion route found", export[:5], notes)


def check_assets(project):
    title = "Asset licence records"
    inventory_files = [f for f in project["files"] if ASSET_INVENTORY.match(f.name)
                       or any(p.lower() in {"licenses", "licences"} for p in f.parts[:-1])]
    inv_text = "\n".join(f.text.lower() for f in inventory_files)
    by_dir: dict[str, list] = {}
    for rel in project["paths"]:
        parent, _, name = rel.rpartition("/")
        by_dir.setdefault(parent, []).append(name)
    uncovered = []
    for font in project["fonts"]:
        parent = font.rpartition("/")[0]
        grand = parent.rpartition("/")[0] if "/" in parent else None
        covered = any(LICENSE_NEAR_FONT.match(n) for n in by_dir.get(parent, []))
        if not covered and grand:  # an OFL or LICENSE file one level up also counts
            covered = any(re.match(r"^(?:ofl|license|licence)\b", n, re.I) for n in by_dir.get(grand, []))
        family = re.split(r"[-_ .]", PurePosixPath(font).stem)[0].lower()
        if not covered and len(family) >= 3 and re.search(rf"\b{re.escape(family)}\b", inv_text):
            covered = True
        if not covered:
            uncovered.append(ev(font, None, "bundled font without a licence file or inventory entry"))
    evidence = [ev(f, None, "asset licence inventory") for f in inventory_files]
    notes = ["Only fonts are checked automatically; images, icons, video and music need inventory rows too."]
    if uncovered:
        return result("ASSET_LICENSES", title, [19], REVIEW,
                      f"{len(uncovered)} of {len(project['fonts'])} bundled font file(s) lack licence evidence",
                      uncovered + evidence, notes)
    if inventory_files or project["fonts"]:
        return result("ASSET_LICENSES", title, [19], PASS,
                      f"Licence evidence found ({len(inventory_files)} inventory file(s); "
                      f"{len(project['fonts'])} font file(s) covered)", evidence, notes)
    return result("ASSET_LICENSES", title, [19], MISSING, "No asset inventory or bundled fonts found", (), notes)


def check_placeholders(project):
    title = "No unfilled [[LEGAL: ...]] placeholders"
    hits = [ev(f, f.line_of(m.start()), m.group(0)[:80]) for f in project["files"] if "[[" in f.text
            for m in LEGAL_PLACEHOLDER.finditer(f.text)]
    if hits:
        return result("UNRESOLVED_PLACEHOLDERS", title, [1, 2, 3, 4, 16], REVIEW,
                      f"{len(hits)} unfilled placeholder(s): launch blockers until the owner supplies the facts", hits)
    return result("UNRESOLVED_PLACEHOLDERS", title, [1, 2, 3, 4, 16], PASS, "No [[LEGAL: ...]] placeholders found")


def check_claims(project):
    title = "Claims that need evidence"
    copy = [f for f in project["files"] if is_copy_file(f)]
    hits = [ev(f, f.line_of(m.start()), f"{label}: {m.group(0).strip()[:60]}")
            for f in copy for label, anchors, rx in CLAIM_PATTERNS for m in find_lines(f, rx, anchors)]
    if not copy:
        return result("CLAIMS_TO_SUBSTANTIATE", title, [12], MISSING, "No user-facing copy files found")
    if hits:
        return result("CLAIMS_TO_SUBSTANTIATE", title, [12], REVIEW, f"{len(hits)} claim-shaped phrase(s) need evidence or rewording",
                      hits, ["Keep a claim only with evidence on file, and record it in the claims register."])
    return result("CLAIMS_TO_SUBSTANTIATE", title, [12], PASS, "No claim-shaped phrases found in copy")


def check_testimonials(project):
    title = "Reviews and testimonials are real"
    files = [f for f in project["files"] if is_copy_file(f) or f.suffix in SCRIPT]
    hits = []
    for f in files:
        hits.extend(ev(f, f.line_of(m.start()), "hard-coded testimonial or review list")
                    for m in find_lines(f, TESTIMONIAL_ARRAY, ("testimonial", "review", "quotes", "endorsement")))
        hits.extend(ev(f, f.line_of(m.start()), "hard-coded rating or review count")
                    for m in find_lines(f, RATING_LITERAL, ("ratingvalue", "reviewcount")))
    for f in project["files"]:
        if f.suffix in {".json", ".yaml", ".yml", ".md", ".mdx"} and TESTIMONIAL_FILE.search(norm(f.name.split(".")[0], strip_suffix=False)):
            hits.append(ev(f, None, "testimonial or review data file"))
    if not files:
        return result("REVIEWS_TESTIMONIALS", title, [11], MISSING, "No user-facing copy or script files found")
    if hits:
        return result("REVIEWS_TESTIMONIALS", title, [11], REVIEW, f"{len(hits)} hard-coded review or testimonial signal(s)", hits,
                      ["Trace every shown review, rating and testimonial to a real, permitted source; delete invented ones."])
    return result("REVIEWS_TESTIMONIALS", title, [11], PASS, "No hard-coded reviews, ratings or testimonials found")


# --------------------------------------------------------------------------- orchestration
def scan(root: Path, include_tests: bool = False) -> dict:
    root = Path(root).resolve()
    if not root.is_dir():
        raise ValueError(f"Not a directory: {root}")
    project = load_project(root, include_tests)
    third = inventory(project)
    payments = sorted({t["matched"][0] for t in third if t["category"] == "payments"})
    trackers = [t for t in third if t["non_essential"]]
    refund_note = (["Payment code detected (" + ", ".join(payments) + "), so a refund and cancellation policy likely applies."]
                   if payments else ["No payment code detected; this may not apply."])
    cookie_note = ["Non-essential third parties detected; the cookie policy must list them."] if trackers else []
    templates = email_templates(project)
    checks = [
        check_page(project, "privacy", "PRIVACY_POLICY", "Privacy policy", [1]),
        check_page(project, "terms", "TERMS_OF_SERVICE", "Terms of service", [2]),
        check_page(project, "refund", "REFUND_POLICY", "Refund and cancellation policy", [3], refund_note),
        check_page(project, "cookie", "COOKIE_POLICY", "Cookie policy", [4], cookie_note),
        check_consent(project, third),
        check_prechecked(project),
        check_third_parties(third),
        check_testimonials(project),
        check_claims(project),
        check_img_alt(project),
        check_business(project),
        check_unsubscribe(project, templates),
        check_one_click(project, templates),
        check_assets(project),
        check_deletion(project),
        check_placeholders(project),
    ]
    counts = {s: sum(1 for c in checks if c["status"] == s) for s in (PASS, REVIEW, MISSING)}
    return {
        "tool": "productcraft-legal-ready-scan",
        "version": VERSION,
        "root": str(root),
        "disclaimer": ("General guidance, not legal advice. Statuses describe source-code signals only; "
                       "they do not establish compliance with any law. Have a qualified lawyer review."),
        "status_legend": {
            PASS: "Expected signal found, or no problem candidates in the files inspected.",
            REVIEW: "Something to inspect: a candidate problem, a partial signal, or data a person must judge.",
            MISSING: "No signal found, or nothing of that kind to inspect (see the summary).",
        },
        "stats": dict(project["stats"], include_tests=include_tests, status_counts=counts),
        "checks": checks,
        "third_parties": third,
    }


def cell(text: str) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ")


def render_table(report: dict, max_evidence: int) -> str:
    lines = ["Legal Ready scan: general guidance, not legal advice.",
             f"Root: {report['root']}  Files scanned: {report['stats']['files_scanned']}"
             + ("  (truncated)" if report["stats"]["truncated"] else ""), "",
             "| Check | Items | Status | Summary |", "|---|---|---|---|"]
    for c in report["checks"]:
        items = ", ".join(str(i) for i in c["items"])
        lines.append(f"| {c['id']} | {items} | {c['status']} | {cell(c['summary'])} |")
    lines += ["", "Details"]
    for c in report["checks"]:
        if not c["evidence"] and not c["notes"]:
            continue
        lines.append(f"- {c['id']} ({c['status']})")
        for e in c["evidence"][:max_evidence]:
            loc = e["file"] + (f":{e['line']}" if e["line"] else "")
            lines.append(f"    {loc}  {e['detail']}")
        if c["evidence_count"] > max_evidence:
            lines.append(f"    ... {c['evidence_count'] - max_evidence} more in the JSON report")
        for n in c["notes"]:
            lines.append(f"    note: {n}")
    if report["third_parties"]:
        lines += ["", "Third parties (record data shared, purpose and consent gate for each)",
                  "| Detected as | Category | Needs consent? | Signals | First location |", "|---|---|---|---|---|"]
        for t in report["third_parties"]:
            first = t["locations"][0]
            loc = first["file"] + (f":{first['line']}" if first["line"] else "")
            gate = "likely" if t["non_essential"] else "check"
            lines.append(f"| {cell(', '.join(t['matched'][:3]))} | {t['category']} | {gate} | {t['signal_count']} | {cell(loc)} |")
    lines += ["", report["disclaimer"]]
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="Read-only scan for legal launch-readiness signals (general guidance, not legal advice).")
    ap.add_argument("--root", default=".", help="project folder to scan (default: current folder)")
    ap.add_argument("--json", action="store_true", help="print the JSON report instead of the table")
    ap.add_argument("--json-out", help="also write the JSON report to this file")
    ap.add_argument("--include-tests", action="store_true", help="also scan test, spec and fixture folders")
    ap.add_argument("--max-evidence", type=int, default=5, help="evidence lines per check in the table (default 5)")
    ap.add_argument("--strict", action="store_true", help="exit with status 1 when any check is not PASS")
    opts = ap.parse_args(argv)
    try:
        report = scan(Path(opts.root), include_tests=opts.include_tests)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    text = json.dumps(report, indent=2, ensure_ascii=False)
    print(text if opts.json else render_table(report, max(0, opts.max_evidence)))
    if opts.json_out:
        out = Path(opts.json_out).expanduser()
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text + "\n", encoding="utf-8")
        if not opts.json:
            print(f"JSON report written: {out}")
    if opts.strict and any(c["status"] != PASS for c in report["checks"]):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
