import ctypes
import errno
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from sentinel import bundle
from sentinel.errors import SentinelError


class AtomicPublicationTests(unittest.TestCase):
    def test_publishes_directory_without_changing_contents(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            staged, destination = root / "staged", root / "installed"
            staged.mkdir()
            (staged / "payload").write_bytes(b"verified bundle")
            self.assertTrue(bundle._publish_noreplace(staged, destination))
            self.assertFalse(staged.exists())
            self.assertEqual((destination / "payload").read_bytes(), b"verified bundle")

    def test_existing_empty_and_populated_directories_are_never_replaced(self):
        for populated in (False, True):
            with self.subTest(populated=populated), tempfile.TemporaryDirectory() as directory:
                root = Path(directory).resolve()
                staged, destination = root / "staged", root / "installed"
                staged.mkdir()
                destination.mkdir()
                (staged / "payload").write_bytes(b"new")
                if populated:
                    (destination / "payload").write_bytes(b"existing")
                inode = destination.stat().st_ino
                self.assertFalse(bundle._publish_noreplace(staged, destination))
                self.assertEqual(destination.stat().st_ino, inode)
                self.assertEqual((staged / "payload").read_bytes(), b"new")
                if populated:
                    self.assertEqual((destination / "payload").read_bytes(), b"existing")
                else:
                    self.assertEqual(list(destination.iterdir()), [])

    def test_macos_uses_exclusive_native_rename(self):
        library = Mock()
        library.renamex_np.return_value = 0
        with patch.object(bundle.sys, "platform", "darwin"), patch.object(bundle.ctypes, "CDLL", return_value=library):
            self.assertTrue(bundle._publish_noreplace(Path("staged"), Path("installed")))
        library.renamex_np.assert_called_once_with(b"staged", b"installed", 4)
        library.renameat2.assert_not_called()
        self.assertEqual(library.renamex_np.restype, ctypes.c_int)

    def test_native_errors_fail_without_ordinary_rename(self):
        library = Mock()
        library.renamex_np.return_value = -1
        with patch.object(bundle.sys, "platform", "darwin"), patch.object(bundle.ctypes, "CDLL", return_value=library), \
                patch.object(bundle.ctypes, "get_errno", return_value=errno.EACCES), patch.object(bundle.os, "rename") as ordinary:
            with self.assertRaises(SentinelError) as stopped:
                bundle._publish_noreplace(Path("staged"), Path("installed"))
        self.assertEqual(stopped.exception.code, "atomicPublishFailed")
        ordinary.assert_not_called()

    def test_missing_macos_api_is_reported(self):
        with patch.object(bundle.sys, "platform", "darwin"), patch.object(bundle.ctypes, "CDLL", return_value=object()):
            with self.assertRaises(SentinelError) as stopped:
                bundle._publish_noreplace(Path("staged"), Path("installed"))
        self.assertEqual(stopped.exception.code, "atomicPublishUnavailable")
