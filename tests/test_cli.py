from contextlib import redirect_stderr, redirect_stdout
import io
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from asm_app import cli

ROOT = Path(__file__).resolve().parents[1]


class CommandTests(unittest.TestCase):
    def test_export_takes_no_preset_output_or_consumer(self):
        # Every preset is exported to exports/paperclip/<id>/; the dashboard downloads ZIPs.
        for args in (["export", "cao"], ["export", "--output", "cao.zip"], ["export", "--consumer", "apm"]):
            with self.subTest(args=args), redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
                cli.main(["--root", str(ROOT), *args])
            self.assertEqual(error.exception.code, 2)

    def test_there_is_no_command_that_reaches_a_consumer(self):
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
            cli.main(["--root", str(ROOT), "paperclip", "cao", "--company", "company-1"])
        self.assertEqual(error.exception.code, 2)

    def test_serve_export_and_check_refuse_a_folder_without_packages(self):
        # Run outside a clone, these once passed, wrote nothing or served no data, and exited 0.
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for args in (["serve", "--port", "0"], ["export"], ["export", "--check"]):
                output = io.StringIO()
                with self.subTest(args=args), redirect_stdout(output), \
                        mock.patch("asm_app.server.create_server") as create_server:
                    code = cli.main(["--root", str(root), *args])
                    self.assertEqual(code, 2)
                    self.assertFalse(create_server.called)
                    self.assertIn(str(root.resolve() / "packages"), output.getvalue())
                    self.assertIn("--root", output.getvalue())
            self.assertEqual(list(root.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
