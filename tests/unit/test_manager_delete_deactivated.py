from autoteam import accounts, manager


class _FakeMailClient:
    provider_name = "cloudmail"

    def login(self):
        return None


def test_cmd_delete_deactivated_dry_run_uses_local_marker(tmp_path, monkeypatch):
    accounts_file = tmp_path / "accounts.json"
    monkeypatch.setattr(accounts, "ACCOUNTS_FILE", accounts_file)
    monkeypatch.setattr(manager, "get_admin_email", lambda: "owner@example.com")
    monkeypatch.setattr(manager, "get_mail_domain", lambda: "")

    accounts.save_accounts(
        [
            {"email": "owner@example.com", "status": accounts.STATUS_ACTIVE},
            {
                "email": "deactivated@example.com",
                "status": accounts.STATUS_AUTH_PENDING,
                "auth_last_error": "deactivated_workspace",
            },
            {"email": "missing-auth@example.com", "status": accounts.STATUS_ACTIVE, "auth_file": None},
        ]
    )

    deleted = []
    monkeypatch.setattr(manager, "delete_managed_account", lambda *args, **kwargs: deleted.append((args, kwargs)))

    result = manager.cmd_delete_deactivated(dry_run=True)

    assert result == {
        "total_accounts": 2,
        "probed_accounts": 0,
        "matched_accounts": 1,
        "deleted_accounts": 0,
        "failed_accounts": 0,
        "skipped_accounts": 1,
        "dry_run": True,
    }
    assert deleted == []
    assert len(accounts.load_accounts()) == 3


def test_cmd_delete_deactivated_probes_login_flow_and_deletes_matches(tmp_path, monkeypatch):
    accounts_file = tmp_path / "accounts.json"

    monkeypatch.setattr(accounts, "ACCOUNTS_FILE", accounts_file)
    monkeypatch.setattr(manager, "get_admin_email", lambda: "owner@example.com")
    monkeypatch.setattr(manager, "get_mail_domain", lambda: "")
    accounts.save_accounts(
        [
            {"email": "owner@example.com", "status": accounts.STATUS_ACTIVE},
            {
                "email": "deactivated@example.com",
                "status": accounts.STATUS_ACTIVE,
                "mail_provider": "cloudmail",
                "mail_account_id": 1,
                "password": "",
            },
            {
                "email": "ok@example.com",
                "status": accounts.STATUS_ACTIVE,
                "mail_provider": "cloudmail",
                "mail_account_id": 2,
                "password": "",
            },
        ]
    )

    def fake_login(email, password, **kwargs):
        if email == "deactivated@example.com":
            return {
                "ok": False,
                "bundle": None,
                "error_type": "account_deactivated",
                "error_detail": "账号已停用 (account_deactivated)",
                "retryable": False,
            }
        return {"ok": True, "bundle": {"email": email, "plan_type": "team"}, "error_type": None}

    def fake_delete(email, **kwargs):
        remaining = [acc for acc in accounts.load_accounts() if acc["email"] != email]
        accounts.save_accounts(remaining)
        return {"local_record": True}

    monkeypatch.setattr(manager, "_get_account_mail_client", lambda _acc: _FakeMailClient())
    monkeypatch.setattr(manager, "_login_codex_with_result", fake_login)
    monkeypatch.setattr(manager, "delete_managed_account", fake_delete)
    monkeypatch.setattr(manager, "sync_to_cpa", lambda: None)

    result = manager.cmd_delete_deactivated(remove_remote=False, remove_cloudmail=False)

    assert result["matched_accounts"] == 1
    assert result["deleted_accounts"] == 1
    assert result["failed_accounts"] == 0
    assert result["probed_accounts"] == 2
    assert [acc["email"] for acc in accounts.load_accounts()] == ["owner@example.com", "ok@example.com"]
