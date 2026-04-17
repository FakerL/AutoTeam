import types

from autoteam import accounts, manager


def test_reinvite_account_uses_unified_oauth_login_and_advances_cursor(monkeypatch):
    updates = []
    advanced = []

    monkeypatch.setattr(
        manager,
        "login_codex_via_browser",
        lambda email, password, mail_client=None: {
            "email": email,
            "access_token": "token-1",
            "refresh_token": "refresh-1",
            "plan_type": "team",
        },
    )
    monkeypatch.setattr(manager, "save_auth_file", lambda bundle: f"/tmp/{bundle['email']}.json")
    monkeypatch.setattr(manager, "update_account", lambda email, **kwargs: updates.append((email, kwargs)))
    monkeypatch.setattr(manager, "advance_reuse_cursor", lambda email: advanced.append(email) or "next@example.com")
    monkeypatch.setattr(manager.time, "time", lambda: 1234567890)

    result = manager.reinvite_account(
        types.SimpleNamespace(browser=False),
        None,
        {"email": "tmp-user@example.com", "password": "secret"},
    )

    assert result is True
    assert updates == [
        (
            "tmp-user@example.com",
            {
                "status": accounts.STATUS_ACTIVE,
                "last_active_at": 1234567890,
                "auth_file": "/tmp/tmp-user@example.com.json",
            },
        )
    ]
    assert advanced == ["tmp-user@example.com"]


def test_reinvite_account_marks_standby_when_oauth_login_returns_non_team(monkeypatch):
    updates = []

    monkeypatch.setattr(
        manager,
        "login_codex_via_browser",
        lambda email, password, mail_client=None: {
            "email": email,
            "access_token": "token-1",
            "refresh_token": "refresh-1",
            "plan_type": "free",
        },
    )
    monkeypatch.setattr(manager, "update_account", lambda email, **kwargs: updates.append((email, kwargs)))

    result = manager.reinvite_account(
        types.SimpleNamespace(browser=False),
        None,
        {"email": "tmp-user@example.com", "password": ""},
    )

    assert result is False
    assert updates == [("tmp-user@example.com", {"status": accounts.STATUS_STANDBY})]


def test_reinvite_account_marks_standby_when_oauth_login_fails(monkeypatch):
    updates = []

    monkeypatch.setattr(manager, "login_codex_via_browser", lambda *args, **kwargs: None)
    monkeypatch.setattr(manager, "update_account", lambda email, **kwargs: updates.append((email, kwargs)))

    result = manager.reinvite_account(
        types.SimpleNamespace(browser=False),
        None,
        {"email": "tmp-user@example.com", "password": "secret"},
    )

    assert result is False
    assert updates == [("tmp-user@example.com", {"status": accounts.STATUS_STANDBY})]
