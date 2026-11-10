"""Run native Keep contract tests on an owned, ephemeral PostgreSQL fixture.

Uses a cached image only, a dedicated no-masquerade bridge and localhost-only
dynamic port. Never connects to or cleans up an existing database/container.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
from uuid import uuid4


def command(arguments, **kwargs):
    return subprocess.run(arguments, check=True, text=True, capture_output=True, **kwargs)


def now():
    return datetime.now(timezone.utc).isoformat()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--python", required=True, help="Local Keep test virtualenv Python")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    token = uuid4().hex[:12]
    name = f"inventory-keep-contract-{token}"
    network = name + "-net"
    database = "inventory_attention_fixture_" + token
    result = {"started_at": now(), "fixture_only": True, "cleanup": {}}
    container_created = network_created = False
    outcome = 1
    try:
        image = command(["docker", "image", "inspect", "postgres:16", "--format", "{{.Id}}"]).stdout.strip()
        command(["docker", "network", "create", "--driver", "bridge", "--opt",
                 "com.docker.network.bridge.enable_ip_masquerade=false", network])
        network_created = True
        container_id = command([
            "docker", "run", "--pull=never", "--detach", "--name", name,
            "--label", "inventory.fixture=keep-native-contract", "--network", network,
            "-p", "127.0.0.1::5432", "-e", "POSTGRES_USER=fixture",
            "-e", "POSTGRES_PASSWORD=fixture-local-only", "-e", f"POSTGRES_DB={database}", image,
        ]).stdout.strip()
        container_created = True
        for _ in range(40):
            metadata = json.loads(command(["docker", "inspect", container_id]).stdout)[0]
            binding = (metadata["NetworkSettings"].get("Ports") or {}).get("5432/tcp")
            ready = subprocess.run(["docker", "exec", container_id, "pg_isready", "-h", "127.0.0.1", "-U", "fixture", "-d", database], capture_output=True)
            if binding and ready.returncode == 0:
                break
            time.sleep(0.25)
        else:
            raise RuntimeError("Owned PostgreSQL fixture did not become ready")
        if binding[0]["HostIp"] != "127.0.0.1":
            raise RuntimeError("Refusing non-loopback database binding")
        port = binding[0]["HostPort"]
        result["environment"] = {
            "container_id": container_id, "image": image, "name": name,
            "network": network, "network_masquerading": False,
            "host": "127.0.0.1", "port": int(port), "database": database,
            "server": command(["docker", "exec", container_id, "psql", "-U", "fixture", "-d", database, "-Atc",
                               "SELECT current_database(), version(), current_setting('fsync'), current_setting('synchronous_commit');"]).stdout.strip(),
            "python": command([args.python, "--version"]).stdout.strip(),
        }
        result["base_sha"] = command(["git", "rev-parse", "HEAD"], cwd=root).stdout.strip()
        result["files"] = {
            str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted((root / "tests/inventory_attention").glob("*.py"))
        }
        environment = os.environ.copy()
        environment["KEEP_INVENTORY_TEST_PG_URL"] = f"postgresql+psycopg2://fixture:fixture-local-only@127.0.0.1:{port}/{database}"
        environment["PYTHONPATH"] = str(root)
        test_command = [args.python, "-m", "pytest", "--confcutdir=tests/inventory_attention", "-q", "tests/inventory_attention"]
        tests = subprocess.run(test_command, cwd=root, env=environment, text=True, capture_output=True)
        result.update(command=test_command, returncode=tests.returncode, stdout=tests.stdout, stderr=tests.stderr)
        outcome = tests.returncode
        print(tests.stdout)
        print(tests.stderr)
    except Exception as error:
        result["error"] = f"{type(error).__name__}: {error}"
        raise
    finally:
        if container_created:
            cleanup = subprocess.run(["docker", "rm", "-f", container_id], text=True, capture_output=True)
            result["cleanup"]["container_exit"] = cleanup.returncode
        if network_created:
            cleanup = subprocess.run(["docker", "network", "rm", network], text=True, capture_output=True)
            result["cleanup"]["network_exit"] = cleanup.returncode
        result["finished_at"] = now()
        destination = Path(args.output)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(result, indent=2) + "\n")
    return outcome


if __name__ == "__main__":
    raise SystemExit(main())
