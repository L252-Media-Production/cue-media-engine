"""pytest plugin: collects results, severity, timings and environment, and writes results.json, report.md and junit.xml."""
import hashlib, json, os, platform, shutil, subprocess, sys, time, xml.etree.ElementTree as ET
from pathlib import Path

from . import client
from .appcopy import tree_hash

SEV_NAMES = {1: "no audio / crash / stuck / wrong track on air", 2: "wrong behaviour", 3: "UI / usability glitch", 4: "cosmetic"}


def file_hash(p):
    try:
        return hashlib.sha256(Path(p).read_bytes()).hexdigest()
    except OSError:
        return None


def environment(project, target=None, ffmpeg_info=None):
    env = {"platform": platform.platform(), "system": platform.system(), "machine": platform.machine(), "python": sys.version.split()[0],
           "python_executable": sys.executable, "pytest": None, "pygame": None, "ffmpeg_local": None, "target": target}
    try:
        import pytest
        env["pytest"] = pytest.__version__
    except Exception:
        pass
    try:
        import pygame
        env["pygame"] = f"{pygame.__name__} {pygame.version.ver}"
    except Exception:
        env["pygame"] = "not importable by the harness"
    ff = shutil.which("ffmpeg")
    if ff:
        try:
            env["ffmpeg_local"] = subprocess.run([ff, "-version"], capture_output=True, text=True, timeout=10).stdout.splitlines()[0]
        except Exception:
            env["ffmpeg_local"] = ff
    pf = Path(project) / "player.py"
    env["player_py"] = {"path": str(pf), "sha256": file_hash(pf), "bytes": pf.stat().st_size if pf.exists() else None,
                        "mtime": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(pf.stat().st_mtime)) if pf.exists() else None}
    th, nf, nb = tree_hash(project)
    env["app_tree"] = {"sha256": th, "files": nf, "bytes": nb}
    try:
        g = subprocess.run(["git", "-C", str(project), "rev-parse", "--short", "HEAD"], capture_output=True, text=True, timeout=5)
        dirty = subprocess.run(["git", "-C", str(project), "status", "--porcelain", "--", "player.py", "cpl", "static"], capture_output=True, text=True, timeout=5)
        env["git"] = (g.stdout.strip() + (" (app files modified)" if dirty.stdout.strip() else "")) if g.returncode == 0 else "not a git repository"
    except Exception:
        env["git"] = "git not available"
    return env


def p95(v):
    v = sorted(v)
    return v[min(len(v) - 1, int(round(0.95 * (len(v) - 1))))] if v else 0


class ReportPlugin:
    def __init__(self, outdir, project, target_info=None):
        self.outdir, self.project, self.target = Path(outdir), project, target_info
        self.meta, self.results, self.t0 = {}, {}, time.time()
        self.remote_env = {}

    # ---- collection: severity / area / controls covered come from markers
    def pytest_collection_modifyitems(self, items):
        for it in items:
            sev = it.get_closest_marker("sev")
            cov = it.get_closest_marker("covers")
            self.meta[it.nodeid] = {"severity": int(sev.args[0]) if sev else 2, "area": Path(str(it.fspath)).stem.replace("test_", ""),
                                    "covers": list(cov.args) if cov else []}

    def pytest_runtest_logreport(self, report):
        r = self.results.setdefault(report.nodeid, {"id": report.nodeid, "outcome": "passed", "duration_s": 0.0, "message": "", "phase": ""})
        r["duration_s"] = round(r["duration_s"] + report.duration, 3)
        if report.failed:
            r["outcome"] = "failed" if report.when == "call" else "error"
            r["phase"] = report.when
            try:
                r["message"] = report.longrepr.reprcrash.message
            except Exception:
                r["message"] = str(report.longrepr)[:1500]
            r["traceback"] = str(report.longrepr)[-3000:]
        elif report.skipped and r["outcome"] == "passed":
            r["outcome"] = "skipped"
            lr = report.longrepr
            r["message"] = lr[2] if isinstance(lr, tuple) and len(lr) > 2 else str(lr)

    def pytest_sessionfinish(self, session, exitstatus):
        self.outdir.mkdir(parents=True, exist_ok=True)
        tests = []
        for nid, r in self.results.items():
            m = self.meta.get(nid, {"severity": 2, "area": "?", "covers": []})
            t = {**r, "area": m["area"], "covers": m["covers"]}
            if r["outcome"] in ("failed", "error"):
                t["severity"] = m["severity"]
            tests.append(t)
        counts = {k: sum(1 for t in tests if t["outcome"] == k) for k in ("passed", "failed", "error", "skipped")}
        by_sev = {s: sum(1 for t in tests if t.get("severity") == s) for s in (1, 2, 3, 4)}
        groups = {}
        for c in client.CALLS:
            groups.setdefault(f"{c['method']} {c['path']}", []).append(c["ms"])
        timing = {k: {"n": len(v), "min_ms": round(min(v), 1), "avg_ms": round(sum(v) / len(v), 1), "p95_ms": round(p95(v), 1), "max_ms": round(max(v), 1)}
                  for k, v in sorted(groups.items())}
        slow = sorted((c for c in client.CALLS if c["method"] != "OSC"), key=lambda c: -c["ms"])[:15]
        env = environment(self.project, self.target)
        env.update(self.remote_env)
        covered = sorted({c for t in tests if t["outcome"] == "passed" for c in t["covers"]})
        doc = {"environment": env, "started": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(self.t0)), "duration_s": round(time.time() - self.t0, 1),
               "summary": {"total": len(tests), **counts, "failed_by_severity": by_sev}, "severity_rubric": SEV_NAMES,
               "tests": tests, "timing": {"calls": len(client.CALLS), "by_endpoint": timing, "slowest": slow}, "controls_passed": covered, "calls": client.CALLS}
        (self.outdir / "results.json").write_text(json.dumps(doc, indent=1), encoding="utf-8")
        (self.outdir / "report.md").write_text(self.markdown(doc), encoding="utf-8")
        self.junit(tests, doc)

    # ---- writers
    def markdown(self, d):
        e, s = d["environment"], d["summary"]
        L = ["# Cue Media Engine API test report", "",
             f"- **Started:** {d['started']}  ({d['duration_s']} s)",
             f"- **Platform:** {e['platform']} ({e['machine']}), Python {e['python']}, {e['pygame']}",
             f"- **ffmpeg (harness machine):** {e['ffmpeg_local'] or 'not found'}",
             f"- **player.py:** sha256 `{(e['player_py']['sha256'] or '')[:16]}`, {e['player_py']['bytes']} bytes, modified {e['player_py']['mtime']}; git: {e['git']}",
             f"- **App tree (player.py + cpl/ + static/):** sha256 `{e['app_tree']['sha256'][:16]}`, {e['app_tree']['files']} files, {e['app_tree']['bytes']} bytes",
             f"- **Target:** {json.dumps(e.get('target'))}"]
        if e.get("instance"):
            L.append(f"- **Instance (as reported by the player):** {json.dumps(e['instance'])}")
        L += ["", "## Summary", "", f"| total | passed | failed | errors | skipped |", "|---|---|---|---|---|",
              f"| {s['total']} | {s['passed']} | {s['failed']} | {s['error']} | {s['skipped']} |", "",
              "Failed tests by severity (1 = no audio/crash/stuck/wrong track on air, 2 = wrong behaviour, 3 = UI/usability glitch, 4 = cosmetic):", "",
              "| 1 | 2 | 3 | 4 |", "|---|---|---|---|", "| " + " | ".join(str(s["failed_by_severity"][k]) for k in (1, 2, 3, 4)) + " |", ""]
        bad = sorted((t for t in d["tests"] if t["outcome"] in ("failed", "error")), key=lambda t: (t.get("severity", 2), t["id"]))
        L.append("## Failures (most severe first)")
        L.append("")
        if not bad:
            L.append("None.")
        for t in bad:
            L += [f"### S{t['severity']} `{t['id']}`", "", "```", (t["message"] or "")[:1200], "```", ""]
        sk = [t for t in d["tests"] if t["outcome"] == "skipped"]
        L += ["## Skipped", ""] + ([f"- `{t['id']}`: {t['message']}" for t in sk] or ["None."]) + ["", "## Timing per endpoint (ms)", "",
              "| endpoint | calls | min | avg | p95 | max |", "|---|---|---|---|---|---|"]
        for k, v in d["timing"]["by_endpoint"].items():
            L.append(f"| `{k}` | {v['n']} | {v['min_ms']} | {v['avg_ms']} | {v['p95_ms']} | {v['max_ms']} |")
        L += ["", "Slowest calls:", ""] + [f"- {c['ms']} ms  {c['method']} {c['path']}  (HTTP {c['status']})  in `{c['test']}`" for c in d["timing"]["slowest"][:10]]
        L += ["", f"## Controls exercised by passing tests: {len(d['controls_passed'])}", ""]
        return "\n".join(L) + "\n"

    def junit(self, tests, doc):
        s = doc["summary"]
        root = ET.Element("testsuites")
        suite = ET.SubElement(root, "testsuite", name="companionplayer-api", tests=str(s["total"]), failures=str(s["failed"]), errors=str(s["error"]),
                              skipped=str(s["skipped"]), time=str(doc["duration_s"]), timestamp=doc["started"].replace(" ", "T"))
        pr = ET.SubElement(suite, "properties")
        for k in ("platform", "python", "pygame", "git"):
            ET.SubElement(pr, "property", name=k, value=str(doc["environment"].get(k)))
        ET.SubElement(pr, "property", name="app_tree_sha256", value=str(doc["environment"]["app_tree"]["sha256"]))
        ET.SubElement(pr, "property", name="player_py_sha256", value=str(doc["environment"]["player_py"]["sha256"]))
        for t in tests:
            cls, _, name = t["id"].rpartition("::")
            tc = ET.SubElement(suite, "testcase", classname=cls.replace("/", ".").replace(".py", ""), name=name, time=str(t["duration_s"]))
            p = ET.SubElement(tc, "properties")
            ET.SubElement(p, "property", name="area", value=t["area"])
            if "severity" in t:
                ET.SubElement(p, "property", name="severity", value=str(t["severity"]))
            if t["outcome"] == "failed":
                ET.SubElement(tc, "failure", message=(t["message"] or "")[:500], type=f"S{t.get('severity', 2)}").text = t.get("traceback", "")
            elif t["outcome"] == "error":
                ET.SubElement(tc, "error", message=(t["message"] or "")[:500]).text = t.get("traceback", "")
            elif t["outcome"] == "skipped":
                ET.SubElement(tc, "skipped", message=(t["message"] or "")[:500])
        ET.ElementTree(root).write(self.outdir / "junit.xml", encoding="utf-8", xml_declaration=True)
