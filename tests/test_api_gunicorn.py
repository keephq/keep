"""Test API image configuration without starting Keep or its database.

Run with: python -m unittest discover -s tests -p 'test_api_gunicorn.py'
Only Gunicorn (the application's pinned major version) is required.
"""

import builtins
import io
import json
import os
import socket
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from gunicorn.app.wsgiapp import WSGIApplication
from gunicorn.sock import create_sockets

ROOT = Path(__file__).resolve().parents[1]


class ApiGunicornTests(unittest.TestCase):
    def load_config(self, env=None, extra_args=()):
        # Read the image's real CMD so reintroducing hardcoded flags fails tests.
        dockerfile = (ROOT / "docker/Dockerfile.api").read_text()
        cmd = next(
            line[4:] for line in dockerfile.splitlines() if line.startswith("CMD ")
        )
        args = json.loads(cmd)
        args[args.index("-c") + 1] = str(ROOT / "keep/api/config.py")

        # Configuration imports Keep's provisioning dependencies; the hooks must
        # remain present, but loading config should not require external services.
        real_import = builtins.__import__
        keep_modules = MagicMock()

        def isolated_import(name, *args, **kwargs):
            if name == "keep" or name.startswith("keep."):
                return keep_modules
            return real_import(name, *args, **kwargs)

        with (
            patch.dict(os.environ, env or {}, clear=True),
            patch.object(sys, "argv", [*args, *extra_args]),
            patch("builtins.__import__", side_effect=isolated_import),
        ):
            return WSGIApplication().cfg

    def test_image_defaults(self):
        cfg = self.load_config()
        self.assertEqual(cfg.bind, ["0.0.0.0:8080"])
        self.assertEqual(cfg.workers, 4)
        self.assertTrue(cfg.preload_app)
        self.assertEqual(
            cfg.settings["worker_class"].value, "uvicorn.workers.UvicornWorker"
        )
        self.assertEqual(cfg.on_starting.__name__, "on_starting")
        self.assertEqual(cfg.post_worker_init.__name__, "post_worker_init")

    def test_environment_defaults(self):
        cfg = self.load_config({"PORT": "9090", "KEEP_API_WORKERS": "2"})
        self.assertEqual(cfg.bind, ["0.0.0.0:9090"])
        self.assertEqual(cfg.workers, 2)

    def test_explicit_bind_includes_port(self):
        cfg = self.load_config({"PORT": "9090", "KEEP_API_BIND": "127.0.0.1:8081"})
        self.assertEqual(cfg.bind, ["127.0.0.1:8081"])

    def test_gunicorn_environment_overrides_defaults(self):
        cfg = self.load_config(
            {
                "KEEP_API_BIND": "[::]:9090",
                "KEEP_API_WORKERS": "2",
                "GUNICORN_CMD_ARGS": "--bind 127.0.0.1:9091 --workers 3",
            }
        )
        self.assertEqual(cfg.bind, ["127.0.0.1:9091"])
        self.assertEqual(cfg.workers, 3)

    def test_explicit_flags_override_environment(self):
        cfg = self.load_config(
            {"GUNICORN_CMD_ARGS": "--bind [::]:9090 --workers 2"},
            ["--bind", "127.0.0.1:9092", "--workers", "5"],
        )
        self.assertEqual(cfg.bind, ["127.0.0.1:9092"])
        self.assertEqual(cfg.workers, 5)

    def test_arq_workers_do_not_change_api_workers(self):
        cfg = self.load_config({"KEEP_WORKERS": "7", "REDIS": "true"})
        self.assertEqual(cfg.workers, 4)

    def test_invalid_worker_count_fails_startup(self):
        for workers in ["0", "-1", "not-a-number"]:
            with (
                self.subTest(workers=workers),
                patch("sys.stderr", new_callable=io.StringIO),
                self.assertRaises(SystemExit),
            ):
                self.load_config({"KEEP_API_WORKERS": workers})

    def test_default_listener_uses_ipv4_socket(self):
        cfg = self.load_config({"PORT": "0"})
        listeners = create_sockets(cfg, MagicMock())
        self.addCleanup(lambda: [listener.close() for listener in listeners])
        listener = listeners[0]
        self.assertEqual(listener.family, socket.AF_INET)
        port = listener.getsockname()[1]
        with socket.create_connection(("127.0.0.1", port), timeout=2):
            connection, _ = listener.accept()
            connection.close()

    @unittest.skipUnless(socket.has_ipv6, "IPv6 unavailable")
    def test_ipv6_listener_accepts_connections(self):
        # IPv6 is explicitly enabled; use an ephemeral port.
        cfg = self.load_config({"KEEP_API_BIND": "[::]:0"})
        listeners = create_sockets(cfg, MagicMock())
        self.addCleanup(lambda: [listener.close() for listener in listeners])
        listener = listeners[0]
        port = listener.getsockname()[1]
        with socket.create_connection(("::1", port), timeout=2):
            connection, _ = listener.accept()
            connection.close()
        # Gunicorn follows the host's dual-stack policy; assert IPv4 only when
        # the host enables IPv4-mapped connections on IPv6 sockets.
        if not listener.getsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY):
            with socket.create_connection(("127.0.0.1", port), timeout=2):
                connection, _ = listener.accept()
                connection.close()


if __name__ == "__main__":
    unittest.main()
