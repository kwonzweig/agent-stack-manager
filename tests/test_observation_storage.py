import os
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
import unittest

from asm_app.server import Connection, save_observation


class ObservationStorageTests(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.connection = Connection("http://127.0.0.1:3100", "lab")

    def test_observation_cannot_write_through_a_link(self):
        outside_dir = TemporaryDirectory()
        self.addCleanup(outside_dir.cleanup)
        outside = Path(outside_dir.name)
        link = self.root / ".asm"
        if os.name == "nt":
            subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(outside)],
                           check=True, capture_output=True)
            self.addCleanup(link.rmdir)
        else:
            link.symlink_to(outside, target_is_directory=True)
            self.addCleanup(link.unlink)
        with self.assertRaises(ValueError):
            save_observation(self.root, "cao", self.connection, {"items": []})
        self.assertFalse((outside / "observations/cao.json").exists())

    def test_observation_does_not_overwrite_an_existing_temp_file(self):
        directory = self.root / ".asm/observations"
        directory.mkdir(parents=True)
        existing = directory / "cao.tmp"
        existing.write_text("unrelated file", encoding="utf-8")
        save_observation(self.root, "cao", self.connection, {"items": []})
        self.assertTrue((directory / "cao.json").is_file())
        self.assertEqual(existing.read_text(encoding="utf-8"), "unrelated file")
