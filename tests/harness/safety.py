"""Keep the harness away from production. A target is "ours" only when its config file lives in a folder the harness created (cptest-*)."""
import ipaddress, json, urllib.parse, urllib.request
from pathlib import Path

MARKER = "cptest-"
PRODUCTION_PORTS = {8080, 9000}


class Refused(Exception):
    pass


def _get(url, timeout=5):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def is_loopback(host):
    if host in ("localhost",):
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def inspect(base_url):
    """What we can learn about the target: harness_owned, loopback, and the signs that it looks like a production player."""
    u = urllib.parse.urlparse(base_url)
    host, port = u.hostname or "", u.port or 80
    info = {"host": host, "port": port, "netloc": f"{host}:{port}", "loopback": is_loopback(host), "reasons": [], "harness_owned": False}
    try:
        st = _get(base_url.rstrip("/") + "/api/state")
        se = _get(base_url.rstrip("/") + "/api/settings")
        pl = _get(base_url.rstrip("/") + "/api/playlists")
    except Exception as e:
        raise Refused(f"cannot read {base_url} ({e}); refusing to run against something I cannot identify")
    cfg = str(se.get("config_file", ""))
    info["config_file"] = cfg
    info["harness_owned"] = Path(cfg.replace("\\", "/")).parent.name.startswith(MARKER)
    if not info["harness_owned"]:
        info["reasons"].append("its config file is not in a harness-created folder (%s)" % (cfg or "unknown"))
    if port in PRODUCTION_PORTS:
        info["reasons"].append(f"port {port} is a default production port")
    if pl:
        info["reasons"].append(f"it has {len(pl)} playlist(s)")
    if st.get("state") not in ("stopped", None):
        info["reasons"].append(f"it is {st.get('state')} right now")
    info["looks_like_production"] = (not info["harness_owned"]) or bool(port in PRODUCTION_PORTS)
    return info


def check_target(base_url, allow_remote=False, confirm_target=None):
    """Raise Refused unless this target may be used. Returns the inspection result."""
    info = inspect(base_url)
    ok_local = info["harness_owned"] and info["loopback"] and info["port"] not in PRODUCTION_PORTS
    if ok_local:
        return info
    why = "; ".join(info["reasons"]) or ("it is not on this machine" if not info["loopback"] else "")
    if not allow_remote:
        raise Refused(f"refusing to run against {info['netloc']}: {why or 'it is not a local harness instance'}.\n"
                      "These tests delete playlists and change settings. If it really is a disposable test instance, pass "
                      f"--allow-remote --confirm-target {info['netloc']}")
    if confirm_target != info["netloc"]:
        raise Refused(f"--allow-remote needs --confirm-target {info['netloc']} (exactly) to confirm that this is the instance you mean")
    return info
