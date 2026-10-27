"""Tests for har_summary.py: aggregation, redaction and exit codes."""
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import har_summary  # noqa: E402


def make_har(entries):
    return {"log": {"version": "1.2", "entries": entries}}


def entry(method="GET", url="https://api.example.com/v1/items", status=200,
          mime="application/json", req_headers=None, resp_headers=None,
          req_cookies=None, resp_cookies=None, post=None):
    req = {"method": method, "url": url, "headers": req_headers or [],
           "cookies": req_cookies or []}
    if post is not None:
        req["postData"] = post
    return {
        "request": req,
        "response": {"status": status, "headers": resp_headers or [],
                     "cookies": resp_cookies or [],
                     "content": {"mimeType": mime}},
    }


def write_tmp(obj):
    fd, path = tempfile.mkstemp(suffix=".har")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        if isinstance(obj, str):
            fh.write(obj)
        else:
            json.dump(obj, fh)
    return path


class SummarizeTests(unittest.TestCase):
    def test_counts_by_host_method_status_mime(self):
        har = make_har([
            entry(method="GET", url="https://a.example.com/x", status=200, mime="text/html"),
            entry(method="POST", url="https://a.example.com/y", status=201, mime="application/json"),
            entry(method="GET", url="https://b.example.com/z", status=404, mime="application/json"),
            entry(method="GET", url="https://b.example.com/z", status=500, mime="text/html"),
        ])
        s = har_summary.summarize(har["log"]["entries"])
        self.assertEqual(s["entries"], 4)
        self.assertEqual(s["hosts"]["a.example.com"], 2)
        self.assertEqual(s["hosts"]["b.example.com"], 2)
        self.assertEqual(s["methods"]["GET"], 3)
        self.assertEqual(s["methods"]["POST"], 1)
        self.assertEqual(s["status_classes"]["2xx"], 2)
        self.assertEqual(s["status_classes"]["4xx"], 1)
        self.assertEqual(s["status_classes"]["5xx"], 1)
        self.assertEqual(s["mimes"]["application/json"], 2)

    def test_detects_auth_header_and_cookies(self):
        har = make_har([
            entry(req_headers=[{"name": "Authorization", "value": "Bearer SEEKRIT"}]),
            entry(req_headers=[{"name": "Cookie", "value": "session=abc"}]),
            entry(resp_headers=[{"name": "Set-Cookie", "value": "session=def"}]),
        ])
        s = har_summary.summarize(har["log"]["entries"])
        self.assertEqual(s["auth_header_requests"], 1)
        self.assertEqual(s["cookie_requests"], 1)
        self.assertEqual(s["set_cookie_responses"], 1)

    def test_secret_in_query_is_flagged_by_name_only(self):
        secret = "a" * 40
        har = make_har([
            entry(url="https://api.example.com/cb?code=%s&state=ok" % secret),
            entry(url="https://api.example.com/items?page=2"),
        ])
        s = har_summary.summarize(har["log"]["entries"])
        self.assertEqual(s["secret_in_url_count"], 1)
        self.assertIn("code", s["sensitive_param_names"])
        self.assertEqual(s["sensitive_param_names"]["code"], 1)

    def test_form_body_param_names_detected(self):
        post = {"mimeType": "application/x-www-form-urlencoded",
                "params": [{"name": "username", "value": "u"},
                           {"name": "password", "value": "p"}]}
        har = make_har([entry(method="POST", post=post)])
        s = har_summary.summarize(har["log"]["entries"])
        self.assertEqual(s["body_requests"], 1)
        self.assertIn("password", s["sensitive_param_names"])

    def test_redacts_token_like_path_segment(self):
        token = "eyJhbGciOiJIUzI1NiJ9.payloadpart"
        har = make_har([entry(url="https://ex.com/reset/%s/confirm" % token)])
        s = har_summary.summarize(har["log"]["entries"])
        path = s["rows"][0]["path"]
        self.assertIn("<redacted>", path)
        self.assertNotIn(token, path)
        self.assertIn("reset", path)
        self.assertIn("confirm", path)


class RedactionOutputTests(unittest.TestCase):
    def test_no_values_in_text_output(self):
        secret_val = "sk_live_" + "x" * 24
        bearer = "Bearer " + "t" * 30
        har = make_har([
            entry(url="https://api.example.com/cb?token=%s" % secret_val,
                  req_headers=[{"name": "Authorization", "value": bearer}],
                  post={"mimeType": "text/plain", "text": secret_val}),
        ])
        s = har_summary.summarize(har["log"]["entries"])
        text = har_summary.format_text(s, top=15, verbose=True)
        self.assertNotIn(secret_val, text)
        self.assertNotIn(bearer, text)
        self.assertNotIn("t" * 30, text)
        # The parameter NAME may appear; the value never does.
        self.assertIn("token", text)

    def test_json_output_has_no_values(self):
        secret_val = "s3cr3t" + "z" * 20
        har = make_har([entry(url="https://api.example.com/x?api_key=%s" % secret_val)])
        s = har_summary.summarize(har["log"]["entries"])
        blob = json.dumps(har_summary.to_json(s))
        self.assertNotIn(secret_val, blob)
        self.assertIn("api_key", blob)


class CliTests(unittest.TestCase):
    def _run(self, argv):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = har_summary.main(argv)
        return code, out.getvalue(), err.getvalue()

    def test_missing_file_exits_2(self):
        code, _, err = self._run(["/no/such/file.har"])
        self.assertEqual(code, 2)
        self.assertIn("error", err.lower())

    def test_non_har_json_exits_2(self):
        path = write_tmp({"not": "a har"})
        try:
            code, _, err = self._run([path])
        finally:
            os.unlink(path)
        self.assertEqual(code, 2)
        self.assertIn("har", err.lower())

    def test_invalid_json_exits_2(self):
        path = write_tmp("{not json")
        try:
            code, _, err = self._run([path])
        finally:
            os.unlink(path)
        self.assertEqual(code, 2)

    def test_clean_capture_exits_0(self):
        path = write_tmp(make_har([entry(url="https://ex.com/a?page=1")]))
        try:
            code, out, _ = self._run([path])
        finally:
            os.unlink(path)
        self.assertEqual(code, 0)
        self.assertIn("HAR summary", out)

    def test_strict_exits_1_on_secret_in_url(self):
        path = write_tmp(make_har([entry(url="https://ex.com/cb?access_token=" + "q" * 30)]))
        try:
            code, _, _ = self._run([path, "--strict"])
        finally:
            os.unlink(path)
        self.assertEqual(code, 1)

    def test_strict_exits_0_when_clean(self):
        path = write_tmp(make_har([entry(url="https://ex.com/a?page=1")]))
        try:
            code, _, _ = self._run([path, "--strict"])
        finally:
            os.unlink(path)
        self.assertEqual(code, 0)

    def test_json_flag_emits_json(self):
        path = write_tmp(make_har([entry()]))
        try:
            code, out, _ = self._run([path, "--json"])
        finally:
            os.unlink(path)
        self.assertEqual(code, 0)
        parsed = json.loads(out)
        self.assertEqual(parsed["entries"], 1)

    def test_bad_top_exits_2(self):
        path = write_tmp(make_har([entry()]))
        try:
            code, _, _ = self._run([path, "--top", "0"])
        finally:
            os.unlink(path)
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
