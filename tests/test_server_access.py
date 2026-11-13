"""Access rules of the HTTP server: requests from web pages refused on /v1/*, API key compared."""
import asyncio
import json
import unittest
from unittest import mock

from transcription import server


def call(path, headers=(), method="GET"):
    """Runs one request through the ASGI app (without the lifespan: no model is loaded)."""
    scope = {"type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1", "method": method, "scheme": "http",
             "path": path, "raw_path": path.encode(), "query_string": b"", "root_path": "",
             "headers": [(k.lower().encode(), v.encode()) for k, v in headers],
             "client": ("127.0.0.1", 50000), "server": ("127.0.0.1", 8000)}
    sent = []

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        sent.append(message)

    asyncio.run(server.app(scope, receive, send))
    start = next(m for m in sent if m["type"] == "http.response.start")
    body = b"".join(m.get("body", b"") for m in sent if m["type"] == "http.response.body")
    return start["status"], json.loads(body or b"null")


class Access(unittest.TestCase):
    def test_program_without_origin_is_served(self):
        self.assertEqual(call("/v1/models")[0], 200)

    def test_web_page_is_refused(self):
        self.assertEqual(call("/v1/models", [("Origin", "https://evil.example")])[0], 403)
        self.assertEqual(call("/v1/audio/transcriptions", [("Origin", "null")], method="POST")[0], 403)

    def test_allowed_origin_is_served(self):
        with mock.patch.object(server, "ALLOWED_ORIGINS", {"https://webui.example"}):
            self.assertEqual(call("/v1/models", [("Origin", "https://webui.example/")])[0], 200)

    def test_health_stays_open(self):
        self.assertEqual(call("/health", [("Origin", "https://evil.example")])[0], 200)

    def test_api_key(self):
        with mock.patch.object(server, "API_KEY", "secret-for-test"):
            self.assertEqual(call("/v1/models")[0], 401)
            self.assertEqual(call("/v1/models", [("Authorization", "Bearer wrong")])[0], 401)
            self.assertEqual(call("/v1/models", [("Authorization", "Bearer secret-for-test")])[0], 200)


if __name__ == "__main__":
    unittest.main()
