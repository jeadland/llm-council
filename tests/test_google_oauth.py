import os
import tempfile
import unittest
from urllib.parse import parse_qs, urlparse
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend import auth, storage
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


def oauth_env(**extra):
    values = {
        "AUTH_REQUIRED": "true",
        "COOKIE_SECURE": "false",
        "GOOGLE_OAUTH_CLIENT_ID": "google-client-id",
        "GOOGLE_OAUTH_CLIENT_SECRET": "google-client-secret",
        "GOOGLE_OAUTH_REDIRECT_URI": "https://joshadland.com/llm-council/api/auth/oauth/google/callback",
        "OAUTH_STATE_SECRET": "test-oauth-state-secret",
    }
    values.update(extra)
    return values


def start_google_flow(client):
    response = client.get("/api/auth/oauth/google/start", follow_redirects=False)
    state = parse_qs(urlparse(response.headers["location"]).query)["state"][0]
    return response, state


class GoogleOAuthTests(TempDataMixin, unittest.TestCase):
    def test_state_rejects_tampering(self):
        with patch.dict(os.environ, oauth_env(), clear=False):
            state = auth.create_oauth_state("google")
            self.assertTrue(auth.verify_oauth_state(state, "google"))
            self.assertFalse(auth.verify_oauth_state(f"{state}tampered", "google"))
            self.assertFalse(auth.verify_oauth_state(state, "github"))

    def test_callback_creates_google_user_session(self):
        client = TestClient(app)

        async def token(code, redirect_uri):
            return {"access_token": "google-access-token"}

        async def profile(access_token):
            return {
                "sub": "google-sub-1",
                "email": "Person@Example.com",
                "email_verified": True,
                "name": "Person Example",
            }

        with patch.dict(os.environ, oauth_env(), clear=False), \
             patch("backend.main._exchange_google_code", side_effect=token), \
             patch("backend.main._fetch_google_profile", side_effect=profile):
            start_response, state = start_google_flow(client)
            callback = client.get(
                f"/api/auth/oauth/google/callback?code=test-code&state={state}",
                follow_redirects=False,
            )
            me = client.get("/api/auth/me")

        self.assertEqual(start_response.status_code, 303)
        self.assertEqual(callback.status_code, 303)
        self.assertEqual(callback.headers["location"], "/llm-council")
        payload = me.json()
        self.assertTrue(payload["authenticated"])
        self.assertEqual(payload["email"], "person@example.com")
        self.assertEqual(payload["name"], "Person Example")
        self.assertEqual(payload["role"], "user")
        self.assertEqual(payload["auth_methods"], ["google"])
        self.assertFalse(payload["password_auth_enabled"])

    def test_callback_links_existing_password_user_without_changing_hash(self):
        client = TestClient(app)

        async def token(code, redirect_uri):
            return {"access_token": "google-access-token"}

        async def profile(access_token):
            return {
                "sub": "google-sub-2",
                "email": "person@example.com",
                "email_verified": True,
                "name": "Google Name",
            }

        with patch.dict(os.environ, oauth_env(), clear=False):
            existing = auth.create_user("person@example.com", "correct horse battery", "Password Name")
            original_hash = existing["password_hash"]

        with patch.dict(os.environ, oauth_env(), clear=False), \
             patch("backend.main._exchange_google_code", side_effect=token), \
             patch("backend.main._fetch_google_profile", side_effect=profile):
            _, state = start_google_flow(client)
            callback = client.get(
                f"/api/auth/oauth/google/callback?code=test-code&state={state}",
                follow_redirects=False,
            )

        linked = storage.get_auth_user("person@example.com")
        self.assertEqual(callback.status_code, 303)
        self.assertEqual(linked["password_hash"], original_hash)
        self.assertEqual(linked["name"], "Password Name")
        self.assertEqual(linked["auth_methods"], ["google", "password"])
        self.assertEqual(linked["oauth_accounts"]["google"]["subject"], "google-sub-2")

    def test_owner_google_login_blocked_by_default(self):
        client = TestClient(app)

        async def token(code, redirect_uri):
            return {"access_token": "google-access-token"}

        async def profile(access_token):
            return {
                "sub": "owner-sub",
                "email": "owner@example.com",
                "email_verified": True,
                "name": "Owner",
            }

        with patch.dict(os.environ, oauth_env(ADMIN_EMAIL="owner@example.com"), clear=False), \
             patch("backend.main._exchange_google_code", side_effect=token), \
             patch("backend.main._fetch_google_profile", side_effect=profile):
            _, state = start_google_flow(client)
            callback = client.get(
                f"/api/auth/oauth/google/callback?code=test-code&state={state}",
                follow_redirects=False,
            )
            me = client.get("/api/auth/me")

        self.assertEqual(callback.status_code, 303)
        self.assertIn("auth_error=Owner+Google+sign-in+is+not+enabled", callback.headers["location"])
        self.assertFalse(me.json()["authenticated"])

    def test_owner_google_login_allowed_when_explicitly_enabled(self):
        client = TestClient(app)

        async def token(code, redirect_uri):
            return {"access_token": "google-access-token"}

        async def profile(access_token):
            return {
                "sub": "owner-google-sub",
                "email": "owner@example.com",
                "email_verified": True,
                "name": "Owner",
            }

        with patch.dict(
            os.environ,
            oauth_env(
                ADMIN_EMAIL="owner@example.com",
                ADMIN_INITIAL_PASSWORD="owner-password",
                ALLOW_OWNER_GOOGLE_OAUTH="true",
            ),
            clear=False,
        ):
            existing = auth.ensure_admin_user()
            original_hash = existing["password_hash"]

        with patch.dict(
            os.environ,
            oauth_env(ADMIN_EMAIL="owner@example.com", ALLOW_OWNER_GOOGLE_OAUTH="true"),
            clear=False,
        ), \
             patch("backend.main._exchange_google_code", side_effect=token), \
             patch("backend.main._fetch_google_profile", side_effect=profile):
            _, state = start_google_flow(client)
            callback = client.get(
                f"/api/auth/oauth/google/callback?code=test-code&state={state}",
                follow_redirects=False,
            )
            me = client.get("/api/auth/me")

        linked = storage.get_auth_user("owner@example.com")
        self.assertEqual(callback.status_code, 303)
        self.assertEqual(callback.headers["location"], "/llm-council")
        self.assertTrue(me.json()["authenticated"])
        self.assertEqual(me.json()["role"], "owner")
        self.assertEqual(linked["password_hash"], original_hash)
        self.assertEqual(linked["auth_methods"], ["google", "password"])
        self.assertEqual(linked["oauth_accounts"]["google"]["subject"], "owner-google-sub")

    def test_unverified_google_email_is_rejected(self):
        client = TestClient(app)

        async def token(code, redirect_uri):
            return {"access_token": "google-access-token"}

        async def profile(access_token):
            return {
                "sub": "google-sub-unverified",
                "email": "person@example.com",
                "email_verified": False,
                "name": "Person",
            }

        with patch.dict(os.environ, oauth_env(), clear=False), \
             patch("backend.main._exchange_google_code", side_effect=token), \
             patch("backend.main._fetch_google_profile", side_effect=profile):
            _, state = start_google_flow(client)
            callback = client.get(
                f"/api/auth/oauth/google/callback?code=test-code&state={state}",
                follow_redirects=False,
            )
            me = client.get("/api/auth/me")

        self.assertEqual(callback.status_code, 303)
        self.assertIn("auth_error=Google+account+email+could+not+be+verified", callback.headers["location"])
        self.assertFalse(me.json()["authenticated"])
        self.assertIsNone(storage.get_auth_user("person@example.com"))

    def test_google_user_without_openrouter_key_cannot_run(self):
        client = TestClient(app)

        async def token(code, redirect_uri):
            return {"access_token": "google-access-token"}

        async def profile(access_token):
            return {
                "sub": "google-sub-no-key",
                "email": "person@example.com",
                "email_verified": True,
                "name": "Person",
            }

        with patch.dict(os.environ, oauth_env(OPENROUTER_API_KEY="sk-or-v1-server-owner-key", ADMIN_EMAIL="owner@example.com"), clear=False), \
             patch("backend.main._exchange_google_code", side_effect=token), \
             patch("backend.main._fetch_google_profile", side_effect=profile):
            _, state = start_google_flow(client)
            callback = client.get(
                f"/api/auth/oauth/google/callback?code=test-code&state={state}",
                follow_redirects=False,
            )
            conversation = client.post("/api/conversations", json={}).json()
            run = client.post(
                f"/api/conversations/{conversation['id']}/runs",
                json={"content": "hello"},
            )

        self.assertEqual(callback.status_code, 303)
        self.assertEqual(run.status_code, 403)


if __name__ == "__main__":
    unittest.main()
