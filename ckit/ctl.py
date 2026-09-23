"""Start / stop / status a repo's reader server in the background.

    ckit up [--host H] [--port P]     # background; URL from kit.json unless overridden
    ckit down
    ckit status

One pidfile per repo root (`.serve.pid`), so several repos serve at once on their own ports.
A port already taken — a server whose pidfile is gone — is stopped so this one can bind.
"""

from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import time

from .paths import Repo, load_repo

PIDFILE = ".serve.pid"
LOGFILE = ".serve.log"


def _pid(repo: Repo) -> int | None:
    p = repo.root / PIDFILE
    if not p.is_file():
        return None
    try:
        pid = int(p.read_text().strip())
        os.kill(pid, 0)
        return pid
    except (ValueError, ProcessLookupError, PermissionError):
        return None


def _url(repo: Repo, host: str | None, port: int | None) -> str:
    return f"http://{host or repo.cfg['host']}:{port or repo.cfg['port']}/"


def _listeners(port: int) -> list[int]:
    """Pids with a TCP listen socket on `port`. Empty when lsof is missing."""
    try:
        out = subprocess.run(
            ["lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN", "-t"],
            capture_output=True, text=True, check=False,
        )
    except FileNotFoundError:
        return []
    pids: list[int] = []
    for line in out.stdout.split():
        try:
            pid = int(line)
        except ValueError:
            continue
        if pid != os.getpid() and pid not in pids:
            pids.append(pid)
    return pids


def _free_port(port: int) -> None:
    """Stop whatever is listening on `port`, so a new server can bind it."""
    for pid in _listeners(port):
        try:
            os.kill(pid, signal.SIGTERM)
        except (ProcessLookupError, PermissionError):
            continue
        print(f"stopping {pid} (port {port} in use)")
    deadline = time.monotonic() + 2.0
    while time.monotonic() < deadline and _listeners(port):
        time.sleep(0.1)
    for pid in _listeners(port):
        try:
            os.kill(pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            continue
        print(f"killed {pid} (port {port} still in use)")
    deadline = time.monotonic() + 1.0
    while time.monotonic() < deadline and _listeners(port):
        time.sleep(0.1)


def up(repo: Repo, host: str | None, port: int | None) -> int:
    pid = _pid(repo)
    if pid:
        print(f"already running at {_url(repo, host, port)}  (pid {pid})")
        return 0
    _free_port(int(port or repo.cfg["port"]))
    cmd = [sys.executable, "-m", "ckit", "serve", "--root", str(repo.root)]
    if host:
        cmd += ["--host", host]
    if port:
        cmd += ["--port", str(port)]
    log = open(repo.root / LOGFILE, "ab")
    proc = subprocess.Popen(cmd, stdout=log, stderr=log, stdin=subprocess.DEVNULL,
                            start_new_session=True, cwd=repo.root)
    (repo.root / PIDFILE).write_text(f"{proc.pid}\n")
    time.sleep(0.4)
    if proc.poll() is not None:
        (repo.root / PIDFILE).unlink(missing_ok=True)
        print(f"failed to start — see {LOGFILE}", file=sys.stderr)
        return 1
    print(f"serving {_url(repo, host, port)}  (pid {proc.pid}; `ckit down` to stop)")
    return 0


def down(repo: Repo) -> int:
    pid = _pid(repo)
    if pid:
        os.kill(pid, signal.SIGTERM)
        print(f"stopping {pid}")
    else:
        print("not running")
    (repo.root / PIDFILE).unlink(missing_ok=True)
    return 0


def status(repo: Repo) -> int:
    pid = _pid(repo)
    if pid:
        print(f"running at {_url(repo, None, None)}  (pid {pid})")
        return 0
    print("not running")
    return 1


def main(argv: list[str], verb: str) -> int:
    ap = argparse.ArgumentParser(prog=f"ckit {verb}")
    ap.add_argument("--host")
    ap.add_argument("--port", type=int)
    args = ap.parse_args(argv)
    repo = load_repo()
    if verb == "up":
        return up(repo, args.host or os.environ.get("HOST") or None,
                  args.port or (int(os.environ["PORT"]) if os.environ.get("PORT") else None))
    if verb == "down":
        return down(repo)
    return status(repo)
