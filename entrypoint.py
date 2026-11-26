"""Run APSM with the configured numeric UID/GID, without modifying host volume contents."""
import os
import pwd
import grp
import sys
import subprocess

def parse_id(name):
    raw=os.environ.get(name,"1000")
    if not raw.isascii() or not raw.isdecimal() or not 1<=int(raw)<=2147483647:
        raise SystemExit(f"{name} must be a positive numeric ID")
    return int(raw)

def main():
    uid,gid=parse_id("PUID"),parse_id("PGID")
    if os.geteuid()==0:
        try:
            group=grp.getgrgid(gid).gr_name
        except KeyError:
            group=f"apsm-g{gid}"
            subprocess.run(["groupadd","-g",str(gid),group],check=True)
        try:
            account=pwd.getpwuid(uid).pw_name
        except KeyError:
            account=f"apsm-u{uid}"
            subprocess.run(["useradd","-u",str(uid),"-g",group,"-d","/config","-M","-s","/usr/sbin/nologin",account],check=True)
        # Bind mounts and Docker volumes must retain the host's ownership.
        # /proc/self/mountinfo identifies bind mounts even on the same filesystem.
        with open("/proc/self/mountinfo") as mounts:
            mountpoints={line.split()[4] for line in mounts if line.strip()}
        for directory in ("/config","/backups","/logs"):
            if directory not in mountpoints:
                os.chown(directory,uid,gid)
                os.chmod(directory,0o775)
        os.setgroups([])
        os.setgid(gid)
        os.setuid(uid)
    elif (os.geteuid(),os.getegid())!=(uid,gid):
        raise SystemExit("Container UID/GID differs from PUID/PGID")
    os.umask(0o002)
    for directory in ("/config","/backups","/logs"):
        if not os.access(directory,os.R_OK|os.W_OK|os.X_OK):
            raise SystemExit(f"{directory} must be writable by {uid}:{gid}; adjust host volume permissions")
    print(f"APSM running as UID={os.getuid()} GID={os.getgid()}",flush=True)
    os.execvp(sys.argv[1],sys.argv[1:])

if __name__=="__main__":
    main()
