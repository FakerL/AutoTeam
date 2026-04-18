import sys

from autoteam import manager


def test_cmd_status_cached_skips_team_sync_and_live_quota(monkeypatch):
    calls = []
    accounts = [
        {
            "email": "active@example.com",
            "status": manager.STATUS_ACTIVE,
            "auth_file": "/tmp/active.json",
            "last_quota": {"primary_pct": 0, "weekly_pct": 20},
        },
        {
            "email": "standby@example.com",
            "status": manager.STATUS_STANDBY,
            "auth_file": None,
        },
    ]

    monkeypatch.setattr(manager, "sync_account_states", lambda: calls.append("sync"))
    monkeypatch.setattr(manager, "load_accounts", lambda: accounts)
    monkeypatch.setattr(
        manager,
        "check_codex_quota",
        lambda token: (_ for _ in ()).throw(AssertionError("live quota lookup should not run in cached mode")),
    )
    monkeypatch.setattr(
        manager,
        "_print_status_table",
        lambda accs, quota_cache=None: calls.append(("print", accs, quota_cache)),
    )

    manager.cmd_status(cached=True)

    assert calls == [("print", accounts, {})]


def test_main_status_cached_skips_setup_check(monkeypatch):
    calls = []

    monkeypatch.setattr(sys, "argv", ["autoteam", "status", "--cached"])
    monkeypatch.setattr(
        manager,
        "cmd_status",
        lambda cached=False: calls.append(("status", cached)),
    )

    import autoteam.setup_wizard

    monkeypatch.setattr(
        autoteam.setup_wizard,
        "check_and_setup",
        lambda interactive=True: (_ for _ in ()).throw(AssertionError("setup check should be skipped")),
    )

    import autoteam.auth_storage

    monkeypatch.setattr(autoteam.auth_storage, "ensure_auth_file_permissions", lambda: None)

    manager.main()

    assert calls == [("status", True)]
