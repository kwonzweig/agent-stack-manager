import json
import io
from pathlib import Path
import tempfile
import threading
import unittest
from zipfile import ZipFile
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from unittest.mock import patch

from asm_app.server import create_server


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.server = create_server(Path(self.temp.name), port=0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = 'http://127.0.0.1:' + str(self.server.server_port)

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.temp.cleanup()

    def request(self, path, *, data=None, headers=None, method=None):
        req = Request(self.base + path, data=data, headers=headers or {}, method=method)
        try:
            with urlopen(req) as response:
                return response.status, response.read(), response.headers
        except HTTPError as error:
            return error.code, error.read(), error.headers

    def test_consumers_are_served_from_the_catalog_file(self):
        source = Path(__file__).resolve().parents[1] / 'catalog/consumers.json'
        (Path(self.temp.name) / 'catalog').mkdir()
        (Path(self.temp.name) / 'catalog/consumers.json').write_bytes(source.read_bytes())
        code, body, _ = self.request('/api/consumers')
        self.assertEqual(code, 200)
        data = json.loads(body)
        consumers = data['consumers']
        catalog = {**data, 'consumers': [{key: value for key, value in row.items() if key != 'export'}
                                        for row in consumers]}
        self.assertEqual(catalog, json.loads(source.read_text(encoding='utf-8')))
        self.assertEqual([x['id'] for x in consumers if x['export']], ['paperclip', 'ccswitch'])

    def test_rejects_cross_origin_write_before_loading_store(self):
        code, _, _ = self.request('/api/presets', data=b'{}', headers={
            'Content-Type':'application/json', 'Origin':'https://unrelated.example'})
        self.assertEqual(code, 403)

    def test_rejects_dns_rebinding_host(self):
        code, _, _ = self.request('/api/consumers', headers={'Host':'unrelated.example'})
        self.assertEqual(code, 403)

    def test_page_opens_from_a_link_on_another_site(self):
        for site in ('cross-site', 'same-site'):
            code, body, _ = self.request('/', headers={
                'Sec-Fetch-Site':site, 'Sec-Fetch-Mode':'navigate', 'Sec-Fetch-Dest':'document'})
            self.assertEqual(code, 200, site)
            self.assertIn(b'<div id="root">', body)

    def test_api_read_from_another_site_is_rejected(self):
        code, _, _ = self.request('/api/consumers', headers={'Sec-Fetch-Site':'cross-site'})
        self.assertEqual(code, 403)

    def test_rejects_non_json_write(self):
        code, _, _ = self.request('/api/presets', data=b'{}')
        self.assertEqual(code, 415)

    def test_early_rejection_reads_the_body_so_the_client_gets_the_answer(self):
        # Closing a socket with unread request bytes resets the connection on Windows,
        # so the client would see ConnectionResetError instead of the status.
        body = b' ' * (512 * 1024)
        for headers, status in (({'Content-Type':'application/json', 'Origin':'https://unrelated.example'}, 403),
                                ({'Content-Type':'text/plain'}, 415)):
            with self.subTest(status=status):
                code, _, _ = self.request('/api/presets', data=body, headers=headers)
                self.assertEqual(code, status)

    def test_a_port_already_in_use_is_refused(self):
        # On Windows SO_REUSEADDR lets a second server bind a listening port and take some of its requests.
        with self.assertRaises(OSError):
            create_server(Path(self.temp.name), port=self.server.server_port).server_close()

    def test_rejects_invalid_json(self):
        for data in (b'{', b'not json', b'\xff'):
            with self.subTest(data=data):
                code, body, _ = self.request('/api/presets', data=data, headers={'Content-Type':'application/json'})
                self.assertEqual((code, json.loads(body)), (400, {'error': 'Request body must be valid JSON.'}))

    def test_catalog_loads_items_with_or_without_legacy_source_list(self):
        catalog_file = Path(self.temp.name) / 'catalog' / 'components.json'
        catalog_file.parent.mkdir()
        for catalog in (
            {'items': [], 'repositories': []},
            {'items': [], 'repositories': [], 'sources': [{'name': 'Example', 'url': 'https://example.com'}]},
        ):
            with self.subTest(legacy='sources' in catalog):
                catalog_file.write_text(json.dumps(catalog), encoding='utf-8')
                code, body, _ = self.request('/api/catalog')
                self.assertEqual((code, json.loads(body)), (200, {'items': []}))

    def test_catalog_sources_report_an_unreachable_source_instead_of_failing(self):
        root = Path(self.temp.name)
        (root/'catalog').mkdir()
        (root/'catalog/components.json').write_bytes((Path(__file__).resolve().parents[1]/'catalog/components.json').read_bytes())
        with patch('asm_app.sources.urlopen', side_effect=OSError('offline')) as opened:
            code, body, _ = self.request('/api/catalog/sources')
        self.assertEqual(code, 200)
        found = json.loads(body)
        self.assertTrue(opened.called)
        self.assertTrue(found['errors'])
        self.assertNotIn('stars', found['items'].get('brainstorming-84f46f', {}))

    def test_a_local_file_error_is_a_server_error(self):
        # ASM contacts no other service, so a disk or permission error is its own failure, not a gateway's.
        with patch('asm_app.store.Store.catalog', side_effect=PermissionError('denied')), \
                self.assertLogs(level='ERROR'):
            code, body, _ = self.request('/api/catalog')
        self.assertEqual(code, 500)
        self.assertEqual(json.loads(body), {'error':'Request failed. See the local server output.'})

    def test_a_save_without_a_revision_is_a_bad_request(self):
        (Path(self.temp.name)/'catalog').mkdir()
        source = Path(__file__).resolve().parents[1]/'catalog/components.json'
        (Path(self.temp.name)/'catalog/components.json').write_bytes(source.read_bytes())
        code, body, _ = self.request('/api/presets', data=json.dumps({'title':'API example','kind':'preset'}).encode(),
                                     headers={'Content-Type':'application/json'})
        self.assertEqual(code, 201)
        code, body, _ = self.request('/api/presets/'+json.loads(body)['id'], data=b'{"description":"x"}',
                                     headers={'Content-Type':'application/json'}, method='PATCH')
        self.assertEqual(code, 400)
        self.assertIn('revision is required', json.loads(body)['error'])

    def test_a_preset_saves_while_apm_lock_runs(self):
        # APM can take minutes; a save from the dashboard must not wait behind it.
        json_headers = {'Content-Type':'application/json'}
        code, body, _ = self.request('/api/presets', data=json.dumps({'title':'Lock example'}).encode(),
                                     headers=json_headers)
        self.assertEqual(code, 201)
        package = json.loads(body)
        started, release = threading.Event(), threading.Event()

        def slow_run(*args, **kwargs):
            started.set()
            release.wait(10)
            return type('Result', (), {'returncode':0, 'stdout':'locked'})()

        with patch('asm_app.store.Store._apm_command', return_value=['apm']), \
                patch('asm_app.store.subprocess.run', side_effect=slow_run):
            locking = threading.Thread(target=self.request, args=('/api/presets/'+package['id']+'/lock',),
                                       kwargs={'data':b'{}', 'headers':json_headers})
            locking.start()
            self.addCleanup(locking.join)
            self.addCleanup(release.set)
            self.assertTrue(started.wait(5))
            done = []
            saving = threading.Thread(target=lambda: done.append(self.request(
                '/api/presets/'+package['id'], method='PATCH', headers=json_headers,
                data=json.dumps({'revision':package['revision'], 'description':'x'}).encode())[0]))
            saving.start()
            saving.join(2)
            self.assertEqual(done, [200])
            release.set()

    def test_static_route_does_not_expose_workspace(self):
        (Path(self.temp.name)/'secret.txt').write_text('private', encoding='utf-8')
        code, body, _ = self.request('/%2e%2e/secret.txt')
        self.assertEqual(code, 404)
        self.assertNotIn(b'private', body)

    def test_conversion_report_comes_straight_from_the_conversion(self):
        root = Path(self.temp.name)
        source = Path(__file__).resolve().parents[1]
        (root/'catalog').mkdir()
        (root/'catalog/components.json').write_bytes((source/'catalog/components.json').read_bytes())
        package = root/'packages/cao'
        for path in (source/'packages/cao').rglob('*'):
            if path.is_file():
                target = package/path.relative_to(source/'packages/cao')
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(path.read_bytes())
        code, body, _ = self.request('/api/presets/cao/paperclip')
        self.assertEqual(code, 200)
        report = json.loads(body)
        self.assertEqual(set(report['summary']), {'total','converted','unconverted'})
        self.assertTrue(all(set(row) == {'id','name','kind','supportKind','source','target','conversion'} for row in report['items']))
        code, _, _ = self.request('/api/presets/cao/paperclip/export')
        self.assertEqual(code, 200)

    def test_package_path_is_not_a_filesystem_route(self):
        code, _, _ = self.request('/api/presets/%2e%2e%2fsecret')
        self.assertEqual(code, 400)

    def test_export_targets_preview_real_artifacts_for_a_new_mixed_preset(self):
        import yaml
        from asm_app.paperclip import write_exports

        identifier = "new-mixed"
        root = Path(self.temp.name)
        package_dir = root / "packages" / identifier
        instruction_path = package_dir / ".apm/agents/new-mixed.agent.md"
        instruction_path.parent.mkdir(parents=True)
        instruction_path.write_text("Use the fixture workflow.\n", encoding="utf-8")
        manifest = {
            "name": identifier,
            "dependencies": {"hooks": [{"name": "stop"}]},
            "x-app-inventory": {"items": [
                {"id": "portable-prompt", "name": "Example prompt", "kind": "prompt",
                 "description": "Portable instructions",
                 "apps": {"codex": {"installed": False, "enabled": None, "selected": True,
                                     "portable": {"prompt": "# New prompt\n"}}}},
                {"id": "unknown-skill", "name": "Undecided skill", "kind": "skill",
                 "description": "Unknown selection",
                 "apps": {"claude": {"installed": True, "enabled": None, "selected": None}}},
                {"id": "hidden-hook", "name": "Observed hook", "kind": "hook",
                 "description": "Observed local hook",
                 "apps": {"codex": {"installed": True, "enabled": True, "selected": False}}},
            ]},
        }
        (package_dir / "apm.yml").write_text(yaml.safe_dump(manifest), encoding="utf-8")

        base = f"/api/presets/{identifier}"
        code, body, _ = self.request(base + "/exports")
        self.assertEqual(code, 200)
        targets = {row["id"]: row for row in json.loads(body)["targets"]}
        paperclip = targets["paperclip"]
        switch = targets["ccswitch"]
        self.assertTrue(paperclip["available"])
        self.assertTrue(switch["available"])
        self.assertEqual({row["app"] for row in paperclip["preview"]["items"] if "app" in row},
                         {"codex", "claude"})
        self.assertTrue(all(row["conversion"]["status"] == "unconverted"
                            for row in paperclip["preview"]["items"] if "app" in row))
        self.assertEqual([row["status"] for row in switch["preview"]["items"] if row.get("app")],
                         ["import-ready", "manual", "excluded"])
        self.assertTrue(any(row["status"] == "manual" for row in switch["preview"]["items"] if not row.get("app")))
        self.assertTrue(any(row["kind"] == "hook" and row["status"] == "unsupported"
                            for row in switch["preview"]["items"] if not row.get("app")))

        code, body, _ = self.request(base + paperclip["download"])
        self.assertEqual(code, 200)
        with ZipFile(io.BytesIO(body)) as archive:
            files = {name: archive.read(name) for name in archive.namelist()}
        self.assertIn(b"Use the fixture workflow.", files[f"agents/{identifier}/AGENTS.md"])
        self.assertTrue(all(b"# New prompt" not in content for content in files.values()))
        write_exports(root)
        self.assertEqual(files, {path: (root / "exports/paperclip" / identifier / path).read_bytes()
                                 for path in files})

        code, body, _ = self.request(base + switch["download"])
        self.assertEqual(code, 200)
        review = json.loads(body)
        self.assertEqual(review["items"], [row for row in switch["preview"]["items"] if row.get("app")])
        self.assertEqual(review["unassignedItems"], [row for row in switch["preview"]["items"] if not row.get("app")])
        self.assertEqual(review["items"][0]["app"], "codex")

        instruction_path.write_text("The saved instruction changed.\n", encoding="utf-8")
        code, _, _ = self.request(base + paperclip["download"])
        self.assertEqual(code, 409)
        code, _, _ = self.request(base + "/paperclip/export")
        self.assertEqual(code, 200)

    def test_unavailable_exporters_explain_missing_app_choices_and_stack_package(self):
        root = Path(self.temp.name)
        for identifier, kind in (("ordinary", "preset"), ("aggregate", "stack")):
            directory = root / "packages" / identifier
            directory.mkdir(parents=True)
            (directory / "apm.yml").write_text(f"name: {identifier}\nx-preset-labels: {{kind: {kind}}}\n",
                                                 encoding="utf-8")
        for identifier, paperclip in (("ordinary", True), ("aggregate", False)):
            with self.subTest(identifier=identifier):
                base = f"/api/presets/{identifier}"
                code, body, _ = self.request(base + "/exports")
                self.assertEqual(code, 200)
                targets = {row["id"]: row for row in json.loads(body)["targets"]}
                self.assertEqual(targets["paperclip"]["available"], paperclip)
                self.assertFalse(targets["ccswitch"]["available"])
                self.assertNotIn("download", targets["ccswitch"])
                code, body, _ = self.request(base + "/cc-switch")
                self.assertEqual(code, 400)
                self.assertEqual(json.loads(body)["error"], targets["ccswitch"]["reason"])
                if not paperclip:
                    code, body, _ = self.request(base + "/paperclip/export")
                    self.assertEqual(code, 400)
                    self.assertEqual(json.loads(body)["error"], targets["paperclip"]["reason"])

    def test_edit_export_comment_and_stale_save_through_http(self):
        root = Path(self.temp.name)
        (root/'catalog').mkdir()
        source = Path(__file__).resolve().parents[1]/'catalog/components.json'
        (root/'catalog/components.json').write_bytes(source.read_bytes())
        def write(path, payload, method='POST'):
            return self.request(path, data=json.dumps(payload).encode(),
                headers={'Content-Type':'application/json'}, method=method)
        _, body, _ = self.request('/api/catalog')
        item = next(x for x in json.loads(body)['items'] if x['name']=='brainstorming')
        # The stored row names only its APM value; the API fills what the Catalog reads.
        self.assertEqual(item['source']['repositoryUrl'], 'https://github.com/obra/superpowers')
        self.assertEqual(item['sourceUrl'], 'https://github.com/obra/superpowers/blob/main/skills/brainstorming/SKILL.md')
        # Stars, installs and the description come from /api/catalog/sources, read from the source.
        self.assertNotIn('stars', item)
        code, body, _ = write('/api/presets', {'title':'API example','kind':'preset',
            'description':'Example','instruction':'Original','componentIds':[item['id']]})
        self.assertEqual(code,201)
        original = json.loads(body)
        path = '/api/presets/'+original['id']
        code, body, _ = write(path, {'revision':original['revision'],'instruction':'Edited',
            'workArea':['Web'],'usage':['Build']},'PATCH')
        self.assertEqual(code,200)
        self.assertEqual(json.loads(body)['instruction'],'Edited')
        self.assertEqual(write(path, {'revision':original['revision'],'instruction':'Stale'},'PATCH')[0],409)
        code, body, _ = self.request(path+'/export')
        self.assertEqual(code,200)
        with ZipFile(io.BytesIO(body)) as archive:
            self.assertIn(b'Edited',archive.read('.apm/agents/api-example.agent.md'))
        code, _, _ = write('/api/comments', {'presetId':original['id'],
            'componentId':item['id'],'body':'Worked in my workspace.','author':'Reviewer'})
        self.assertEqual(code,201)
        code, body, _ = self.request('/api/comments?presetId='+original['id']+'&componentId='+item['id'])
        self.assertEqual(code,200)
        self.assertEqual(json.loads(body)['comments'][0]['body'],'Worked in my workspace.')


if __name__ == '__main__':
    unittest.main()
