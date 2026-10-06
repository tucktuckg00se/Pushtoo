"""`pushtoo doctor` and the frame rate chosen for the machine."""

from pushtoo import doctor
from pushtoo.system import DEFAULT_FPS, LOW_POWER_FPS, default_fps


def fake_usb(root, vendor="2982", product="1967", bus=3, dev=7):
    device = root / "3-1"
    device.mkdir(parents=True)
    for name, value in (("idVendor", vendor), ("idProduct", product),
                        ("busnum", str(bus)), ("devnum", str(dev))):  # fmt: skip
        (device / name).write_text(value + "\n")
    return root


def test_no_push_is_a_warning_not_a_failure(tmp_path):
    check = doctor._push_usb(tmp_path)
    assert check.state == "warn" and "not plugged in" in check.detail


def test_a_push_without_display_access_points_at_the_udev_rule(tmp_path):
    check = doctor._push_usb(fake_usb(tmp_path))  # /dev/bus/usb/003/007 isn't ours
    assert check.state == "fail" and "udev rule" in check.detail


def test_other_usb_devices_are_ignored(tmp_path):
    assert doctor._push_usb(fake_usb(tmp_path, vendor="1234")).state == "warn"


def test_missing_sequencer_fails_with_a_fix(tmp_path):
    check = doctor._sequencer(str(tmp_path / "seq"))
    assert check.state == "fail" and "snd-seq" in check.detail


def test_service_states():
    assert "not installed" in doctor._service(lambda *a: "").detail
    replies = {"is-enabled": "enabled", "is-active": "active"}
    assert doctor._service(lambda q: replies[q]).detail == "enabled, active"


def test_running_instance_is_reported(tmp_path):
    from pushtoo import instance

    lock = instance.acquire(tmp_path / "l")
    assert doctor._running(tmp_path / "l").detail == "running"
    lock.close()
    assert doctor._running(tmp_path / "l").detail == "not running"


def test_exit_code_follows_failures(monkeypatch, capsys):
    ok, fail = doctor.Check("a", "ok", ""), doctor.Check("b", "fail", "fix it")
    monkeypatch.setattr(doctor, "checks", lambda: [ok, doctor.Check("c", "warn", "")])
    assert doctor.main() == 0
    monkeypatch.setattr(doctor, "checks", lambda: [ok, fail])
    assert doctor.main() == 1
    assert "✗ b: fix it" in capsys.readouterr().out


def test_raspberry_pi_gets_a_lower_frame_rate(tmp_path):
    model = tmp_path / "model"
    model.write_text("Raspberry Pi 4 Model B Rev 1.4\x00")
    assert default_fps(model) == LOW_POWER_FPS
    model.write_text("Some PC")
    assert default_fps(model) == DEFAULT_FPS
    assert default_fps(tmp_path / "missing") == DEFAULT_FPS
