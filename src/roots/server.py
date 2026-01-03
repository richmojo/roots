"""
server - Embedding server daemon for fast inference.

Keeps the embedding model loaded in memory. All roots processes
connect to the same server via Unix socket.

Usage:
    roots server start    # Start daemon
    roots server stop     # Stop daemon
    roots server status   # Check if running
"""

import json
import os
import signal
import socket
import sys
import threading
from pathlib import Path

SOCKET_PATH = Path("/tmp/roots-embedder.sock")
PID_FILE = Path("/tmp/roots-embedder.pid")
LOG_FILE = Path("/tmp/roots-embedder.log")


class EmbeddingServer:
    """Unix socket server for embedding requests."""

    def __init__(self, model_name: str, model_type: str):
        self.model_name = model_name
        self.model_type = model_type
        self.embedder = None
        self.running = False
        self.socket = None

    def start(self):
        """Start the server."""
        from roots.embeddings import get_embedder

        print(f"Loading model: {self.model_name}", flush=True)
        # use_server=False to avoid circular dependency
        self.embedder = get_embedder(self.model_name, self.model_type, use_server=False)

        # Warm up
        _ = self.embedder.embed("warmup")
        print("Model ready", flush=True)

        # Clean up old socket
        if SOCKET_PATH.exists():
            SOCKET_PATH.unlink()

        self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.socket.bind(str(SOCKET_PATH))
        self.socket.listen(10)
        self.socket.settimeout(1.0)

        signal.signal(signal.SIGTERM, self._shutdown)
        signal.signal(signal.SIGINT, self._shutdown)

        self.running = True
        print(f"Listening on {SOCKET_PATH}", flush=True)

        while self.running:
            try:
                conn, _ = self.socket.accept()
                threading.Thread(target=self._handle, args=(conn,), daemon=True).start()
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    print(f"Accept error: {e}", flush=True)

        self._cleanup()

    def _handle(self, conn: socket.socket):
        """Handle client request."""
        try:
            data = conn.recv(65536)
            if not data:
                return

            req = json.loads(data.decode().strip())
            cmd = req.get("cmd")

            if cmd == "embed":
                emb = self.embedder.embed(req["text"])
                resp = {"ok": True, "embedding": emb}
            elif cmd == "embed_batch":
                embs = self.embedder.embed_batch(req["texts"])
                resp = {"ok": True, "embeddings": embs}
            elif cmd == "ping":
                resp = {"ok": True, "model": self.model_name}
            elif cmd == "stop":
                resp = {"ok": True}
                self.running = False
            else:
                resp = {"ok": False, "error": f"unknown: {cmd}"}

            conn.sendall(json.dumps(resp).encode())
        except Exception as e:
            try:
                conn.sendall(json.dumps({"ok": False, "error": str(e)}).encode())
            except:
                pass
        finally:
            conn.close()

    def _shutdown(self, *_):
        print("\nShutting down...", flush=True)
        self.running = False

    def _cleanup(self):
        if self.socket:
            self.socket.close()
        if SOCKET_PATH.exists():
            SOCKET_PATH.unlink()
        if PID_FILE.exists():
            PID_FILE.unlink()
        print("Stopped", flush=True)


class EmbeddingClient:
    """Client to connect to embedding server."""

    @staticmethod
    def is_running() -> bool:
        if not SOCKET_PATH.exists():
            return False
        try:
            return EmbeddingClient._send({"cmd": "ping"}).get("ok", False)
        except:
            return False

    @staticmethod
    def get_model() -> str | None:
        try:
            resp = EmbeddingClient._send({"cmd": "ping"})
            return resp.get("model") if resp.get("ok") else None
        except:
            return None

    @staticmethod
    def embed(text: str) -> list[float]:
        resp = EmbeddingClient._send({"cmd": "embed", "text": text})
        if not resp.get("ok"):
            raise RuntimeError(resp.get("error", "server error"))
        return resp["embedding"]

    @staticmethod
    def embed_batch(texts: list[str]) -> list[list[float]]:
        resp = EmbeddingClient._send({"cmd": "embed_batch", "texts": texts})
        if not resp.get("ok"):
            raise RuntimeError(resp.get("error", "server error"))
        return resp["embeddings"]

    @staticmethod
    def stop() -> bool:
        try:
            EmbeddingClient._send({"cmd": "stop"})
            return True
        except:
            return False

    @staticmethod
    def _send(req: dict) -> dict:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(60.0)
        try:
            sock.connect(str(SOCKET_PATH))
            sock.sendall(json.dumps(req).encode())
            data = sock.recv(1024 * 1024)  # 1MB max response
            return json.loads(data.decode())
        finally:
            sock.close()


def start_server(model_name: str, model_type: str, foreground: bool = False):
    """Start embedding server."""
    if EmbeddingClient.is_running():
        current = EmbeddingClient.get_model()
        if current == model_name:
            return True
        else:
            stop_server()

    if foreground:
        server = EmbeddingServer(model_name, model_type)
        server.start()
        return True

    # Double-fork to fully daemonize
    pid = os.fork()
    if pid > 0:
        # Parent - wait for server to be ready
        import time
        for _ in range(60):  # Wait up to 60 seconds
            time.sleep(1)
            if EmbeddingClient.is_running():
                return True
        return False

    # First child - become session leader
    os.setsid()

    # Second fork - prevent zombie and ensure full detachment
    pid2 = os.fork()
    if pid2 > 0:
        os._exit(0)  # First child exits

    # Grandchild - the actual daemon
    os.chdir("/")
    os.umask(0)

    # Close all file descriptors
    import resource
    maxfd = resource.getrlimit(resource.RLIMIT_NOFILE)[1]
    if maxfd == resource.RLIM_INFINITY:
        maxfd = 1024
    for fd in range(3, maxfd):
        try:
            os.close(fd)
        except OSError:
            pass

    # Redirect stdin/stdout/stderr
    sys.stdin = open("/dev/null", "r")
    log = open(LOG_FILE, "a")
    sys.stdout = log
    sys.stderr = log

    # Write PID after we're fully daemonized
    PID_FILE.write_text(str(os.getpid()))

    server = EmbeddingServer(model_name, model_type)
    server.start()
    os._exit(0)


def stop_server() -> bool:
    """Stop embedding server."""
    if not EmbeddingClient.is_running():
        # Clean up stale files
        if SOCKET_PATH.exists():
            SOCKET_PATH.unlink()
        if PID_FILE.exists():
            PID_FILE.unlink()
        return True

    EmbeddingClient.stop()

    # Wait for it to stop
    import time
    for _ in range(10):
        time.sleep(0.5)
        if not EmbeddingClient.is_running():
            return True

    # Force kill
    if PID_FILE.exists():
        try:
            pid = int(PID_FILE.read_text().strip())
            os.kill(pid, signal.SIGKILL)
        except:
            pass
    return True


def server_status() -> dict:
    """Get server status."""
    if EmbeddingClient.is_running():
        pid = None
        if PID_FILE.exists():
            try:
                pid = int(PID_FILE.read_text().strip())
            except:
                pass
        return {
            "running": True,
            "model": EmbeddingClient.get_model(),
            "pid": pid,
            "socket": str(SOCKET_PATH),
        }
    return {"running": False}


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Roots embedding server")
    parser.add_argument("--model", required=True, help="Model name")
    parser.add_argument("--type", default="sentence-transformers", help="Model type")
    args = parser.parse_args()

    # Run in foreground (Rust handles daemonization via nohup)
    server = EmbeddingServer(args.model, args.type)
    server.start()
