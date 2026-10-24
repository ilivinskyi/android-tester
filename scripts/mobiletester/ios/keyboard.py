"""Typing on the iOS on-screen keyboard key by key, the way a person does.

The keys come from the runner's tree (ios/hierarchy.py). Letter keys are labelled in the case they type ("q",
or "Q" while shift is on), other keys by what they type ("1", "@") or by name ("space", "ampersand").
Characters not on the current layer are reached through the layer keys: shift, numbers, symbols, letters.
"""

from __future__ import annotations

from collections.abc import Callable

from .hierarchy import Key

# Keys labelled by name instead of the character they type.
NAMED = {"space": " ", "ampersand": "&", "return": "\n"}
_SWITCH_LABELS = ("shift", "numbers", "symbols", "letters")


class NoKeyboard(Exception):
    def __str__(self) -> str:
        return "no on-screen keyboard is shown: tap a text field first (or the simulator uses the Mac's keyboard)"


class CannotType(Exception):
    def __init__(self, char: str, typed: int):
        super().__init__(char, typed)
        self.char, self.typed = char, typed

    def __str__(self) -> str:
        return (f"no key for {self.char!r} on any keyboard layer (typed {self.typed} chars so far); it may need "
                "a long press (accents) or another keyboard language")


def types(key: Key) -> str:
    return NAMED.get(key.label, key.label if len(key.label) == 1 else "")


def _layer(keys: list[Key]) -> frozenset[str]:
    return frozenset(k.label for k in keys)


def _switches(keys: list[Key], char: str) -> list[Key]:
    """Layer keys worth trying for `char`, most likely first."""
    order = ("letters", "shift") if char.isalpha() else ("numbers", "symbols", "letters")
    by_label = {k.label: k for k in keys if k.label in _SWITCH_LABELS}
    return [by_label[label] for label in order if label in by_label]


class Typist:
    def __init__(self, read_keys: Callable[[], list[Key]], press: Callable[[Key], None]):
        self._read = read_keys
        self._press = press
        self._keys: list[Key] | None = None

    def _current(self) -> list[Key]:
        if self._keys is None:
            self._keys = self._read()
            if not self._keys:
                raise NoKeyboard()
        return self._keys

    def _find(self, char: str) -> Key | None:
        return next((k for k in self._current() if types(k) == char), None)

    def type(self, text: str) -> None:
        for i, char in enumerate(text):
            self._type_char(char, i)

    def _type_char(self, char: str, typed: int) -> None:
        tried: set[tuple[frozenset[str], str]] = set()
        while (key := self._find(char)) is None:
            layer = _layer(self._current())
            move = next((k for k in _switches(self._current(), char) if (layer, k.label) not in tried), None)
            if move is None:
                raise CannotType(char, typed)
            tried.add((layer, move.label))
            self._press(move)
            self._keys = None
        self._press(key)
        # Shift turns itself off after a letter, iOS capitalises after ". " and may return to letters after
        # a symbol: read the keyboard again unless the layer can't have changed.
        if not (char.isalpha() and char.islower()):
            self._keys = None

    def press_named(self, label: str) -> None:
        key = next((k for k in self._current() if k.label == label), None)
        if key is None:
            raise CannotType(label, 0)
        self._press(key)
        self._keys = None
