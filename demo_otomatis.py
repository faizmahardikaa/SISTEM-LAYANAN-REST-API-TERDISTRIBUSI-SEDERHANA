"""Opsional: reproduksi seluruh pengujian dalam satu perintah.
Untuk penghentian manual Server A, ikuti README.md (Ctrl+C).
"""
import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
NGINX = os.environ.get("NGINX_BIN", "nginx")


def wait_port(port):
    for _ in range(100):
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=.1):
                return
        except OSError:
            time.sleep(.1)
    raise RuntimeError(f"Port {port} belum siap; periksa logs/")


if __name__ == "__main__":
    os.chdir(ROOT)
    for port in (5001, 5002, 8080):
        with socket.socket() as sock:
            if sock.connect_ex(("127.0.0.1", port)) == 0:
                sys.exit(f"Port {port} sedang digunakan. Hentikan demo lama dahulu.")
    (ROOT / "logs").mkdir(exist_ok=True)
    (ROOT / "bukti").mkdir(exist_ok=True)
    processes, files = [], []
    nginx_args = [NGINX, "-p", str(ROOT) + "/", "-c", "nginx.conf"]
    # Hanya untuk sandbox pengujian; kosongkan untuk komputer biasa.
    extra = os.environ.get("NGINX_TEST_GLOBALS", "")
    try:
        subprocess.run([sys.executable, "init_db.py"], check=True)
        for server_id, port in (("A", 5001), ("B", 5002)):
            f = open(ROOT / "logs" / f"server-{server_id}.log", "w")
            files.append(f)
            processes.append(subprocess.Popen(
                [sys.executable, "server.py", "--id", server_id, "--port", str(port)],
                stdout=f, stderr=f))
            wait_port(port)
        validate = subprocess.run(nginx_args + (["-g", extra] if extra else []) + ["-t"],
                                  text=True, capture_output=True)
        (ROOT / "bukti" / "nginx-check.txt").write_text(validate.stdout + validate.stderr)
        validate.check_returncode()
        f = open(ROOT / "logs" / "nginx-console.log", "w")
        files.append(f)
        processes.append(subprocess.Popen(
            nginx_args + ["-g", "daemon off; " + extra], stdout=f, stderr=f))
        wait_port(8080)
        for mode in ("round-robin", "shared"):
            subprocess.run([sys.executable, "uji.py", mode], check=True)
        a = processes[0]
        command = f"$ kill -TERM {a.pid}  # PID Server A saja\n"
        print(command, end="", flush=True)
        os.kill(a.pid, signal.SIGTERM)
        a.wait(timeout=5)
        (ROOT / "bukti" / "stop-a.txt").write_text(
            command + f"Server A telah berhenti; returncode={a.returncode}.\n")
        subprocess.run([sys.executable, "uji.py", "failover"], check=True)
    finally:
        for process in reversed(processes):
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
        for f in files:
            f.close()
