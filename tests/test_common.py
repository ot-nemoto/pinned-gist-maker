import io
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import common  # noqa: E402


class DisplayTest(unittest.TestCase):
    def test_width_counts_wide_chars_as_two(self):
        self.assertEqual(common.width("aあ🗻"), 5)

    def test_bar(self):
        self.assertEqual(common.bar(0, 100, 4), "    ")
        self.assertEqual(common.bar(0, 0, 4), "    ")
        self.assertEqual(common.bar(1, 100, 4), "█   ")
        self.assertEqual(common.bar(100, 100, 4), "████")


class UpdateGistTest(unittest.TestCase):
    def test_renames_single_placeholder_file(self):
        with mock.patch.object(common, "api", side_effect=[{"files": {"gistfile1.txt": {"content": "x"}}}, {}]) as api, \
             mock.patch("sys.stdout", io.StringIO()):
            common.update_gist("g", "t", "rank.txt", "new")
        self.assertEqual(api.call_args.args[3],
                         {"files": {"gistfile1.txt": {"filename": "rank.txt", "content": "new"}}})

    def test_skips_when_unchanged(self):
        with mock.patch.object(common, "api", return_value={"files": {"rank.txt": {"content": "same"}}}) as api, \
             mock.patch("sys.stdout", io.StringIO()):
            common.update_gist("g", "t", "rank.txt", "same")
        self.assertEqual(api.call_count, 1)


if __name__ == "__main__":
    unittest.main()
