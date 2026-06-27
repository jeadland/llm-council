import os
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend import auth, storage
from backend.main import GOOGLE_ONLY_AUTH_DETAIL, app


class TempDataMixin:
    def setUp(self):
        self._cwd = os.getcwd()
        self._tempdir = tempfile.TemporaryDirectory()
        os.chdir(self._tempdir.name)
        os.makedirs("data", exist_ok=True)
        self._patches = [
            patch.object(storage, "DATA_DIR", os.path.join(self._tempdir.name, "data", "conversations")),
            patch.object(storage, "RUNS_DIR", os.path.join(self._tempdir.name, "data", "runs")),
            patch.object(storage, "SETTINGS_PATH", os.path.join(self._tempdir.name, "data", "settings.json")),
            patch.object(storage, "USER_SETTINGS_PATH", os.path.join(self._tempdir.name, "data", "user-settings.json")),
            patch.object(storage, "AUTH_USERS_PATH", os.path.join(self._tempdir.name, "data", "auth-users.json")),
            patch.object(storage, "AUTH_SESSIONS_DIR", os.path.join(self._tempdir.name, "data", "auth-sessions")),
            patch.object(storage, "INTEGRATIONS_PATH", os.path.join(self._tempdir.name, "data", "integrations.json")),
            patch.object(storage, "_using_redis", return_value=False),
        ]
        for item in self._patches:
            item.start()

    def tearDown(self):
        for item in reversed(self._patches):
            item.stop()
        os.chdir(self._cwd)
        self._tempdir.cleanup()


def sign_in_google_user(client, email="person@example.com", key=None):
    user = auth.upsert_oauth_user("google", email, f"google-sub-{email}", "Person")
    token = auth.create_session(user["email"])
    client.cookies.set(auth.SESSION_COOKIE, token)
    if key:
        storage.save_openrouter_api_key(user["email"], key)
    return user


class ByokOnboardingApiTests(TempDataMixin, unittest.TestCase):
    def test_password_signup_login_and_reset_are_disabled(self):
        client = TestClient(app)

        with patch.dict(os.environ, {"AUTH_REQUIRED": "true", "COOKIE_SECURE": "false"}, clear=False):
            signup = client.post(
                "/api/auth/signup",
                json={
                    "name": "Person",
                    "email": "person@example.com",
                    "password": "correct horse battery",
                    "openrouter_api_key": "sk-or-v1-valid-test-key",
                },
            )
            login = client.post(
                "/api/auth/login",
                json={"email": "person@example.com", "password": "correct horse battery"},
            )
            reset = client.post(
                "/api/auth/reset-password",
                json={
                    "email": "person@example.com",
                    "reset_token": "test-token",
                    "new_password": "correct horse battery",
                },
            )
            sign_in_google_user(client)
            change = client.post(
                "/api/auth/change-password",
                json={
                    "current_password": "correct horse battery",
                    "new_password": "different horse battery",
                },
            )

        self.assertEqual(signup.status_code, 403)
        self.assertEqual(login.status_code, 403)
        self.assertEqual(reset.status_code, 403)
        self.assertEqual(change.status_code, 403)
        self.assertEqual(signup.json()["detail"], GOOGLE_ONLY_AUTH_DETAIL)
        self.assertEqual(login.json()["detail"], GOOGLE_ONLY_AUTH_DETAIL)
        self.assertEqual(reset.json()["detail"], GOOGLE_ONLY_AUTH_DETAIL)
        self.assertEqual(change.json()["detail"], GOOGLE_ONLY_AUTH_DETAIL)

    def test_google_user_conversations_and_settings_are_isolated(self):
        first = TestClient(app)
        second = TestClient(app)

        with patch.dict(os.environ, {"AUTH_REQUIRED": "true", "COOKIE_SECURE": "false"}, clear=False):
            sign_in_google_user(first, email="first@example.com", key="sk-or-v1-first-valid-key")
            sign_in_google_user(second, email="second@example.com", key="sk-or-v1-second-valid-key")
            first_conv = first.post("/api/conversations", json={})
            first.patch("/api/settings", json={"theme_mode": "dark"})
            second_convs = second.get("/api/conversations")
            second_settings = second.get("/api/settings")

        self.assertEqual(first_conv.status_code, 200)
        self.assertEqual(second_convs.json(), [])
        self.assertEqual(second_settings.json()["theme_mode"], "system")

    def test_non_owner_without_key_cannot_run_even_with_server_key(self):
        client = TestClient(app)

        with patch.dict(
            os.environ,
            {
                "AUTH_REQUIRED": "true",
                "COOKIE_SECURE": "false",
                "OPENROUTER_API_KEY": "sk-or-v1-server-owner-key",
                "ADMIN_EMAIL": "owner@example.com",
            },
            clear=False,
        ):
            sign_in_google_user(client)
            conversation = client.post("/api/conversations", json={}).json()
            run = client.post(
                f"/api/conversations/{conversation['id']}/runs",
                json={"content": "hello"},
            )

        self.assertEqual(run.status_code, 403)


if __name__ == "__main__":
    unittest.main()
