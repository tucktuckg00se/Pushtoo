from pushtoo.midi.router import OUT_PORT, MidiRouter, port_display_name


class FakeOutput:
    def __init__(self) -> None:
        self.sent: list[list[int]] = []
        self.closed = False

    def send_message(self, message):
        self.sent.append(message)

    def close_port(self):
        self.closed = True


ALSA_PORTS = [
    "Midi Through:Midi Through Port-0 14:0",
    "Ableton Push 2:Ableton Push 2 Live Port 32:0",
    "Pushtoo:Pushtoo Out 129:0",
    "RtMidiIn Client:RtMidi input 133:0",
    "USB MIDI:USB MIDI MIDI 1 24:0",
]


def make_router(ports=ALSA_PORTS):
    virtual = FakeOutput()
    opened: dict[str, FakeOutput] = {}
    present = list(ports)

    def open_port(name):
        if name not in [port_display_name(p) for p in present]:
            return None
        opened[name] = FakeOutput()
        return opened[name]

    router = MidiRouter(virtual_out=virtual, list_ports=lambda: present, open_port=open_port)
    return router, virtual, opened, present


def test_port_display_name_drops_alsa_address():
    assert port_display_name("USB MIDI:USB MIDI MIDI 1 24:0") == "USB MIDI:USB MIDI MIDI 1"


def test_destinations_hide_own_push_and_system_ports():
    router, *_ = make_router()
    assert router.destinations() == [OUT_PORT]  # cached until refreshed
    assert router.refresh_destinations() == [OUT_PORT, "USB MIDI:USB MIDI MIDI 1"]


def test_notes_go_to_their_destination_and_release_there():
    router, virtual, opened, _ = make_router()
    router.note_on("pad", "USB MIDI:USB MIDI MIDI 1", 1, 60, 100)
    router.note_on("other", OUT_PORT, 0, 62, 90)
    usb = opened["USB MIDI:USB MIDI MIDI 1"]
    assert usb.sent == [[0x91, 60, 100]]
    assert virtual.sent == [[0x90, 62, 90]]
    router.note_off("pad")
    assert usb.sent[-1] == [0x81, 60, 0]


def test_missing_destination_drops_messages_without_raising():
    router, virtual, opened, _ = make_router()
    router.note_on("pad", "Gone:Port", 0, 60, 100)
    assert opened == {}
    assert virtual.sent == []


def test_vanished_port_is_closed_on_refresh():
    router, _, opened, present = make_router()
    router.note_on("pad", "USB MIDI:USB MIDI MIDI 1", 0, 60, 100)
    present.pop()  # unplugged
    router.refresh_destinations()
    assert opened["USB MIDI:USB MIDI MIDI 1"].closed


def test_pitch_bend_is_14_bit_centered():
    router, virtual, *_ = make_router()
    router.pitch_bend(OUT_PORT, 0, 0)
    router.pitch_bend(OUT_PORT, 0, 8191)
    router.pitch_bend(OUT_PORT, 0, -8192)
    assert virtual.sent == [[0xE0, 0, 64], [0xE0, 127, 127], [0xE0, 0, 0]]


def test_aftertouch_follows_the_held_note():
    router, virtual, *_ = make_router()
    router.note_on("pad", OUT_PORT, 2, 50, 100)
    router.poly_aftertouch("pad", 70)
    router.poly_aftertouch("not held", 70)
    assert virtual.sent[-1] == [0xA2, 50, 70]
    assert len(virtual.sent) == 2


def test_panic_covers_every_open_destination():
    router, virtual, opened, _ = make_router()
    router.note_on("pad", "USB MIDI:USB MIDI MIDI 1", 0, 60, 100)
    router.panic()
    usb = opened["USB MIDI:USB MIDI MIDI 1"]
    assert [0x80, 60, 0] in usb.sent
    assert sum(1 for m in usb.sent if m[0] & 0xF0 == 0xB0) == 32
    assert sum(1 for m in virtual.sent if m[0] & 0xF0 == 0xB0) == 32


def test_short_port_name_drops_repeated_client_name():
    from pushtoo.midi.router import short_port_name

    assert short_port_name("USB MIDI:USB MIDI MIDI 1") == "USB MIDI MIDI 1"
    assert short_port_name(OUT_PORT) == OUT_PORT
