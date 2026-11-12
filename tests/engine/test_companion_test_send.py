"""2.7.5: the Companion "Send test" endpoint reports plain reasons when the OSC send fails (in-process, the send is made to fail)."""
import errno
import json
import socket
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from harness.engine import EngineCase          # noqa: E402


class FakeOut:
    def __init__(self, exc=None):
        self.exc, self.sent = exc, []

    def send_message(self, addr, val, force=False):
        if self.exc:
            raise self.exc
        self.sent.append((addr, val))


class CompanionTestSend(EngineCase):
    async def call(self, out):
        self.P.osc_out = out
        r = await self.P.h_companion_test(None)
        return json.loads(r.text)

    async def test_ok_sends_the_prefixed_variable_through_the_one_sender(self):
        out = FakeOut()
        d = await self.call(out)
        self.assertTrue(d["ok"])
        self.assertEqual(d["sent_to"], "127.0.0.1:12321")
        self.assertEqual(out.sent, [("/custom-variable/mp_test/value", d["at"])])
        self.assertRegex(d["at"], r"^\d\d:\d\d:\d\d$")

    async def test_failures_have_a_short_plain_reason_and_do_not_record_a_test(self):
        for exc, text in ((socket.gaierror(8, "x"), "Host not found"), (OSError(errno.ENETUNREACH, "Network is unreachable"), "Network unreachable"),
                          (OSError(errno.EPERM, "Operation not permitted"), "Socket error")):
            d = await self.call(FakeOut(exc))
            self.assertFalse(d["ok"])
            self.assertTrue(d["error"].startswith(text), d)
            self.assertNotIn("sent_to_x", d)
        self.assertEqual(self.P.TEST_LAST["value"], "")

    def test_host_checks(self):
        for bad in ("", "192.168.1.", "192.168.1", "256.1.1.1", "bad host", ".x", "x.", "a..b", "1:2"):
            self.assertTrue(self.P.host_error(bad), bad)
        for good in ("192.168.1.50", "localhost", "my-host.local", "::1", "fe80::1"):
            self.assertIsNone(self.P.host_error(good), good)


class SenderWithoutDns(EngineCase):
    """2.7.5 rc2: a well-formed host name that does not resolve must not stop the player, block the event loop or be cached as a failure."""

    def setUp(self):
        import unittest.mock as mock
        self.mock = mock

    async def sender(self, host="companion.local"):
        out = self.P.OscOut(host, 12321)               # making it does no lookup
        self.assertIsNone(out.found)
        return out

    async def test_unresolvable_name_raises_host_not_found_and_does_not_crash_push(self):
        calls = []

        def nope(*a, **k):
            calls.append(a)
            raise socket.gaierror(socket.EAI_NONAME, "nope")
        with self.mock.patch("socket.getaddrinfo", nope):
            out = await self.sender()
            self.P.osc_out = out
            with self.assertRaises(socket.gaierror):
                out.send_message("/x", "1")
            out._thread.join(2)
            self.assertIs(out.found, False)
            self.P.CFG["companion_host"] = "companion.local"
            self.P.push(True)                              # must not raise
            self.P.push(True)
            n = len(calls)
            self.P.push(True)
            self.assertEqual(len(calls), n, "no lookup per push inside the retry time")
            d = await self.call_test(out)
            self.assertEqual((d["ok"], d["error"]), (False, "Host not found"))
            self.assertIs(d["host_found"], False)

    async def test_recovers_when_the_name_starts_to_resolve_and_failures_are_not_cached(self):
        sent = []
        state = {"up": False}

        def gai(host, port, *a, **k):
            if not state["up"]:
                raise socket.gaierror(socket.EAI_NONAME, "nope")
            return [(socket.AF_INET, socket.SOCK_DGRAM, 17, "", ("127.0.0.1", port))]

        class Cli:
            def __init__(self, ip, port):
                self.ip = ip

            def send_message(self, a, v):
                sent.append((self.ip, a, v))
        with self.mock.patch("socket.getaddrinfo", gai), self.mock.patch.object(self.P, "SimpleUDPClient", Cli):
            out = await self.sender()
            with self.assertRaises(socket.gaierror):
                out.send_message("/x", "1")
            out._thread.join(2)
            state["up"] = True
            self.fake.t += 3                              # past RETRY_S
            for _ in range(3):
                try:
                    out.send_message("/x", "2")
                    break
                except socket.gaierror:
                    out._thread.join(2)
            self.assertTrue(out.found)
            self.assertEqual(sent[-1], ("127.0.0.1", "/x", "2"))
            state["up"] = False                           # host gone again after the refresh time: the old answer is not kept for ever
            self.fake.t += 61
            try:
                out.send_message("/x", "3")               # the old address may still be used while the lookup runs
            except socket.gaierror:
                pass
            out._thread.join(2)
            self.assertIs(out.found, False)
            with self.assertRaises(socket.gaierror):
                out.send_message("/x", "4")

    async def call_test(self, out):
        self.P.osc_out = out
        return json.loads((await self.P.h_companion_test(None)).text)

    async def test_ip_address_needs_no_lookup(self):
        with self.mock.patch("socket.getaddrinfo", side_effect=AssertionError("looked up")):
            out = self.P.OscOut("127.0.0.1", 12321)
            self.assertTrue(out.found)


    async def test_sender_survives_threads_and_a_flapping_name(self):
        """push() also runs on worker threads (S.notify): the lookup thread resetting the address while another thread sends must only ever raise OSError."""
        import threading
        n = {"i": 0}

        def gai(host, port, *a, **k):
            n["i"] += 1
            if n["i"] % 2:
                raise socket.gaierror(socket.EAI_NONAME, "nope")
            return [(socket.AF_INET, socket.SOCK_DGRAM, 17, "", ("127.0.0.1", port))]

        class Cli:
            def __init__(self, ip, port):
                pass

            def send_message(self, a, v):
                if n["i"] % 3 == 0:
                    raise OSError(errno.ENETUNREACH, "down")
        bad = []
        with self.mock.patch("socket.getaddrinfo", gai), self.mock.patch.object(self.P, "SimpleUDPClient", Cli):
            out = self.P.OscOut("flap.local", 12321)

            def work():
                for _ in range(400):
                    self.fake.t += 0.9                       # every few sends the retry / refresh time has passed
                    try:
                        out.send_message("/x", "1")
                    except OSError:
                        pass
                    except Exception as e:                   # an AttributeError from a client reset under our feet would land here
                        bad.append(repr(e))
            ts = [threading.Thread(target=work) for _ in range(8)]
            [t.start() for t in ts]
            [t.join(30) for t in ts]
        self.assertEqual(bad, [])


class PrefixDefault(EngineCase):
    async def test_a_config_without_the_setting_loads_the_default_prefix(self):
        self.assertNotIn("var_prefix", json.loads((self.dir / "config.json").read_text()))
        self.assertEqual(self.P.CFG["var_prefix"], "mp_")
        self.assertIsNone(self.P.prefix_error("mp_"))
        for bad in ("", "1a", "a b", "x" * 17, None):
            self.assertTrue(self.P.prefix_error(bad), bad)
