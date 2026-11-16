"""Run the local editor or export a selected package."""
import argparse
import json
import logging
from pathlib import Path


def main(argv=None):
    parser=argparse.ArgumentParser(prog='agent-stack-manager')
    parser.add_argument('--root',type=Path,default=Path.cwd(),help='Repo containing packages/ and catalog/.')
    commands=parser.add_subparsers(dest='command',required=True)
    serve=commands.add_parser('serve',help='Open the local dashboard server.')
    serve.add_argument('--port',type=int,default=4319)
    export=commands.add_parser('export',help='Export the native APM or Paperclip package.')
    export.add_argument('preset')
    export.add_argument('--consumer',choices=['apm','paperclip'],default='apm')
    export.add_argument('--output',type=Path,required=True)
    lock=commands.add_parser('lock',help='Resolve APM dependencies without deploying host configuration.')
    lock.add_argument('preset')
    lock.add_argument('--update',action='store_true')
    args=parser.parse_args(argv)
    try:
        if args.command=='serve':
            from .server import create_server
            logging.basicConfig(level=logging.INFO,format='%(message)s')
            server=create_server(args.root,port=args.port)
            print('Agent Stack Manager: http://127.0.0.1:'+str(server.server_port),flush=True)
            try:
                server.serve_forever()
            except KeyboardInterrupt:
                pass
            finally:
                server.server_close()
            return 0
        from .store import Store
        store=Store(args.root)
        if args.command=='export':
            if args.consumer=='apm':
                content=store.export(args.preset)
            else:
                from .paperclip import convert,export_package
                content=export_package(convert(store.get(args.preset),root=args.root))
            args.output.parent.mkdir(parents=True,exist_ok=True)
            args.output.write_bytes(content)
            print(str(args.output.resolve()))
            return 0
        if args.command=='lock':
            result=store.lock(args.preset,args.update)
            print(json.dumps(result,ensure_ascii=False,indent=2))
            return 0 if result['ok'] else 1
    except (ValueError,OSError) as error:
        print(json.dumps({'error':str(error)},ensure_ascii=False))
        return 2
    return 0
