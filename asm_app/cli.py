"""Run the local editor, or write and check the committed Paperclip exports."""
import argparse
import json
import logging
from pathlib import Path


def _report(results):
    """Print each preset's export folder and every component it does not export; True if any needs attention."""
    from .paperclip import EXPORTS, needs_attention
    attention = False
    for result in results:
        if 'error' in result:
            attention = True
            print(f"{EXPORTS}/{result['id']}: not exported. {result['error']}")
            continue
        report = result['report']
        print(report['folder']['path'])
        for row in report['items']:
            if row['conversion']['status'] == 'converted':
                continue
            label = 'needs attention' if needs_attention(row) else 'left out'
            attention = attention or label == 'needs attention'
            print(f"  {label}: {row['name']} ({row['kind']}): {row['conversion']['reason']}")
    return attention


def _export(root, check):
    from .paperclip import EXPORTS, check_exports, write_exports
    if not check:
        return 1 if _report(write_exports(root)) else 0
    results, differences = check_exports(root)
    attention = _report(results)
    stale = [(word, name) for word in ('changed', 'missing', 'extra') for name in differences[word]]
    for word, name in stale:
        print(f'{word}: {EXPORTS}/{name}')
    if stale:
        print(f'{EXPORTS}/ does not match the presets. Run python -m asm_app export and commit the result.')
    else:
        print(f'{EXPORTS}/ matches the presets.')
    return 1 if attention or stale else 0


def main(argv=None):
    parser=argparse.ArgumentParser(prog='agent-stack-manager')
    parser.add_argument('--root',type=Path,default=Path.cwd(),help='Repo containing packages/ and catalog/.')
    commands=parser.add_subparsers(dest='command',required=True)
    serve=commands.add_parser('serve',help='Open the local dashboard server.')
    serve.add_argument('--port',type=int,default=4319)
    export=commands.add_parser('export',help='Write every preset\'s Paperclip package to exports/paperclip/<id>/.')
    export.add_argument('--check',action='store_true',help='Write nothing; fail if exports/paperclip/ is not current.')
    lock=commands.add_parser('lock',help='Resolve APM dependencies without deploying host configuration.')
    lock.add_argument('preset')
    lock.add_argument('--update',action='store_true')
    args=parser.parse_args(argv)
    packages=args.root.resolve()/'packages'
    if args.command in ('serve','export') and not packages.is_dir():
        print(f'{packages} is not a folder. Run in a clone of the repo, or name one with --root <clone>.')
        return 2
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
        if args.command=='export':
            return _export(args.root,args.check)
        from .store import Store
        store=Store(args.root)
        if args.command=='lock':
            result=store.lock(args.preset,args.update)
            print(json.dumps(result,ensure_ascii=False,indent=2))
            return 0 if result['ok'] else 1
    except (ValueError,OSError) as error:
        print(json.dumps({'error':str(error)},ensure_ascii=False))
        return 2
    return 0
