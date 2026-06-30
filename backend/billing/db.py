"""Billing persistence.

Hosted deployments should set DATABASE_URL to Supabase/Postgres. Local tests
and local-only development use SQLite so the billing code can be verified
without mutating a real hosted database.
"""

from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional
from urllib.parse import urlparse

import psycopg
from psycopg.rows import dict_row

from .profiles import service_multiplier


SQLITE_DEFAULT_PATH = "data/billing.sqlite3"


def utc_now() -> str:
    return datetime.utcnow().isoformat()


def database_url() -> str:
    return (
        os.getenv("BILLING_DATABASE_URL")
        or os.getenv("DATABASE_URL")
        or f"sqlite:///{os.path.abspath(SQLITE_DEFAULT_PATH)}"
    )


def _is_sqlite(url: str) -> bool:
    return url.startswith("sqlite://")


def _sqlite_path(url: str) -> str:
    parsed = urlparse(url)
    if parsed.path in {"", "/:memory:"} or url == "sqlite:///:memory:":
        return ":memory:"
    return parsed.path


def _normalize_sql_for_sqlite(sql: str) -> str:
    return sql.replace("%s", "?")


@contextmanager
def connect() -> Iterator[Any]:
    url = database_url()
    if _is_sqlite(url):
        path = _sqlite_path(url)
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
        return

    with psycopg.connect(url, row_factory=dict_row) as conn:
        yield conn


def _execute(conn: Any, sql: str, params: tuple = ()):
    if isinstance(conn, sqlite3.Connection):
        return conn.execute(_normalize_sql_for_sqlite(sql), params)
    return conn.execute(sql, params)


def _db_bool(conn: Any, value: bool) -> Any:
    if isinstance(conn, sqlite3.Connection):
        return 1 if value else 0
    return bool(value)


def _fetchone(conn: Any, sql: str, params: tuple = ()) -> Optional[Dict[str, Any]]:
    row = _execute(conn, sql, params).fetchone()
    if row is None:
        return None
    return dict(row)


def _fetchall(conn: Any, sql: str, params: tuple = ()) -> List[Dict[str, Any]]:
    return [dict(row) for row in _execute(conn, sql, params).fetchall()]


def _json(value: Any) -> str:
    return json.dumps(value if value is not None else {}, sort_keys=True)


def _parse_json(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    if not value:
        return {}
    try:
        return json.loads(value)
    except Exception:
        return {}


def ensure_schema() -> None:
    url = database_url()
    with connect() as conn:
        if isinstance(conn, sqlite3.Connection):
            _ensure_sqlite_schema(conn)
        else:
            _ensure_postgres_schema(conn)


def _ensure_sqlite_schema(conn: sqlite3.Connection) -> None:
    statements = [
        """
        create table if not exists billing_profiles (
            user_id text primary key,
            billing_mode text not null default 'byok',
            managed_enabled integer not null default 0,
            byok_enabled integer not null default 1,
            service_multiplier real not null default 1.35,
            stripe_customer_id text,
            disabled_at text,
            created_at text not null,
            updated_at text not null
        )
        """,
        """
        create table if not exists app_credit_ledger (
            id integer primary key autoincrement,
            user_id text not null,
            entry_type text not null,
            amount_usd real not null,
            currency text not null default 'usd',
            council_run_id text,
            reservation_id text,
            stripe_checkout_session_id text,
            stripe_payment_intent_id text,
            stripe_event_id text,
            metadata_json text not null default '{}',
            created_at text not null
        )
        """,
        """
        create table if not exists billing_reservations (
            reservation_id text primary key,
            user_id text not null,
            council_run_id text not null,
            amount_usd real not null,
            status text not null,
            metadata_json text not null default '{}',
            created_at text not null,
            released_at text,
            finalized_at text
        )
        """,
        """
        create table if not exists stripe_events (
            stripe_event_id text primary key,
            event_type text not null,
            payload_json text not null,
            processed_status text not null,
            error_message text,
            created_at text not null,
            processed_at text
        )
        """,
        """
        create table if not exists stripe_payments (
            checkout_session_id text primary key,
            user_id text not null,
            stripe_customer_id text,
            payment_intent_id text,
            gross_amount_usd real not null,
            app_credit_amount_usd real not null,
            stripe_fee_usd real,
            stripe_net_usd real,
            status text not null,
            created_at text not null,
            updated_at text not null
        )
        """,
        """
        create table if not exists managed_openrouter_keys (
            user_id text primary key,
            openrouter_key_hash text,
            encrypted_openrouter_key text,
            openrouter_name text,
            limit_total_usd real not null default 0,
            limit_remaining_usd real,
            usage_total_usd real not null default 0,
            usage_daily_usd real,
            usage_weekly_usd real,
            usage_monthly_usd real,
            limit_reset text,
            disabled integer not null default 0,
            last_synced_at text,
            created_at text not null,
            updated_at text not null
        )
        """,
        """
        create table if not exists managed_run_receipts (
            council_run_id text primary key,
            user_id text not null,
            billing_mode text not null,
            profile_slug text,
            estimated_app_cost_low_usd real,
            estimated_app_cost_high_usd real,
            max_app_charge_usd real,
            reserved_amount_usd real,
            actual_raw_cost_usd real,
            actual_app_cost_usd real,
            service_multiplier real,
            remaining_balance_usd real,
            metadata_json text not null default '{}',
            created_at text not null
        )
        """,
        """
        create table if not exists openrouter_account_snapshots (
            id integer primary key autoincrement,
            total_credits_usd real,
            total_usage_usd real,
            available_credits_usd real,
            managed_raw_liability_usd real,
            operating_buffer_usd real,
            required_floor_usd real,
            coverage_ratio real,
            status text not null,
            created_at text not null
        )
        """,
        """
        create table if not exists billing_config (
            key text primary key,
            value text not null,
            updated_at text not null
        )
        """,
        """
        create table if not exists admin_audit_events (
            id integer primary key autoincrement,
            admin_user_id text not null,
            action text not null,
            target_user_id text,
            target_object_type text,
            target_object_id text,
            before_json text,
            after_json text,
            reason text,
            created_at text not null
        )
        """,
    ]
    for statement in statements:
        conn.execute(statement)
    indexes = [
        "create index if not exists app_credit_ledger_user_idx on app_credit_ledger (user_id)",
        "create index if not exists app_credit_ledger_run_idx on app_credit_ledger (council_run_id)",
        "create unique index if not exists app_credit_ledger_checkout_purchase_uidx on app_credit_ledger (stripe_checkout_session_id) where entry_type = 'purchase' and stripe_checkout_session_id is not null",
        "create index if not exists billing_reservations_user_status_idx on billing_reservations (user_id, status)",
        "create index if not exists stripe_events_status_idx on stripe_events (processed_status)",
        "create index if not exists stripe_payments_payment_intent_idx on stripe_payments (payment_intent_id)",
        "create unique index if not exists stripe_payments_payment_intent_uidx on stripe_payments (payment_intent_id) where payment_intent_id is not null",
        "create index if not exists managed_run_receipts_user_idx on managed_run_receipts (user_id)",
        "create index if not exists openrouter_snapshots_created_idx on openrouter_account_snapshots (created_at)",
    ]
    for statement in indexes:
        conn.execute(statement)


def _ensure_postgres_schema(conn: Any) -> None:
    with open(Path(__file__).resolve().parents[2] / "migrations" / "20260627_managed_billing.sql", "r") as f:
        conn.execute(f.read())


def get_or_create_profile(user_id: str) -> Dict[str, Any]:
    ensure_schema()
    now = utc_now()
    multiplier = service_multiplier()
    with connect() as conn:
        existing = _fetchone(conn, "select * from billing_profiles where user_id = %s", (user_id,))
        if existing:
            return existing
        _execute(
            conn,
            """
            insert into billing_profiles
                (user_id, billing_mode, managed_enabled, byok_enabled, service_multiplier, created_at, updated_at)
            values (%s, 'byok', %s, %s, %s, %s, %s)
            """,
            (user_id, _db_bool(conn, False), _db_bool(conn, True), multiplier, now, now),
        )
        return _fetchone(conn, "select * from billing_profiles where user_id = %s", (user_id,)) or {}


def set_billing_mode(user_id: str, mode: str) -> Dict[str, Any]:
    if mode not in {"byok", "managed"}:
        raise ValueError("Unsupported billing mode")
    ensure_schema()
    get_or_create_profile(user_id)
    now = utc_now()
    with connect() as conn:
        _execute(
            conn,
            """
            update billing_profiles
            set billing_mode = %s,
                managed_enabled = case when %s = 'managed' then %s else managed_enabled end,
                updated_at = %s
            where user_id = %s
            """,
            (mode, mode, _db_bool(conn, True), now, user_id),
        )
    return get_or_create_profile(user_id)


def ledger_balance(user_id: str) -> float:
    ensure_schema()
    with connect() as conn:
        row = _fetchone(
            conn,
            "select coalesce(sum(amount_usd), 0) as balance from app_credit_ledger where user_id = %s",
            (user_id,),
        )
    return round(float(row.get("balance") or 0), 4) if row else 0.0


def reserved_balance(user_id: str) -> float:
    ensure_schema()
    with connect() as conn:
        row = _fetchone(
            conn,
            "select coalesce(sum(amount_usd), 0) as reserved from billing_reservations where user_id = %s and status = 'active'",
            (user_id,),
        )
    return round(float(row.get("reserved") or 0), 4) if row else 0.0


def available_balance(user_id: str) -> float:
    return round(ledger_balance(user_id) - reserved_balance(user_id), 4)


def add_ledger_entry(
    user_id: str,
    entry_type: str,
    amount_usd: float,
    *,
    council_run_id: Optional[str] = None,
    reservation_id: Optional[str] = None,
    stripe_checkout_session_id: Optional[str] = None,
    stripe_payment_intent_id: Optional[str] = None,
    stripe_event_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    ensure_schema()
    now = utc_now()
    with connect() as conn:
        _execute(
            conn,
            """
            insert into app_credit_ledger
                (user_id, entry_type, amount_usd, currency, council_run_id, reservation_id,
                 stripe_checkout_session_id, stripe_payment_intent_id, stripe_event_id, metadata_json, created_at)
            values (%s, %s, %s, 'usd', %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                user_id,
                entry_type,
                round(float(amount_usd), 4),
                council_run_id,
                reservation_id,
                stripe_checkout_session_id,
                stripe_payment_intent_id,
                stripe_event_id,
                _json(metadata),
                now,
            ),
        )
    return {"user_id": user_id, "entry_type": entry_type, "amount_usd": round(float(amount_usd), 4)}


def list_ledger(user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
    ensure_schema()
    with connect() as conn:
        rows = _fetchall(
            conn,
            """
            select * from app_credit_ledger
            where user_id = %s
            order by created_at desc, id desc
            limit %s
            """,
            (user_id, limit),
        )
    for row in rows:
        row["metadata"] = _parse_json(row.pop("metadata_json", None))
    return rows


def create_reservation(user_id: str, council_run_id: str, amount_usd: float, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    ensure_schema()
    get_or_create_profile(user_id)
    reservation_id = f"res_{council_run_id}"
    now = utc_now()
    with connect() as conn:
        if not isinstance(conn, sqlite3.Connection):
            _execute(conn, "select user_id from billing_profiles where user_id = %s for update", (user_id,))
        existing = _fetchone(conn, "select * from billing_reservations where reservation_id = %s", (reservation_id,))
        if existing:
            return existing
        row = _fetchone(
            conn,
            "select coalesce(sum(amount_usd), 0) as balance from app_credit_ledger where user_id = %s",
            (user_id,),
        )
        held = _fetchone(
            conn,
            "select coalesce(sum(amount_usd), 0) as reserved from billing_reservations where user_id = %s and status = 'active'",
            (user_id,),
        )
        available = float(row.get("balance") or 0) - float(held.get("reserved") or 0)
        if available + 0.000001 < amount_usd:
            raise ValueError("Insufficient LLM Council Balance for this profile")
        _execute(
            conn,
            """
            insert into billing_reservations
                (reservation_id, user_id, council_run_id, amount_usd, status, metadata_json, created_at)
            values (%s, %s, %s, %s, 'active', %s, %s)
            """,
            (reservation_id, user_id, council_run_id, round(float(amount_usd), 4), _json(metadata), now),
        )
        return _fetchone(conn, "select * from billing_reservations where reservation_id = %s", (reservation_id,)) or {}


def release_reservation(reservation_id: str) -> Optional[Dict[str, Any]]:
    ensure_schema()
    now = utc_now()
    with connect() as conn:
        reservation = _fetchone(conn, "select * from billing_reservations where reservation_id = %s", (reservation_id,))
        if not reservation:
            return None
        if reservation.get("status") == "active":
            _execute(
                conn,
                "update billing_reservations set status = 'released', released_at = %s where reservation_id = %s",
                (now, reservation_id),
            )
        return _fetchone(conn, "select * from billing_reservations where reservation_id = %s", (reservation_id,))


def finalize_reservation(reservation_id: str, actual_app_cost_usd: float, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    ensure_schema()
    now = utc_now()
    with connect() as conn:
        reservation = _fetchone(conn, "select * from billing_reservations where reservation_id = %s", (reservation_id,))
        if not reservation:
            raise ValueError("Billing reservation not found")
        if reservation.get("status") == "finalized":
            return reservation
        if reservation.get("status") != "active":
            raise ValueError("Billing reservation is not active")
        amount = min(float(actual_app_cost_usd), float(reservation["amount_usd"]))
        _execute(
            conn,
            """
            insert into app_credit_ledger
                (user_id, entry_type, amount_usd, currency, council_run_id, reservation_id, metadata_json, created_at)
            values (%s, 'usage', %s, 'usd', %s, %s, %s, %s)
            """,
            (
                reservation["user_id"],
                -round(amount, 4),
                reservation["council_run_id"],
                reservation_id,
                _json(metadata),
                now,
            ),
        )
        _execute(
            conn,
            "update billing_reservations set status = 'finalized', finalized_at = %s where reservation_id = %s",
            (now, reservation_id),
        )
        return _fetchone(conn, "select * from billing_reservations where reservation_id = %s", (reservation_id,)) or {}


def insert_stripe_event(stripe_event_id: str, event_type: str, payload: Dict[str, Any]) -> str:
    ensure_schema()
    now = utc_now()
    with connect() as conn:
        existing = _fetchone(
            conn,
            "select stripe_event_id, processed_status from stripe_events where stripe_event_id = %s",
            (stripe_event_id,),
        )
        if existing:
            status = existing.get("processed_status")
            if status in {"processed", "ignored"}:
                return "duplicate"
            _execute(
                conn,
                """
                update stripe_events
                set event_type = %s, payload_json = %s, processed_status = 'pending',
                    error_message = null, processed_at = null
                where stripe_event_id = %s
                """,
                (event_type, _json(payload), stripe_event_id),
            )
            return "retry"
        _execute(
            conn,
            """
            insert into stripe_events
                (stripe_event_id, event_type, payload_json, processed_status, created_at)
            values (%s, %s, %s, 'pending', %s)
            """,
            (stripe_event_id, event_type, _json(payload), now),
        )
        return "inserted"


def mark_stripe_event(stripe_event_id: str, status: str, error_message: Optional[str] = None) -> None:
    ensure_schema()
    now = utc_now()
    with connect() as conn:
        _execute(
            conn,
            """
            update stripe_events
            set processed_status = %s, error_message = %s, processed_at = %s
            where stripe_event_id = %s
            """,
            (status, error_message, now, stripe_event_id),
        )


def upsert_stripe_payment(
    *,
    user_id: str,
    checkout_session_id: str,
    payment_intent_id: Optional[str],
    app_credit_amount_usd: float,
    gross_amount_usd: float,
    stripe_customer_id: Optional[str],
    status: str,
) -> None:
    ensure_schema()
    now = utc_now()
    with connect() as conn:
        existing = _fetchone(conn, "select checkout_session_id from stripe_payments where checkout_session_id = %s", (checkout_session_id,))
        if existing:
            _execute(
                conn,
                """
                update stripe_payments
                set payment_intent_id = %s, status = %s, updated_at = %s
                where checkout_session_id = %s
                """,
                (payment_intent_id, status, now, checkout_session_id),
            )
            return
        _execute(
            conn,
            """
            insert into stripe_payments
                (checkout_session_id, user_id, stripe_customer_id, payment_intent_id,
                 gross_amount_usd, app_credit_amount_usd, status, created_at, updated_at)
            values (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                checkout_session_id,
                user_id,
                stripe_customer_id,
                payment_intent_id,
                round(float(gross_amount_usd), 4),
                round(float(app_credit_amount_usd), 4),
                status,
                now,
                now,
            ),
        )


def get_stripe_payment_by_intent(payment_intent_id: Optional[str]) -> Optional[Dict[str, Any]]:
    if not payment_intent_id:
        return None
    ensure_schema()
    with connect() as conn:
        return _fetchone(conn, "select * from stripe_payments where payment_intent_id = %s", (payment_intent_id,))


def get_stripe_payment_by_session(checkout_session_id: Optional[str]) -> Optional[Dict[str, Any]]:
    if not checkout_session_id:
        return None
    ensure_schema()
    with connect() as conn:
        return _fetchone(conn, "select * from stripe_payments where checkout_session_id = %s", (checkout_session_id,))


def stripe_purchase_credit_exists(checkout_session_id: Optional[str]) -> bool:
    if not checkout_session_id:
        return False
    ensure_schema()
    with connect() as conn:
        row = _fetchone(
            conn,
            """
            select id
            from app_credit_ledger
            where stripe_checkout_session_id = %s and entry_type = 'purchase'
            limit 1
            """,
            (checkout_session_id,),
        )
    return bool(row)


def ledger_adjustment_total(payment_intent_id: str, entry_type: str) -> float:
    ensure_schema()
    with connect() as conn:
        row = _fetchone(
            conn,
            """
            select coalesce(sum(amount_usd), 0) as amount
            from app_credit_ledger
            where stripe_payment_intent_id = %s and entry_type = %s
            """,
            (payment_intent_id, entry_type),
        )
    return round(float(row.get("amount") or 0), 4) if row else 0.0


def update_stripe_payment_status(checkout_session_id: str, status: str) -> None:
    ensure_schema()
    now = utc_now()
    with connect() as conn:
        _execute(
            conn,
            "update stripe_payments set status = %s, updated_at = %s where checkout_session_id = %s",
            (status, now, checkout_session_id),
        )


def get_managed_key(user_id: str) -> Optional[Dict[str, Any]]:
    ensure_schema()
    with connect() as conn:
        return _fetchone(conn, "select * from managed_openrouter_keys where user_id = %s", (user_id,))


def save_managed_key(user_id: str, key_data: Dict[str, Any]) -> Dict[str, Any]:
    ensure_schema()
    now = utc_now()
    existing = get_managed_key(user_id)
    values = {
        "openrouter_key_hash": key_data.get("openrouter_key_hash"),
        "encrypted_openrouter_key": key_data.get("encrypted_openrouter_key"),
        "openrouter_name": key_data.get("openrouter_name") or f"llm-council-managed-user-{user_id}",
        "limit_total_usd": round(float(key_data.get("limit_total_usd") or 0), 4),
        "limit_remaining_usd": key_data.get("limit_remaining_usd"),
        "usage_total_usd": round(float(key_data.get("usage_total_usd") or 0), 4),
        "usage_daily_usd": key_data.get("usage_daily_usd"),
        "usage_weekly_usd": key_data.get("usage_weekly_usd"),
        "usage_monthly_usd": key_data.get("usage_monthly_usd"),
        "limit_reset": key_data.get("limit_reset"),
        "disabled": bool(key_data.get("disabled")),
        "last_synced_at": key_data.get("last_synced_at") or now,
    }
    with connect() as conn:
        if existing:
            _execute(
                conn,
                """
                update managed_openrouter_keys
                set openrouter_key_hash = %s, encrypted_openrouter_key = %s, openrouter_name = %s,
                    limit_total_usd = %s, limit_remaining_usd = %s, usage_total_usd = %s,
                    usage_daily_usd = %s, usage_weekly_usd = %s, usage_monthly_usd = %s,
                    limit_reset = %s, disabled = %s, last_synced_at = %s, updated_at = %s
                where user_id = %s
                """,
                (
                    values["openrouter_key_hash"],
                    values["encrypted_openrouter_key"],
                    values["openrouter_name"],
                    values["limit_total_usd"],
                    values["limit_remaining_usd"],
                    values["usage_total_usd"],
                    values["usage_daily_usd"],
                    values["usage_weekly_usd"],
                    values["usage_monthly_usd"],
                    values["limit_reset"],
                    _db_bool(conn, values["disabled"]),
                    values["last_synced_at"],
                    now,
                    user_id,
                ),
            )
        else:
            _execute(
                conn,
                """
                insert into managed_openrouter_keys
                    (user_id, openrouter_key_hash, encrypted_openrouter_key, openrouter_name,
                     limit_total_usd, limit_remaining_usd, usage_total_usd, usage_daily_usd,
                     usage_weekly_usd, usage_monthly_usd, limit_reset, disabled, last_synced_at,
                     created_at, updated_at)
                values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    user_id,
                    values["openrouter_key_hash"],
                    values["encrypted_openrouter_key"],
                    values["openrouter_name"],
                    values["limit_total_usd"],
                    values["limit_remaining_usd"],
                    values["usage_total_usd"],
                    values["usage_daily_usd"],
                    values["usage_weekly_usd"],
                    values["usage_monthly_usd"],
                    values["limit_reset"],
                    _db_bool(conn, values["disabled"]),
                    values["last_synced_at"],
                    now,
                    now,
                ),
            )
    return get_managed_key(user_id) or {}


def save_run_receipt(receipt: Dict[str, Any]) -> Dict[str, Any]:
    ensure_schema()
    now = utc_now()
    with connect() as conn:
        _execute(
            conn,
            """
            insert into managed_run_receipts
                (council_run_id, user_id, billing_mode, profile_slug,
                 estimated_app_cost_low_usd, estimated_app_cost_high_usd, max_app_charge_usd,
                 reserved_amount_usd, actual_raw_cost_usd, actual_app_cost_usd, service_multiplier,
                 remaining_balance_usd, metadata_json, created_at)
            values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            on conflict (council_run_id) do nothing
            """,
            (
                receipt["council_run_id"],
                receipt["user_id"],
                receipt.get("billing_mode", "managed"),
                receipt.get("profile_slug"),
                receipt.get("estimated_app_cost_low_usd"),
                receipt.get("estimated_app_cost_high_usd"),
                receipt.get("max_app_charge_usd"),
                receipt.get("reserved_amount_usd"),
                receipt.get("actual_raw_cost_usd"),
                receipt.get("actual_app_cost_usd"),
                receipt.get("service_multiplier"),
                receipt.get("remaining_balance_usd"),
                _json(receipt.get("metadata")),
                now,
            ),
        )
    return receipt


def save_coverage_snapshot(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    ensure_schema()
    now = utc_now()
    with connect() as conn:
        _execute(
            conn,
            """
            insert into openrouter_account_snapshots
                (total_credits_usd, total_usage_usd, available_credits_usd,
                 managed_raw_liability_usd, operating_buffer_usd, required_floor_usd,
                 coverage_ratio, status, created_at)
            values (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                snapshot.get("total_credits_usd"),
                snapshot.get("total_usage_usd"),
                snapshot.get("available_credits_usd"),
                snapshot.get("managed_raw_liability_usd"),
                snapshot.get("operating_buffer_usd"),
                snapshot.get("required_floor_usd"),
                snapshot.get("coverage_ratio"),
                snapshot.get("status", "unknown"),
                now,
            ),
        )
    return {**snapshot, "created_at": now}


def latest_coverage_snapshot() -> Optional[Dict[str, Any]]:
    ensure_schema()
    with connect() as conn:
        return _fetchone(
            conn,
            "select * from openrouter_account_snapshots order by created_at desc, id desc limit 1",
        )


def outstanding_app_credits() -> float:
    ensure_schema()
    with connect() as conn:
        row = _fetchone(conn, "select coalesce(sum(amount_usd), 0) as amount from app_credit_ledger")
    return round(float(row.get("amount") or 0), 4) if row else 0.0


def managed_raw_liability() -> float:
    multiplier = service_multiplier()
    if multiplier <= 0:
        return 0.0
    return round(max(0.0, outstanding_app_credits()) / multiplier, 4)


def recent_payments(limit: int = 10) -> List[Dict[str, Any]]:
    ensure_schema()
    with connect() as conn:
        return _fetchall(conn, "select * from stripe_payments order by created_at desc limit %s", (limit,))


def recent_runs(limit: int = 10) -> List[Dict[str, Any]]:
    ensure_schema()
    with connect() as conn:
        rows = _fetchall(conn, "select * from managed_run_receipts order by created_at desc limit %s", (limit,))
    for row in rows:
        row["metadata"] = _parse_json(row.pop("metadata_json", None))
    return rows


def users_by_balance(limit: int = 50) -> List[Dict[str, Any]]:
    ensure_schema()
    with connect() as conn:
        rows = _fetchall(
            conn,
            """
            select user_id, coalesce(sum(amount_usd), 0) as balance
            from app_credit_ledger
            group by user_id
            order by balance desc
            limit %s
            """,
            (limit,),
        )
    for row in rows:
        row["reserved_balance_usd"] = reserved_balance(row["user_id"])
        row["available_balance_usd"] = round(float(row["balance"] or 0) - row["reserved_balance_usd"], 4)
    return rows


def failed_webhooks(limit: int = 10) -> List[Dict[str, Any]]:
    ensure_schema()
    with connect() as conn:
        return _fetchall(
            conn,
            """
            select stripe_event_id, event_type, processed_status, error_message, created_at, processed_at
            from stripe_events
            where processed_status = 'failed'
            order by created_at desc
            limit %s
            """,
            (limit,),
        )


def set_config(key: str, value: Any) -> None:
    ensure_schema()
    now = utc_now()
    with connect() as conn:
        existing = _fetchone(conn, "select key from billing_config where key = %s", (key,))
        if existing:
            _execute(conn, "update billing_config set value = %s, updated_at = %s where key = %s", (_json(value), now, key))
        else:
            _execute(conn, "insert into billing_config (key, value, updated_at) values (%s, %s, %s)", (key, _json(value), now))


def get_config(key: str, default: Any = None) -> Any:
    ensure_schema()
    with connect() as conn:
        row = _fetchone(conn, "select value from billing_config where key = %s", (key,))
    return _parse_json(row["value"]) if row else default


def audit(admin_user_id: str, action: str, *, target_user_id: Optional[str] = None, target_object_type: Optional[str] = None, target_object_id: Optional[str] = None, before: Any = None, after: Any = None, reason: Optional[str] = None) -> None:
    ensure_schema()
    now = utc_now()
    with connect() as conn:
        _execute(
            conn,
            """
            insert into admin_audit_events
                (admin_user_id, action, target_user_id, target_object_type, target_object_id,
                 before_json, after_json, reason, created_at)
            values (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (admin_user_id, action, target_user_id, target_object_type, target_object_id, _json(before), _json(after), reason, now),
        )
