from datetime import timedelta
import unittest

from CNA.Framework import Color, Game, GameTime, NativeUnavailableError, Vector2
from Microsoft.Xna.Framework import Color as XnaColor


class ValueTypeTests(unittest.TestCase):
    def test_vector_arithmetic_is_local(self) -> None:
        vector = Vector2(2, 3).Add(Vector2(4, -1))
        self.assertEqual(vector, Vector2(6, 2))
        self.assertEqual(Vector2(3, 4).LengthSquared, 25)

    def test_known_colors(self) -> None:
        self.assertEqual(Color.CornflowerBlue, Color(100, 149, 237, 255))
        self.assertEqual(XnaColor.CornflowerBlue, Color.CornflowerBlue)
        with self.assertRaises(ValueError):
            Color(256, 0, 0)

    def test_game_time_defaults(self) -> None:
        self.assertEqual(GameTime().ElapsedGameTime, timedelta())


class LifecycleTests(unittest.TestCase):
    def test_run_reports_missing_native_abi(self) -> None:
        with self.assertRaises(NativeUnavailableError):
            Game().Run()

    def test_context_manager_closes_game(self) -> None:
        game = Game()
        with game:
            pass
        with self.assertRaises(RuntimeError):
            game.Exit()


if __name__ == "__main__":
    unittest.main()
