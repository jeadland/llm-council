import unittest

from backend import storage


class SettingsPresetTests(unittest.TestCase):
    def test_active_curated_preset_preserves_selected_resolved_models(self):
        settings = {
            "available_models": [
                "provider/fallback",
                "provider-two/available",
            ],
            "council_models": [
                "provider/fallback",
                "provider-two/available",
            ],
            "chairman_model": "provider/fallback",
            "active_model_group_id": "preset-test",
            "custom_model_groups": [],
            "curated_model_presets": [{
                "id": "preset-test",
                "slots": [
                    ["provider/unavailable-primary", "provider/fallback"],
                    ["provider-two/available"],
                ],
                "chairman_candidates": [
                    "provider/unavailable-primary",
                    "provider/fallback",
                ],
            }],
        }

        sanitized = storage._sanitize_settings(settings)

        self.assertEqual(
            sanitized["council_models"],
            ["provider/fallback", "provider-two/available"],
        )
        self.assertEqual(sanitized["chairman_model"], "provider/fallback")
        self.assertNotIn("provider/unavailable-primary", sanitized["available_models"])
        self.assertNotIn("provider/unavailable-primary", sanitized["council_models"])

    def test_chairman_is_forced_into_selected_council(self):
        sanitized = storage._sanitize_settings({
            "available_models": ["provider/a", "provider/b", "provider/c"],
            "council_models": ["provider/a", "provider/b"],
            "chairman_model": "provider/c",
            "custom_model_groups": [],
            "curated_model_presets": [],
        })

        self.assertEqual(sanitized["chairman_model"], "provider/a")

    def test_active_custom_group_uses_corrected_custom_chairman(self):
        sanitized = storage._sanitize_settings({
            "available_models": ["provider/a", "provider/b", "provider/c"],
            "council_models": ["provider/c"],
            "chairman_model": "provider/c",
            "active_model_group_id": "custom-1",
            "custom_model_groups": [{
                "id": "custom-1",
                "name": "Custom",
                "models": ["provider/a", "provider/b"],
                "chairman_model": "provider/c",
            }],
            "curated_model_presets": [],
        })

        self.assertEqual(sanitized["council_models"], ["provider/a", "provider/b"])
        self.assertEqual(sanitized["chairman_model"], "provider/a")
        self.assertEqual(
            sanitized["custom_model_groups"][0]["chairman_model"],
            "provider/a",
        )


if __name__ == "__main__":
    unittest.main()
