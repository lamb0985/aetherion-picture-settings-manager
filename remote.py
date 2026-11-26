"""Single-user scrcpy session inside a private Xvfb display.
Browser access uses a same-origin Flask WebSocket proxy; VNC is loopback-only.
"""
import os
import socket
import subprocess
import threading
import time
from pathlib import Path

class Remote:
    def __init__(self):
        self.lock=threading.RLock()
        self.processes=[]
        self.target=None
        self.expires=0
        self.log=None

    def running(self):
        return bool(self.processes) and all(p.poll() is None for p in self.processes)

    def stop(self):
        with self.lock:
            for p in reversed(self.processes):
                if p.poll() is None:
                    p.terminate()
            for p in reversed(self.processes):
                try: p.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    p.kill()
                    p.wait()
            self.processes=[]
            self.target=None
            if self.log:
                self.log.close()
                self.log=None

    def start(self,target,size,bitrate,fps):
        with self.lock:
            self.stop()
            Path("/logs").mkdir(parents=True,exist_ok=True)
            self.log=open("/logs/scrcpy.log","a",buffering=1)
            env={**os.environ,"DISPLAY":":93","SDL_AUDIODRIVER":"dummy"}
            def spawn(args):
                p=subprocess.Popen(args,env=env,stdout=self.log,stderr=self.log)
                self.processes.append(p)
                return p
            try:
                spawn(["Xvfb",":93","-screen","0","1280x720x24","-nolisten","tcp","-noreset"])
                for _ in range(40):
                    if Path("/tmp/.X11-unix/X93").exists(): break
                    if self.processes[0].poll() is not None: raise RuntimeError("Xvfb failed")
                    time.sleep(.1)
                else: raise RuntimeError("Xvfb startup timed out")
                spawn(["scrcpy","--serial",target,"--max-size",str(size),"--video-bit-rate",str(bitrate)+"M","--max-fps",str(fps),"--no-audio","--fullscreen","--window-title","APSM"])
                spawn(["x11vnc","-display",":93","-localhost","-rfbport","5903","-forever","-shared","-nopw","-quiet"])
                for _ in range(50):
                    if not self.running(): raise RuntimeError("scrcpy startup failed; see /logs/scrcpy.log")
                    try:
                        with socket.create_connection(("127.0.0.1",5903),timeout=.2): pass
                        break
                    except OSError: time.sleep(.1)
                else: raise RuntimeError("VNC startup timed out")
                time.sleep(.5)
                if not self.running(): raise RuntimeError("scrcpy exited; see /logs/scrcpy.log")
                self.target=target
                self.expires=time.monotonic()+90
            except Exception:
                self.stop()
                raise

    def set_view_only(self, enabled):
        with self.lock:
            if not self.running():
                return False
            flag = "viewonly" if enabled else "noviewonly"
            args = ["x11vnc", "-display", ":93"]
            subprocess.check_output(args + ["-sync", "-R", flag],
                                    stderr=subprocess.STDOUT, text=True, timeout=5)
            result = subprocess.check_output(args + ["-Q", "viewonly"],
                                             stderr=subprocess.STDOUT, text=True, timeout=5)
            if f"ans=viewonly:{int(enabled)}" not in result:
                raise RuntimeError("Cannot verify mirror input lock")
            return True

    def touch(self):
        self.expires=time.monotonic()+90

    def reap(self):
        with self.lock:
            if self.processes and (not self.running() or time.monotonic()>self.expires):
                self.stop()

remote=Remote()
