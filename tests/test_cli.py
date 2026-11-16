from contextlib import redirect_stderr, redirect_stdout
import io
from pathlib import Path
import tempfile
import unittest
from zipfile import ZipFile

from asm_app import cli

ROOT = Path(__file__).resolve().parents[1]


class CommandTests(unittest.TestCase):
    def test_export_writes_the_paperclip_package(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "cao-paperclip.zip"
            with redirect_stdout(io.StringIO()):
                code = cli.main(["--root", str(ROOT), "export", "cao", "--consumer", "paperclip", "--output", str(output)])
            self.assertEqual(code, 0)
            with ZipFile(output) as archive:
                self.assertIn("remote-import-plan.json", archive.namelist())

    def test_there_is_no_command_that_reaches_a_consumer(self):
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
            cli.main(["--root", str(ROOT), "paperclip", "cao", "--company", "company-1"])
        self.assertEqual(error.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
