import hashlib

import pytest

from keep.api.core.dependencies import SINGLE_TENANT_UUID
from tests.fixtures.client import client, test_app  # noqa


def _create_db_user(db_session, username, password, role="admin"):
    from keep.api.models.db.user import User

    db_session.add(
        User(
            tenant_id=SINGLE_TENANT_UUID,
            username=username,
            password_hash=hashlib.sha256(password.encode()).hexdigest(),
            role=role,
        )
    )
    db_session.commit()


def _signin(client, username, password):
    response = client.post(
        "/signin",
        json={"username": username, "password": password},
    )
    return response


def _get_password_hash(db_session, username):
    from keep.api.models.db.user import User
    from sqlmodel import select

    user = db_session.exec(
        select(User)
        .where(User.tenant_id == SINGLE_TENANT_UUID)
        .where(User.username == username)
    ).first()
    return user.password_hash if user else None


@pytest.mark.parametrize(
    "test_app",
    [{"AUTH_TYPE": "DB", "KEEP_JWT_SECRET": "somesecret"}],
    indirect=True,
)
def test_change_own_password_success(db_session, client, test_app):
    """A local (DB) user can change their own password."""
    _create_db_user(db_session, "alice", "oldpassword")

    signin = _signin(client, "alice", "oldpassword")
    assert signin.status_code == 200
    token = signin.json()["accessToken"]

    response = client.put(
        "/auth/users/me/password",
        json={"current_password": "oldpassword", "new_password": "newpassword"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "OK"

    # old password no longer works
    assert _signin(client, "alice", "oldpassword").status_code == 401
    # new password works
    assert _signin(client, "alice", "newpassword").status_code == 200

    # password hash was actually updated in the db
    expected_hash = hashlib.sha256("newpassword".encode()).hexdigest()
    assert _get_password_hash(db_session, "alice") == expected_hash


@pytest.mark.parametrize(
    "test_app",
    [{"AUTH_TYPE": "DB", "KEEP_JWT_SECRET": "somesecret"}],
    indirect=True,
)
def test_change_own_password_wrong_current_password(db_session, client, test_app):
    """Changing password fails if the current password is incorrect."""
    _create_db_user(db_session, "bob", "correctpassword")

    signin = _signin(client, "bob", "correctpassword")
    assert signin.status_code == 200
    token = signin.json()["accessToken"]

    response = client.put(
        "/auth/users/me/password",
        json={"current_password": "wrongpassword", "new_password": "newpassword"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Current password is incorrect"

    # password unchanged
    assert _signin(client, "bob", "correctpassword").status_code == 200


@pytest.mark.parametrize(
    "test_app",
    [{"AUTH_TYPE": "DB", "KEEP_JWT_SECRET": "somesecret"}],
    indirect=True,
)
def test_change_own_password_empty_new_password(db_session, client, test_app):
    """Changing password fails if the new password is empty."""
    _create_db_user(db_session, "carol", "somepassword")

    signin = _signin(client, "carol", "somepassword")
    assert signin.status_code == 200
    token = signin.json()["accessToken"]

    response = client.put(
        "/auth/users/me/password",
        json={"current_password": "somepassword", "new_password": "   "},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422


@pytest.mark.parametrize(
    "test_app",
    [{"AUTH_TYPE": "DB", "KEEP_JWT_SECRET": "somesecret"}],
    indirect=True,
)
def test_change_password_requires_authentication(db_session, client, test_app):
    """Changing password requires authentication."""
    response = client.put(
        "/auth/users/me/password",
        json={"current_password": "x", "new_password": "y"},
    )
    assert response.status_code == 401


@pytest.mark.parametrize(
    "test_app",
    [{"AUTH_TYPE": "DB", "KEEP_JWT_SECRET": "somesecret"}],
    indirect=True,
)
def test_noc_user_can_change_own_password(db_session, client, test_app):
    """A non-admin (noc) local user can still change their own password."""
    _create_db_user(db_session, "dave", "oldpass", role="noc")

    signin = _signin(client, "dave", "oldpass")
    assert signin.status_code == 200
    token = signin.json()["accessToken"]

    response = client.put(
        "/auth/users/me/password",
        json={"current_password": "oldpass", "new_password": "brandnewpass"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert _signin(client, "dave", "brandnewpass").status_code == 200


@pytest.mark.parametrize(
    "test_app",
    [{"AUTH_TYPE": "DB", "KEEP_JWT_SECRET": "somesecret"}],
    indirect=True,
)
def test_admin_can_reset_user_password_via_update(db_session, client, test_app):
    """An admin can reset another user's password via the update endpoint."""
    _create_db_user(db_session, "admin_user", "adminpass", role="admin")
    _create_db_user(db_session, "managed_user", "initialpass", role="noc")

    signin = _signin(client, "admin_user", "adminpass")
    assert signin.status_code == 200
    token = signin.json()["accessToken"]

    response = client.put(
        "/auth/users/managed_user",
        json={"password": "resetpass"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200

    # managed_user can sign in with new password
    assert _signin(client, "managed_user", "resetpass").status_code == 200
    assert _signin(client, "managed_user", "initialpass").status_code == 401


@pytest.mark.parametrize(
    "test_app",
    [{"AUTH_TYPE": "DB", "KEEP_JWT_SECRET": "somesecret"}],
    indirect=True,
)
def test_admin_can_update_user_role_via_update(db_session, client, test_app):
    """An admin can update a local user's role via the update endpoint."""
    _create_db_user(db_session, "admin_user", "adminpass", role="admin")
    _create_db_user(db_session, "managed_user", "managedpass", role="noc")

    signin = _signin(client, "admin_user", "adminpass")
    assert signin.status_code == 200
    token = signin.json()["accessToken"]
    headers = {"Authorization": f"Bearer {token}"}

    response = client.put(
        "/auth/users/managed_user",
        json={"role": "admin"},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["role"] == "admin"
    assert _signin(client, "managed_user", "managedpass").json()["role"] == "admin"

    response = client.put(
        "/auth/users/managed_user",
        json={"role": "admin"},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["role"] == "admin"

    response = client.put(
        "/auth/users/missing_user",
        json={"role": "admin"},
        headers=headers,
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "User not found"
