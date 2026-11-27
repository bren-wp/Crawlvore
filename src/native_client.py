"""WebView-free native desktop transport. Never follows redirects or loads HTML."""
import http.client
import json
import re
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlencode

READY = re.compile(r"CRAWLVORA_READY http://127\.0\.0\.1:([0-9]{1,5})/session/([a-f0-9]{64})")
MAX_JSON = 32 * 1024 * 1024

class NativeClient:
    def __init__(self, port, token):
        if not 1 <= port <= 65535 or not re.fullmatch(r"[a-f0-9]{64}", token):
            raise ValueError("Neispravna lokalna sesija.")
        self.port = port
        self._token = token

    @classmethod
    def from_ready(cls, line):
        match = READY.fullmatch(line.strip())
        if not match:
            raise ValueError("Radni proces nije spreman.")
        return cls(int(match[1]), match[2])

    def request(self, route, params=None, data=None, timeout=90):
        if not re.fullmatch(r"/api/[a-z0-9/-]+", route):
            raise ValueError("Nedopuštena lokalna ruta.")
        path = route + ("?" + urlencode(params) if params else "")
        headers = {"Cookie": f"crawlvora_session_{self.port}={self._token}",
                   "X-Local-Token": self._token, "Accept": "application/json"}
        body = None
        if data is not None:
            body = json.dumps(data, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json"
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=max(1,min(900,timeout)))
        try:
            connection.request("POST" if body is not None else "GET", path, body=body, headers=headers)
            with connection.getresponse() as response:
                if response.status >= 300 and response.status < 400:
                    raise ValueError("Neočekivano preusmjeravanje.")
                if "application/json" not in response.getheader("Content-Type", ""):
                    raise ValueError("Neočekivan odgovor servisa.")
                raw = response.read(MAX_JSON + 1)
                if len(raw) > MAX_JSON:
                    raise ValueError("Odgovor je prevelik.")
                result = json.loads(raw)
                if response.status != 200:
                    raise ValueError(result.get("error", "Operacija nije uspjela."))
                return result
        finally:
            connection.close()

class WorkerProcess:
    def __init__(self, workspace, primary=False, smoke=False, cancel=None):
        if getattr(sys, "frozen", False):
            args = [sys.executable, "--worker"]
        else:
            args = [sys.executable, str(Path(__file__).with_name("tvrtk_scraper.py")), "--worker"]
        args += ["--native-api-only", "--port", "0", "--data-dir", str(workspace)]
        if primary:
            args.append("--primary-workspace")
        kwargs = {"creationflags": subprocess.CREATE_NO_WINDOW} if sys.platform == "win32" else {}
        import os
        env = os.environ.copy()
        if smoke:
            for name in ("SUDREG_CLIENT_ID", "SUDREG_CLIENT_SECRET", "CRAWLVORA_REGISTRY_PROVISION"):
                env.pop(name, None)
        self.process = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                        stderr=subprocess.DEVNULL, env=env, **kwargs)  # nosec B603
        try:
            with ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(self.process.stdout.readline)
                deadline=time.monotonic()+900
                while True:
                    try:
                        line=future.result(timeout=.25)
                        break
                    except TimeoutError:
                        if time.monotonic()>=deadline or (cancel is not None and cancel.is_set()):
                            self.process.kill()
                            raise TimeoutError("Priprema radnog prostora je prekinuta.") from None
            self.client = NativeClient.from_ready(line.decode("ascii"))
            # Drain subsequent worker notifications without retaining secrets or logs.
            threading.Thread(target=self._drain, daemon=True).start()
        except BaseException:
            self.close()
            raise

    def _drain(self):
        try:
            for _ in self.process.stdout:
                pass
        except (OSError, ValueError):
            pass

    def close(self):
        p = self.process
        if p.stdin and not p.stdin.closed:
            p.stdin.close()
        try:
            p.wait(timeout=20)
        except subprocess.TimeoutExpired:
            p.kill()
            p.wait()
        if p.stdout and not p.stdout.closed:
            p.stdout.close()
