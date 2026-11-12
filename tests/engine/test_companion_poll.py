"""2.8.0 follow-up: how the player recognises the Companion module's polls. The header X-CompanionPlayer-Client always counts; the Node user agent counts only until
a header-bearing poll has been seen (older modules), so another Node client (n8n) cannot look like Companion afterwards."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from harness.engine import EngineCase          # noqa: E402


class Req:
    def __init__(self, **h):
        self.headers = h


class CompanionPolls(EngineCase):

    async def test_user_agent_fallback_until_a_header_is_seen(self):
        P = self.P
        P.COMP["hdr"] = False
        self.assertTrue(P.is_companion_poll(Req(**{"User-Agent": "node"})))            # an older module
        self.assertTrue(P.is_companion_poll(Req(**{"User-Agent": "undici"})))
        self.assertFalse(P.is_companion_poll(Req(**{"User-Agent": "Mozilla/5.0"})))
        self.assertFalse(P.is_companion_poll(Req(**{"User-Agent": "curl/8"})))
        self.assertFalse(P.COMP["hdr"])

    async def test_after_a_header_only_the_header_counts(self):
        P = self.P
        P.COMP["hdr"] = False
        self.assertTrue(P.is_companion_poll(Req(**{"X-CompanionPlayer-Client": "companion-module", "User-Agent": "node"})))
        self.assertTrue(P.COMP["hdr"])
        self.assertFalse(P.is_companion_poll(Req(**{"User-Agent": "node"})), "n8n (Node) is no longer taken for Companion")
        self.assertFalse(P.is_companion_poll(Req(**{"User-Agent": "undici"})))
        self.assertTrue(P.is_companion_poll(Req(**{"X-CompanionPlayer-Client": "companion-module"})))
