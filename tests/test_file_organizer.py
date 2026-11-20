import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from file_organizer import organize, remove_duplicates


class FileOrganizerTests(unittest.TestCase):
    def test_scan_error_stops_before_moving_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            source.mkdir()
            original = source / "document.pdf"
            original.write_text("content", encoding="utf-8")

            with patch("file_organizer.os.walk", side_effect=PermissionError("denied")):
                result = organize(source, root / "output")

            self.assertEqual(result, 1)
            self.assertTrue(original.exists())

    def test_invalid_category_directory_returns_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            output = root / "output"
            source.mkdir()
            output.mkdir()
            original = source / "document.pdf"
            original.write_text("content", encoding="utf-8")
            (output / "Documents").write_text("not a directory", encoding="utf-8")

            with patch("builtins.input", return_value="Documents"):
                result = organize(source, output)

            self.assertEqual(result, 1)
            self.assertTrue(original.exists())

    def test_unwritable_log_prevents_duplicate_deletion(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            directory = root / "duplicates"
            directory.mkdir()
            first = directory / "first.bin"
            second = directory / "second.bin"
            first.write_bytes(b"same")
            second.write_bytes(b"same")
            log_parent = root / "not-a-directory"
            log_parent.write_text("file", encoding="utf-8")

            with patch("builtins.input", return_value="y"):
                result = remove_duplicates(directory, log_parent / "removed.log")

            self.assertEqual(result, 1)
            self.assertTrue(first.exists())
            self.assertTrue(second.exists())

    def test_removed_duplicates_are_written_to_log(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            directory = root / "duplicates"
            directory.mkdir()
            kept = directory / "a.bin"
            removed = directory / "b.bin"
            kept.write_bytes(b"same")
            removed.write_bytes(b"same")
            log_file = root / "removed.log"

            with patch("builtins.input", return_value="y"):
                result = remove_duplicates(directory, log_file)

            self.assertEqual(result, 0)
            self.assertTrue(kept.exists())
            self.assertFalse(removed.exists())
            log = log_file.read_text(encoding="utf-8")
            self.assertIn(f"REMOVED: {removed.resolve()}", log)
            self.assertIn(f"KEPT: {kept.resolve()}", log)


if __name__ == "__main__":
    unittest.main()