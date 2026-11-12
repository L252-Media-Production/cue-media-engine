"""The one product version (APP_VERSION in the app: player.py, or cpl/ after the split): in /api/state, as a Companion variable, in the variable list and in the Settings footer."""
import re, sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import gen_controls                                           # noqa: E402

PLAYER = Path(__file__).resolve().parent.parent.parent / "player.py"
VERSION = re.search(r'^APP_VERSION = "([^"]+)"', gen_controls.read_sources(PLAYER), re.M).group(1)


@pytest.mark.sev(3)
def test_version_is_in_state_and_is_a_variable(api):
    assert re.fullmatch(r"\d+\.\d+\.\d+", VERSION), VERSION
    s = api.state()
    assert s["version"] == VERSION and s["player_version"] == VERSION
    v = {x["name"]: x for x in api.get("/api/variables").json["vars"]}
    assert v["player_version"]["value"] == VERSION and v["player_version"]["info"].strip()


@pytest.mark.sev(4)
@pytest.mark.covers("http.GET /")
def test_settings_footer_shows_the_version(api):
    page = api.request("GET", "/").text
    assert 'id=appver' in page and "'Cue Media Engine '+s.version" in page
