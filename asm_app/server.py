"""Local dashboard API. It edits presets and converts them; it never contacts a consumer."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import logging
import mimetypes
from pathlib import Path
import os
import re
import threading
from urllib.parse import parse_qs, unquote, urlsplit

WEB = Path(__file__).parent / 'web'
MAX_BODY = 1024 * 1024


def package_id(value):
    value = unquote(value)
    if not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_-]{0,119}', value):
        raise ValueError('Invalid package id.')
    return value


class DashboardServer(ThreadingHTTPServer):
    daemon_threads = True
    # SO_REUSEADDR on Windows lets a second server bind a port another one listens on, so a busy port
    # would serve the other program without an error. Elsewhere it only allows a quick restart.
    allow_reuse_address = os.name != 'nt'

    def __init__(self, address, root, *, base_root=None):
        self.root = Path(root).resolve()
        self.base_root = base_root
        self.io_lock = threading.RLock()
        self._store = None
        self._sources = None
        super().__init__(address, Handler)

    @property
    def store(self):
        if self._store is None:
            from .store import Store
            self._store = Store(self.root, base_root=self.base_root)
        return self._store

    @property
    def sources(self):
        if self._sources is None:
            from .sources import SourceReader
            self._sources = SourceReader(self.store._checked(self.root / '.asm' / 'sources.json'))
        return self._sources


class Handler(BaseHTTPRequestHandler):
    server: DashboardServer

    def log_message(self, format, *args):
        logging.info('%s %s', self.address_string(), format % args)

    def send(self, status, body, content_type='application/json; charset=utf-8', filename=None):
        if not isinstance(body, bytes):
            body = json.dumps(body, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' https: data:; frame-ancestors 'none'; base-uri 'none'")
        if filename:
            self.send_header('Content-Disposition', 'attachment; filename="'+filename+'"')
        self.end_headers()
        if self.command != 'HEAD':
            self.wfile.write(body)

    def discard_body(self):
        # A socket closed with unread request bytes resets the connection on Windows, and the
        # client then sees the reset instead of the answer.
        try:
            length = int(self.headers.get('Content-Length','0'))
        except ValueError:
            return
        if 0 < length <= MAX_BODY:
            self.rfile.read(length)

    def body(self):
        if self.headers.get('Content-Type','').split(';')[0].strip() != 'application/json':
            self.discard_body()
            self.send(415, {'error':'Use application/json.'})
            return None
        length = int(self.headers.get('Content-Length','0'))
        if not 0 < length <= MAX_BODY:
            raise ValueError('Request body must be between 1 byte and 1 MB.')
        try:
            data = json.loads(self.rfile.read(length))
        except ValueError:  # not JSON, or not UTF-8
            raise ValueError('Request body must be valid JSON.') from None
        if not isinstance(data, dict):
            raise ValueError('Request body must be an object.')
        return data

    def allowed_request(self):
        host = self.headers.get('Host','')
        parsed = urlsplit('http://'+host)
        if parsed.hostname not in ('localhost','127.0.0.1','::1') or parsed.port != self.server.server_port:
            return False
        # A link on another page may open the app. Its static files hold no data.
        if self.command in ('GET','HEAD') and not urlsplit(self.path).path.startswith('/api/'):
            return True
        origin = self.headers.get('Origin')
        if origin and origin not in ('http://'+host,'https://'+host):
            return False
        return self.headers.get('Sec-Fetch-Site') not in ('cross-site','same-site')

    def dispatch(self):
        try:
            if not self.allowed_request():
                self.discard_body()
                return self.send(403, {'error':'Request origin is not allowed.'})
            parsed = urlsplit(self.path)
            path = parsed.path
            query = parse_qs(parsed.query)
            write = self.command in ('POST','PATCH')
            data = self.body() if write else {}
            if write and data is None:
                return
            if self.command in ('GET','HEAD'):
                if path == '/api/consumers':
                    return self.send(200, self.server.store.consumers())
                if path == '/api/catalog':
                    return self.send(200, self.server.store.catalog())
                if path == '/api/catalog/sources':
                    items = [item for item in self.server.store.catalog()['items'] if item['type'] == 'component']
                    return self.send(200, self.server.sources.read(items))
                if path == '/api/presets':
                    return self.send(200, {'presets':self.server.store.list_packages()})
                if path == '/api/comments':
                    pid = package_id(query.get('presetId',[''])[0])
                    key = query.get('componentId',[''])[0]
                    return self.send(200, {'comments':self.server.store.comments(pid,key)})
            elif self.command == 'POST':
                if path == '/api/presets':
                    with self.server.io_lock:
                        return self.send(201, self.server.store.create(data))
                if path == '/api/comments':
                    pid = package_id(data.get('presetId',''))
                    with self.server.io_lock:
                        comment = self.server.store.add_comment(pid,data.get('componentId',''),data)
                    return self.send(201, {'comment':comment})
            match = re.fullmatch(r'/api/presets/([^/]+)(/.*)?',path)
            if match:
                pid = package_id(match[1])
                suffix = match[2] or ''
                if self.command in ('GET','HEAD'):
                    if not suffix:
                        return self.send(200,self.server.store.get(pid))
                    if suffix == '/export':
                        return self.send(200,self.server.store.export(pid),'application/zip',pid+'.zip')
                    from .exporters import DOWNLOADS, EXPORTERS, choices
                    if suffix == '/exports':
                        return self.send(200,choices(self.server.store.get(pid),self.server.store))
                    if exporter := DOWNLOADS.get(suffix):
                        revision = query.get('revision',[None])[0]
                        return self.send(200,*exporter.produce(self.server.store.get(pid),self.server.store,revision))
                    if suffix == '/paperclip':
                        assessment = EXPORTERS['paperclip'].assess(self.server.store.get(pid),self.server.store)
                        return self.send(200,assessment.artifact if assessment.artifact is not None
                                         else {**assessment.preview, 'files': []})
                elif self.command == 'PATCH' and not suffix:
                    with self.server.io_lock:
                        return self.send(200,self.server.store.save(pid,data))
                elif self.command == 'POST':
                    if suffix == '/lock':
                        if not isinstance(data.get('update',False),bool):
                            raise ValueError('update must be a boolean.')
                        # No io_lock: APM can run for minutes, and the store guards its own check step.
                        return self.send(200,self.server.store.lock(pid,data.get('update',False)))
            if self.command in ('GET','HEAD') and not path.startswith('/api/'):
                relative = 'index.html' if path=='/' else unquote(path).lstrip('/')
                target = (WEB/relative).resolve()
                if target.is_relative_to(WEB.resolve()) and target.is_file():
                    mime = 'application/javascript' if target.suffix=='.js' else mimetypes.guess_type(target.name)[0] or 'application/octet-stream'
                    return self.send(200,target.read_bytes(),mime)
            self.send(404,{'error':'Not found.'})
        except (ValueError,TypeError) as error:
            self.send(getattr(error,'status',400), {'error':str(error)})
        except FileNotFoundError:
            self.send(404,{'error':'Package or file not found.'})
        except Exception:
            logging.exception('Dashboard request failed')
            self.send(500,{'error':'Request failed. See the local server output.'})

    do_GET = dispatch
    do_HEAD = dispatch
    do_POST = dispatch
    do_PATCH = dispatch


def create_server(root, host='127.0.0.1', port=4319, *, base_root=None):
    if host not in ('127.0.0.1','localhost'):
        raise ValueError('This local server binds to loopback only.')
    return DashboardServer((host,port),root,base_root=base_root)
