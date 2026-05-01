from autoteam import codex_auth


class _FakeResponse:
    status_code = 402
    text = '{"detail":{"code":"deactivated_workspace"}}'

    def json(self):
        return {"detail": {"code": "deactivated_workspace"}}


def test_check_codex_quota_returns_deactivated_workspace(monkeypatch):
    monkeypatch.setattr(codex_auth, "get_chatgpt_account_id", lambda: "acc-1")

    def fake_get(url, headers=None, timeout=None):
        assert url == "https://chatgpt.com/backend-api/wham/usage"
        assert headers["Authorization"] == "Bearer token"
        assert headers["Chatgpt-Account-Id"] == "acc-1"
        assert timeout == 30
        return _FakeResponse()

    import requests

    monkeypatch.setattr(requests, "get", fake_get)

    status, info = codex_auth.check_codex_quota("token")

    assert status == "deactivated_workspace"
    assert info == {"code": "deactivated_workspace", "status_code": 402}


def test_classify_oauth_failure_detects_account_deactivated_on_email_verification_page():
    status, detail, retryable = codex_auth._classify_oauth_failure(
        "https://auth.openai.com/email-verification",
        "验证过程中出错 (account_deactivated)。请重试。",
    )

    assert status == "account_deactivated"
    assert detail == "账号已停用 (account_deactivated)"
    assert retryable is False
