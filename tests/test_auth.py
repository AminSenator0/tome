from pathlib import Path

from tome.web.auth import AuthManager


def test_auth_manager_default_users(tmp_path: Path):
    db_file = tmp_path / "test_users.db"
    mgr = AuthManager(db_path=db_file)

    token_aren = mgr.authenticate("aren", "0009", "127.0.0.1")
    assert token_aren is not None
    user_aren = mgr.validate_session(token_aren)
    assert user_aren is not None
    assert user_aren.username == "aren"
    assert user_aren.is_admin is True

    token_mobina = mgr.authenticate("mobina", "1383", "127.0.0.1")
    assert token_mobina is not None
    user_mobina = mgr.validate_session(token_mobina)
    assert user_mobina is not None
    assert user_mobina.username == "mobina"


def test_auth_manager_invalid_credentials(tmp_path: Path):
    db_file = tmp_path / "test_users.db"
    mgr = AuthManager(db_path=db_file)

    token = mgr.authenticate("aren", "wrongpassword", "127.0.0.1")
    assert token is None

    token_ghost = mgr.authenticate("unknown_user", "0000", "127.0.0.1")
    assert token_ghost is None


def test_auth_manager_rate_limiting(tmp_path: Path):
    db_file = tmp_path / "test_users.db"
    mgr = AuthManager(db_path=db_file)

    for _ in range(5):
        assert mgr.authenticate("aren", "badpass", "192.168.1.50") is None

    blocked_token = mgr.authenticate("aren", "0009", "192.168.1.50")
    assert blocked_token is None

    mgr.reset_failed_attempts("192.168.1.50")
    mgr.reset_failed_attempts("aren")
    good_token = mgr.authenticate("aren", "0009", "192.168.1.50")
    assert good_token is not None


def test_auth_manager_revoke_session(tmp_path: Path):
    db_file = tmp_path / "test_users.db"
    mgr = AuthManager(db_path=db_file)

    token = mgr.authenticate("aren", "0009", "127.0.0.1")
    assert token is not None
    assert mgr.validate_session(token) is not None

    mgr.revoke_session(token)
    assert mgr.validate_session(token) is None
