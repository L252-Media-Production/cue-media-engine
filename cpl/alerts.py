"""Push on state change (2.8.0): a webhook message when the health state changes or the watchdog restarts the audio engine.

  * `Notifier` is the state machine: it watches the health report once a second, debounces (a state must hold DEBOUNCE_S before it counts), decides
    which events to send, queues them while something is playing when "hold until idle" is on, and hands finished messages to a `Poster`.
  * `Poster` sends: an HTTP POST with a JSON body, 5 s timeout, up to 2 retries with backoff, on ONE worker thread, so the audio, the main loop and
    the API never wait for the network. The HTTP call, the sleep and the thread are injected, so tests use a fake sender and the fake clock.
The webhook address is a secret (many services put the key in the path): it is never logged or returned; only `mask_url()` (the host) is.
"""
import json, queue, socket, threading, urllib.error, urllib.request
from datetime import datetime
from urllib.parse import urlsplit

from cpl import clock

DEBOUNCE_S = 5.0                   # a state must hold this long before it produces a message
DEGRADED_LONG_S = 300.0            # "degraded has lasted more than 5 minutes"
TIMEOUT_S = 5.0
RETRIES = 2
BACKOFF_S = (1.0, 3.0)
HOLD_MAX = 50                      # queued messages while something plays (memory only)
EVENTS = ("problem", "recovered", "degraded_long", "watchdog")
EVENT_TITLES = {"problem": "A problem starts", "recovered": "It recovers", "degraded_long": "Degraded lasts more than 5 minutes", "watchdog": "The watchdog restarts the audio engine"}


def clean_url(s):
    """The webhook address, checked: http or https with a host, no spaces. '' clears it. Raises ValueError with a sentence."""
    s = (s or "").strip() if isinstance(s, str) else ""
    if not s:
        return ""
    if len(s) > 2048 or any(c.isspace() for c in s):
        raise ValueError("the webhook address must be one line without spaces")
    u = urlsplit(s)
    if u.scheme not in ("http", "https"):
        raise ValueError("the webhook address must start with http:// or https://")
    if not u.hostname:
        raise ValueError("the webhook address has no host name")
    try:
        u.port
    except ValueError:
        raise ValueError("the webhook address has a bad port number")
    return s


def mask_url(url):
    """Only the host is ever shown: 'https://hooks.example.com/…'. '' when there is no address."""
    if not url:
        return ""
    u = urlsplit(url)
    host = u.hostname or "?"
    if u.port:
        host += f":{u.port}"
    return f"{u.scheme}://{host}/…"


def clean_events(d, base=None):
    cur = dict(base or {k: True for k in EVENTS})
    if isinstance(d, dict):
        for k in EVENTS:
            if k in d:
                if not isinstance(d[k], bool):
                    raise ValueError(f"{k} must be true or false")
                cur[k] = d[k]
    return {k: bool(cur.get(k, True)) for k in EVENTS}


def first_sentence(text):
    """'The live output (X) is not available. Start ...' -> 'the live output (X) is not available' (one sentence, lower-case start)."""
    s = (text or "").strip()
    cut = s.find(". ")
    s = (s[:cut] if cut >= 0 else s.rstrip("."))
    if len(s) > 1 and s[0].isupper() and not s[1].isupper():
        s = s[0].lower() + s[1:]
    return s


def _http_post(url, data, timeout):
    """The real sender: returns the HTTP status; raises urllib errors. Redirects are followed by urllib for GET only, so a POST that is redirected fails (HTTP 30x)."""
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json", "User-Agent": "CueME"}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status


def reason_of(exc):
    """A short reason for the panel, never containing the address."""
    if isinstance(exc, urllib.error.HTTPError):
        return f"Refused (HTTP {exc.code})"
    if isinstance(exc, (socket.timeout, TimeoutError)):
        return "Timed out"
    if isinstance(exc, urllib.error.URLError):
        r = exc.reason
        if isinstance(r, (socket.timeout, TimeoutError)):
            return "Timed out"
        if isinstance(r, socket.gaierror):
            return "Host not found"
        if isinstance(r, ConnectionRefusedError):
            return "Connection refused"
        return "Could not connect"
    if isinstance(exc, ConnectionError):
        return "Connection refused"
    return "Could not send"


class Poster:
    """Sends payloads one at a time on one worker thread. `post(url, data, timeout)` and `sleep(s)` are injected; `inline=True` (tests) sends on the caller's thread."""

    def __init__(self, get_url, post=_http_post, sleep=None, log=print, inline=False):
        self.get_url, self.post, self.log, self.inline = get_url, post, log, inline
        self.sleep = sleep or clock.sleep
        self.last_error = ""            # "" = the last send worked (or none yet)
        self.last_error_at = None
        self.last_ok_at = None
        self.sent = 0
        self._q = queue.Queue(maxsize=HOLD_MAX)
        self._thread = None

    def send(self, payload, retries=RETRIES):
        """Queue a payload (never blocks). Returns False when the worker's queue is full (the message is dropped and logged)."""
        if self.inline:
            self._deliver(payload, retries)
            return True
        try:
            self._q.put_nowait((payload, retries))
        except queue.Full:
            self.log("Push: too many messages waiting, one was dropped")
            return False
        if self._thread is None or not self._thread.is_alive():
            self._thread = threading.Thread(target=self._work, daemon=True, name="push")
            self._thread.start()
        return True

    def _work(self):
        while True:
            try:
                payload, retries = self._q.get(timeout=30)
            except queue.Empty:
                return
            self._deliver(payload, retries)

    def deliver_now(self, payload, retries=0):
        """Send on the calling thread and return (ok, reason). For the Send test button: the caller runs it in an executor."""
        return self._deliver(payload, retries)

    def _deliver(self, payload, retries):
        url = self.get_url()
        if not url:
            return False, "No webhook address"
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        reason = ""
        for attempt in range(retries + 1):
            try:
                status = self.post(url, data, TIMEOUT_S)
                if 200 <= status < 300:
                    self.last_error, self.last_ok_at, self.sent = "", clock.time(), self.sent + 1
                    return True, ""
                reason = f"Refused (HTTP {status})"
            except Exception as e:
                reason = reason_of(e)
                code = getattr(e, "code", None)
                if isinstance(code, int) and 400 <= code < 500 and code not in (408, 429):
                    break                                    # the address or the body is wrong; trying again will not help
            if attempt < retries:
                self.sleep(BACKOFF_S[min(attempt, len(BACKOFF_S) - 1)])
        self.last_error, self.last_error_at = reason, clock.time()
        self.log(f"Push failed: {reason}")                   # never the address
        return False, reason


class Notifier:
    """The state machine. `cfg` is a dict-like (CFG) with push_enabled, push_events, push_hold; `name()` the player's name; `playing()` whether anything plays."""

    def __init__(self, cfg, name, playing, poster, log=print):
        self.cfg, self.name, self.playing, self.poster, self.log = cfg, name, playing, poster, log
        self.stable = None             # the last state that held DEBOUNCE_S
        self.cand = None
        self.cand_since = 0.0
        self.degraded_since = None
        self.long_sent = False
        self.held = []                 # [(text, event)] while something plays and hold is on
        self.dropped = 0
        self.sentence = ""

    # ---- time and text
    @staticmethod
    def hhmm(ts=None):
        return datetime.fromtimestamp(clock.time() if ts is None else ts).strftime("%H:%M")

    def _payload(self, text, event, state):
        return {"text": text, "content": text, "player": self.name(), "event": event, "state": state,
                "time": datetime.fromtimestamp(clock.time()).astimezone().isoformat(timespec="seconds")}

    # ---- sending
    def _enabled(self, event):
        return bool(self.cfg.get("push_enabled")) and bool(self.cfg.get("push_url")) and bool((self.cfg.get("push_events") or {}).get(event, True))

    def _emit(self, event, text, state):
        if not self._enabled(event):
            return False
        if self.cfg.get("push_hold") and self.playing():
            self.held.append((text, event, state))
            if len(self.held) > HOLD_MAX:
                del self.held[0]
                self.dropped += 1
            return True
        return self.poster.send(self._payload(text, event, state))

    def flush(self):
        """Hold until idle: when nothing plays, the queued messages go out as ONE message."""
        if not self.held or self.playing():
            return
        items, self.held = self.held, []
        if len(items) == 1 and not self.dropped:
            text, event, state = items[0]
        else:
            n = len(items) + self.dropped
            text = f"{self.name()}: {n} messages while playing:\n" + "\n".join("- " + t for t, _, _ in items)
            if self.dropped:
                text += f"\n(+ {self.dropped} older ones not shown)"
            event, state = items[-1][1], items[-1][2]
            self.dropped = 0
        self.poster.send(self._payload(text, event, state))

    def send_test(self):
        """Immediately, whatever the hold setting says; changes no state. -> (ok, reason)."""
        text = f"{self.name()}: Test message. The webhook works. {self.hhmm()}"
        return self.poster.deliver_now(self._payload(text, "test", "test"), retries=0)

    # ---- events
    def watchdog_restarted(self, stall_s=10):
        self._emit("watchdog", f"{self.name()}: Audio engine restarted by the watchdog (output stalled for {int(stall_s)} s). {self.hhmm()}", "restarted")

    def observe(self, rep):
        """Once a second with the health report ({state, summary, checks})."""
        now = clock.monotonic()
        state = rep["state"]
        if state != "starting":                                  # start-up is not a state change
            if state != self.cand:
                self.cand, self.cand_since = state, now
            if self.cand != self.stable and now - self.cand_since >= DEBOUNCE_S:
                self._changed(self.stable, self.cand, rep, now)
                self.stable = self.cand
        if self.stable == "degraded" and not self.long_sent and self.degraded_since is not None and now - self.degraded_since > DEGRADED_LONG_S:
            self.long_sent = True
            self._emit("degraded_long", f"{self.name()}: Degraded for more than 5 minutes: {self._why(rep, 'warn')}. {self.hhmm()}", "degraded")
        self.flush()

    def _why(self, rep, level):
        for c in rep.get("checks", []):
            if c.get("status") == level and c.get("text"):
                return first_sentence(c["text"])
        return str(rep.get("summary") or "see the Health panel")

    def _changed(self, prev, new, rep, now):
        if new == "degraded":
            self.degraded_since, self.long_sent = now, False
        else:
            self.degraded_since, self.long_sent = None, False
        if new == "problem" and prev != "problem":
            self._emit("problem", f"{self.name()}: PROBLEM — {self._why(rep, 'bad')}. {self.hhmm()}", "problem")
        elif new == "ready" and prev in ("problem", "degraded"):
            self._emit("recovered", f"{self.name()}: Recovered — everything is ready. {self.hhmm()}", "ready")

    def info(self):
        return {"queued": len(self.held)}
