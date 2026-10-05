from pushtoo.midi.notes import SoundingNotes, panic_messages

OUT, USB = "Pushtoo Out", "USB MIDI"


def test_release_sends_the_pitch_that_was_pressed():
    notes = SoundingNotes()
    assert notes.press("pad", OUT, 0, 60, 100) == [(OUT, [0x90, 60, 100])]
    # Layout changes while held don't matter: release uses the stored pitch.
    assert notes.release("pad") == [(OUT, [0x80, 60, 0])]


def test_release_of_unknown_source_is_silent():
    assert SoundingNotes().release("nothing") == []


def test_shared_pitch_stays_on_until_last_source_releases():
    notes = SoundingNotes()
    notes.press("a", OUT, 0, 60, 100)
    notes.press("b", OUT, 0, 60, 90)
    assert notes.release("a") == []
    assert notes.notes_on(OUT, 0) == {60}
    assert notes.release("b") == [(OUT, [0x80, 60, 0])]


def test_repress_releases_previous_note():
    notes = SoundingNotes()
    notes.press("pad", OUT, 0, 60, 100)
    assert notes.press("pad", OUT, 0, 62, 100) == [(OUT, [0x80, 60, 0]), (OUT, [0x90, 62, 100])]


def test_channels_and_destinations_are_independent():
    notes = SoundingNotes()
    notes.press("a", OUT, 0, 60, 100)
    notes.press("b", OUT, 9, 60, 100)
    notes.press("c", USB, 0, 60, 100)
    assert notes.release("a") == [(OUT, [0x80, 60, 0])]
    assert notes.notes_on(OUT, 9) == {60}
    assert notes.notes_on(USB, 0) == {60}
    assert notes.notes_on(OUT, 0) == set()


def test_release_goes_to_the_destination_used_at_press_time():
    notes = SoundingNotes()
    notes.press("pad", USB, 1, 64, 100)
    # Even if the layout's output changes to OUT while the pad is held:
    assert notes.release("pad") == [(USB, [0x81, 64, 0])]


def test_held_by_reports_the_sounding_key():
    notes = SoundingNotes()
    notes.press("pad", USB, 2, 50, 100)
    assert notes.held_by("pad") == (USB, 2, 50)
    assert notes.held_by("other") is None


def test_panic_releases_tracked_notes_then_resets_every_destination():
    notes = SoundingNotes()
    notes.press("a", USB, 1, 64, 100)
    messages = panic_messages(notes, [OUT, USB])
    assert messages[0] == (USB, [0x81, 64, 0])
    cc = messages[1:]
    assert len(cc) == 64  # 2 destinations x 16 channels x 2 controllers
    assert {d for d, _ in cc} == {OUT, USB}
    assert {m[0] & 0x0F for _, m in cc} == set(range(16))
    assert {m[1] for _, m in cc} == {121, 123}
    assert notes.notes_on(USB, 1) == set()
