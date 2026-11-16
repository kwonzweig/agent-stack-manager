import io
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from asm_app import cli

ROOT = Path(__file__).resolve().parents[1]
REPORT = {"items": [], "summary": {"notImported": 0}}


class PaperclipCommandTests(unittest.TestCase):
    def run_command(self, *options):
        with patch("asm_app.paperclip.import_package", return_value=REPORT) as imported, \
                patch("asm_app.paperclip.observe", return_value=REPORT) as observed, \
                patch("asm_app.server.save_observation"), redirect_stdout(io.StringIO()) as output:
            code = cli.main(["--root", str(ROOT), "paperclip", "cao", "--url", "http://127.0.0.1:1",
                             "--company", "company-1", *options])
        return code, imported, observed, output.getvalue()

    def test_recheck_is_passed_to_the_import(self):
        code, imported, _, _ = self.run_command("--apply", "--recheck")
        self.assertEqual(code, 0)
        self.assertIs(imported.call_args.kwargs["recheck"], True)

    def test_import_does_not_recheck_unless_asked(self):
        _, imported, _, _ = self.run_command("--apply")
        self.assertIs(imported.call_args.kwargs["recheck"], False)

    def test_recheck_without_apply_changes_nothing_and_says_why(self):
        code, imported, observed, output = self.run_command("--recheck")
        self.assertEqual(code, 2)
        self.assertFalse(imported.called or observed.called)
        self.assertIn("--apply", output)


if __name__ == "__main__":
    unittest.main()
