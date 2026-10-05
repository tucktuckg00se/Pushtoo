import os
import time
from importlib import resources

import pytest

from pushtoo.profiles.loader import ProfileError, ProfileStore, ensure_default, parse
from pushtoo.profiles.schema import FREE_CCS, Profile
from pushtoo.profiles.state import StateSaver, StateStore


def test_shipped_template_is_valid_and_matches_defaults():
    text = (resources.files("pushtoo.profiles") / "default.yaml").read_text()
    assert parse(text) == Profile()


def test_default_knob_map_follows_the_prd():
    pages = Profile().knobs.pages
    assert len(pages) == 8 and all(len(p.controls) == 8 for p in pages)
    ccs_ch15 = [c.cc for p in pages[:4] for c in p.controls]
    assert ccs_ch15 == list(FREE_CCS)
    assert {c.channel for p in pages[:4] for c in p.controls} == {15}
    assert {c.channel for p in pages[4:] for c in p.controls} == {16}
    assert 64 not in ccs_ch15 and 7 not in ccs_ch15 and 1 not in ccs_ch15


def test_empty_file_means_all_defaults():
    assert parse("") == Profile()


def test_custom_knobs_replace_the_default_map():
    profile = parse(
        """
knobs:
  pages:
    - name: Synth
      controls:
        - {name: Cutoff, cc: 74, channel: 1, color: orange}
        - null
        - {name: Detune, cc: 94, channel: 1, bipolar: true}
"""
    )
    page = profile.knobs.pages[0]
    assert len(profile.knobs.pages) == 1
    assert page.controls[1] is None
    assert page.controls[2].start_value == 64  # bipolar starts centered


def test_errors_name_the_field_and_line():
    text = """name: Test
knobs:
  pages:
    - name: Synth
      controls:
        - {name: Cutoff, cc: 200, channel: 1}
"""
    with pytest.raises(ProfileError) as error:
        parse(text, "test.yaml")
    message = str(error.value)
    assert message.startswith("test.yaml line 6: knobs.pages[0].controls[0]")
    assert "127" in message


def test_unknown_keys_are_rejected():
    with pytest.raises(ProfileError, match="mixx"):
        parse("mixx: {}\n")


def test_undo_action_needs_exactly_one_kind():
    with pytest.raises(ProfileError, match="exactly one"):
        parse("undo:\n  undo: {keys: ctrl+z, midi: {cc: 1, channel: 1}}\n")


def test_invalid_yaml_reports_line():
    with pytest.raises(ProfileError, match="line 2: not valid YAML"):
        parse("name: ok\n  oops: bad indent\n")


def test_store_reloads_on_change_and_keeps_last_good(tmp_path):
    store = ProfileStore(tmp_path)
    path = ensure_default(tmp_path)
    store.select(path)
    assert store.poll() is None

    path.write_text("name: Changed\n")
    future = time.time() + 5
    os.utime(path, (future, future))
    reloaded = store.poll()
    assert isinstance(reloaded, Profile) and reloaded.name == "Changed"

    path.write_text("mix: {channel: 99}\n")
    os.utime(path, (future + 5, future + 5))
    error = store.poll()
    assert isinstance(error, ProfileError)
    assert store.profile.name == "Changed"


def test_state_round_trips(tmp_path):
    store = StateStore(tmp_path / "state.yaml")
    store.update("default.yaml", "Default", {"mode": "knobs", "knobs": {"values": {"0,1": 64}}})
    store.save()
    again = StateStore(tmp_path / "state.yaml")
    assert again.last_profile == "default.yaml"
    assert again.for_profile("Default")["knobs"]["values"]["0,1"] == 64
    assert again.for_profile("Other") == {}


def test_corrupt_state_is_ignored(tmp_path):
    (tmp_path / "state.yaml").write_text("{{{ not yaml")
    assert StateStore(tmp_path / "state.yaml").data == {}


def test_saver_debounces_bursts(tmp_path, monkeypatch):
    monkeypatch.setattr("pushtoo.profiles.state.SAVE_DELAY", 0.2)
    calls = []

    def snapshot():
        calls.append(1)
        return ("default.yaml", "Default", {"n": len(calls)})

    saver = StateSaver(StateStore(tmp_path / "state.yaml"), snapshot)
    saver.start()
    for _ in range(20):  # a burst well inside one debounce window
        saver.mark_dirty()
    time.sleep(0.6)
    assert len(calls) == 1
    saver.stop()
    assert (tmp_path / "state.yaml").exists()
