import hashlib
import hmac
import json
import os
import tempfile
import time
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend import auth, storage
from backend.billing import db, openrouter_management, service, stripe_service
from backend.main import app


class BillingTempMixin:
    def setUp(self):
        self._cwd = os.getcwd()
        self._tempdir = tempfile.TemporaryDirectory()
        os.chdir(self._tempdir.name)
        os.makedirs("data", exist_ok=True)
        self.billing_db = os.path.join(self._tempdir.name, "billing.sqlite3")
        self._patches = [
            patch.dict(
                os.environ,
                {
                    "BILLING_DATABASE_URL": f"sqlite:///{self.billing_db}",
                    "KEY_ENCRYPTION_SECRET": "test-encryption-secret",
                    "COOKIE_SECURE": "false",
                    "AUTH_REQUIRED": "true",
                },
                clear=False,
            ),
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


class BillingLedgerTests(BillingTempMixin, unittest.TestCase):
    def test_ledger_reservation_and_finalize_prevent_negative_available_balance(self):
        db.add_ledger_entry("person@example.com", "purchase", 5.00)
        reservation = db.create_reservation("person@example.com", "run-1", 0.90)

        self.assertEqual(round(db.ledger_balance("person@example.com"), 2), 5.00)
        self.assertEqual(round(db.reserved_balance("person@example.com"), 2), 0.90)
        self.assertEqual(round(db.available_balance("person@example.com"), 2), 4.10)

        with self.assertRaises(ValueError):
            db.create_reservation("person@example.com", "run-2", 10.00)

        db.finalize_reservation(reservation["reservation_id"], 0.61)
        self.assertEqual(round(db.ledger_balance("person@example.com"), 2), 4.39)
        self.assertEqual(round(db.reserved_balance("person@example.com"), 2), 0.00)
        self.assertEqual(round(db.available_balance("person@example.com"), 2), 4.39)

    def test_release_reservation_restores_available_balance(self):
        db.add_ledger_entry("person@example.com", "purchase", 5.00)
        reservation = db.create_reservation("person@example.com", "run-1", 1.00)
        db.release_reservation(reservation["reservation_id"])

        self.assertEqual(round(db.ledger_balance("person@example.com"), 2), 5.00)
        self.assertEqual(round(db.available_balance("person@example.com"), 2), 5.00)


class BillingStripeTests(BillingTempMixin, unittest.TestCase):
    def _signed_payload(self, payload):
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        timestamp = str(int(time.time()))
        signature = hmac.new(
            b"whsec_test",
            timestamp.encode("utf-8") + b"." + body,
            hashlib.sha256,
        ).hexdigest()
        return body, f"t={timestamp},v1={signature}"

    def test_checkout_webhook_is_verified_and_idempotent(self):
        with patch.dict(os.environ, {"STRIPE_WEBHOOK_SECRET": "whsec_test"}, clear=False):
            event = {
                "id": "evt_test_1",
                "type": "checkout.session.completed",
                "data": {
                    "object": {
                        "id": "cs_test_1",
                        "payment_status": "paid",
                        "payment_intent": "pi_test_1",
                        "amount_total": 1000,
                        "metadata": {
                            "user_id": "person@example.com",
                            "credit_package": "standard_10",
                            "app_credit_amount_usd": "10.00",
                        },
                    }
                },
            }
            body, signature = self._signed_payload(event)
            verified = stripe_service.verify_webhook(body, signature)
            first = stripe_service.fulfill_checkout_session(verified)
            second = stripe_service.fulfill_checkout_session(verified)

        self.assertEqual(first["status"], "processed")
        self.assertEqual(second["status"], "duplicate")
        self.assertEqual(round(db.ledger_balance("person@example.com"), 2), 10.00)
        self.assertEqual(db.get_or_create_profile("person@example.com")["billing_mode"], "managed")

    def test_checkout_webhook_rejects_mismatched_package_amount(self):
        event = {
            "id": "evt_mismatch",
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "cs_test_mismatch",
                    "payment_status": "paid",
                    "payment_intent": "pi_test_mismatch",
                    "amount_total": 100,
                    "metadata": {
                        "user_id": "person@example.com",
                        "credit_package": "standard_10",
                    },
                }
            },
        }

        with self.assertRaises(ValueError):
            stripe_service.fulfill_checkout_session(event)

        self.assertEqual(round(db.ledger_balance("person@example.com"), 2), 0.00)

    def test_refund_and_dispute_webhooks_adjust_balance_once_and_cap_at_payment(self):
        checkout_event = {
            "id": "evt_checkout",
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "cs_test_1",
                    "payment_status": "paid",
                    "payment_intent": "pi_test_1",
                    "amount_total": 1000,
                    "metadata": {
                        "user_id": "person@example.com",
                        "credit_package": "standard_10",
                    },
                }
            },
        }
        refund_event = {
            "id": "evt_refund",
            "type": "refund.created",
            "data": {"object": {"id": "re_test_1", "payment_intent": "pi_test_1", "amount": 400}},
        }
        cumulative_refund_event = {
            "id": "evt_charge_refunded",
            "type": "charge.refunded",
            "data": {"object": {"id": "ch_test_1", "payment_intent": "pi_test_1", "amount_refunded": 600}},
        }
        dispute_event = {
            "id": "evt_dispute",
            "type": "charge.dispute.created",
            "data": {"object": {"id": "dp_test_1", "payment_intent": "pi_test_1", "amount": 1000}},
        }

        stripe_service.fulfill_checkout_session(checkout_event)
        refund = stripe_service.fulfill_checkout_session(refund_event)
        duplicate_refund = stripe_service.fulfill_checkout_session(refund_event)
        cumulative_refund = stripe_service.fulfill_checkout_session(cumulative_refund_event)
        dispute = stripe_service.fulfill_checkout_session(dispute_event)

        self.assertEqual(refund["adjusted_usd"], 4.00)
        self.assertEqual(duplicate_refund["status"], "duplicate")
        self.assertEqual(cumulative_refund["adjusted_usd"], 2.00)
        self.assertEqual(dispute["adjusted_usd"], 4.00)
        self.assertEqual(round(db.ledger_balance("person@example.com"), 2), 0.00)


class BillingEncryptionTests(BillingTempMixin, unittest.TestCase):
    def test_openrouter_byok_key_is_encrypted_at_rest_with_legacy_read_compatibility(self):
        raw_key = "sk-or-v1-valid-test-secret"
        storage.save_openrouter_api_key("person@example.com", raw_key)
        status = storage.get_openrouter_api_key_status("person@example.com")

        self.assertTrue(status["configured"])
        self.assertTrue(status["encrypted"])
        self.assertEqual(storage.get_openrouter_api_key("person@example.com"), raw_key)

        with open(storage.INTEGRATIONS_PATH, "r") as f:
            stored = f.read()
        self.assertNotIn(raw_key, stored)

        # Existing plaintext records are still readable for a safe rolling deploy.
        legacy = {
            "openrouter": {
                "legacy@example.com": {
                    "api_key": "sk-or-v1-legacy-test-secret",
                    "updated_at": "2026-06-27T00:00:00",
                }
            }
        }
        with open(storage.INTEGRATIONS_PATH, "w") as f:
            json.dump(legacy, f)

        self.assertEqual(
            storage.get_openrouter_api_key("legacy@example.com"),
            "sk-or-v1-legacy-test-secret",
        )
        self.assertTrue(storage.get_openrouter_api_key_status("legacy@example.com")["legacy_plaintext"])


class ManagedOpenRouterKeyTests(BillingTempMixin, unittest.IsolatedAsyncioTestCase):
    def test_openrouter_management_unwrap_preserves_child_key_and_hash(self):
        payload = {
            "data": {"hash": "or-key-hash", "limit": 5.0, "usage": 0},
            "key": "sk-or-v1-managed-child-key",
        }
        normalized = openrouter_management._unwrap_data(payload)

        self.assertEqual(normalized["key"], "sk-or-v1-managed-child-key")
        self.assertEqual(normalized["hash"], "or-key-hash")

    async def test_prepare_managed_run_creates_child_key_and_reserves_max_charge(self):
        db.add_ledger_entry("person@example.com", "purchase", 5.00)
        db.save_coverage_snapshot({
            "total_credits_usd": 100,
            "total_usage_usd": 0,
            "available_credits_usd": 100,
            "managed_raw_liability_usd": 3.70,
            "operating_buffer_usd": 25,
            "required_floor_usd": 28.70,
            "coverage_ratio": 27,
            "status": "healthy",
        })

        original_create = service.openrouter_management.create_child_key
        original_update = service.openrouter_management.update_child_key
        original_configured = service.openrouter_management.configured

        async def fake_create(user_id, raw_allowance_usd):
            return {
                "key": "sk-or-v1-managed-child-key",
                "hash": "or-key-hash",
                "name": f"llm-council-managed-user-{user_id}",
                "limit": raw_allowance_usd,
                "usage": 0,
            }

        async def fake_update(key_hash, *, limit_usd, disabled=False, name=None):
            return {"hash": key_hash, "limit": limit_usd, "usage": 0, "disabled": disabled}

        service.openrouter_management.create_child_key = fake_create
        service.openrouter_management.update_child_key = fake_update
        service.openrouter_management.configured = lambda: True

        try:
            with patch.dict(os.environ, {"MANAGED_MODE_ENABLED": "true"}, clear=False):
                profile = {
                    "slug": "balanced",
                    "enabled": True,
                    "models": ["openai/gpt-test"],
                    "chairman_model": "openai/gpt-test",
                    "max_user_visible_charge_usd": 0.90,
                }
                estimate = {
                    "profile": profile,
                    "estimated_app_cost_low_usd": 0.45,
                    "estimated_app_cost_high_usd": 0.70,
                    "max_app_charge_usd": 0.90,
                }
                prepared = await service.prepare_managed_run(
                    "person@example.com",
                    "run-1",
                    profile,
                    estimate,
                )
                receipt = await service.finalize_managed_run(
                    "person@example.com",
                    "run-1",
                    prepared,
                    {"total_usd": 0.10, "status": "complete"},
                )
        finally:
            service.openrouter_management.create_child_key = original_create
            service.openrouter_management.update_child_key = original_update
            service.openrouter_management.configured = original_configured

        self.assertEqual(prepared["openrouter_api_key"], "sk-or-v1-managed-child-key")
        self.assertEqual(round(db.reserved_balance("person@example.com"), 2), 0.00)
        self.assertEqual(round(receipt["actual_app_cost_usd"], 2), 0.14)
        self.assertEqual(round(db.ledger_balance("person@example.com"), 2), 4.87)

    async def test_prepare_managed_run_releases_reservation_when_key_provisioning_fails(self):
        db.add_ledger_entry("person@example.com", "purchase", 5.00)
        db.save_coverage_snapshot({
            "total_credits_usd": 100,
            "total_usage_usd": 0,
            "available_credits_usd": 100,
            "managed_raw_liability_usd": 3.70,
            "operating_buffer_usd": 25,
            "required_floor_usd": 28.70,
            "coverage_ratio": 27,
            "status": "healthy",
        })

        async def fail_create(_user_id, _raw_allowance_usd):
            raise RuntimeError("OpenRouter provisioning failed")

        profile = {
            "slug": "balanced",
            "enabled": True,
            "models": ["openai/gpt-test"],
            "chairman_model": "openai/gpt-test",
            "max_user_visible_charge_usd": 0.90,
        }
        estimate = {
            "profile": profile,
            "estimated_app_cost_low_usd": 0.45,
            "estimated_app_cost_high_usd": 0.70,
            "max_app_charge_usd": 0.90,
        }

        with (
            patch.dict(os.environ, {"MANAGED_MODE_ENABLED": "true"}, clear=False),
            patch.object(service.openrouter_management, "configured", return_value=True),
            patch.object(service.openrouter_management, "create_child_key", fail_create),
        ):
            with self.assertRaises(RuntimeError):
                await service.prepare_managed_run(
                    "person@example.com",
                    "run-1",
                    profile,
                    estimate,
                )

        self.assertEqual(round(db.reserved_balance("person@example.com"), 2), 0.00)
        self.assertEqual(round(db.available_balance("person@example.com"), 2), 5.00)

    async def test_coverage_pause_blocks_managed_reservations(self):
        db.add_ledger_entry("person@example.com", "purchase", 5.00)
        db.save_coverage_snapshot({"status": "healthy", "managed_raw_liability_usd": 1.00})
        service.pause_managed_mode("owner@example.com")
        profile = {
            "slug": "balanced",
            "enabled": True,
            "models": ["openai/gpt-test"],
            "chairman_model": "openai/gpt-test",
            "max_user_visible_charge_usd": 0.90,
        }
        estimate = {"profile": profile, "max_app_charge_usd": 0.90}

        with patch.dict(os.environ, {"MANAGED_MODE_ENABLED": "true"}, clear=False):
            with self.assertRaises(ValueError):
                await service.prepare_managed_run("person@example.com", "run-1", profile, estimate)
        self.assertEqual(round(db.reserved_balance("person@example.com"), 2), 0.00)


class BillingApiTests(BillingTempMixin, unittest.TestCase):
    def _sign_in(self, client, email="person@example.com"):
        user = auth.upsert_oauth_user("google", email, f"google-sub-{email}", "Person")
        token = auth.create_session(user["email"])
        client.cookies.set(auth.SESSION_COOKIE, token)
        return user

    def test_billing_status_and_mode_are_user_scoped(self):
        first = TestClient(app)
        second = TestClient(app)
        self._sign_in(first, "first@example.com")
        self._sign_in(second, "second@example.com")
        db.add_ledger_entry("first@example.com", "purchase", 5.00)

        mode_response = first.post("/api/billing/mode", json={"billing_mode": "managed"})
        first_status = first.get("/api/billing/status")
        second_status = second.get("/api/billing/status")

        self.assertEqual(mode_response.status_code, 200)
        self.assertEqual(first_status.status_code, 200)
        self.assertEqual(second_status.status_code, 200)
        self.assertEqual(first_status.json()["billing_mode"], "managed")
        self.assertEqual(first_status.json()["available_balance_usd"], 5.00)
        self.assertEqual(second_status.json()["billing_mode"], "byok")
        self.assertEqual(second_status.json()["available_balance_usd"], 0.00)

    def test_managed_run_fails_closed_when_managed_mode_disabled(self):
        client = TestClient(app)
        self._sign_in(client, "person@example.com")
        db.add_ledger_entry("person@example.com", "purchase", 5.00)
        conversation = client.post("/api/conversations", json={}).json()

        async def fake_catalog():
            return []

        with patch("backend.main.fetch_openrouter_model_catalog", fake_catalog):
            response = client.post(
                f"/api/conversations/{conversation['id']}/runs",
                json={
                    "content": "hello",
                    "billing_mode": "managed",
                    "profile_slug": "balanced",
                },
            )

        self.assertEqual(response.status_code, 402)
        self.assertIn("not enabled", response.json()["detail"])
        stored = client.get(f"/api/conversations/{conversation['id']}").json()
        self.assertEqual(stored["messages"], [])

    def test_checkout_redirect_uses_llm_council_subpath(self):
        client = TestClient(app)
        self._sign_in(client, "person@example.com")
        captured = {}

        async def fake_checkout_session(**kwargs):
            captured.update(kwargs)
            return {"checkout_session_id": "cs_test", "url": "https://checkout.stripe.test/session"}

        with (
            patch.dict(os.environ, {"MANAGED_MODE_ENABLED": "true"}, clear=False),
            patch("backend.main.stripe_service.create_checkout_session", fake_checkout_session),
        ):
            response = client.post(
                "/llm-council/api/billing/checkout",
                json={"package_id": "standard_10"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(captured["success_url"], "http://testserver/llm-council?billing=success")
        self.assertEqual(captured["cancel_url"], "http://testserver/llm-council?billing=cancelled")

    def test_checkout_fails_closed_when_managed_mode_disabled(self):
        client = TestClient(app)
        self._sign_in(client, "person@example.com")

        response = client.post(
            "/api/billing/checkout",
            json={"package_id": "standard_10"},
        )

        self.assertEqual(response.status_code, 403)
        self.assertIn("not enabled", response.json()["detail"])


if __name__ == "__main__":
    unittest.main()
