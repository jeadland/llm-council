import os
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend import model_curation, storage
from backend.main import app


def _catalog():
    base_pricing = {"prompt_per_million": 1.0, "completion_per_million": 1.0}
    return [
        {
            "id": "provider/curator-next",
            "name": "Next Curator",
            "provider": "Provider",
            "price_tier": "Low",
            "context_length": 100000,
            "recommendation_tags": ["Recommended"],
            "pricing": base_pricing,
        },
        {
            "id": "provider/model-a",
            "name": "Model A",
            "provider": "Provider",
            "price_tier": "Low",
            "context_length": 100000,
            "recommendation_tags": ["Recommended"],
            "pricing": base_pricing,
        },
        {
            "id": "provider-two/model-b",
            "name": "Model B",
            "provider": "Provider Two",
            "price_tier": "Low",
            "context_length": 100000,
            "recommendation_tags": ["Recommended"],
            "pricing": base_pricing,
        },
    ]


class TempDataMixin:
    def _start_temp_data(self):
        self._cwd = os.getcwd()
        self._tempdir = tempfile.TemporaryDirectory()
        os.chdir(self._tempdir.name)
        os.makedirs("data", exist_ok=True)
        self._patches = [
            patch.object(storage, "DATA_DIR", os.path.join(self._tempdir.name, "data", "conversations")),
            patch.object(storage, "SETTINGS_PATH", os.path.join(self._tempdir.name, "data", "settings.json")),
            patch.object(storage, "MODEL_CURATION_STATE_PATH", os.path.join(self._tempdir.name, "data", "model-curation-state.json")),
            patch.object(storage, "_using_redis", return_value=False),
        ]
        for item in self._patches:
            item.start()

    def _stop_temp_data(self):
        for item in reversed(self._patches):
            item.stop()
        os.chdir(self._cwd)
        self._tempdir.cleanup()

    def setUp(self):
        self._start_temp_data()

    def tearDown(self):
        self._stop_temp_data()


class ModelCurationStateTests(TempDataMixin, unittest.TestCase):
    def test_fresh_install_uses_openrouter_auto(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("MODEL_CURATION_MODEL", None)
            state = storage.get_model_curation_state()

        self.assertEqual(state["current_curation_model"], "openrouter/auto")

    def test_env_override_bootstraps_when_no_state_exists(self):
        with patch.dict(os.environ, {"MODEL_CURATION_MODEL": "provider/custom-curator"}):
            state = storage.get_model_curation_state()

        self.assertEqual(state["current_curation_model"], "provider/custom-curator")

    def test_stored_promoted_curator_wins_over_env_default(self):
        storage.save_model_curation_state({"current_curation_model": "provider/promoted"})

        with patch.dict(os.environ, {"MODEL_CURATION_MODEL": "provider/env-default"}):
            state = storage.get_model_curation_state()

        self.assertEqual(state["current_curation_model"], "provider/promoted")

    def test_invalid_stored_curator_falls_back(self):
        storage.save_model_curation_state({"current_curation_model": "not-routable"})

        state = storage.get_model_curation_state()

        self.assertEqual(state["current_curation_model"], "openrouter/auto")


class ModelCurationPromotionTests(TempDataMixin, unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    async def asyncSetUp(self):
        self._start_temp_data()

    async def asyncTearDown(self):
        self._stop_temp_data()

    async def test_valid_recommended_curator_is_promoted_without_applying_presets(self):
        proposed = [{
            "id": "proposed",
            "name": "Proposed",
            "badge": "Test",
            "cost_tier": "Low",
            "speed_tier": "Fast",
            "best_for": "Tests",
            "chairman_candidates": ["provider/model-a"],
            "slots": [["provider/model-a"], ["provider-two/model-b"]],
        }]

        async def fake_catalog(force_refresh=False):
            return _catalog()

        async def fake_query_model(model, messages, timeout=120.0):
            return {
                "content": (
                    '{"notes":"ok","risks":[],"recommended_next_curation_model":"provider/curator-next",'
                    f'"proposed_preset_definitions":{model_curation.json.dumps(proposed)}}}'
                )
            }

        with patch.object(model_curation, "fetch_openrouter_model_catalog", side_effect=fake_catalog), \
             patch.object(model_curation, "query_model", side_effect=fake_query_model):
            draft = await model_curation.create_model_curation_draft(trigger="cron", owner_email="owner@example.com")

        state = storage.get_model_curation_state()
        settings = storage.get_settings()
        self.assertEqual(draft["next_curator_status"], "promoted")
        self.assertEqual(state["current_curation_model"], "provider/curator-next")
        self.assertEqual(settings["curated_model_presets"], [])

    async def test_invalid_recommended_curator_is_not_promoted(self):
        async def fake_catalog(force_refresh=False):
            return _catalog()

        async def fake_query_model(model, messages, timeout=120.0):
            return {"content": '{"recommended_next_curation_model":"missing/model"}'}

        with patch.object(model_curation, "fetch_openrouter_model_catalog", side_effect=fake_catalog), \
             patch.object(model_curation, "query_model", side_effect=fake_query_model):
            draft = await model_curation.create_model_curation_draft(trigger="manual", owner_email="owner@example.com")

        state = storage.get_model_curation_state()
        self.assertEqual(draft["next_curator_status"], "not_promoted")
        self.assertEqual(state["current_curation_model"], "openrouter/auto")


class ModelCurationApiTests(TempDataMixin, unittest.TestCase):
    def test_cron_rejects_invalid_secret(self):
        client = TestClient(app)

        with patch.dict(os.environ, {"CRON_SECRET": "expected"}):
            response = client.get("/api/cron/model-curation", headers={"authorization": "Bearer wrong"})

        self.assertEqual(response.status_code, 401)

    def test_approve_applies_proposed_presets(self):
        draft = storage.save_model_curation_draft({
            "id": "draft-1",
            "proposed_preset_definitions": [{
                "id": "approved",
                "slots": [["provider/model-a"]],
            }],
        })
        client = TestClient(app)

        response = client.post(f"/api/model-curation/{draft['id']}/approve")

        self.assertEqual(response.status_code, 200)
        settings = response.json()["settings"]
        self.assertEqual(settings["last_approved_curation_id"], "draft-1")
        self.assertEqual(settings["curated_model_presets"][0]["id"], "approved")

    def test_non_owner_cannot_run_or_approve_model_curation(self):
        user = {
            "email": "user@example.com",
            "role": "user",
            "password_hash": "unused",
            "created_at": "2026-06-24T00:00:00",
        }
        draft = storage.save_model_curation_draft({
            "id": "draft-1",
            "proposed_preset_definitions": [{"id": "approved"}],
        })
        client = TestClient(app)
        token = "test-session-token"
        token_hash = "test-session-token-hash"

        with patch.dict(os.environ, {"AUTH_REQUIRED": "true", "ADMIN_EMAIL": "owner@example.com"}, clear=False), \
             patch("backend.auth.get_user_from_request", return_value=user), \
             patch("backend.auth.hash_token", return_value=token_hash):
            client.cookies.set("llm_council_session", token)
            run_response = client.post("/api/model-curation/run")
            approve_response = client.post(f"/api/model-curation/{draft['id']}/approve")

        self.assertEqual(run_response.status_code, 403)
        self.assertEqual(approve_response.status_code, 403)


if __name__ == "__main__":
    unittest.main()
