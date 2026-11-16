from contextlib import redirect_stderr
import io
from pathlib import Path
import unittest

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


if __name__ == "__main__":
    unittest.main()
