import time

from autoteam import manager
from autoteam import config


def test_pending_historical_exhausted_info_blocks_weekly_window_before_reset():
    now = int(time.time())
    quota_info = {
        "primary_pct": 0,
        "primary_resets_at": now - 300,
        "weekly_pct": 100,
        "weekly_resets_at": now + 3600,
    }

    exhausted_info = manager._pending_historical_exhausted_info(quota_info, now=now)

    assert exhausted_info is not None
    assert exhausted_info["window"] == "weekly"
    assert manager._quota_window_label(exhausted_info["window"]) == "周"


def test_pending_historical_exhausted_info_ignores_expired_weekly_snapshot():
    now = int(time.time())
    quota_info = {
        "primary_pct": 0,
        "primary_resets_at": now - 300,
        "weekly_pct": 100,
        "weekly_resets_at": now - 60,
    }

    assert manager._pending_historical_exhausted_info(quota_info, now=now) is None


def test_cmd_check_include_exhausted_updates_low_quota_snapshot(monkeypatch, tmp_path):
    auth_file = tmp_path / "codex.json"
    auth_file.write_text("{}", encoding="utf-8")
    now = 1_710_000_000
    quota_info = {
        "primary_pct": 100,
        "primary_resets_at": now + 1800,
        "weekly_pct": 25,
        "weekly_resets_at": now + 7200,
    }
    updates = []

    monkeypatch.setattr(config, "AUTO_CHECK_THRESHOLD", 10)
    monkeypatch.setattr(config, "CLOUDMAIL_DOMAIN", "")
    monkeypatch.setattr(manager.time, "time", lambda: now)
    monkeypatch.setattr(
        manager,
        "load_accounts",
        lambda: [{"email": "used@example.com", "status": manager.STATUS_EXHAUSTED, "auth_file": str(auth_file)}],
    )
    monkeypatch.setattr(manager, "_is_main_account_email", lambda email: False)
    monkeypatch.setattr(manager, "_check_and_refresh", lambda acc: ("ok", quota_info))
    monkeypatch.setattr(manager, "update_account", lambda email, **kwargs: updates.append((email, kwargs)))

    exhausted = manager.cmd_check(include_exhausted=True)

    assert [item["email"] for item in exhausted] == ["used@example.com"]
    assert updates == [
        ("used@example.com", {"last_quota": quota_info}),
        (
            "used@example.com",
            {
                "status": manager.STATUS_EXHAUSTED,
                "quota_exhausted_at": now,
                "quota_resets_at": quota_info["primary_resets_at"],
            },
        ),
    ]


def test_cmd_check_include_exhausted_restores_recovered_account(monkeypatch, tmp_path):
    auth_file = tmp_path / "codex.json"
    auth_file.write_text("{}", encoding="utf-8")
    quota_info = {
        "primary_pct": 20,
        "primary_resets_at": 1_710_003_600,
        "weekly_pct": 10,
        "weekly_resets_at": 1_710_064_800,
    }
    updates = []

    monkeypatch.setattr(config, "AUTO_CHECK_THRESHOLD", 10)
    monkeypatch.setattr(config, "CLOUDMAIL_DOMAIN", "")
    monkeypatch.setattr(
        manager,
        "load_accounts",
        lambda: [{"email": "recovered@example.com", "status": manager.STATUS_EXHAUSTED, "auth_file": str(auth_file)}],
    )
    monkeypatch.setattr(manager, "_is_main_account_email", lambda email: False)
    monkeypatch.setattr(manager, "_check_and_refresh", lambda acc: ("ok", quota_info))
    monkeypatch.setattr(manager, "update_account", lambda email, **kwargs: updates.append((email, kwargs)))

    exhausted = manager.cmd_check(include_exhausted=True)

    assert exhausted == []
    assert updates == [
        ("recovered@example.com", {"last_quota": quota_info}),
        (
            "recovered@example.com",
            {
                "status": manager.STATUS_ACTIVE,
                "quota_exhausted_at": None,
                "quota_resets_at": None,
            },
        ),
    ]
