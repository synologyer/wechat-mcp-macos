#!/usr/bin/env python3
"""Validate captured keys against the configured account before installing them."""
import argparse
import json
import os
from pathlib import Path
from datetime import datetime
from capture_launch_keys import page_matches
from configure_claude import private_json


def validate_keys(source, db_dir):
    payload = json.loads(Path(source).read_text(encoding='utf-8'))
    keys = payload.get('keys', payload)
    if not isinstance(keys, dict) or not keys:
        raise ValueError('No keys found')
    valid = {}
    for rel, entry in keys.items():
        if not isinstance(rel, str) or Path(rel).is_absolute() or '..' in Path(rel).parts or '\\' in rel:
            raise ValueError('Expected a relative database path')
        if rel.startswith('_'):
            continue
        path = (db_dir / rel).resolve()
        path.relative_to(db_dir.resolve())
        if not path.is_file() or not isinstance(entry, dict):
            raise ValueError('Missing database or invalid key entry')
        key = bytes.fromhex(entry['enc_key'])
        with path.open('rb') as f:
            page = f.read(4096)
        if not page_matches(key, page):
            raise ValueError('Key does not match the selected database')
        valid[rel] = {'enc_key': key.hex()}
    if not valid:
        raise ValueError('No verified keys')
    return valid


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source', type=Path, required=True)
    ap.add_argument('--apply', action='store_true')
    args = ap.parse_args()
    state = Path.home() / '.wechat-mcp'
    cfg = json.loads((state / 'config.json').read_text())
    db = Path(cfg['db_dir'])
    keys = validate_keys(args.source.expanduser(), db)
    print('Verified database keys:', len(keys))
    if not args.apply:
        print('Preview only; use --apply to install.')
        return
    os.umask(0o077)
    output = state / 'all_keys.json'
    if output.exists():
        stamp = datetime.now().strftime('%Y%m%d-%H%M%S-%f')
        private_json(state / ('all_keys.backup-' + stamp + '.json'), json.loads(output.read_text()))
    private_json(output, keys)
    print('Installed privately. Restart Claude Desktop to reload cached keys.')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, KeyError, TypeError):
        raise SystemExit('Invalid key file or database mismatch; no keys installed.')
