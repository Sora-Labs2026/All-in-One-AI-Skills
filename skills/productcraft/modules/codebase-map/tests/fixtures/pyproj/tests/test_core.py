import unittest

from app import core


class CoreTest(unittest.TestCase):
    def test_run(self):
        self.assertTrue(callable(core.run))


if __name__ == "__main__":
    unittest.main()
