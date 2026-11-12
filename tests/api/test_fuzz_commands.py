"""Every command template with awkward values: the answer must be a result word (HTTP 200), never a server error, and nothing may go on air."""
import itertools
import pytest

ODD = ["inf", "-inf", "nan", "1e999", "-0", "0x10", "²", "½", "٣", "99999999999999999999", "-1", "1.5", "%20", "a" * 300, "../..", "é", "true", "null"]
TEMPLATES = ["{v}/0", "0/{v}", "{v}/{v}", "0/0/{v}", "0/0/in/{v}", "0/0/out/{v}", "0/0/xftime/{v}", "0/0/end/{v}", "0/0/loop/{v}", "{v}/play", "{v}/mode/stop", "0/mode/{v}",
             "0/norm/lufs/{v}", "0/norm/track/{v}", "0/norm/ref/{v}", "seek/{v}", "volume/{v}", "volume/up/{v}", "volume/down/{v}", "duck/threshold/{v}", "duck/ratio/{v}",
             "duck/attack/{v}", "duck/release/{v}", "duck/level/{v}", "duck/threshold/inc/{v}", "duck/hold/{v}", "go_transition/{v}", "mode/{v}", "device/{v}",
             "preview/{v}/{v}", "preview/volume/{v}", "solo/{v}", "loop/{v}", "fadeout/{v}"]


@pytest.mark.sev(3)
@pytest.mark.parametrize("tpl", TEMPLATES)
def test_odd_values_in_commands_never_cause_a_server_error(std, tpl):
    api = std
    bad = []
    for v in ODD:
        r = api.request("GET", "/api/" + "/".join(__import__("urllib.parse").parse.quote(x, safe="") for x in tpl.format(v=v).split("/")))
        if r.status != 200:
            bad.append((v, r.status))
        else:
            assert isinstance(r.json["result"], str)
    assert not bad, f"/{tpl}: {bad[:6]}"
    s = api.state()
    assert s["state"] in ("stopped", "playing", "loading")
