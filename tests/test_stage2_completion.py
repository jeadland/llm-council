import unittest
from unittest.mock import patch

from backend import council


def ranking_response(labels=None):
    labels = labels or ["Response A", "Response B"]
    ranking = "\n".join(f"{index}. {label}" for index, label in enumerate(labels, start=1))
    return {
        "content": f"FINAL RANKING:\n{ranking}\n\nLooks good.",
        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
    }


class Stage2CompletionTests(unittest.IsolatedAsyncioTestCase):
    async def test_stage2_retries_missing_reviewer_until_all_rankings_complete(self):
        attempts = {"model-a": 0, "model-b": 0}

        async def fake_query_model_detailed(model, messages, timeout, max_tokens=None):
            attempts[model] += 1
            if model == "model-b" and attempts[model] == 1:
                return {
                    "response": None,
                    "diagnostic": {
                        "requested_model": model,
                        "provider_source": "openrouter_direct",
                        "error_type": "timeout",
                        "message": "Timed out.",
                        "timeout_seconds": timeout,
                    },
                }
            return {"response": ranking_response(), "diagnostic": None}

        progress = []

        async def progress_callback(results, label_to_model, execution):
            progress.append((len(results), execution["completed_rankings_count"], list(execution["pending_models"])))

        with patch.object(council, "query_model_detailed", side_effect=fake_query_model_detailed):
            results, label_to_model, execution = await council.stage2_collect_rankings(
                "Question?",
                [{"model": "answer-a", "response": "A"}, {"model": "answer-b", "response": "B"}],
                council_models=["model-a", "model-b"],
                progress_callback=progress_callback,
            )

        self.assertEqual(attempts, {"model-a": 1, "model-b": 2})
        self.assertEqual(len(results), 2)
        self.assertEqual(label_to_model["Response A"], "answer-a")
        self.assertFalse(execution["is_partial"])
        self.assertEqual(execution["completed_rankings_count"], 2)
        self.assertEqual(execution["pending_models"], [])
        self.assertEqual(execution["attempt_diagnostics"]["model-b"][0]["error_type"], "timeout")
        self.assertTrue(progress)

    async def test_stage2_incomplete_error_names_missing_models_and_stops_synthesis(self):
        async def fake_query_model_detailed(model, messages, timeout, max_tokens=None):
            if model == "model-a":
                return {"response": ranking_response(), "diagnostic": None}
            return {
                "response": None,
                "diagnostic": {
                    "requested_model": model,
                    "provider_source": "openrouter_direct",
                    "error_type": "http_status",
                    "status_code": 429,
                    "message": "Rate limit exceeded.",
                    "timeout_seconds": timeout,
                },
            }

        with patch.object(council, "query_model_detailed", side_effect=fake_query_model_detailed):
            results, _, execution = await council.stage2_collect_rankings(
                "Question?",
                [{"model": "answer-a", "response": "A"}, {"model": "answer-b", "response": "B"}],
                council_models=["model-a", "model-b"],
            )

        self.assertEqual(len(results), 1)
        self.assertTrue(execution["is_partial"])
        self.assertEqual(execution["completed_rankings_count"], 1)
        self.assertEqual(execution["pending_models"], ["model-b"])
        self.assertEqual(execution["attempts_by_model"]["model-b"], council.STAGE2_MAX_ATTEMPTS)
        self.assertEqual(len(execution["attempt_diagnostics"]["model-b"]), council.STAGE2_MAX_ATTEMPTS)
        self.assertEqual(execution["latest_diagnostics"]["model-b"]["status_code"], 429)

        message = council.format_stage2_incomplete_error(execution)
        self.assertIn("Stage 2 peer review incomplete", message)
        self.assertIn("Expected 2 peer rankings; completed 1", message)
        self.assertIn("model-b", message)
        self.assertIn("http_status 429", message)
        self.assertIn("Stage 3 synthesis did not run", message)

    async def test_malformed_peer_rankings_are_marked_invalid_and_excluded_from_aggregate(self):
        async def fake_query_model_detailed(model, messages, timeout, max_tokens=None):
            if model == "model-a":
                return {"response": ranking_response(), "diagnostic": None}
            return {
                "response": {
                    "content": "FINAL RANKING:\n1. Response A\n2. Response A",
                    "finish_reason": "stop",
                    "native_finish_reason": "completed",
                    "provider_source": "openrouter_direct",
                },
                "diagnostic": None,
            }

        with patch.object(council, "query_model_detailed", side_effect=fake_query_model_detailed):
            results, label_to_model, execution = await council.stage2_collect_rankings(
                "Question?",
                [{"model": "answer-a", "response": "A"}, {"model": "answer-b", "response": "B"}],
                council_models=["model-a", "model-b"],
            )

        invalid = next(result for result in results if result["model"] == "model-b")
        self.assertFalse(invalid["ranking_valid"])
        self.assertIn("duplicate labels", "; ".join(invalid["ranking_issues"]))
        self.assertEqual(execution["completed_rankings_count"], 1)
        self.assertEqual(execution["invalid_models"], ["model-b"])

        aggregate = council.calculate_aggregate_rankings(results, label_to_model)
        self.assertEqual([item["model"] for item in aggregate], ["answer-a", "answer-b"])
        self.assertEqual([item["rankings_count"] for item in aggregate], [1, 1])


if __name__ == "__main__":
    unittest.main()
