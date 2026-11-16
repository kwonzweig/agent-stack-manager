import json
import io
from pathlib import Path
import tempfile
import threading
import unittest
from zipfile import ZipFile
from urllib.error import HTTPError
from urllib.request import Request, urlopen

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

    def test_only_paperclip_is_supported(self):
        code, body, _ = self.request('/api/consumers')
        self.assertEqual(code, 200)
        consumers = json.loads(body)['consumers']
        self.assertEqual([x['id'] for x in consumers if x['supported']], ['paperclip'])

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

    def test_rejects_invalid_json(self):
        code, _, _ = self.request('/api/presets', data=b'{', headers={'Content-Type':'application/json'})
        self.assertEqual(code, 400)

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
        self.assertTrue(all(set(row) == {'id','name','kind','source','target','conversion'} for row in report['items']))
        code, _, _ = self.request('/api/presets/cao/paperclip/export')
        self.assertEqual(code, 200)

    def test_package_path_is_not_a_filesystem_route(self):
        code, _, _ = self.request('/api/presets/%2e%2e%2fsecret')
        self.assertEqual(code, 400)

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
