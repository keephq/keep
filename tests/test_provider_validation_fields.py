import pytest
from pydantic import BaseModel, ValidationError

from keep.validation.fields import (
    HttpsUrl,
    MultiHostUrl,
    NoSchemeMultiHostUrl,
    NoSchemeUrl,
)


@pytest.mark.parametrize(
    "value,expected",
    [
        ("example.org", "https://example.org"),
        ("https://example.org", "https://example.org"),
        ("https://example.org?a=1&b=2", "https://example.org?a=1&b=2"),
        ("example.org#a=3;b=3", "https://example.org#a=3;b=3"),
        ("https://foo_bar.example.com/", "https://foo_bar.example.com/"),
        ("https://example.xn--p1ai", "https://example.xn--p1ai"),
    ],
)
def test_https_url_valid(value, expected):
    class Model(BaseModel):
        v: HttpsUrl

    assert str(Model(v=value).v) == expected


@pytest.mark.parametrize(
    "value",
    [
        "ftp://example.com/",
        "http://example.com/",
        "x" * 2084,
    ],
)
def test_https_url_invalid(value):
    class Model(BaseModel):
        v: HttpsUrl

    with pytest.raises(ValidationError) as exc_info:
        Model(v=value)
    assert len(exc_info.value.errors()) == 1, exc_info.value.errors()


@pytest.mark.parametrize(
    "value,expected",
    [
        ("example.org", "example.org"),
        ("https://example.org", "example.org"),
        ("localhost:8000", "localhost:8000"),
        ("http://localhost:8000", "localhost:8000"),
        ("postgres://user:pass@localhost:5432/app", "user:pass@localhost:5432/app"),
        (
            "postgresql+psycopg2://postgres:postgres@localhost:5432/hatch",
            "postgres:postgres@localhost:5432/hatch",
        ),
        ("http://123.45.67.8:8329/", "123.45.67.8:8329/"),
        ("http://[2001:db8::ff00:42]:8329", "[2001:db8::ff00:42]:8329"),
        ("http://example.org/path?query#fragment", "example.org/path?query#fragment"),
    ],
)
def test_no_scheme_url_valid(value, expected):
    class Model(BaseModel):
        v: NoSchemeUrl

    assert str(Model(v=value).v) == expected


@pytest.mark.parametrize(
    "value",
    [
        "http://??",
        "https://example.org more",
        "$https://example.org",
        "../icons/logo.gif",
        "http://2001:db8::ff00:42:8329",
        "http://[192.168.1.1]:8329",
        "..",
        "/rando/",
        "http://example.com:99999",
    ],
)
def test_no_scheme_url_invalid(value):
    class Model(BaseModel):
        v: NoSchemeUrl

    with pytest.raises(ValidationError) as exc_info:
        Model(v=value)
    assert len(exc_info.value.errors()) == 1, exc_info.value.errors()


@pytest.mark.parametrize(
    "value",
    [
        "http://localhost:5000",
        "http://localhost:5000,localhost:2222",
        "https://user:pass@localhost:4321,localhost:3000/app",
        "http://123.45.67.8:8329/,113.45.67.8:9309/",
        "http://[2001:db8::ff00:42]:8329,[2001:db8::ff00:42]:5000",
        "ampq://broker.com,en.broker.com/app",
        "postgres://user:pass@host1.db.net:4321,host2.db.net:6432/app",
        "mongodb://user:pass@host1.db.net:4321,host2.db.net:6432/app?query#fragment",
    ],
)
def test_multihost_url_valid(value):
    class Model(BaseModel):
        v: MultiHostUrl

    assert str(Model(v=value).v) == value


@pytest.mark.parametrize(
    "value",
    [
        "localhost:5000,localhost:2222",
        "broker.com,en.broker.com/app",
        "http://[192.168.1.1]:8329,[192.168.1.2]:8421",
        "user:pass@host1.db.net:4321,host2.db.net:6432/app?query#fragment",
    ],
)
def test_multihost_url_invalid(value):
    class Model(BaseModel):
        v: MultiHostUrl

    with pytest.raises(ValidationError) as exc_info:
        Model(v=value)
    assert len(exc_info.value.errors()) == 1, exc_info.value.errors()


@pytest.mark.parametrize(
    "value,expected",
    [
        ("http://localhost:5000,localhost:2222", "localhost:5000,localhost:2222"),
        ("localhost:5000,localhost:2222", "localhost:5000,localhost:2222"),
        (
            "https://user:pass@localhost:4321,localhost:3000/app",
            "user:pass@localhost:4321,localhost:3000/app",
        ),
        (
            "postgres://user:pass@host1.db.net:4321,host2.db.net:6432/app?query#fragment",
            "user:pass@host1.db.net:4321,host2.db.net:6432/app?query#fragment",
        ),
    ],
)
def test_no_scheme_multihost_url_valid(value, expected):
    class Model(BaseModel):
        v: NoSchemeMultiHostUrl

    assert str(Model(v=value).v) == expected


@pytest.mark.parametrize(
    "value",
    [
        "http://??, localhost:5000",
        "../icons/logo.gif",
        "http://[192.168.1.1]:8329",
        "..",
        "/rando/",
        "http://example.com:99999",
    ],
)
def test_no_scheme_multihost_url_invalid(value):
    class Model(BaseModel):
        v: NoSchemeMultiHostUrl

    with pytest.raises(ValidationError) as exc_info:
        Model(v=value)
    assert len(exc_info.value.errors()) == 1, exc_info.value.errors()
