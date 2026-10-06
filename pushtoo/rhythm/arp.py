"""Arpeggiator patterns (PRD: Rhythm). Pure functions over MIDI note numbers."""

PATTERNS = ("Up", "Down", "Up-down", "As played", "Random")
MAX_OCTAVES = 4


def sequence(notes: list[int], pattern: str, octaves: int = 1) -> list[int]:
    """The notes an arp steps through, given the held notes in the order they were
    played. Random returns the pool; the player picks from it each step."""
    if not notes:
        return []
    ordered = list(dict.fromkeys(notes)) if pattern == "As played" else sorted(set(notes))
    pool = [n + 12 * o for o in range(octaves) for n in ordered if n + 12 * o <= 127]
    if pattern == "Down":
        return pool[::-1]
    if pattern == "Up-down":
        return pool + pool[-2:0:-1]  # the top and bottom notes aren't repeated at the turns
    return pool
