import os
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend import storage
from backend.main import app


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


async def _valid_key(api_key: str):
    return {"label": f"{api_key[:8]}...test", "limit": 25}


class ByokOnboardingApiTests(TempDataMixin, unittest.TestCase):
    def _signup(self, client, email="person@example.com", key="sk-or-v1-valid-test-key"):
        with patch("backend.main._validate_openrouter_api_key", side_effect=_valid_key):
            return client.post(
                "/api/auth/signup",
                json={
                    "name": "Person",
                    "email": email,
                    "password": "correct horse battery",
                    "openrouter_api_key": key,
                },
            )

    def test_signup_creates_session_and_saves_masked_openrouter_status(self):
        client = TestClient(app)

        with patch.dict(os.environ, {"AUTH_REQUIRED": "true", "COOKIE_SECURE": "false"}, clear=False):
            response = self._signup(client)
            me = client.get("/api/auth/me")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["email"], "person@example.com")
        self.assertEqual(payload["name"], "Person")
        self.assertEqual(payload["role"], "user")
        self.assertTrue(payload["openrouter"]["configured"])
        self.assertNotIn("valid-test-key", payload["openrouter"]["masked_key"])
        self.assertEqual(me.json()["email"], "person@example.com")

    def test_signup_rejects_duplicate_email(self):
        client = TestClient(app)

        with patch.dict(os.environ, {"AUTH_REQUIRED": "true", "COOKIE_SECURE": "false"}, clear=False):
            first = self._signup(client, email="person@example.com")
            second = self._signup(client, email="PERSON@example.com")

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 409)

    def test_signup_rejects_invalid_openrouter_key(self):
        client = TestClient(app)

        async def invalid_key(api_key: str):
            from fastapi import HTTPException
            raise HTTPException(status_code=400, detail="OpenRouter API key was rejected")

        with patch.dict(os.environ, {"AUTH_REQUIRED": "true", "COOKIE_SECURE": "false"}, clear=False), \
             patch("backend.main._validate_openrouter_api_key", side_effect=invalid_key):
            response = client.post(
                "/api/auth/signup",
                json={
                    "email": "person@example.com",
                    "password": "correct horse battery",
                    "openrouter_api_key": "sk-or-v1-invalid-test-key",
                },
            )

        self.assertEqual(response.status_code, 400)

    def test_user_conversations_and_settings_are_isolated(self):
        first = TestClient(app)
        second = TestClient(app)

        with patch.dict(os.environ, {"AUTH_REQUIRED": "true", "COOKIE_SECURE": "false"}, clear=False):
            first_signup = self._signup(first, email="first@example.com", key="sk-or-v1-first-valid-key")
            second_signup = self._signup(second, email="second@example.com", key="sk-or-v1-second-valid-key")
            first_conv = first.post("/api/conversations", json={})
            first.patch("/api/settings", json={"theme_mode": "dark"})
            second_convs = second.get("/api/conversations")
            second_settings = second.get("/api/settings")

        self.assertEqual(first_signup.status_code, 200)
        self.assertEqual(second_signup.status_code, 200)
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
            response = self._signup(client)
            storage.delete_openrouter_api_key("person@example.com")
            conversation = client.post("/api/conversations", json={}).json()
            run = client.post(
                f"/api/conversations/{conversation['id']}/runs",
                json={"content": "hello"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(run.status_code, 403)


if __name__ == "__main__":
    unittest.main()
