"""Local dashboard API. Consumer imports are deliberately CLI-only."""
from dataclasses import dataclass
from hashlib import sha256
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import logging
import mimetypes
from pathlib import Path
import re
import threading
from urllib.parse import parse_qs, unquote, urlsplit

WEB = Path(__file__).parent / 'web'
CONSUMERS = [
    {'id':'paperclip','name':'Paperclip','supported':True},
    {'id':'codex','name':'Codex','supported':False},
    {'id':'claudeCode','name':'Claude Code','supported':False},
    {'id':'ccswitch','name':'CC Switch','supported':False},
]
MAX_BODY = 1024 * 1024


@dataclass(frozen=True)
class Connection:
    base_url: str = ''
    company_id: str = ''

    def require(self):
        if not self.base_url or not self.company_id:
            raise ValueError('Set ASM_PAPERCLIP_URL and ASM_PAPERCLIP_COMPANY_ID to inspect a company.')
        parsed = urlsplit(self.base_url)
        if parsed.scheme not in ('http','https') or not parsed.netloc or parsed.username or parsed.password:
            raise ValueError('Set ASM_PAPERCLIP_URL to the Paperclip server URL.')
        if not re.fullmatch(r'[A-Za-z0-9-]{1,100}', self.company_id):
            raise ValueError('Set ASM_PAPERCLIP_COMPANY_ID to the company to inspect.')
        return self


def package_id(value):
    value = unquote(value)
    if not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_-]{0,119}', value):
        raise ValueError('Invalid package id.')
    return value


def fingerprint(report):
    fields = []
    for row in report['items']:
        item = {k:row.get(k) for k in ('id','source','target','conversion')}
        if isinstance(item['target'],dict):
            item['target'] = {k:v for k,v in item['target'].items() if k != 'key'}
        fields.append(item)
    identity = {'sourceRevision':report.get('sourceRevision'),'items':fields}
    return sha256(json.dumps(identity, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def observation_path(root, pid):
    from .store import Store, _package_id

    store = Store(root)
    path = store.root / '.asm' / 'observations' / (_package_id(pid) + '.json')
    # Python 3.11 resolves Windows junctions but has no Path.is_junction().
    if not path.resolve().is_relative_to(store.root):
        raise ValueError('Observation path must stay within the workspace.')
    return store._checked(path)


def save_observation(root,pid,connection,report):
    from .store import _atomic_write

    path=observation_path(root,pid)
    path.parent.mkdir(parents=True,exist_ok=True)
    data={'fingerprint':fingerprint(report),'connection':[connection.base_url,connection.company_id],'report':report}
    _atomic_write(path,json.dumps(data,ensure_ascii=False,indent=2).encode('utf-8'))


class DashboardServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, root, connection):
        self.root = Path(root).resolve()
        self.connection = connection
        self.io_lock = threading.RLock()
        self._store = None
        super().__init__(address, Handler)

    @property
    def store(self):
        if self._store is None:
            from .store import Store
            self._store = Store(self.root)
        return self._store


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

    def body(self):
        if self.headers.get('Content-Type','').split(';')[0].strip() != 'application/json':
            self.send(415, {'error':'Use application/json.'})
            return None
        length = int(self.headers.get('Content-Length','0'))
        if not 0 < length <= MAX_BODY:
            raise ValueError('Request body must be between 1 byte and 1 MB.')
        data = json.loads(self.rfile.read(length))
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
                    return self.send(200, {'consumers':CONSUMERS})
                if path == '/api/connection':
                    c = self.server.connection
                    return self.send(200, {'paperclip':{'configured':bool(c.base_url and c.company_id)}})
                if path == '/api/catalog':
                    return self.send(200, self.server.store.catalog())
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
                    if suffix in ('/paperclip','/paperclip/export'):
                        from .paperclip import convert, export_package
                        package = self.server.store.get(pid)
                        report = convert(package,root=self.server.root)
                        if suffix.endswith('/export'):
                            return self.send(200,export_package(report),'application/zip',pid+'-paperclip.zip')
                        cached = self.load_observation(pid,report)
                        return self.send(200,cached or report)
                elif self.command == 'PATCH' and not suffix:
                    with self.server.io_lock:
                        return self.send(200,self.server.store.save(pid,data))
                elif self.command == 'POST':
                    if suffix == '/lock':
                        if not isinstance(data.get('update',False),bool):
                            raise ValueError('update must be a boolean.')
                        with self.server.io_lock:
                            return self.send(200,self.server.store.lock(pid,data.get('update',False)))
                    if suffix == '/paperclip/observe':
                        connection = self.server.connection.require()
                        from .paperclip import observe
                        package = self.server.store.get(pid)
                        report = observe(package,root=self.server.root,
                            base_url=connection.base_url,company_id=connection.company_id)
                        if self.server.store.get(pid)['revision'] != package['revision']:
                            return self.send(409,{'error':'Preset changed during refresh. Refresh again.'})
                        self.save_observation(pid,report)
                        return self.send(200,report)
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
        except RuntimeError as error:
            self.send(502,{'error':str(error)})
        except (ConnectionError,TimeoutError,OSError) as error:
            logging.exception('Local service request failed')
            self.send(502,{'error':'The local service could not complete the request.'})
        except Exception:
            logging.exception('Dashboard request failed')
            self.send(500,{'error':'Request failed. See the local server output.'})

    def load_observation(self,pid,report):
        try:
            data = json.loads(observation_path(self.server.root,pid).read_text(encoding='utf-8'))
            c = self.server.connection
            if data['fingerprint']==fingerprint(report) and data['connection']==[c.base_url,c.company_id]:
                return data['report']
        except (OSError,ValueError,KeyError):
            pass
        return None

    def save_observation(self,pid,report):
        with self.server.io_lock:
            save_observation(self.server.root,pid,self.server.connection,report)

    do_GET = dispatch
    do_HEAD = dispatch
    do_POST = dispatch
    do_PATCH = dispatch


def create_server(root, host='127.0.0.1', port=4319, *, base_url='', company_id=''):
    if host not in ('127.0.0.1','localhost'):
        raise ValueError('This local server binds to loopback only.')
    return DashboardServer((host,port),root,Connection(base_url,company_id))
