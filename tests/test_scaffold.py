from datetime import timedelta
import unittest

from cna import Color, Game, GameTime, NativeUnavailableError, Vector2


class ValueTypeTests(unittest.TestCase):
    def test_vector_arithmetic_is_local(self) -> None:
        vector = (Vector2(2, 3) + Vector2(4, -1)).scale(2)
        self.assertEqual(vector, Vector2(12, 4))
        self.assertEqual(Vector2(3, 4).length_squared, 25)

    def test_known_colors(self) -> None:
        self.assertEqual(Color.CORNFLOWER_BLUE, Color(100, 149, 237, 255))
        with self.assertRaises(ValueError):
            Color(256, 0, 0)

    def test_game_time_defaults(self) -> None:
        self.assertEqual(GameTime().elapsed_game_time, timedelta())


class LifecycleTests(unittest.TestCase):
    def test_run_reports_missing_native_abi(self) -> None:
        with self.assertRaises(NativeUnavailableError):
            Game().run()

    def test_context_manager_closes_game(self) -> None:
        game = Game()
        with game:
            pass
        with self.assertRaises(RuntimeError):
            game.exit()


if __name__ == "__main__":
    unittest.main()
