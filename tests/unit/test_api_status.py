import json
import time

from autoteam import api


def test_get_status_normalizes_main_account_status_from_saved_auth(tmp_path, monkeypatch):
    main_email = "owner@example.com"
    auth_file = tmp_path / "codex-main.json"
    auth_file.write_text(json.dumps({"access_token": "token-main"}), encoding="utf-8")

    monkeypatch.setattr(
        "autoteam.accounts.load_accounts",
        lambda: [
            {
                "email": main_email,
                "status": "exhausted",
                "auth_file": "/app/auths/codex-main.json",
                "last_quota": {
                    "primary_pct": 8,
                    "primary_resets_at": 1710000000,
                    "weekly_pct": 1,
                    "weekly_resets_at": 1710600000,
                },
            }
        ],
    )
    monkeypatch.setattr(api, "_is_main_account_email", lambda email: email == main_email)
    monkeypatch.setattr("autoteam.codex_auth.get_saved_main_auth_file", lambda: str(auth_file))
    monkeypatch.setattr(
        "autoteam.codex_auth.check_codex_quota",
        lambda access_token: (
            "ok",
            {
                "primary_pct": 8,
                "primary_resets_at": 1710000000,
                "weekly_pct": 1,
                "weekly_resets_at": 1710600000,
            },
        ),
    )

    result = api.get_status()

    assert result["quota_cache"][main_email]["primary_pct"] == 8
    assert result["accounts"][0]["is_main_account"] is True
    assert result["accounts"][0]["status"] == "active"
    assert result["summary"] == {
        "active": 1,
        "standby": 0,
        "exhausted": 0,
        "pending": 0,
        "total": 1,
    }


def test_sanitize_account_keeps_exportable_main_account_active_without_live_quota(tmp_path, monkeypatch):
    main_email = "owner@example.com"
    auth_file = tmp_path / "codex-main.json"
    auth_file.write_text("{}", encoding="utf-8")

    monkeypatch.setattr(api, "_is_main_account_email", lambda email: email == main_email)
    monkeypatch.setattr("autoteam.codex_auth.get_saved_main_auth_file", lambda: str(auth_file))

    sanitized = api._sanitize_account(
        {"email": main_email, "status": "exhausted", "auth_file": "/app/auths/missing.json"}
    )

    assert sanitized["is_main_account"] is True
    assert sanitized["status"] == "active"


def test_sanitize_account_marks_standby_with_unreset_weekly_exhaustion_as_exhausted(monkeypatch):
    now = int(time.time())
    monkeypatch.setattr(api, "_is_main_account_email", lambda email: False)

    sanitized = api._sanitize_account(
        {
            "email": "standby@example.com",
            "status": "standby",
            "last_quota": {
                "primary_pct": 0,
                "primary_resets_at": now - 300,
                "weekly_pct": 100,
                "weekly_resets_at": now + 3600,
            },
        }
    )

    assert sanitized["is_main_account"] is False
    assert sanitized["status"] == "exhausted"


def test_sanitize_account_keeps_standby_when_exhausted_snapshot_has_expired(monkeypatch):
    now = int(time.time())
    monkeypatch.setattr(api, "_is_main_account_email", lambda email: False)

    sanitized = api._sanitize_account(
        {
            "email": "standby@example.com",
            "status": "standby",
            "last_quota": {
                "primary_pct": 0,
                "primary_resets_at": now - 300,
                "weekly_pct": 100,
                "weekly_resets_at": now - 60,
            },
        }
    )

    assert sanitized["status"] == "standby"


def test_post_setup_save_keeps_cpa_url_required_and_generates_api_key(monkeypatch):
    written = {}

    def fake_write_env(key, value):
        written[key] = value

    monkeypatch.setattr("autoteam.setup_wizard._write_env", fake_write_env)
    monkeypatch.setattr("autoteam.setup_wizard._verify_cloudmail", lambda: True)
    monkeypatch.setattr("autoteam.setup_wizard._verify_cpa", lambda: True)
    monkeypatch.setattr("secrets.token_urlsafe", lambda _n: "generated-token")
    monkeypatch.setattr("importlib.reload", lambda module: module)
    monkeypatch.setattr(api, "API_KEY", "")
    monkeypatch.delenv("CPA_URL", raising=False)
    monkeypatch.delenv("API_KEY", raising=False)

    result = api.post_setup_save(
        api.SetupConfig(
            CLOUDMAIL_BASE_URL="http://mail.example.com",
            CLOUDMAIL_EMAIL="admin@example.com",
            CLOUDMAIL_PASSWORD="secret",
            CLOUDMAIL_DOMAIN="@example.com",
            CPA_URL="",
            CPA_KEY="key-1",
            PLAYWRIGHT_PROXY_URL="",
            PLAYWRIGHT_PROXY_BYPASS="",
            API_KEY="",
        )
    )

    assert written["CPA_URL"] == "http://127.0.0.1:8317"
    assert written["API_KEY"] == "generated-token"
    assert result["api_key"] == "generated-token"
    assert api.API_KEY == "generated-token"


def test_auto_check_exhausted_update_persists_low_quota_snapshot():
    now = 1_710_000_000
    quota_info = {
        "primary_pct": 95,
        "primary_resets_at": now + 1800,
        "weekly_pct": 12,
        "weekly_resets_at": now + 7200,
    }

    fields = api._auto_check_exhausted_update("ok", quota_info, threshold=10, now=now)

    assert fields == {
        "last_quota": quota_info,
        "quota_exhausted_at": now,
        "quota_resets_at": quota_info["primary_resets_at"],
    }


def test_auto_check_exhausted_update_uses_exhausted_window_reset():
    now = 1_710_000_000
    exhausted_info = {
        "window": "weekly",
        "resets_at": now + 86400,
        "quota_info": {
            "primary_pct": 0,
            "primary_resets_at": now + 1800,
            "weekly_pct": 100,
            "weekly_resets_at": now + 86400,
        },
    }

    fields = api._auto_check_exhausted_update("exhausted", exhausted_info, threshold=10, now=now)

    assert fields == {
        "last_quota": exhausted_info["quota_info"],
        "quota_exhausted_at": now,
        "quota_resets_at": exhausted_info["resets_at"],
    }
