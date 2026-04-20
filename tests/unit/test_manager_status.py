import sys
import time

from autoteam import manager


def test_display_account_status_marks_standby_with_unreset_weekly_exhaustion_as_exhausted():
    now = int(time.time())
    status = manager._display_account_status(
        {
            "email": "standby@example.com",
            "status": manager.STATUS_STANDBY,
            "last_quota": {
                "primary_pct": 0,
                "primary_resets_at": now - 300,
                "weekly_pct": 100,
                "weekly_resets_at": now + 3600,
            },
        }
    )

    assert status == manager.STATUS_EXHAUSTED


def test_print_status_table_counts_derived_exhausted_status(monkeypatch):
    now = int(time.time())
    printed = []

    class FakeConsole:
        def __init__(self, *args, **kwargs):
            pass

        def print(self, value=""):
            printed.append(value)

    monkeypatch.setattr("rich.console.Console", FakeConsole)

    manager._print_status_table(
        [
            {
                "email": "standby@example.com",
                "status": manager.STATUS_STANDBY,
                "last_quota": {
                    "primary_pct": 0,
                    "primary_resets_at": now - 300,
                    "weekly_pct": 100,
                    "weekly_resets_at": now + 3600,
                },
            }
        ]
    )

    assert "✗ 用完 1" in printed[-1]
    assert "○ 待命 0" in printed[-1]


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
