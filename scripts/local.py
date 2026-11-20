"""Project-local process lifecycle; only touches Suhail-owned resources."""
import argparse
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / ".runtime"
LOGS = ROOT / "runtime" / "logs"


def boot():
    os.chdir(ROOT)
    RUNTIME.mkdir(exist_ok=True)
    LOGS.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(ROOT))


def wait(url, timeout=50):
    import httpx
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        try:
            response = httpx.get(url, timeout=2)
            if response.status_code == 200:
                if url.endswith("18000/health") and response.json().get("policy_version") != "demo-fit-v1":
                    return False
                if url in {"http://127.0.0.1:3000", "http://127.0.0.1:3000/"} and "Guiding every" not in response.text:
                    return False
                return True
        except httpx.HTTPError:
            pass
        time.sleep(0.5)
    return False


def start(name, args, env=None, cwd=ROOT):
    pidfile = RUNTIME / (name + ".pid")
    if pidfile.exists():
        try:
            os.kill(int(pidfile.read_text()), 0)
            return
        except (ProcessLookupError, ValueError):
            pass
    with (LOGS / (name + ".log")).open("a") as log:
        p = subprocess.Popen(args, cwd=cwd, env=env, stdout=log, stderr=log, start_new_session=True)
    pidfile.write_text(str(p.pid))
    with (ROOT / "runtime" / "commands.jsonl").open("a") as f:
        f.write(json.dumps({"time": time.time(), "command": args, "cwd": str(cwd), "service": name}) + "\n")


def up():
    from dotenv import dotenv_values
    from services.api.config import settings
    config = settings()
    if config["database_url"].startswith("postgresql"):
        check = subprocess.run(["docker", "inspect", "-f", "{{.State.Running}}", "suhail-postgres"], capture_output=True, text=True)
        if check.returncode == 0:
            if check.stdout.strip() != "true":
                subprocess.run(["docker", "start", "suhail-postgres"], check=True, stdout=subprocess.DEVNULL)
        else:
            local = dotenv_values(RUNTIME / "app.env")
            db_env = {**os.environ, "POSTGRES_DB": "suhail", "POSTGRES_USER": "suhail", "POSTGRES_PASSWORD": local.get("POSTGRES_PASSWORD", "")}
            if not db_env["POSTGRES_PASSWORD"]:
                raise SystemExit("Run make setup to generate local database settings.")
            subprocess.run(["docker", "run", "-d", "--name", "suhail-postgres", "--restart", "unless-stopped", "-e", "POSTGRES_DB", "-e", "POSTGRES_USER", "-e", "POSTGRES_PASSWORD", "-p", "127.0.0.1:55432:5432", "-v", "suhail_pgdata:/var/lib/postgresql/data", "postgres:17.7-alpine"], env=db_env, check=True, stdout=subprocess.DEVNULL)
        from sqlalchemy import create_engine, text
        engine = create_engine(config["database_url"])
        for attempt in range(40):
            try:
                with engine.connect() as c:
                    c.execute(text("SELECT 1"))
                break
            except Exception:
                if attempt == 39:
                    raise SystemExit("PostgreSQL did not become ready; inspect docker logs suhail-postgres.")
                time.sleep(.5)
    subprocess.run([sys.executable, "-m", "services.api.seed"], check=True)
    common = {**os.environ, "PYTHONUNBUFFERED": "1"}
    for name, module, port, extra in [("provider-a", "integrations.provider", 8101, {"PROVIDER_ID": "provider-a"}), ("provider-b", "integrations.provider", 8102, {"PROVIDER_ID": "provider-b"}), ("fhir", "integrations.fhir", 8103, {}), ("api", "services.api.main", 18000, {})]:
        start(name, [sys.executable, "-m", "uvicorn", module + ":app", "--host", "127.0.0.1", "--port", str(port)], {**common, **extra})
        if not wait(f"http://127.0.0.1:{port}/health"):
            raise SystemExit(f"{name} failed to start; see runtime/logs/{name}.log")
    start("worker", [sys.executable, "-m", "services.api.worker"], common)
    # Only non-secret variables enter the frontend server environment.
    node = ROOT / ".runtime/node/bin"
    web_env = {k: v for k, v in os.environ.items() if k in ("HOME", "LANG", "LC_ALL", "TMPDIR", "USER")}
    web_env.update(PATH=str(node) + ":" + os.environ.get("PATH", ""), NEXT_TELEMETRY_DISABLED="1", API_INTERNAL_URL="http://127.0.0.1:18000", NODE_ENV="production")
    start("web", [str(node / "node") if (node / "node").exists() else "node", "node_modules/next/dist/bin/next", "start", "--hostname", "127.0.0.1", "--port", "3000"], web_env, ROOT / "apps/web")
    if not wait("http://127.0.0.1:3000", timeout=60):
        raise SystemExit("Web server failed to start; run make build and inspect runtime/logs/web.log.")
    print("Suhail Health: http://127.0.0.1:3000 | API http://127.0.0.1:18000/docs")
    print("Synthetic provider A/B: 8101/8102 | FHIR test server: 8103 | Demo accounts: .runtime/demo-credentials.json")
    print("Local synthetic demo only. Notifications stay in the visible outbox simulator.")


def down():
    for name in ("web", "worker", "api", "fhir", "provider-a", "provider-b"):
        pidfile = RUNTIME / (name + ".pid")
        if pidfile.exists():
            try:
                pid = int(pidfile.read_text())
                cmdline = Path(f"/proc/{pid}/cmdline").read_bytes().decode(errors="replace")
                process_cwd = Path(f"/proc/{pid}/cwd").resolve()
                owned_cwd = process_cwd in {ROOT, ROOT / "apps/web"}
                if owned_cwd and ("services.api" in cmdline or "integrations." in cmdline or "next" in cmdline):
                    os.killpg(pid, signal.SIGTERM)
            except (ProcessLookupError, FileNotFoundError, ValueError):
                pass
            pidfile.unlink(missing_ok=True)
    print("Suhail application processes stopped. PostgreSQL volume is retained.")


def status():
    import httpx
    for name, port, path in [("web", 3000, "/"), ("api", 18000, "/health"), ("provider-a", 8101, "/health"), ("provider-b", 8102, "/health"), ("fhir", 8103, "/health")]:
        try:
            r = httpx.get(f"http://127.0.0.1:{port}{path}", timeout=3)
            print(f"{name}: {'ready' if r.status_code == 200 else 'HTTP ' + str(r.status_code)} http://127.0.0.1:{port}")
        except httpx.HTTPError:
            print(f"{name}: unavailable; inspect runtime/logs/{name}.log")


if __name__ == "__main__":
    boot()
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("up", "down", "status"))
    globals()[parser.parse_args().action]()
