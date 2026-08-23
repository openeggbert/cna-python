from __future__ import annotations

import ctypes
import unittest

from Microsoft.Xna.Framework import Color, Game, GraphicsDeviceManager, PlayerIndex, Vector2
from Microsoft.Xna.Framework.Graphics import SpriteBatch, Texture2D
from Microsoft.Xna.Framework.Input import ButtonState, Keys
from Microsoft.Xna.Framework._language import Event


class EventOwner:
    Changed = Event()


class MappingTests(unittest.TestCase):
    def test_pascal_case_and_keyword_collision(self) -> None:
        self.assertTrue(hasattr(Game, "Run"))
        self.assertTrue(hasattr(Texture2D, "FromStream"))
        self.assertEqual(Keys.None_.value, 0)

    def test_events_preserve_duplicates_order_and_self_removal(self) -> None:
        owner, calls = EventOwner(), []
        def first(*args):
            calls.append("first")
            owner.Changed -= first
        def second(*args): calls.append("second")
        owner.Changed += first
        owner.Changed += first
        owner.Changed += second
        owner.Changed(owner, None)
        self.assertEqual(calls, ["first", "first", "second"])
        calls.clear()
        owner.Changed(owner, None)
        self.assertEqual(calls, ["second"])

    def test_event_exception_propagates_and_stops(self) -> None:
        owner, calls = EventOwner(), []
        def fail(*args): raise LookupError("event")
        def later(*args): calls.append("later")
        owner.Changed += fail
        owner.Changed += later
        with self.assertRaisesRegex(LookupError, "event"):
            owner.Changed(owner, None)
        self.assertEqual(calls, [])

    def test_public_types_do_not_inherit_native_or_ctypes_types(self) -> None:
        public = (Game, GraphicsDeviceManager, SpriteBatch, Texture2D, Vector2, Color, Keys, ButtonState, PlayerIndex)
        for value in public:
            with self.subTest(value=value):
                self.assertFalse(any(base.__module__.startswith("_cna_native") for base in value.__mro__))
                self.assertFalse(issubclass(value, (ctypes.Structure, ctypes._Pointer)))

    def test_invented_scaffold_members_are_absent(self) -> None:
        self.assertFalse(hasattr(SpriteBatch, "DrawRect"))
        from Microsoft.Xna.Framework import Graphics
        self.assertFalse(hasattr(Graphics, "BasicEffect"))


if __name__ == "__main__":
    unittest.main()
