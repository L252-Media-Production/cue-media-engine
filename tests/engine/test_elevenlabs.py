"""ElevenLabs (2.9.0), in-process with the fake clock: the key file, redaction, the error classes, the voice list and its cache, Test key,
one generation at a time, cancel, discard, save through the normal import path (upload.finish_import), duplicates, Replace, the
one-use preview link, and that a failed call leaves the health alone.

No network: every test replaces cpl.elevenlabs.transport with Fake. The keys below are made up for the tests and are not real."""
import asyncio, contextlib, io, json, os, sys, unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from harness.engine import EngineCase          # noqa: E402

KEY = "test-not-a-real-key-0000-wxyz"          # made up; never a real ElevenLabs key
AUDIO = b"ID3\x04\x00\x00\x00\x00\x00\x00" + bytes(range(256)) * 8        # stands in for mp3 bytes (never decoded in these tests)


def ok(body):
    return (200, {"content-type": "application/json"}, json.dumps(body).encode())


def err(status, st="", msg="", headers=None):
    return (status, headers or {}, json.dumps({"detail": {"status": st, "message": msg}}).encode())


VOICES = {"voices": [{"voice_id": "v_lib", "name": "Narrator", "category": "premade", "preview_url": "https://example.invalid/a.mp3"},
                     {"voice_id": "v_own", "name": "Mine", "category": "generated", "is_owner": True, "preview_url": None},
                     {"voice_id": "v_clone", "name": "Clone", "category": "professional", "preview_url": "http://insecure.invalid/x.mp3"},
                     {"name": "no id"}], "has_more": False, "total_count": 3, "next_page_token": None}
USAGE = {"character_count": 9000, "character_limit": 10000, "next_character_count_reset_unix": 1800000000, "tier": "starter"}


class Fake:
    """Stands in for el.transport. routes: what -> (status, headers, body) | Exception | callable returning one of them."""

    def __init__(self, **routes):
        self.routes, self.calls, self.gate = routes, [], None

    async def __call__(self, method, path, api_key, params=None, body=None, timeout=10.0):
        what = "voices" if path.startswith("/v2/voices") else "usage" if path == "/v1/user/subscription" else "models" if path == "/v1/models" else "speech"
        self.calls.append({"what": what, "path": path, "params": params, "body": body, "key": api_key})
        if self.gate is not None:
            await self.gate.wait()
        r = self.routes.get(what, ok({}))
        if callable(r):
            r = r()
        if isinstance(r, Exception):
            raise r
        return r

    def n(self, what):
        return sum(1 for c in self.calls if c["what"] == what)


class ElevenLabsCase(EngineCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.el, self.gen, self.up = self.app.mod("elevenlabs"), self.app.mod("generate"), self.app.mod("upload")
        self.lib = self.app.mod("library")
        self.fake_t = Fake(voices=ok(VOICES), usage=ok(USAGE), speech=(200, {"content-type": "audio/mpeg"}, AUDIO))
        self._real_transport = self.el.transport
        self.el.transport = self.fake_t

    async def asyncTearDown(self):
        self.gen.cancel()
        self.el.transport = self._real_transport
        await super().asyncTearDown()

    def setkey(self):
        good, e = self.el.save_key(KEY)
        self.assertTrue(good, e)

    async def wait_job(self):
        for _ in range(200):
            if self.gen.JOB["state"] != "running":
                return self.gen.state()
            await asyncio.sleep(0.01)
        self.fail("the generation did not finish")

    async def generate(self, name="Doors open", text="Doors are now open.", audio=None, **extra):
        if audio is not None:
            self.fake_t.routes["speech"] = (200, {"content-type": "audio/mpeg"}, audio)
        d, status = self.gen.start({"name": name, "text": text, "voice_id": "v_lib", "voice_name": "Narrator", **extra})
        self.assertEqual(status, 200, d)
        return await self.wait_job()


class KeyFile(ElevenLabsCase):
    async def test_key_file_is_private_and_only_last_four_leave(self):
        self.assertEqual(self.el.key_info(), {"set": False, "last4": "", "note": ""})
        self.setkey()
        self.assertTrue(self.el.KEY_FILE.is_file())
        self.assertEqual(self.el.KEY_FILE.parent.resolve(), self.dir.resolve(), "the key lives in the install folder, next to config.json")
        if os.name != "nt":
            self.assertEqual(self.el.KEY_FILE.stat().st_mode & 0o777, 0o600)
        info = self.el.key_info()
        self.assertEqual(info, {"set": True, "last4": "wxyz", "note": ""})
        self.assertNotIn(KEY, json.dumps(info))
        self.assertNotIn(KEY, (self.dir / "config.json").read_text())
        self.el.remove_key()
        self.assertFalse(self.el.KEY_FILE.exists())
        self.assertFalse(self.el.key_info()["set"])

    @unittest.skipIf(os.name == "nt", "POSIX permissions")
    async def test_loosened_file_is_tightened_on_read(self):
        self.el.KEY_FILE.write_text(KEY + "\n")
        os.chmod(self.el.KEY_FILE, 0o644)
        self.el._K.update(v=None, read=False)
        self.assertEqual(self.el.key(), KEY)
        self.assertEqual(self.el.KEY_FILE.stat().st_mode & 0o777, 0o600)

    async def test_bad_keys_refused(self):
        for bad in ("", "   ", "short", "has space inside the key", "x" * 300, "tab\tinside-key"):
            good, e = self.el.save_key(bad)
            self.assertFalse(good, bad)
            self.assertTrue(e)
        self.assertFalse(self.el.KEY_FILE.exists())

    async def test_not_in_state_json_or_playlists(self):
        self.setkey()
        self.app.mod("persist").save_state()
        self.app.mod("persist").save()
        for f in ("state.json", "playlists.json"):
            self.assertNotIn(KEY, (self.dir / f).read_text(), f)
        self.assertNotIn(KEY, json.dumps(self.P.CFG, default=str))

    async def test_windows_icacls_failure_still_saves_with_note(self):
        self.patch_os_name = self.el.os.name
        calls = []
        self.el._protect_windows, real = (lambda p: calls.append(p) or False), self.el._protect_windows
        real_name = self.el.os.name
        try:
            self.el.os.name = "nt"
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                good, e = self.el.save_key(KEY)
        finally:
            self.el.os.name = real_name
            self.el._protect_windows = real
        self.assertTrue(good, e)
        self.assertTrue(calls)
        self.assertIn("Couldn't restrict the key file", self.el.key_info()["note"])
        self.assertIn("WARNING", buf.getvalue())
        self.assertNotIn(KEY, buf.getvalue())


class Redaction(ElevenLabsCase):
    async def test_redact(self):
        self.setkey()
        s = self.el.redact(f"failed with {KEY} and headers {{'xi-api-key': 'other-secret-123'}} xi-api-key: zzz-999")
        self.assertNotIn(KEY, s)
        self.assertNotIn("other-secret-123", s)
        self.assertNotIn("zzz-999", s)

    async def test_error_text_and_log_never_carry_the_key(self):
        self.setkey()
        e = self.el.map_error(500, {}, json.dumps({"detail": {"status": "oops", "message": f"bad key {KEY}"}}).encode(), "speech")
        self.assertNotIn(KEY, e.message)
        self.fake_t.routes["speech"] = RuntimeError(f"socket said {KEY}")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            st = await self.generate()
        self.assertEqual(st["state"], "error")
        self.assertIn("WARNING", buf.getvalue())
        self.assertNotIn(KEY, buf.getvalue())
        self.assertNotIn(KEY, json.dumps(st))


class Errors(ElevenLabsCase):
    def kind(self, *a, **k):
        return self.el.map_error(*a, **k)

    async def test_each_error_class(self):
        m = self.el.map_error
        self.assertEqual(m(401, {}, err(401, "invalid_api_key")[2], "voices").kind, "invalid_key")
        for what, perm in (("speech", "text_to_speech"), ("voices", "voices_read"), ("usage", "user_read"), ("models", "models_read")):
            e = m(401, {}, err(401, "missing_permissions", "The API key you used is missing the permission")[2], what)
            self.assertEqual((e.kind, e.perm), ("permission", perm))
            self.assertIn(perm, e.message)
            self.assertEqual(m(403, {}, b"", what).kind, "permission")
        e = m(401, {}, err(401, "quota_exceeded", "This request exceeds your quota")[2], "speech")
        self.assertEqual((e.kind, e.level), ("quota", "warn"))
        e = m(400, {}, err(400, "max_character_limit_exceeded")[2], "speech", limit=10000)
        self.assertEqual(e.kind, "too_long")
        self.assertIn("10,000", e.message)
        e = m(429, {"retry-after": "12"}, err(429, "too_many_concurrent_requests")[2], "speech")
        self.assertEqual((e.kind, e.retry_s), ("rate", 12))
        self.assertIn("Try again in 12 s", e.message)
        e = m(429, {}, err(429, "system_busy")[2], "speech")
        self.assertEqual((e.kind, e.retry_s), ("rate", None))
        self.assertIn("Try again in a moment", e.message)
        self.assertEqual(m(404, {}, err(404, "voice_not_found")[2], "speech").kind, "voice_gone")
        e = m(500, {}, b"<html>oops</html>", "speech")
        self.assertEqual(e.kind, "unexpected")
        self.assertIn("500", e.message)
        self.assertEqual(m(422, {}, json.dumps({"detail": [{"loc": ["body", "text"], "msg": "field required", "type": "missing"}]}).encode(), "speech").kind, "unexpected")

    async def test_no_key_network_timeout_reach_the_job(self):
        st, status = self.gen.start({"name": "x", "text": "y", "voice_id": "v_lib"})
        self.assertEqual((status, st["kind"]), (400, "no_key"))
        self.setkey()
        for exc, kind in ((self.el.ElError("network", "Can't reach ElevenLabs."), "network"),
                          (self.el.ElError("timeout", "no answer", "warn"), "timeout")):
            self.fake_t.routes["speech"] = exc
            st = await self.generate()
            self.assertEqual((st["state"], st["error"]["kind"]), ("error", kind))
        self.fake_t.routes["speech"] = (200, {"content-type": "application/json"}, b"{}")
        st = await self.generate()
        self.assertEqual(st["error"]["kind"], "unexpected")

    async def test_text_limits(self):
        self.setkey()
        d, status = self.gen.start({"name": "x", "text": "a" * 10001, "voice_id": "v_lib"})
        self.assertEqual((status, d["kind"]), (400, "too_long"))
        self.assertEqual(self.fake_t.n("speech"), 0, "a text over the default model's limit is never sent")
        d, status = self.gen.start({"name": "x", "text": "a" * 10000, "voice_id": "v_lib"})
        self.assertEqual(status, 200, d)
        await self.wait_job()


class VoicesAndUsage(ElevenLabsCase):
    async def test_parse_kinds_and_samples(self):
        self.setkey()
        v = await self.el.list_voices()
        self.assertEqual([(x["id"], x["kind"]) for x in v], [("v_own", "own"), ("v_clone", "cloned"), ("v_lib", "library")])
        pv = {x["id"]: x["preview"] for x in v}
        self.assertEqual(pv, {"v_own": None, "v_clone": None, "v_lib": "https://example.invalid/a.mp3"})
        self.assertEqual(self.fake_t.calls[0]["params"]["page_size"], "100")

    async def test_pages_followed(self):
        self.setkey()
        p1 = {"voices": [{"voice_id": "a", "name": "A", "category": "premade"}], "has_more": True, "next_page_token": "T2", "total_count": 2}
        p2 = {"voices": [{"voice_id": "b", "name": "B", "category": "cloned"}], "has_more": False, "next_page_token": None, "total_count": 2}
        pages = iter([ok(p1), ok(p2)])
        self.fake_t.routes["voices"] = lambda: next(pages)
        v = await self.el.list_voices()
        self.assertEqual({x["id"] for x in v}, {"a", "b"})
        self.assertEqual(self.fake_t.calls[1]["params"]["next_page_token"], "T2")

    async def test_cache_minutes_refresh_and_new_key(self):
        self.setkey()
        await self.el.list_voices()
        await self.el.list_voices()
        self.assertEqual(self.fake_t.n("voices"), 1, "cached")
        self.fake.t += 120
        await self.el.list_voices()
        self.assertEqual(self.fake_t.n("voices"), 1, "still cached after 2 minutes")
        await self.el.list_voices(refresh=True)
        self.assertEqual(self.fake_t.n("voices"), 2, "Refresh fetches")
        self.fake.t += self.el.CACHE_S + 1
        await self.el.list_voices()
        self.assertEqual(self.fake_t.n("voices"), 3, "expired")
        self.setkey()
        await self.el.list_voices()
        self.assertEqual(self.fake_t.n("voices"), 4, "a new key forgets the list")

    async def test_usage_and_quota_numbers(self):
        self.setkey()
        u = await self.el.usage()
        self.assertEqual(u, {"used": 9000, "limit": 10000, "left": 1000, "reset": 1800000000})
        self.assertIsNone(self.el.parse_usage({"character_count": "x"}))

    async def test_models_need_permission(self):
        self.setkey()
        self.fake_t.routes["models"] = err(401, "missing_permissions", "missing the permission models_read")
        self.assertIsNone(await self.el.list_models())
        self.assertEqual(self.gen.limit_for(None), 10000)
        self.assertIsNone(self.gen.limit_for("some_model"), "unknown limit: the API decides")
        self.el.forget_cache()
        self.fake_t.routes["models"] = ok([{"model_id": "m1", "name": "M1", "can_do_text_to_speech": True, "maximum_text_length_per_request": 500},
                                           {"model_id": "sts", "name": "STS", "can_do_text_to_speech": False}, {"model_id": "m2", "name": "M2"}])
        ms = await self.el.list_models()
        self.assertEqual([(m["id"], m["limit"]) for m in ms], [("m1", 500), ("m2", None)])
        self.assertEqual(self.gen.limit_for("m1"), 500)
        d, status = self.gen.start({"name": "x", "text": "a" * 501, "voice_id": "v_lib", "model": "m1"})
        self.assertEqual((status, d["kind"]), (400, "too_long"))


class TestKey(ElevenLabsCase):
    async def test_three_results_and_the_usage_note(self):
        r = await self.el.test_key()
        self.assertEqual(r["level"], "bad")
        self.setkey()
        r = await self.el.test_key()
        self.assertEqual((r["level"], r["title"]), ("ok", "Key works"))
        self.assertEqual(r["usage"]["left"], 1000)
        self.assertEqual(self.fake_t.calls[0]["params"], {"page_size": "1"})
        self.assertEqual(self.fake_t.n("speech"), 0, "Test never spends characters")
        self.fake_t.routes["usage"] = err(401, "missing_permissions", "missing user_read")
        r = await self.el.test_key()
        self.assertEqual(r["level"], "ok")
        self.assertIn("lacks the usage permission", r["msg"])
        self.fake_t.routes["voices"] = err(401, "invalid_api_key", "Invalid API key")
        r = await self.el.test_key()
        self.assertEqual((r["level"], r["title"]), ("bad", "Key not valid"))
        self.fake_t.routes["voices"] = err(403, "missing_permissions", "missing voices_read")
        r = await self.el.test_key()
        self.assertEqual(r["level"], "bad")
        self.assertIn("voices_read", r["msg"])
        self.fake_t.routes["voices"] = self.el.ElError("network", "Can't reach ElevenLabs.")
        r = await self.el.test_key()
        self.assertEqual((r["level"], r["title"]), ("warn", "Can't reach ElevenLabs"))


class Generation(ElevenLabsCase):
    async def test_one_at_a_time_and_cancel(self):
        self.setkey()
        self.fake_t.gate = asyncio.Event()
        d, status = self.gen.start({"name": "A", "text": "one", "voice_id": "v_lib"})
        self.assertEqual(status, 200, d)
        await asyncio.sleep(0)
        self.assertEqual(self.gen.state()["state"], "running")
        d, status = self.gen.start({"name": "B", "text": "two", "voice_id": "v_lib"})
        self.assertEqual((status, d["kind"]), (409, "busy"))
        self.assertTrue(self.gen.cancel())
        await asyncio.sleep(0.01)
        self.assertEqual(self.gen.state()["state"], "cancelled")
        self.assertIsNone(self.gen.temp_path())
        self.assertFalse(list(self.up.IMPORT_DIR.glob("gen-*")) if self.up.IMPORT_DIR.exists() else [])
        self.fake_t.gate = None
        st = await self.generate()
        self.assertEqual(st["state"], "done", "a new one can start after a cancel")

    async def test_request_shape(self):
        self.setkey()
        await self.generate(stability=0.3, similarity=0.9)
        c = [x for x in self.fake_t.calls if x["what"] == "speech"][-1]
        self.assertEqual(c["path"], "/v1/text-to-speech/v_lib")
        self.assertEqual(c["params"], {"output_format": "mp3_44100_128"})
        self.assertNotIn("model_id", c["body"], "no model id unless one is chosen")
        self.assertEqual(c["body"]["voice_settings"], {"stability": 0.3, "similarity_boost": 0.9})
        await self.generate(model="m2")
        c = [x for x in self.fake_t.calls if x["what"] == "speech"][-1]
        self.assertEqual(c["body"]["model_id"], "m2")

    async def test_discard_deletes_the_temp_file(self):
        self.setkey()
        st = await self.generate()
        self.assertEqual(st["state"], "done")
        p = Path(self.gen.temp_path())
        self.assertTrue(p.is_file())
        self.assertEqual(p.parent, self.up.IMPORT_DIR, "temporary files live in _import/, emptied at every start")
        self.assertTrue(self.gen.discard())
        self.assertFalse(p.exists())
        self.assertIsNone(self.gen.temp_path())

    async def test_new_generation_replaces_unsaved_temp(self):
        self.setkey()
        await self.generate()
        first = Path(self.gen.temp_path())
        await self.generate(audio=AUDIO + b"2")
        self.assertFalse(first.exists())

    async def test_save_goes_through_the_import_path(self):
        self.setkey()
        seen = []
        real = self.up.finish_import

        async def spy(*a, **k):
            seen.append(a)
            return await real(*a, **k)
        self.up.finish_import = spy
        try:
            await self.generate(name="Doors: open?")
            d, status = await self.gen.save_new("Doors: open?", new_folder="Generated")
        finally:
            self.up.finish_import = real
        self.assertEqual(status, 200, d)
        self.assertEqual(d["id"], "Generated/Doors_ open_.mp3")
        self.assertEqual(len(seen), 1, "upload.finish_import (the upload path) adds the library entry")
        self.assertIn(d["id"], self.P.library)
        self.assertIn("Generated", self.P.LIBDIRS)
        self.assertEqual((self.dir / "media" / "library" / d["id"]).read_bytes(), AUDIO)
        meta = self.app.mod("state").GENERATED[d["id"]]
        self.assertEqual({k: meta[k] for k in ("text", "voice_id", "voice_name", "model")},
                         {"text": "Doors are now open.", "voice_id": "v_lib", "voice_name": "Narrator", "model": ""})
        saved = json.loads((self.dir / "playlists.json").read_text())
        self.assertIn(d["id"], saved["generated"])
        self.assertIsNone(self.gen.temp_path())

    async def test_duplicate_is_reported_and_not_entered_twice(self):
        self.setkey()
        await self.generate()
        a, _ = await self.gen.save_new("First", new_folder="Generated")
        await self.generate()
        b, status = await self.gen.save_new("Second", new_folder="Other")
        self.assertEqual(status, 200, b)
        self.assertTrue(b["duplicate"])
        self.assertEqual(b["id"], a["id"])
        G = self.app.mod("state").GENERATED
        self.assertEqual(list(G), [a["id"]])
        self.assertFalse((self.dir / "media" / "library" / "Generated" / "Second.mp3").exists())
        self.assertFalse((self.dir / "media" / "library" / "Other").exists(), "no folder is created for a duplicate")

    async def test_folder_and_name_checks(self):
        self.setkey()
        await self.generate()
        lib = self.dir / "media" / "library"
        for bad in ("../outside", "Nope", "/etc", "Generated/../..", "_import", ["x"], 5):
            d, status = await self.gen.save_new("x", folder=bad)
            self.assertEqual((status, d.get("field")), (400, "folder"), bad)
        for bad in ("", "  ", "a/b", "..", "../up", "a\\b", "_hidden", ".dot", "bad*name", "two  spaces"):
            d, status = await self.gen.save_new("x", new_folder=bad)
            self.assertEqual((status, d.get("field")), (400, "new_folder"), bad)
        self.assertFalse((self.dir / "media" / "outside").exists())
        self.assertEqual({p.name for p in lib.iterdir() if p.is_dir()}, set(), "nothing was created")
        d, status = await self.gen.save_new("   ", folder="")
        self.assertEqual(status, 400)
        self.assertIsNotNone(self.gen.temp_path(), "a refused save keeps the audio")
        d, status = await self.gen.save_new("ok", new_folder="Shows")
        self.assertEqual((status, d["id"], d["folder"]), (200, "Shows/ok.mp3", "Shows"))
        self.assertIn("Shows", self.P.LIBDIRS)
        await self.generate(audio=AUDIO + b"2")
        d, status = await self.gen.save_new("again", new_folder="shows")
        self.assertEqual((status, d["field"]), (409, "new_folder"), "an existing folder (any letter case) is refused as a new one")
        self.assertIn("already exists", d["error"])
        d, status = await self.gen.save_new("again", folder="Shows")
        self.assertEqual((status, d["id"]), (200, "Shows/again.mp3"), "an existing folder")
        await self.generate(audio=AUDIO + b"3")
        d, status = await self.gen.save_new("top", folder="")
        self.assertEqual((status, d["id"]), (200, "top.mp3"), "the top level, as in Rename or move")

    async def test_folder_error_rules(self):
        fe = self.gen.folder_error
        self.assertEqual(fe("Generated"), "")
        self.assertEqual(fe("Walk-in music 2"), "")
        for bad in ("", "a/b", "a\\b", "_x", ".x", "x*", "two  spaces", "trailing."):
            self.assertTrue(fe(bad), bad)
        self.assertEqual(self.lib.lib_mkdir("Existing")[1], 200)
        self.assertIn("already exists", fe("existing"))

    async def test_clean_name(self):
        c = self.gen.clean_name
        self.assertEqual(c("../evil/name"), "evil_name")
        self.assertEqual(c(".hidden"), "hidden")
        self.assertEqual(c("_under"), "under")
        self.assertEqual(c("  many   spaces  "), "many spaces")
        self.assertEqual(c("a\\b:c*d?e\"f<g>h|i"), "a_b_c_d_e_f_g_h_i")
        self.assertEqual(c(""), "")
        self.assertEqual(len(c("x" * 200)), 80)

    async def test_rename_rekeys_and_delete_drops_the_metadata(self):
        self.setkey()
        await self.generate()
        d, _ = await self.gen.save_new("Walk in", new_folder="Generated")
        G = self.app.mod("state").GENERATED
        new, status = self.lib.lib_rename(d["id"], "Shows/Walk in.mp3")
        self.assertEqual(status, 200, new)
        self.assertNotIn(d["id"], G)
        self.assertIn("Shows/Walk in.mp3", G)
        self.lib.lib_rename("Shows", "Archive")
        self.assertIn("Archive/Walk in.mp3", G)
        self.lib.delete_from_library("Archive/Walk in.mp3")
        self.assertEqual(G, {})

    async def test_one_use_short_lived_preview_link(self):
        self.setkey()
        self.assertIsNone(self.gen.new_token())
        await self.generate()
        t = self.gen.new_token()
        self.assertEqual(self.gen.take_token(t), self.gen.temp_path())
        self.assertIsNone(self.gen.take_token(t), "one use")
        t = self.gen.new_token()
        self.fake.t += self.gen.TOKEN_S + 1
        self.assertIsNone(self.gen.take_token(t), "expired")
        self.assertIsNone(self.gen.take_token("guess"))


class Replace(ElevenLabsCase):
    async def test_replace_keeps_playlist_places_and_clears_what_belonged_to_the_old_audio(self):
        self.setkey()
        await self.generate()
        d, _ = await self.gen.save_new("Notice", new_folder="Generated")
        fid = d["id"]
        P = self.P
        P.playlists[0]["tracks"].append(fid)
        t = len(P.playlists[0]["tracks"]) - 1
        self.assertTrue(P.set_trim(0, t, {"in": 0.0, "out": 0.5, "end": "cut"}))
        lst, e = P.set_triggers(0, t, "add", {"at": 0.2, "file": "a.wav"})
        self.assertIsNone(e, e)
        P.DURS[fid] = (1, 1, 9.0)
        path = str(self.app.mod("config").LIB / fid)
        self.app.mod("cache")._cache[path] = object()                  # pretend its sound is in RAM
        await self.generate(audio=AUDIO + b"new")
        r, status = self.gen.replace(fid, in_use=True)
        self.assertEqual(status, 409, "refused while playing")
        r, status = self.gen.replace(fid, in_use=False)
        self.assertEqual(status, 200, r)
        self.assertEqual((self.dir / "media" / "library" / fid).read_bytes(), AUDIO + b"new")
        self.assertEqual(P.playlists[0]["tracks"][t], fid)
        self.assertNotIn(fid, P.playlists[0].get("trims", {}))
        self.assertNotIn(fid, P.playlists[0].get("triggers", {}))
        self.assertNotIn(fid, P.DURS)
        self.assertNotIn(path, self.app.mod("cache")._cache)
        self.assertEqual(P.library[fid], len(AUDIO) + 3)
        self.assertEqual(r["cleared"], 2)

    async def test_replace_only_generated_tracks(self):
        self.setkey()
        await self.generate()
        r, status = self.gen.replace("a.wav", in_use=False)
        self.assertEqual(status, 404)


class Health(ElevenLabsCase):
    async def test_failed_calls_leave_health_unchanged(self):
        P, S = self.P, self.app.mod("state")
        before_issues = dict(S.ISSUES)
        before = P.health_report(force=True)
        self.setkey()
        for r in (err(401, "invalid_api_key"), err(429, "system_busy"), self.el.ElError("network", "x"), (500, {}, b"")):
            self.fake_t.routes["speech"] = r
            self.fake_t.routes["voices"] = r
            await self.generate()
            await self.el.test_key()
            with contextlib.suppress(self.el.ElError):
                await self.el.list_voices(refresh=True)
        after = P.health_report(force=True)
        self.assertEqual(dict(S.ISSUES), before_issues)
        self.assertEqual(after.get("state"), before.get("state"))
        self.assertEqual(after.get("status"), before.get("status"))


class RealTransportLocal(ElevenLabsCase):
    """The real transport() (aiohttp) against a local server on 127.0.0.1 standing in for api.elevenlabs.io: never the internet."""

    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.el.transport = self._real_transport
        self._api = self.el.API

    async def asyncTearDown(self):
        self.el.API = self._api
        await super().asyncTearDown()

    async def test_chunked_body_headers_errors_and_timeout(self):
        from aiohttp import web
        big, seen = os.urandom(300_000), {}

        async def tts(req):
            seen.update(key=req.headers.get("xi-api-key"), q=dict(req.query), body=await req.json(), path=req.path)
            resp = web.StreamResponse(headers={"Content-Type": "audio/mpeg"})
            await resp.prepare(req)
            for i in range(0, len(big), 7000):          # many small chunks: one read() would stop early
                await resp.write(big[i:i + 7000])
                await asyncio.sleep(0)
            await resp.write_eof()
            return resp

        async def voices(req):
            if req.query.get("page_size") == "1":
                return web.json_response({"detail": {"status": "invalid_api_key", "message": "Invalid API key"}}, status=401)
            return web.json_response(VOICES)

        async def slow(req):
            await asyncio.sleep(2)
            return web.json_response({})
        app = web.Application()
        app.router.add_post("/v1/text-to-speech/{v}", tts)
        app.router.add_get("/v2/voices", voices)
        app.router.add_get("/v1/models", slow)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "127.0.0.1", 0)
        await site.start()
        port = site._server.sockets[0].getsockname()[1]
        self.el.API = f"http://127.0.0.1:{port}"
        self.setkey()
        try:
            audio = await self.el.speech("v_lib", "Hello there")
            self.assertEqual(audio, big, "the whole chunked body")
            self.assertEqual((seen["key"], seen["q"], seen["body"], seen["path"]),
                             (KEY, {"output_format": "mp3_44100_128"}, {"text": "Hello there"}, "/v1/text-to-speech/v_lib"))
            self.assertEqual(len(await self.el.list_voices()), 3)
            r = await self.el.test_key()
            self.assertEqual((r["level"], r["title"]), ("bad", "Key not valid"))
            with self.assertRaises(self.el.ElError) as cm:
                await self.el.transport("GET", "/v1/models", KEY, timeout=0.3)
            self.assertEqual(cm.exception.kind, "timeout")
        finally:
            await runner.cleanup()
        with self.assertRaises(self.el.ElError) as cm:
            await self.el.list_voices(refresh=True)
        self.assertEqual(cm.exception.kind, "network", "nothing listening: no network")


if __name__ == "__main__":
    unittest.main()
