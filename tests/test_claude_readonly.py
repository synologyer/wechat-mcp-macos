import asyncio
import hashlib
import hmac
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))
from capture_launch_keys import candidate_key, page_matches
from configure_claude import private_json, update_desktop
from import_claude_keys import validate_keys


def encrypted_fixture(key):
    # Synthetic authenticated page, no real account data or keys.
    salt = bytes(range(16))
    page = bytearray(salt + bytes(4080))
    mk = hashlib.pbkdf2_hmac('sha512', key, bytes(v ^ 0x3a for v in salt), 2, 32)
    page[4032:] = hmac.new(mk, page[16:4032] + b'\x01\0\0\0', hashlib.sha512).digest()
    return bytes(page)


class ClaudeReadonlyTests(unittest.TestCase):
    def test_authentication_and_capture_filter(self):
        key = bytes(range(32))
        page = encrypted_fixture(key)
        self.assertTrue(page_matches(key, page))
        self.assertFalse(page_matches(bytes(32), page))
        damaged = bytearray(page); damaged[80] ^= 1
        self.assertFalse(page_matches(key, damaged))
        salt = bytes(v ^ 0x3a for v in page[:16])
        self.assertEqual(candidate_key(key, salt, 5, 2, [page]), key)
        self.assertIsNone(candidate_key(key, salt, 3, 2, [page]))
        self.assertIsNone(candidate_key(key, bytes(16), 5, 2, [page]))

    def test_password_derivation_path(self):
        password = b'synthetic-password'
        salt = bytes(range(16))
        key = hashlib.pbkdf2_hmac('sha512', password, salt, 256000, 32)
        page = encrypted_fixture(key)
        self.assertEqual(candidate_key(password, salt, 5, 256000, [page]), key)

    def test_import_rejects_other_account_and_path_escape(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); db = root / 'db_storage'; db.mkdir()
            page = encrypted_fixture(bytes(range(32)))
            (db / 'test.db').write_bytes(page)
            source = root / 'keys.json'
            source.write_text(json.dumps({'test.db': {'enc_key': bytes(32).hex()}}))
            with self.assertRaises(ValueError): validate_keys(source, db)
            source.write_text(json.dumps({'test.db': {'enc_key': bytes(range(32)).hex()}}))
            self.assertEqual(len(validate_keys(source, db)), 1)
            (root / 'outside.db').write_bytes(page)
            source.write_text(json.dumps({'../outside.db': {'enc_key': bytes(range(32)).hex()}}))
            with self.assertRaises(ValueError): validate_keys(source, db)

    def test_desktop_preserves_other_connections_and_preferences(self):
        old = {'mcpServers': {'mail': {'command': '/mail'}}, 'preferences': {'language': 'zh'}}
        new = update_desktop(old, Path('/project/python'), Path('/project/entry.py'))
        self.assertEqual(new['mcpServers']['mail'], old['mcpServers']['mail'])
        self.assertEqual(new['preferences'], old['preferences'])
        self.assertNotIn('work-wechat-readonly', old['mcpServers'])

    def test_key_files_private_and_atomic(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / 'keys.json'
            private_json(p, {'count': 1})
            self.assertEqual(p.stat().st_mode & 0o777, 0o600)
            private_json(p, {'count': 2})
            self.assertEqual(json.loads(p.read_text()), {'count': 2})
            self.assertFalse(p.with_name('keys.json.new').exists())

    def test_exposed_tools_exclude_mutating_upstream_tools(self):
        from wechat_mcp_macos import config
        spec = importlib.util.spec_from_file_location('readonly_entry', ROOT / 'claude_wechat_readonly.py')
        entry = importlib.util.module_from_spec(spec); spec.loader.exec_module(entry)
        with tempfile.TemporaryDirectory() as td:
            state = Path(td); db = state / 'db_storage'; db.mkdir()
            cfg = state / 'config.json'; keys = state / 'all_keys.json'
            cfg.write_text(json.dumps({'db_dir': str(db), 'keys_file': str(keys)}))
            previous_umask = os.umask(0o077)
            try:
                with patch.object(config, 'CONFIG_FILE', cfg), patch.object(config, 'DATA_DIR', state), patch.object(config, 'KEYS_FILE', keys):
                    mcp = entry.build_server()
                    names = {t.name for t in asyncio.run(mcp.list_tools())}
                    self.assertEqual(names, set(entry.TOOLS) | {'connection_status'})
                    cfg.write_text(json.dumps({'db_dir': str(state / 'missing')}))
                    with self.assertRaises(RuntimeError): entry.build_server()
            finally:
                os.umask(previous_umask)


if __name__ == '__main__':
    unittest.main()
