from autoteam import accounts, cpa_sync


def test_sync_active_account_to_cpa_uploads_requested_active_account(tmp_path, monkeypatch):
    accounts_file = tmp_path / "accounts.json"
    auth_file = tmp_path / "codex-user-team-1234.json"
    auth_file.write_text("{}", encoding="utf-8")

    monkeypatch.setattr(accounts, "ACCOUNTS_FILE", accounts_file)
    monkeypatch.setattr(accounts, "get_admin_email", lambda: "")
    monkeypatch.setattr(cpa_sync, "_cleanup_local_duplicates", lambda accounts_list: (0, False))

    uploaded = []
    monkeypatch.setattr(cpa_sync, "upload_to_cpa", lambda path: uploaded.append(str(path)) or True)

    accounts.save_accounts(
        [
            {
                "email": "user@example.com",
                "status": accounts.STATUS_ACTIVE,
                "auth_file": str(auth_file),
            }
        ]
    )

    assert cpa_sync.sync_active_account_to_cpa("user@example.com") is True
    assert uploaded == [str(auth_file)]
