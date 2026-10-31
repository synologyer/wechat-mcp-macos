#!/usr/bin/env python3
"""Configure Claude Desktop for an explicitly chosen local WeChat database."""
import argparse
import json
import os
from datetime import datetime
from pathlib import Path


def private_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.new')
    fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write('\n')
        os.replace(temp, path)
    finally:
        if temp.exists():
            temp.unlink()


def update_desktop(existing, python, entry):
    result = dict(existing)
    servers = dict(result.get('mcpServers', {}))
    servers['work-wechat-readonly'] = {'command': str(python), 'args': [str(entry)]}
    result['mcpServers'] = servers
    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--db-dir', type=Path, required=True, help='Exact account db_storage directory')
    ap.add_argument('--apply', action='store_true', help='Write configuration; otherwise preview only')
    ap.add_argument('--replace-account', action='store_true', help='Allow changing an existing account directory')
    args = ap.parse_args()
    root = Path(__file__).resolve().parent.parent
    python = root / 'backend/.venv/bin/python'
    entry = root / 'claude_wechat_readonly.py'
    db = args.db_dir.expanduser().resolve(strict=True)
    if db.name != 'db_storage' or not (db / 'contact/contact.db').is_file():
        raise SystemExit('Expected an account db_storage containing contact/contact.db.')
    if not python.is_file():
        raise SystemExit('Create backend/.venv and install requirements-claude.txt first.')
    state = Path.home() / '.wechat-mcp'
    cfg_path = state / 'config.json'
    cfg = json.loads(cfg_path.read_text()) if cfg_path.exists() else {}
    previous = cfg.get('db_dir', '')
    changed = bool(previous and Path(previous).expanduser().resolve() != db)
    if changed and not args.replace_account:
        raise SystemExit('Another account is configured. Review it, then use --replace-account explicitly.')
    cfg.update(db_dir=str(db), keys_file=str(state / 'all_keys.json'), decrypted_dir=str(state / 'decrypted'))
    cfg.setdefault('self_name', '')
    desktop_path = Path.home() / 'Library/Application Support/Claude/claude_desktop_config.json'
    existing = json.loads(desktop_path.read_text()) if desktop_path.exists() else {}
    desktop = update_desktop(existing, python, entry)
    if not args.apply:
        print('Preview only. Selected database:', db)
        print(json.dumps(desktop['mcpServers']['work-wechat-readonly'], ensure_ascii=False, indent=2))
        print('Use --apply to save. Existing MCP connections will be preserved.')
        return
    os.umask(0o077)
    state.mkdir(mode=0o700, parents=True, exist_ok=True)
    state.chmod(0o700)
    stamp = datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    for p in (cfg_path, desktop_path):
        if p.exists():
            private_json(state / (p.name + '.backup-' + stamp), json.loads(p.read_text()))
    # Preserve old-account keys privately; never carry them into a new account.
    key_path = state / 'all_keys.json'
    if changed and key_path.exists():
        key_path.rename(state / ('all_keys.previous-account-' + stamp + '.json'))
    private_json(cfg_path, cfg)
    private_json(desktop_path, desktop)
    print('Saved. Restart Claude Desktop. This does not extract keys or restart WeChat.')


if __name__ == '__main__':
    main()
