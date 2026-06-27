import os
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend import agent_auth, storage
from backend.main import app


AGENT_TOKEN = "test-agent-token"
AGENT_HASH = agent_auth.hash_agent_token(AGENT_TOKEN)


def catalog_for_agent_presets():
    pricing = {"prompt_per_million": 1.0, "completion_per_million": 1.0}
    return [
        {
            "id": "provider/frontier-a",
            "name": "Frontier A",
            "provider": "Provider",
            "price_tier": "Low",
            "context_length": 100000,
            "recommendation_tags": ["Recommended"],
            "pricing": pricing,
        },
        {
            "id": "provider-two/frontier-b",
            "name": "Frontier B",
            "provider": "Provider Two",
            "price_tier": "Low",
            "context_length": 100000,
            "recommendation_tags": ["Recommended"],
            "pricing": pricing,
        },
        {
            "id": "provider/daily-a",
            "name": "Daily A",
            "provider": "Provider",
            "price_tier": "Low",
            "context_length": 100000,
            "recommendation_tags": ["Recommended"],
            "pricing": pricing,
        },
    ]


def approved_presets():
    return [
        {
            "id": "ultra-premium-frontier",
            "name": "Frontier",
            "cost_tier": "High",
            "speed_tier": "Slow",
            "best_for": "Hard research",
            "chairman_candidates": ["provider/frontier-a"],
            "slots": [["provider/frontier-a"], ["provider-two/frontier-b"]],
        },
        {
            "id": "premium-balanced",
            "name": "Balanced",
            "cost_tier": "Medium",
            "speed_tier": "Medium",
            "best_for": "Standard research",
            "chairman_candidates": ["provider/frontier-a"],
            "slots": [["provider/frontier-a"], ["provider-two/frontier-b"]],
        },
        {
            "id": "efficient-daily",
            "name": "Daily",
            "cost_tier": "Low",
            "speed_tier": "Fast",
            "best_for": "Quick research",
            "chairman_candidates": ["provider/daily-a"],
            "slots": [["provider/daily-a"]],
        },
    ]


class AgentResearchTests(unittest.TestCase):
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
            patch.object(storage, "AGENT_APPROVALS_PATH", os.path.join(self._tempdir.name, "data", "agent-approvals.json")),
            patch.object(storage, "_using_redis", return_value=False),
            patch("backend.main.fetch_openrouter_model_catalog", return_value=catalog_for_agent_presets()),
        ]
        for item in self._patches:
            item.start()
        storage.save_settings({"curated_model_presets": approved_presets()}, "owner@example.com")
        self.client = TestClient(app)

    def tearDown(self):
        for item in reversed(self._patches):
            item.stop()
        os.chdir(self._cwd)
        self._tempdir.cleanup()

    def auth_headers(self):
        return {"authorization": f"Bearer {AGENT_TOKEN}"}

    def agent_env(self, **overrides):
        env = {
            "LLM_COUNCIL_AGENT_TOKEN_HASH": AGENT_HASH,
            "LLM_COUNCIL_AGENT_OWNER_EMAIL": "owner@example.com",
            "LLM_COUNCIL_AGENT_MAX_USD": "3.00",
            "AUTH_REQUIRED": "false",
        }
        env.update(overrides)
        return env

    def test_agent_endpoints_disabled_without_token_hash(self):
        with patch.dict(os.environ, {"LLM_COUNCIL_AGENT_TOKEN_HASH": ""}, clear=False):
            response = self.client.post(
                "/api/agent/research/prepare",
                headers=self.auth_headers(),
                json={"question": "What is hard?"},
            )

        self.assertEqual(response.status_code, 503)

    def test_agent_auth_rejects_wrong_token_and_accepts_valid_token(self):
        with patch.dict(os.environ, self.agent_env(), clear=False):
            rejected = self.client.post(
                "/api/agent/research/prepare",
                headers={"authorization": "Bearer wrong"},
                json={"question": "What is hard?", "research_depth": "quick"},
            )
            accepted = self.client.post(
                "/api/agent/research/prepare",
                headers=self.auth_headers(),
                json={"question": "What is hard?", "research_depth": "quick"},
            )

        self.assertEqual(rejected.status_code, 401)
        self.assertEqual(accepted.status_code, 200)

    def test_prepare_selects_expected_approved_preset(self):
        with patch.dict(os.environ, self.agent_env(), clear=False):
            response = self.client.post(
                "/api/agent/research/prepare",
                headers=self.auth_headers(),
                json={"question": "Need deep analysis", "research_depth": "hard"},
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["preset_id"], "ultra-premium-frontier")
        self.assertEqual(payload["chairman_model"], "provider/frontier-a")
        self.assertEqual(payload["council_models"], ["provider/frontier-a", "provider-two/frontier-b"])

    def test_prepare_rejects_cost_cap_violation(self):
        with patch.dict(os.environ, self.agent_env(), clear=False):
            response = self.client.post(
                "/api/agent/research/prepare",
                headers=self.auth_headers(),
                json={"question": "Need deep analysis", "research_depth": "hard", "max_cost_usd": 0.0001},
            )

        self.assertEqual(response.status_code, 400)
        self.assertIn("exceeds allowed cap", response.json()["detail"])

    def test_run_rejects_payload_hash_mismatch(self):
        with patch.dict(os.environ, self.agent_env(), clear=False):
            prepared = self.client.post(
                "/api/agent/research/prepare",
                headers=self.auth_headers(),
                json={"question": "Need deep analysis", "research_depth": "quick"},
            ).json()
            approval = storage.get_agent_research_approval(prepared["approval_id"])
            storage.update_agent_research_approval(prepared["approval_id"], {
                **approval,
                "question": "Changed after approval",
            })
            response = self.client.post(
                "/api/agent/research/run",
                headers=self.auth_headers(),
                json={"approval_id": prepared["approval_id"], "approved_cost_cap_usd": prepared["estimated_cost_usd"]},
            )

        self.assertEqual(response.status_code, 400)
        self.assertIn("hash mismatch", response.json()["detail"])

    def test_run_returns_disclosure_and_cost_fields(self):
        async def fake_execute(run_id):
            storage.update_run(run_id, {
                "status": "complete",
                "stage3": {"status": "complete", "data": {"response": "Council answer"}},
                "cost_summary": {
                    "status": "complete",
                    "total_usd": 0.0123,
                    "calls": [],
                    "unpriced_calls_count": 0,
                    "failed_calls_count": 0,
                },
            })

        with patch.dict(os.environ, self.agent_env(), clear=False), \
             patch("backend.main._execute_run", side_effect=fake_execute):
            prepared = self.client.post(
                "/api/agent/research/prepare",
                headers=self.auth_headers(),
                json={"question": "Need deep analysis", "research_depth": "quick"},
            ).json()
            response = self.client.post(
                "/api/agent/research/run",
                headers=self.auth_headers(),
                json={"approval_id": prepared["approval_id"], "approved_cost_cap_usd": prepared["estimated_cost_usd"]},
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["used_llm_council_mcp"])
        self.assertEqual(payload["final_answer"], "Council answer")
        self.assertEqual(payload["actual_cost_usd"], 0.0123)
        self.assertIsNone(payload["cost_warning"])
        self.assertIn("I used LLM Council via MCP", payload["required_disclosure_text"])


if __name__ == "__main__":
    unittest.main()
