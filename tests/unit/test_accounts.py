import time

from autoteam import accounts


def test_add_and_update_account_persists_data(tmp_path, monkeypatch):
    accounts_file = tmp_path / "accounts.json"
    rotation_state_file = tmp_path / "rotation_state.json"
    monkeypatch.setattr(accounts, "ACCOUNTS_FILE", accounts_file)
    monkeypatch.setattr(accounts, "ROTATION_STATE_FILE", rotation_state_file)
    monkeypatch.setattr(accounts, "get_admin_email", lambda: "")

    accounts.add_account("user@example.com", "secret", cloudmail_account_id=123)
    created = accounts.load_accounts()

    assert len(created) == 1
    assert created[0]["email"] == "user@example.com"
    assert created[0]["cloudmail_account_id"] == 123
    assert created[0]["status"] == accounts.STATUS_PENDING

    updated = accounts.update_account("user@example.com", status=accounts.STATUS_ACTIVE, auth_file="auth.json")

    assert updated["status"] == accounts.STATUS_ACTIVE
    assert updated["auth_file"] == "auth.json"
    assert accounts.load_accounts()[0]["auth_file"] == "auth.json"


def test_get_active_accounts_excludes_main_account(tmp_path, monkeypatch):
    accounts_file = tmp_path / "accounts.json"
    rotation_state_file = tmp_path / "rotation_state.json"
    monkeypatch.setattr(accounts, "ACCOUNTS_FILE", accounts_file)
    monkeypatch.setattr(accounts, "ROTATION_STATE_FILE", rotation_state_file)
    monkeypatch.setattr(accounts, "get_admin_email", lambda: "owner@example.com")

    accounts.save_accounts(
        [
            {"email": "owner@example.com", "status": accounts.STATUS_ACTIVE},
            {"email": "member@example.com", "status": accounts.STATUS_ACTIVE},
            {"email": "standby@example.com", "status": accounts.STATUS_STANDBY},
        ]
    )

    active = accounts.get_active_accounts()

    assert [item["email"] for item in active] == ["member@example.com"]


def test_get_standby_accounts_orders_recovered_first_and_skips_main_account(tmp_path, monkeypatch):
    accounts_file = tmp_path / "accounts.json"
    rotation_state_file = tmp_path / "rotation_state.json"
    monkeypatch.setattr(accounts, "ACCOUNTS_FILE", accounts_file)
    monkeypatch.setattr(accounts, "ROTATION_STATE_FILE", rotation_state_file)
    monkeypatch.setattr(accounts, "get_admin_email", lambda: "owner@example.com")

    now = time.time()
    accounts.save_accounts(
        [
            {
                "email": "owner@example.com",
                "status": accounts.STATUS_STANDBY,
                "quota_resets_at": None,
                "quota_exhausted_at": None,
            },
            {
                "email": "ready@example.com",
                "status": accounts.STATUS_STANDBY,
                "quota_resets_at": now - 60,
                "quota_exhausted_at": now - 120,
            },
            {
                "email": "later@example.com",
                "status": accounts.STATUS_STANDBY,
                "quota_resets_at": now + 600,
                "quota_exhausted_at": now - 30,
            },
            {
                "email": "always@example.com",
                "status": accounts.STATUS_STANDBY,
                "quota_resets_at": None,
                "quota_exhausted_at": None,
            },
        ]
    )

    standby = accounts.get_standby_accounts()

    assert [item["email"] for item in standby] == [
        "ready@example.com",
        "always@example.com",
        "later@example.com",
    ]
    assert standby[0]["_quota_recovered"] is True
    assert standby[1]["_quota_recovered"] is True
    assert standby[2]["_quota_recovered"] is False
    assert accounts.get_next_reusable_account()["email"] == "ready@example.com"


def test_get_standby_accounts_resumes_from_saved_cursor(tmp_path, monkeypatch):
    accounts_file = tmp_path / "accounts.json"
    rotation_state_file = tmp_path / "rotation_state.json"
    monkeypatch.setattr(accounts, "ACCOUNTS_FILE", accounts_file)
    monkeypatch.setattr(accounts, "ROTATION_STATE_FILE", rotation_state_file)
    monkeypatch.setattr(accounts, "get_admin_email", lambda: "")

    accounts.save_accounts(
        [
            {"email": "first@example.com", "status": accounts.STATUS_STANDBY, "quota_resets_at": None},
            {"email": "second@example.com", "status": accounts.STATUS_STANDBY, "quota_resets_at": None},
            {"email": "third@example.com", "status": accounts.STATUS_STANDBY, "quota_resets_at": None},
        ]
    )
    accounts.set_next_reuse_email("third@example.com")

    standby = accounts.get_standby_accounts()

    assert [item["email"] for item in standby] == [
        "third@example.com",
        "first@example.com",
        "second@example.com",
    ]


def test_advance_reuse_cursor_persists_next_account(tmp_path, monkeypatch):
    accounts_file = tmp_path / "accounts.json"
    rotation_state_file = tmp_path / "rotation_state.json"
    monkeypatch.setattr(accounts, "ACCOUNTS_FILE", accounts_file)
    monkeypatch.setattr(accounts, "ROTATION_STATE_FILE", rotation_state_file)
    monkeypatch.setattr(accounts, "get_admin_email", lambda: "")

    accounts.save_accounts(
        [
            {"email": "first@example.com", "status": accounts.STATUS_STANDBY},
            {"email": "second@example.com", "status": accounts.STATUS_STANDBY},
            {"email": "third@example.com", "status": accounts.STATUS_STANDBY},
        ]
    )

    assert accounts.advance_reuse_cursor("second@example.com") == "third@example.com"
    assert accounts.get_next_reuse_email() == "third@example.com"
    assert accounts.advance_reuse_cursor("third@example.com") == "first@example.com"
    assert accounts.get_next_reuse_email() == "first@example.com"
