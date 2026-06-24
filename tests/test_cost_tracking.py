import unittest

from backend import openrouter
from backend.council import build_council_cost_summary


class CostTrackingTests(unittest.TestCase):
    def test_normalizes_completion_usage(self):
        usage = openrouter.normalize_usage({
            "prompt_tokens": 10,
            "completion_tokens": 4,
            "total_tokens": 14,
            "prompt_tokens_details": {"cached_tokens": 2},
            "completion_tokens_details": {"reasoning_tokens": 1},
            "cost": 0.00014,
        })

        self.assertEqual(usage["prompt_tokens"], 10)
        self.assertEqual(usage["completion_tokens"], 4)
        self.assertEqual(usage["total_tokens"], 14)
        self.assertEqual(usage["cached_tokens"], 2)
        self.assertEqual(usage["reasoning_tokens"], 1)
        self.assertEqual(usage["cost_usd"], 0.00014)

    def test_normalizes_generation_metadata(self):
        metadata = openrouter.normalize_generation_metadata({
            "data": {
                "id": "gen-test",
                "model": "openai/gpt-test",
                "provider_name": "OpenAI",
                "tokens_prompt": 50,
                "tokens_completion": 25,
                "native_tokens_reasoning": 5,
                "native_tokens_cached": 3,
                "total_cost": 0.0015,
            }
        })

        self.assertEqual(metadata["generation_id"], "gen-test")
        self.assertEqual(metadata["resolved_model"], "openai/gpt-test")
        self.assertEqual(metadata["provider_name"], "OpenAI")
        self.assertEqual(metadata["usage"]["prompt_tokens"], 50)
        self.assertEqual(metadata["usage"]["completion_tokens"], 25)
        self.assertEqual(metadata["usage"]["total_tokens"], 75)
        self.assertEqual(metadata["usage"]["reasoning_tokens"], 5)
        self.assertEqual(metadata["usage"]["cached_tokens"], 3)
        self.assertEqual(metadata["usage"]["cost_usd"], 0.0015)

    def test_cost_summary_counts_priced_unpriced_and_failed_calls(self):
        summary = openrouter.build_cost_summary([
            {
                "stage": "stage1",
                "call_type": "individual_response",
                "requested_model": "model-a",
                "cost_usd": 0.001,
                "total_tokens": 100,
                "status": "priced",
            },
            {
                "stage": "stage2",
                "call_type": "peer_ranking",
                "requested_model": "model-b",
                "generation_id": "gen-pending",
                "status": "pending",
            },
            {
                "stage": "stage3",
                "call_type": "synthesis",
                "requested_model": "model-c",
                "status": "failed",
            },
        ])

        self.assertEqual(summary["status"], "partial")
        self.assertEqual(summary["total_usd"], 0.001)
        self.assertEqual(summary["total_tokens"], 100)
        self.assertEqual(summary["priced_calls_count"], 1)
        self.assertEqual(summary["unpriced_calls_count"], 1)
        self.assertEqual(summary["failed_calls_count"], 1)
        self.assertEqual(summary["calls"][1]["status"], "unpriced")

    def test_council_summary_adds_failed_calls_for_missing_stage_results(self):
        stage1 = [{
            "model": "model-a",
            "response": "Answer",
            "cost_call": openrouter.build_cost_call(
                "stage1",
                "individual_response",
                "model-a",
                {
                    "usage": {"prompt_tokens": 1, "completion_tokens": 2, "cost": 0.01},
                    "provider_source": "openrouter_direct",
                },
            ),
        }]
        summary = build_council_cost_summary(
            stage1,
            [],
            {"cost_calls": []},
            ["model-a", "model-b"],
        )

        self.assertEqual(summary["priced_calls_count"], 1)
        self.assertEqual(summary["failed_calls_count"], 3)
        self.assertEqual(summary["unpriced_calls_count"], 0)
        self.assertEqual(summary["status"], "complete")


class ReconciliationTests(unittest.IsolatedAsyncioTestCase):
    async def test_reconcile_cost_calls_uses_generation_metadata(self):
        original = openrouter.fetch_generation_metadata

        async def fake_fetch(generation_id, api_key, timeout=10.0):
            return {
                "generation_id": generation_id,
                "resolved_model": "openai/gpt-test",
                "provider_name": "OpenAI",
                "finish_reason": "stop",
                "usage": {
                    "cost_usd": 0.002,
                    "prompt_tokens": 20,
                    "completion_tokens": 5,
                    "total_tokens": 25,
                    "reasoning_tokens": 0,
                    "cached_tokens": 0,
                },
            }

        openrouter.fetch_generation_metadata = fake_fetch
        try:
            calls = await openrouter.reconcile_cost_calls(
                [{
                    "stage": "stage1",
                    "call_type": "individual_response",
                    "requested_model": "openai/gpt-test",
                    "generation_id": "gen-test",
                    "status": "pending",
                    "cost_usd": None,
                }],
                api_key="test-key",
                retries=0,
            )
        finally:
            openrouter.fetch_generation_metadata = original

        self.assertEqual(calls[0]["status"], "priced")
        self.assertEqual(calls[0]["cost_usd"], 0.002)
        self.assertEqual(calls[0]["total_tokens"], 25)

    async def test_reconcile_leaves_unavailable_generation_unpriced(self):
        original = openrouter.fetch_generation_metadata

        async def fake_fetch(generation_id, api_key, timeout=10.0):
            return None

        openrouter.fetch_generation_metadata = fake_fetch
        try:
            calls = await openrouter.reconcile_cost_calls(
                [{
                    "stage": "stage1",
                    "call_type": "individual_response",
                    "requested_model": "openai/gpt-test",
                    "generation_id": "gen-missing",
                    "status": "pending",
                    "cost_usd": None,
                }],
                api_key="test-key",
                retries=0,
            )
        finally:
            openrouter.fetch_generation_metadata = original

        summary = openrouter.build_cost_summary(calls)
        self.assertEqual(summary["status"], "unavailable")
        self.assertEqual(summary["unpriced_calls_count"], 1)
        self.assertIsNone(summary["total_usd"])


if __name__ == "__main__":
    unittest.main()
