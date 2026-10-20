"""Provider transport against a real isolated Redis and a simulated Chat quota.

No Google request is made. Redis is started with no TCP listener and empty state.
"""

import logging
import os
import shutil
import socket
import subprocess
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier, Lock
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import redis

from keep.exceptions.provider_exception import ProviderException
from keep.providers.google_chat_provider import google_chat_provider as module


@pytest.fixture
def isolated_redis(monkeypatch):
    binary = os.getenv("KEEP_TEST_REDIS_SERVER") or shutil.which("redis-server")
    if not binary:
        pytest.skip("Set KEEP_TEST_REDIS_SERVER for isolated Redis integration tests")
    with tempfile.TemporaryDirectory(prefix="chat-redis-", dir="/tmp") as directory:
        path = str(Path(directory) / "redis.sock")
        process = subprocess.Popen(
            [
                binary,
                "--port",
                "0",
                "--unixsocket",
                path,
                "--save",
                "",
                "--appendonly",
                "no",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        client = redis.Redis(unix_socket_path=path)
        try:
            for _ in range(100):
                try:
                    if client.ping():
                        break
                except redis.RedisError:
                    time.sleep(0.02)
            else:
                pytest.fail("Isolated Redis did not start")
            monkeypatch.setenv("GOOGLE_CHAT_RATE_LIMIT_ENABLED", "true")
            monkeypatch.setenv("REDIS", "true")
            # Native config has no unix socket option; inject the transport only.
            monkeypatch.setattr(
                module,
                "_pacing_redis_client",
                lambda stack: stack.enter_context(redis.Redis(unix_socket_path=path)),
                raising=False,
            )
            original_connect = socket.socket.connect

            def local_only(sock, address):
                if sock.family != socket.AF_UNIX:
                    raise AssertionError("External network is forbidden")
                return original_connect(sock, address)

            monkeypatch.setattr(socket.socket, "connect", local_only)
            yield client
        finally:
            client.close()
            process.terminate()
            process.wait(timeout=5)


def provider(space="shared", index=0):
    value = object.__new__(module.GoogleChatProvider)
    value.authentication_config = SimpleNamespace(
        webhook_url=f"https://chat.googleapis.com/v1/spaces/{space}/messages?key=fixture&token={index}"
    )
    value.logger = logging.getLogger("google-chat-pacing-test")
    return value


def test_six_concurrent_webhooks_in_one_space_all_deliver(isolated_redis, monkeypatch):
    barrier, lock = Barrier(6), Lock()
    timestamps, errors = [], []
    last = [-float("inf")]

    def post(url, **kwargs):
        with lock:
            now = time.monotonic()
            status = 200 if now - last[0] >= 1 else 429
            if status == 200:
                last[0] = now
            timestamps.append((now, status))
        return SimpleNamespace(status_code=status, headers={})

    monkeypatch.setattr(module.requests, "post", post)

    def send(index):
        barrier.wait()
        try:
            provider(index=index)._notify(message=f"fixture-{index}")
        except ProviderException as error:
            errors.append(str(error))

    with ThreadPoolExecutor(max_workers=6) as pool:
        list(pool.map(send, range(6)))
    assert not errors
    assert len(timestamps) == 6
    assert all(status == 200 for _, status in timestamps)
    assert all(b[0] - a[0] >= 1 for a, b in zip(timestamps, timestamps[1:]))
    assert all(
        b"token" not in key and b"fixture" not in key for key in isolated_redis.keys()
    )


def test_distinct_spaces_do_not_share_a_wait(isolated_redis, monkeypatch):
    calls = []
    monkeypatch.setattr(
        module.requests,
        "post",
        lambda *a, **kw: calls.append(time.monotonic())
        or SimpleNamespace(status_code=200, headers={}),
    )
    provider("internal")._notify(message="internal")
    provider("external")._notify(message="external")
    assert calls[1] - calls[0] < 0.5


def test_redis_failure_does_not_send_or_leak_credentials(monkeypatch, caplog):
    monkeypatch.setenv("GOOGLE_CHAT_RATE_LIMIT_ENABLED", "true")
    monkeypatch.setenv("REDIS", "true")
    broken = Mock()
    broken.set.side_effect = redis.ConnectionError(
        "redis://secret-user:secret-password@private"
    )
    monkeypatch.setattr(
        module, "_pacing_redis_client", lambda stack: broken, raising=False
    )
    post = Mock(return_value=SimpleNamespace(status_code=200, headers={}))
    monkeypatch.setattr(module.requests, "post", post)
    with pytest.raises(ProviderException) as error:
        provider()._notify(message="fixture")
    post.assert_not_called()
    assert "secret-password" not in str(error.value) + caplog.text


def test_busy_space_times_out_without_posting(monkeypatch):
    monkeypatch.setenv("GOOGLE_CHAT_RATE_LIMIT_ENABLED", "true")
    busy = Mock()
    busy.set.return_value = False
    busy.pttl.return_value = 1100
    monkeypatch.setattr(module, "_pacing_redis_client", lambda stack: busy)
    clock = [0.0]
    monkeypatch.setattr(module.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(
        module.time, "sleep", lambda delay: clock.__setitem__(0, clock[0] + delay)
    )
    post = Mock()
    monkeypatch.setattr(module.requests, "post", post)
    with pytest.raises(ProviderException, match="remained busy"):
        provider()._notify(message="fixture")
    assert clock[0] == 60
    post.assert_not_called()


def test_no_expiry_key_fails_without_posting(monkeypatch):
    monkeypatch.setenv("GOOGLE_CHAT_RATE_LIMIT_ENABLED", "true")
    busy = Mock()
    busy.set.return_value = False
    busy.pttl.return_value = -1
    monkeypatch.setattr(module, "_pacing_redis_client", lambda stack: busy)
    post = Mock()
    monkeypatch.setattr(module.requests, "post", post)
    with pytest.raises(ProviderException, match="no expiry"):
        provider()._notify(message="fixture")
    post.assert_not_called()


def test_rate_limited_retry_takes_a_new_space_slot(isolated_redis, monkeypatch):
    calls = []

    def post(*a, **kw):
        calls.append(time.monotonic())
        return SimpleNamespace(
            status_code=429 if len(calls) == 1 else 200, headers={"Retry-After": "1"}
        )

    monkeypatch.setattr(module.requests, "post", post)
    provider()._notify(message="fixture")
    assert len(calls) == 2
    assert calls[1] - calls[0] >= 1.1


def test_failure_in_internal_audience_does_not_suppress_external(
    isolated_redis, monkeypatch
):
    calls = []

    def post(url, **kwargs):
        calls.append(url.split("/spaces/")[1].split("/")[0])
        return SimpleNamespace(
            status_code=403 if calls[-1] == "internal" else 200, headers={}
        )

    monkeypatch.setattr(module.requests, "post", post)
    with pytest.raises(ProviderException, match="403"):
        provider("internal")._notify(message="internal")
    provider("external")._notify(message="external")
    assert calls == ["internal", "external"]


def test_enabled_pacing_requires_redis_configuration(monkeypatch):
    monkeypatch.setenv("GOOGLE_CHAT_RATE_LIMIT_ENABLED", "true")
    monkeypatch.setenv("REDIS", "false")
    post = Mock()
    monkeypatch.setattr(module.requests, "post", post)
    with pytest.raises(ProviderException, match="requires Keep Redis"):
        provider()._notify(message="fixture")
    post.assert_not_called()


def test_six_separate_processes_share_the_same_space_limit(isolated_redis):
    import json
    import sys

    socket_path = isolated_redis.connection_pool.connection_kwargs["path"]
    child_code = """
import json, logging, socket, sys, time
from types import SimpleNamespace
import redis
from keep.providers.google_chat_provider import google_chat_provider as module
path, index = sys.argv[1:]
original_connect = socket.socket.connect
def local_only(sock, address):
    if sock.family != socket.AF_UNIX:
        raise AssertionError("External network forbidden")
    return original_connect(sock, address)
socket.socket.connect = local_only
module._pacing_redis_client = lambda stack: stack.enter_context(redis.Redis(unix_socket_path=path))
client = redis.Redis(unix_socket_path=path)
def post(*args, **kwargs):
    accepted = client.set("simulated-chat-quota", "1", nx=True, px=1000)
    code = 200 if accepted else 429
    client.rpush("simulated-chat-attempts", json.dumps([time.monotonic(), code]))
    return SimpleNamespace(status_code=code, headers={})
module.requests.post = post
client.incr("ready-processes")
deadline = time.monotonic() + 20
while int(client.get("ready-processes")) < 6:
    if time.monotonic() > deadline:
        raise RuntimeError("Isolated process barrier failed")
    time.sleep(0.01)
provider = object.__new__(module.GoogleChatProvider)
provider.authentication_config = SimpleNamespace(webhook_url=f"https://chat.googleapis.com/v1/spaces/shared/messages?key=fixture&token={index}")
provider.logger = logging.getLogger("pacing-process-test")
provider._notify(message="isolated fixture")
client.close()
"""
    processes = [
        subprocess.Popen(
            [sys.executable, "-c", child_code, socket_path, str(index)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for index in range(6)
    ]
    try:
        for process in processes:
            _, stderr = process.communicate(timeout=30)
            assert process.returncode == 0, stderr
    finally:
        for process in processes:
            if process.poll() is None:
                process.kill()
                process.wait()
    attempts = [
        json.loads(row)
        for row in isolated_redis.lrange("simulated-chat-attempts", 0, -1)
    ]
    assert len(attempts) == 6
    assert all(code == 200 for _, code in attempts)
    assert all(b[0] - a[0] >= 1 for a, b in zip(attempts, attempts[1:]))


def test_direct_redis_reuses_keep_database_credentials_and_tls(monkeypatch):
    from contextlib import ExitStack
    from arq.connections import RedisSettings

    monkeypatch.setenv("REDIS", "true")
    settings = RedisSettings(
        host="redis.invalid",
        port=6380,
        database=4,
        username="fixture-user",
        password="fixture-secret",
        ssl=True,
        ssl_check_hostname=True,
    )
    monkeypatch.setattr(module, "get_redis_settings", lambda: settings)
    constructor = Mock()
    monkeypatch.setattr(module.redis, "Redis", constructor)
    with ExitStack() as stack:
        result = module._pacing_redis_client(stack)
        assert result is constructor.return_value
        result.close.assert_not_called()
    result.close.assert_called_once()
    options = constructor.call_args.kwargs
    assert options["host"] == "redis.invalid"
    assert options["port"] == 6380
    assert options["db"] == 4
    assert options["username"] == "fixture-user"
    assert options["password"] == "fixture-secret"
    assert options["ssl"] is True
    assert options["ssl_check_hostname"] is True
    assert options["socket_connect_timeout"] == options["socket_timeout"] == 2


def test_sentinel_connections_are_closed_after_delivery(monkeypatch):
    from contextlib import ExitStack
    from arq.connections import RedisSettings

    monkeypatch.setenv("REDIS", "true")
    settings = RedisSettings(
        host=[("sentinel.invalid", 26379)],
        sentinel=True,
        sentinel_master="keep-main",
        database=3,
    )
    monkeypatch.setattr(module, "get_redis_settings", lambda: settings)
    sentinel = Mock()
    sentinel.sentinels = [Mock(), Mock()]
    constructor = Mock(return_value=sentinel)
    monkeypatch.setattr(module, "Sentinel", constructor)
    with ExitStack() as stack:
        result = module._pacing_redis_client(stack)
    sentinel.master_for.assert_called_once_with("keep-main")
    result.close.assert_called_once()
    assert constructor.call_args.kwargs["db"] == 3
    for node in sentinel.sentinels:
        node.close.assert_called_once()


def test_pacing_rejects_non_google_webhook_without_sending(isolated_redis, monkeypatch):
    value = provider()
    value.authentication_config.webhook_url = "https://example.invalid/secret-webhook"
    post = Mock()
    monkeypatch.setattr(module.requests, "post", post)
    with pytest.raises(ProviderException, match="Google Chat webhook URL"):
        value._notify(message="fixture")
    post.assert_not_called()


def test_late_redis_permit_does_not_send_after_wait_budget(monkeypatch):
    monkeypatch.setenv("GOOGLE_CHAT_RATE_LIMIT_ENABLED", "true")
    clock = [0.0]
    monkeypatch.setattr(module.time, "monotonic", lambda: clock[0])
    client = Mock()

    def late_permit(*args, **kwargs):
        clock[0] = 61.0
        return True

    client.set.side_effect = late_permit
    monkeypatch.setattr(module, "_pacing_redis_client", lambda stack: client)
    post = Mock(return_value=SimpleNamespace(status_code=200, headers={}))
    monkeypatch.setattr(module.requests, "post", post)
    with pytest.raises(ProviderException, match="remained busy"):
        provider()._notify(message="fixture")
    post.assert_not_called()


def test_work_between_admission_and_post_preserves_next_request_spacing(
    isolated_redis, monkeypatch
):
    original = module._wait_for_space
    admitted = []
    calls = []

    def delayed(client, url):
        permit = original(client, url)
        admitted.append(True)
        if len(admitted) == 1:
            time.sleep(1.2)
        return permit

    monkeypatch.setattr(module, "_wait_for_space", delayed)
    monkeypatch.setattr(
        module.requests,
        "post",
        lambda *a, **kw: calls.append(time.monotonic())
        or SimpleNamespace(status_code=200, headers={}),
    )
    provider()._notify(message="delayed workflow")
    provider()._notify(message="ordinary next message")
    assert calls[1] - calls[0] >= 1


def test_lost_space_owner_does_not_post_or_remove_replacement(
    isolated_redis, monkeypatch
):
    original = module._wait_for_space

    def replaced(client, url):
        permit = original(client, url)
        key = next(iter(client.scan_iter("keep:google-chat:space:*")))
        client.set(key, "new-worker-owner", px=60000)
        return permit

    monkeypatch.setattr(module, "_wait_for_space", replaced)
    post = Mock()
    monkeypatch.setattr(module.requests, "post", post)
    with pytest.raises(ProviderException, match="lease"):
        provider()._notify(message="stale worker")
    post.assert_not_called()
    assert list(isolated_redis.scan_iter("keep:google-chat:space:*"))
    assert all(
        isolated_redis.get(key) == b"new-worker-owner"
        for key in isolated_redis.scan_iter("keep:google-chat:space:*")
    )


def test_redis_restart_between_admission_and_post_fails_closed(
    isolated_redis, monkeypatch
):
    original = module._wait_for_space

    def restarted(client, url):
        permit = original(client, url)
        client.flushdb()
        return permit

    monkeypatch.setattr(module, "_wait_for_space", restarted)
    post = Mock()
    monkeypatch.setattr(module.requests, "post", post)
    with pytest.raises(ProviderException, match="lease"):
        provider()._notify(message="lost state")
    post.assert_not_called()


def test_response_time_does_not_consume_the_next_cooldown(isolated_redis, monkeypatch):
    calls, finished = [], []

    def post(*args, **kwargs):
        calls.append(time.monotonic())
        if len(calls) == 1:
            time.sleep(1.2)
            finished.append(time.monotonic())
        return SimpleNamespace(status_code=200, headers={})

    monkeypatch.setattr(module.requests, "post", post)
    provider()._notify(message="slow response")
    provider()._notify(message="next request")
    assert calls[1] - finished[0] >= 1


def test_release_redis_failure_is_explicit_without_repeating_successful_post(
    isolated_redis, monkeypatch
):
    monkeypatch.setattr(module, "_pacing_redis_client", lambda stack: isolated_redis)
    calls = []

    def post(*args, **kwargs):
        calls.append(True)
        monkeypatch.setattr(
            isolated_redis,
            "eval",
            Mock(side_effect=redis.ConnectionError("fixture-secret")),
        )
        return SimpleNamespace(status_code=200, headers={})

    monkeypatch.setattr(module.requests, "post", post)
    with pytest.raises(ProviderException, match="after delivery") as failed:
        provider()._notify(message="already accepted")
    assert calls == [True]
    assert "fixture-secret" not in str(failed.value)


def test_released_or_expired_worker_cannot_reuse_its_space_token(isolated_redis):
    url = provider().authentication_config.webhook_url
    permit = module._wait_for_space(isolated_redis, url)
    with permit:
        permit.ensure_owned()
    with pytest.raises(ProviderException, match="lease"):
        permit.ensure_owned()
    key = next(iter(isolated_redis.scan_iter("keep:google-chat:space:*")))
    assert isolated_redis.get(key) == b"cooldown"
    assert 0 < isolated_redis.pttl(key) <= 1100
    isolated_redis.pexpire(key, 1)
    time.sleep(0.01)
    with module._wait_for_space(isolated_redis, url) as replacement:
        replacement.ensure_owned()
        with pytest.raises(ProviderException, match="lease"):
            permit.ensure_owned()


def test_abandoned_owner_expires_and_cannot_release_replacement_worker(isolated_redis):
    url = provider().authentication_config.webhook_url
    abandoned = module._wait_for_space(isolated_redis, url)
    key = next(iter(isolated_redis.scan_iter("keep:google-chat:space:*")))
    assert 59000 < isolated_redis.pttl(key) <= 60000
    # Exercise real Redis expiry with a shorter clock, without waiting a minute.
    isolated_redis.pexpire(key, 1)
    time.sleep(0.01)
    with module._wait_for_space(isolated_redis, url) as replacement:
        current = isolated_redis.get(key)
        with pytest.raises(ProviderException, match="lease"):
            abandoned.ensure_owned()
        abandoned.__exit__(None, None, None)
        assert isolated_redis.get(key) == current
        assert isolated_redis.pttl(key) > 59000
        replacement.ensure_owned()
