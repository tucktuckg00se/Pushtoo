from pushtoo.midi.notes import SoundingNotes, panic_messages


def test_release_sends_the_pitch_that_was_pressed():
    notes = SoundingNotes()
    assert notes.press("pad", 0, 60, 100) == [[0x90, 60, 100]]
    # Layout changes while held don't matter: release uses the stored pitch.
    assert notes.release("pad") == [[0x80, 60, 0]]


def test_release_of_unknown_source_is_silent():
    assert SoundingNotes().release("nothing") == []


def test_shared_pitch_stays_on_until_last_source_releases():
    notes = SoundingNotes()
    notes.press("a", 0, 60, 100)
    notes.press("b", 0, 60, 90)
    assert notes.release("a") == []
    assert notes.is_sounding(0, 60)
    assert notes.release("b") == [[0x80, 60, 0]]


def test_repress_releases_previous_note():
    notes = SoundingNotes()
    notes.press("pad", 0, 60, 100)
    assert notes.press("pad", 0, 62, 100) == [[0x80, 60, 0], [0x90, 62, 100]]


def test_channels_are_independent():
    notes = SoundingNotes()
    notes.press("a", 0, 60, 100)
    notes.press("b", 9, 60, 100)
    assert notes.release("a") == [[0x80, 60, 0]]
    assert notes.is_sounding(9, 60)


def test_panic_releases_tracked_notes_then_resets_every_channel():
    notes = SoundingNotes()
    notes.press("a", 1, 64, 100)
    messages = panic_messages(notes)
    assert messages[0] == [0x81, 64, 0]
    cc = messages[1:]
    assert len(cc) == 32
    assert {m[0] & 0x0F for m in cc} == set(range(16))
    assert {m[1] for m in cc} == {121, 123}
    assert notes.sounding_notes() == set()
