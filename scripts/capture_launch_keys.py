#!/usr/bin/env python3
"""Explicit ARM64 launch-time capture. No signing, sudo, attach, or message sending.

Run with Apple's Python and LLDB bindings. Validated keys are written in the
wechat-mcp-macos backend format; secrets are never printed. See docs/CLAUDE.md.
"""
import argparse
import hashlib
import hmac
import json
import os
import plistlib
import subprocess
import time
from pathlib import Path


def page_matches(key, page):
    if len(key) != 32 or len(page) != 4096:
        return False
    salt = bytes(value ^ 0x3a for value in page[:16])
    mac_key = hashlib.pbkdf2_hmac('sha512', key, salt, 2, 32)
    mac = hmac.new(mac_key, page[16:4032] + (1).to_bytes(4, 'little'), hashlib.sha512).digest()
    return hmac.compare_digest(mac, page[4032:])


def candidate_key(password, salt, prf, rounds, pages):
    if prf != 5 or len(salt) != 16 or not 0 < len(password) <= 256:
        return None
    for page in pages:
        if rounds == 256000 and salt == page[:16]:
            key = hashlib.pbkdf2_hmac('sha512', password, salt, rounds, 32)
        elif rounds == 2 and salt == bytes(value ^ 0x3a for value in page[:16]):
            key = password
        else:
            continue
        if page_matches(key, page):
            return key
    return None


def save_keys(path, keys):
    from configure_claude import private_json
    private_json(path, keys)


def emit(event, **fields):
    print(json.dumps(dict(event=event, **fields)), flush=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--app', type=Path, required=True)
    ap.add_argument('--db-dir', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True, help='New private key file; never overwrites existing keys')
    ap.add_argument('--timeout', type=int, default=150)
    ap.add_argument('--acknowledge-debug-launch', action='store_true')
    args = ap.parse_args()
    if not args.acknowledge_debug_launch:
        ap.error('Debug launch may pause or crash WeChat; review docs and acknowledge explicitly.')
    app = args.app.expanduser().resolve(strict=True)
    db = args.db_dir.expanduser().resolve(strict=True)
    output = args.out.expanduser().absolute()
    if output.exists():
        ap.error('Output already exists; choose a new path.')
    if db.name != 'db_storage':
        ap.error('--db-dir must point to the selected account db_storage.')
    with (app / 'Contents/Info.plist').open('rb') as f:
        info = plistlib.load(f)
    executable = (app / 'Contents/MacOS' / info['CFBundleExecutable']).resolve(strict=True)
    running = subprocess.check_output(['ps', '-axo', 'comm='], text=True)
    if any(line.strip() == str(executable) for line in running.splitlines()):
        ap.error('Selected app is already running. Quit it normally; this tool will not kill it.')
    rows = {}
    for path in sorted(db.rglob('*.db')):
        with path.open('rb') as f:
            page = f.read(4096)
        if len(page) == 4096 and not page.startswith(b'SQLite format 3'):
            rows[str(path.relative_to(db))] = page
    if not rows:
        ap.error('No supported encrypted database pages found.')
    import lldb
    os.umask(0o077)
    output.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    # Restrict a directory created for keys; do not chmod arbitrary user folders.
    debugger = lldb.SBDebugger.Create()
    debugger.SkipLLDBInitFiles(True)
    debugger.SetAsync(True)
    process = None
    found = {}
    calls = 0
    try:
        target = debugger.CreateTarget(str(executable))
        if not target.IsValid() or not target.GetTriple().startswith('arm64'):
            raise RuntimeError('Only native ARM64 launch capture is supported.')
        bp = target.BreakpointCreateByName('CCKeyDerivationPBKDF')
        launch = lldb.SBLaunchInfo([])
        launch.SetWorkingDirectory(str(executable.parent))
        for fd in range(3):
            launch.AddSuppressFileAction(fd, fd == 0, fd != 0)
        error = lldb.SBError()
        process = target.Launch(launch, error)
        if error.Fail() or not process.IsValid():
            raise RuntimeError('Debugger launch failed; no automatic re-signing will be attempted.')
        emit('launched', pid=process.GetProcessID(), databases=len(rows), breakpoint_locations=bp.GetNumLocations())
        listener = debugger.GetListener()
        deadline = time.monotonic() + max(10, min(args.timeout, 300))
        while time.monotonic() < deadline and len(found) < len(rows):
            event = lldb.SBEvent()
            if not listener.WaitForEvent(1, event) or not lldb.SBProcess.EventIsProcessEvent(event):
                continue
            state = lldb.SBProcess.GetStateFromEvent(event)
            if state in (lldb.eStateExited, lldb.eStateCrashed, lldb.eStateDetached):
                emit('process_ended', state=state)
                break
            if state != lldb.eStateStopped:
                continue
            for thread in process:
                if thread.GetStopReason() != lldb.eStopReasonBreakpoint:
                    continue
                if thread.GetStopReasonDataCount() < 2 or thread.GetStopReasonDataAtIndex(0) != bp.GetID():
                    continue
                calls += 1
                frame = thread.GetFrameAtIndex(0)
                values = [frame.FindRegister('x' + str(i)).GetValueAsUnsigned() for i in range(1, 7)]
                password_ptr, password_len, salt_ptr, salt_len, prf, rounds = values
                if salt_len != 16 or not 0 < password_len <= 256 or prf != 5 or rounds not in (2, 256000):
                    continue
                error = lldb.SBError()
                salt = process.ReadMemory(salt_ptr, 16, error)
                if error.Fail() or len(salt) != 16:
                    continue
                # Read secret input only after the salt matches the chosen account.
                pending = [page for name, page in rows.items() if name not in found]
                acceptable = [page[:16] if rounds == 256000 else bytes(v ^ 0x3a for v in page[:16]) for page in pending]
                if salt not in acceptable:
                    continue
                password = process.ReadMemory(password_ptr, password_len, error)
                if error.Fail() or len(password) != password_len:
                    continue
                key = candidate_key(password, salt, prf, rounds, pending)
                if key is None:
                    continue
                for name, page in rows.items():
                    if name not in found and page_matches(key, page):
                        found[name] = {'enc_key': key.hex()}
                save_keys(output, found)
                emit('verified', count=len(found), total=len(rows))
            error = process.Continue()
            if error.Fail():
                raise RuntimeError('Unable to resume selected app.')
        emit('finished', verified=len(found), total=len(rows), calls=calls)
        return 0 if len(found) == len(rows) else 3
    finally:
        # Never kill WeChat; leave the launched app running after removing breakpoints.
        if process and process.IsValid() and process.GetState() not in (lldb.eStateExited, lldb.eStateDetached, lldb.eStateInvalid):
            target.DeleteAllBreakpoints()
            error = process.Detach()
            if error.Fail():
                emit('detach_failed', action='Inspect the app manually before restarting it.')
            else:
                emit('detached', pid=process.GetProcessID())
        lldb.SBDebugger.Destroy(debugger)


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130)
    except Exception as error:
        # Avoid emitting arbitrary exception values that could contain key material.
        emit('failed', error_type=type(error).__name__)
        raise SystemExit(2)
