import ast
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WHAT_ASM_IS = ("Agent Stack Manager converts presets into formats that consumers can import and exports them. "
               "It does not connect to a consumer: it reads no consumer's state, imports nothing into one and "
               "stores nothing a consumer reports. Importing an export is done by hand, by a person or an agent.")
NETWORK_CLIENTS = {"urllib.request", "http.client", "socket", "requests", "httpx", "aiohttp",
                   "urllib3", "ssl", "websockets"}
# Calls that open a connection, or load a module by a name the import check cannot see.
NETWORK_CALLS = {"open_connection", "open_unix_connection", "create_connection", "import_module", "__import__"}
NETWORK_COMMANDS = {"curl", "wget"}
FRONTEND_NETWORK = ("XMLHttpRequest", "WebSocket", "EventSource", "sendBeacon", "fetch(")
# This file is the one place these names may appear.
REMOVED = ("ASM_PAPERCLIP_URL", "ASM_PAPERCLIP_COMPANY_ID", "/api/connection", "paperclip/observe",
           "Refresh import status", "import status")


def tracked_files():
    try:
        listed = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, check=True).stdout
        paths = [ROOT / name for name in listed.decode("utf-8").split("\0") if name]
    except (OSError, subprocess.CalledProcessError):
        skipped = {".git", "node_modules", ".venv", ".asm", "__pycache__"}
        paths = [path for path in ROOT.rglob("*") if not skipped & set(path.relative_to(ROOT).parts)]
    return [path for path in paths if path.is_file()]


def imported_modules(tree):
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            yield from (alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
            yield node.module
            yield from (f"{node.module}.{alias.name}" for alias in node.names)


def network_calls(tree):
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            name = node.func.attr if isinstance(node.func, ast.Attribute) else getattr(node.func, "id", None)
            if name in NETWORK_CALLS:
                yield name + "()"
        elif isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value in NETWORK_COMMANDS:
            yield node.value


def python_modules():
    for path in sorted((ROOT / "asm_app").rglob("*.py")):
        yield path, ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


class StandaloneTests(unittest.TestCase):
    maxDiff = None

    def test_no_module_imports_a_network_client(self):
        found = {}
        for path, tree in python_modules():
            clients = sorted({module for module in imported_modules(tree)
                              if any(module == client or module.startswith(client + ".") for client in NETWORK_CLIENTS)})
            if clients:
                found[path.relative_to(ROOT).as_posix()] = clients
        self.assertEqual(found, {}, WHAT_ASM_IS)

    def test_no_module_opens_a_connection_another_way(self):
        found = {}
        for path, tree in python_modules():
            calls = sorted(set(network_calls(tree)))
            if calls:
                found[path.relative_to(ROOT).as_posix()] = calls
        self.assertEqual(found, {}, WHAT_ASM_IS)

    def test_dashboard_requests_only_its_own_server(self):
        # frontend/src/api.ts holds the one fetch, and it refuses any path outside /api/.
        found = {}
        for path in sorted((ROOT / "frontend" / "src").rglob("*")):
            if path.suffix not in (".ts", ".tsx", ".js", ".jsx"):
                continue
            text = path.read_text(encoding="utf-8")
            names = [name for name in FRONTEND_NETWORK if name in text]
            if path.name == "api.ts" and text.count("fetch(") == 1 and 'path.startsWith("/api/")' in text:
                names.remove("fetch(")
            if names:
                found[path.relative_to(ROOT).as_posix()] = names
        self.assertEqual(found, {}, WHAT_ASM_IS)

    def test_removed_consumer_connection_does_not_come_back(self):
        this_file = Path(__file__).resolve()
        found = {}
        for path in tracked_files():
            if path.resolve() == this_file:
                continue
            text = path.read_bytes().decode("utf-8", errors="ignore").casefold()
            names = [name for name in REMOVED if name.casefold() in text]
            if names:
                found[path.relative_to(ROOT).as_posix()] = names
        self.assertEqual(found, {}, WHAT_ASM_IS)


class RemovedRouteTests(unittest.TestCase):
    def test_no_route_reaches_a_consumer(self):
        from asm_app.server import create_server
        from urllib.error import HTTPError
        from urllib.request import Request, urlopen
        import tempfile
        import threading

        with tempfile.TemporaryDirectory() as root:
            server = create_server(Path(root), port=0)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base = f"http://127.0.0.1:{server.server_port}"
                for request in (Request(base + "/api/connection"),
                                Request(base + "/api/presets/cao/paperclip/observe", data=b"{}", method="POST",
                                        headers={"Content-Type": "application/json"})):
                    with self.subTest(path=request.full_url), self.assertRaises(HTTPError) as error:
                        urlopen(request)
                    error.exception.close()
                    self.assertEqual(error.exception.code, 404, WHAT_ASM_IS)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)


if __name__ == "__main__":
    unittest.main()
