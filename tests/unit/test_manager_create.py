from autoteam import manager


class _FakeMailClient:
    def __init__(self, temp_emails):
        self._temp_emails = iter(temp_emails)
        self.deleted = []

    def create_temp_email(self):
        return next(self._temp_emails)

    def delete_account(self, account_id):
        self.deleted.append(account_id)


def test_create_account_direct_retries_with_fresh_email(monkeypatch):
    mail_client = _FakeMailClient(
        [
            ("acc-1", "first@example.com"),
            ("acc-2", "second@example.com"),
        ]
    )
    register_calls = []
    sleep_calls = []
    added = []
    updated = []

    def fake_register(_mail_client, email, password, cloudmail_account_id=None):
        register_calls.append((email, password, cloudmail_account_id))
        return email == "second@example.com"

    monkeypatch.setattr(manager, "_register_direct_once", fake_register)
    monkeypatch.setattr(manager, "_is_email_in_team", lambda email: False)
    monkeypatch.setattr(manager.time, "sleep", lambda seconds: sleep_calls.append(seconds))
    monkeypatch.setattr(
        manager,
        "add_account",
        lambda email, password, cloudmail_account_id=None: added.append((email, password, cloudmail_account_id)),
    )
    monkeypatch.setattr(
        manager,
        "login_codex_via_browser",
        lambda email, password, mail_client=None: {"email": email, "plan_type": "team"},
    )
    monkeypatch.setattr(manager, "save_auth_file", lambda bundle: f"/tmp/{bundle['email']}.json")
    monkeypatch.setattr(manager, "update_account", lambda email, **kwargs: updated.append((email, kwargs)))

    result = manager.create_account_direct(mail_client)

    assert result == "second@example.com"
    assert [email for email, _password, _account_id in register_calls] == ["first@example.com", "second@example.com"]
    assert mail_client.deleted == ["acc-1"]
    assert sleep_calls == [60]
    assert added == [("second@example.com", register_calls[1][1], "acc-2")]
    assert len(updated) == 1
    assert updated[0][0] == "second@example.com"
    assert updated[0][1]["status"] == manager.STATUS_ACTIVE
    assert updated[0][1]["auth_file"] == "/tmp/second@example.com.json"
    assert updated[0][1]["last_active_at"] > 0


def test_create_account_direct_deletes_every_failed_temp_email(monkeypatch):
    mail_client = _FakeMailClient(
        [
            ("acc-1", "first@example.com"),
            ("acc-2", "second@example.com"),
            ("acc-3", "third@example.com"),
        ]
    )
    sleep_calls = []

    monkeypatch.setattr(manager, "_register_direct_once", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(manager, "_is_email_in_team", lambda email: False)
    monkeypatch.setattr(manager.time, "sleep", lambda seconds: sleep_calls.append(seconds))
    monkeypatch.setattr(manager, "add_account", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError()))
    monkeypatch.setattr(
        manager,
        "login_codex_via_browser",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError()),
    )
    monkeypatch.setattr(manager, "update_account", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError()))

    result = manager.create_account_direct(mail_client)

    assert result is None
    assert mail_client.deleted == ["acc-1", "acc-2", "acc-3"]
    assert sleep_calls == [60, 60]
