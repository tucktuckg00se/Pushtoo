"""The profile editor: overrides beside the profile, and the local server."""

import http.client
import json
import threading

import pytest

from pushtoo.edit import Editor, diff, serve
from pushtoo.profiles.loader import ProfileError, ProfileStore, load, parse

PROFILE = """# My synth rig, by hand
name: Rig
knobs:
  pages:
    - name: Synth
      controls:
        - {name: Cutoff, cc: 74, channel: 1, color: orange}
"""


@pytest.fixture
def folder(tmp_path):
    config = tmp_path / "profiles"
    config.mkdir()
    (config / "rig.yaml").write_text(PROFILE)
    return config


def test_diff_keeps_only_what_changed():
    base = {"name": "A", "play": {"strip": "Pitch bend", "keyboard": {"channel": 1}}, "x": [1, 2]}
    edited = {"name": "A", "play": {"strip": "Mod wheel", "keyboard": {"channel": 1}}, "x": [1, 3]}
    assert diff(base, edited) == {"play": {"strip": "Mod wheel"}, "x": [1, 3]}
    assert diff(base, base) is None


def test_overrides_merge_over_the_profile_and_lists_replace_whole():
    profile = parse(PROFILE, "rig.yaml", "play: {strip: Mod wheel}\nname: Rig 2\n")
    assert profile.name == "Rig 2" and profile.play.strip == "Mod wheel"
    assert profile.knobs.pages[0].controls[0].name == "Cutoff"  # untouched
    replaced = parse(PROFILE, "rig.yaml", "knobs: {pages: [{name: New}]}\n")
    assert [p.name for p in replaced.knobs.pages] == ["New"]


def test_errors_name_the_file_the_bad_value_came_from():
    with pytest.raises(ProfileError, match=r"^rig-user.yaml line 2: play.strip"):
        parse(PROFILE, "rig.yaml", "play:\n  strip: Sideways\n", "rig-user.yaml")
    with pytest.raises(ProfileError, match=r"^rig.yaml line 2: name"):
        parse("knobs: {}\nname: ''\n", "rig.yaml", "play: {strip: Mod wheel}\n", "rig-user.yaml")


def test_saving_writes_only_the_edits_and_leaves_the_profile_alone(folder):
    editor = Editor(folder)
    edited = editor.profile("rig.yaml")["profile"]
    edited["knobs"]["pages"][0]["controls"][0]["name"] = "Filter"
    edited["rhythm"]["tempo"] = 96.0
    result = editor.save("rig.yaml", edited)
    assert result == {"ok": True, "changes": result["changes"], "saved": "rig-user.yaml"}
    assert (folder / "rig.yaml").read_text() == PROFILE  # byte for byte
    profile = load(folder / "rig.yaml")
    assert profile.knobs.pages[0].controls[0].name == "Filter" and profile.rhythm.tempo == 96
    assert set(result["changes"]) == {"knobs", "rhythm"}
    # Back to the file as written: the edits file goes.
    assert editor.save("rig.yaml", editor.profile("rig.yaml")["base"])["saved"] is None
    assert not (folder / "rig-user.yaml").exists()


def test_a_bad_edit_is_refused_and_nothing_is_written(folder):
    editor = Editor(folder)
    edited = editor.profile("rig.yaml")["profile"]
    edited["knobs"]["pages"][0]["controls"][0]["cc"] = 300
    result = editor.save("rig.yaml", edited)
    assert not result["ok"]
    assert result["error"].startswith("knobs.pages[0].controls[0].cc: Input should be less")
    assert not (folder / "rig-user.yaml").exists()


def test_only_profiles_in_the_folder_can_be_reached(folder):
    editor = Editor(folder)
    with pytest.raises(ProfileError):
        editor.profile("../state.yaml")


def test_browse_lists_profiles_without_their_edits(folder):
    (folder / "rig-user.yaml").write_text("name: Rig edited\n")
    store = ProfileStore(folder)
    assert [p.name for p in store.paths()] == ["default.yaml", "rig.yaml"]
    assert store.select(folder / "rig.yaml").name == "Rig edited"


def test_the_watcher_reloads_when_only_the_edits_change(folder):
    store = ProfileStore(folder)
    store.select(folder / "rig.yaml")
    (folder / "rig-user.yaml").write_text("name: Rig edited\n")
    assert store.poll().name == "Rig edited"


@pytest.fixture
def server(folder):
    server = serve(folder)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield server.server_address[1]
    server.shutdown()
    server.server_close()


def request(port, method, path, body=None, host=None):
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    headers = {"Host": host or f"127.0.0.1:{port}"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    connection.request(method, path, json.dumps(body) if body is not None else None, headers)
    response = connection.getresponse()
    return response.status, response.read()


def test_the_server_serves_the_page_and_saves(server, folder):
    status, page = request(server, "GET", "/")
    assert status == 200 and b"Pushtoo" in page
    status, body = request(server, "GET", "/api/profile?file=rig.yaml")
    edited = json.loads(body)["profile"]
    edited["name"] = "Rig live"
    status, body = request(server, "POST", "/api/save", {"file": "rig.yaml", "profile": edited})
    assert status == 200 and json.loads(body)["ok"]
    assert load(folder / "rig.yaml").name == "Rig live"


def test_the_server_turns_away_other_hosts(server):
    status, _ = request(server, "GET", "/api/profiles", host="evil.example:80")
    assert status == 403
