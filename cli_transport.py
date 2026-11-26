"""Persistent avmw_cli JSON transport, one session per scan."""
import json
import queue
import re
import subprocess
import threading
import time

ANSI = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
RESPONSE = re.compile(r"\[my_cli\]\s+(get|set) cmd:.*?\bret = (-?\d+)\.")

class CliSession:
    def __init__(self, target):
        self.target = target
        self.proc = None
        self.lines = None
        self.reader = None

    def start(self):
        self.close()
        self.lines = queue.Queue()
        self.proc = subprocess.Popen(
            ["adb", "-s", self.target, "shell", "timeout 3600 avmw_cli"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, text=True, encoding="utf-8",
            errors="replace", bufsize=1)
        proc, lines = self.proc, self.lines
        def read():
            try:
                for line in proc.stdout:
                    clean = ANSI.sub("", line)
                    if RESPONSE.search(clean):
                        lines.put(clean)
            finally:
                lines.put(None)
        self.reader = threading.Thread(target=read, daemon=True)
        self.reader.start()
        try:
            self.proc.stdin.write("debug_on\ncd /1.15\n")
            self.proc.stdin.flush()
        except Exception:
            self.close()
            raise

    def close(self):
        proc, self.proc = self.proc, None
        if proc is None:
            return
        try:
            if proc.poll() is None:
                try:
                    proc.stdin.write("exit\n")
                    proc.stdin.flush()
                    proc.wait(timeout=2)
                except (OSError, subprocess.TimeoutExpired):
                    proc.kill()
                    proc.wait(timeout=2)
        finally:
            proc.stdin.close()
            if self.reader:
                self.reader.join(timeout=2)
            proc.stdout.close()

    def call(self, tx, payload):
        if self.proc is None:
            raise RuntimeError("CLI session is not running")
        action = {1:"get", 2:"set"}[tx]
        encoded = json.dumps(payload, separators=(",", ":"))
        try:
            self.proc.stdin.write(f'"{action} {encoded}"\n')
            self.proc.stdin.flush()
            line = self.lines.get(timeout=10)
            if line is None:
                raise RuntimeError("CLI exited before response")
            match = RESPONSE.search(line)
            if match.group(1) != action:
                raise RuntimeError("Unexpected CLI response")
            # Match the echoed request as well as the action, to reject stale replies.
            if f"'{encoded}'" not in line:
                raise RuntimeError("CLI response request mismatch")
            ret = int(match.group(2))
            if ret != 0:
                raise ValueError(f"CLI {action} rejected ({ret}): {encoded}")
            if tx == 2:
                return {"status":0, "result":0}
            ack = re.search(r"ack:\s*=\s*'(.*?)'\s*done", line)
            if not ack:
                raise RuntimeError("Missing CLI JSON response")
            return json.loads(ack.group(1))
        except ValueError:
            # JSON decoding errors are transport failures; rejected commands are not replayed.
            self.close()
            raise
        except (OSError, RuntimeError, queue.Empty):
            self.close()
            raise RuntimeError(f"CLI response failed: {action} {encoded}") from None

    def recover(self):
        if self.proc is None or self.proc.poll() is not None:
            self.start()
