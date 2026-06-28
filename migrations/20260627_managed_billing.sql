create table if not exists billing_profiles (
  user_id text primary key,
  billing_mode text not null default 'byok' check (billing_mode in ('byok', 'managed')),
  managed_enabled boolean not null default false,
  byok_enabled boolean not null default true,
  service_multiplier numeric(8,4) not null default 1.35,
  stripe_customer_id text,
  disabled_at timestamptz,
  created_at timestamptz not null,
  updated_at timestamptz not null
);

create table if not exists app_credit_ledger (
  id bigint generated always as identity primary key,
  user_id text not null,
  entry_type text not null,
  amount_usd numeric(12,4) not null,
  currency text not null default 'usd',
  council_run_id text,
  reservation_id text,
  stripe_checkout_session_id text,
  stripe_payment_intent_id text,
  stripe_event_id text,
  metadata_json jsonb not null default '{}'::jsonb,
  created_at timestamptz not null
);

create index if not exists app_credit_ledger_user_idx on app_credit_ledger (user_id);
create index if not exists app_credit_ledger_run_idx on app_credit_ledger (council_run_id);
create index if not exists app_credit_ledger_stripe_event_idx on app_credit_ledger (stripe_event_id);

create table if not exists billing_reservations (
  reservation_id text primary key,
  user_id text not null,
  council_run_id text not null,
  amount_usd numeric(12,4) not null,
  status text not null check (status in ('active', 'released', 'finalized')),
  metadata_json jsonb not null default '{}'::jsonb,
  created_at timestamptz not null,
  released_at timestamptz,
  finalized_at timestamptz
);

create index if not exists billing_reservations_user_status_idx on billing_reservations (user_id, status);
create index if not exists billing_reservations_run_idx on billing_reservations (council_run_id);

create table if not exists stripe_events (
  stripe_event_id text primary key,
  event_type text not null,
  payload_json jsonb not null,
  processed_status text not null check (processed_status in ('pending', 'processed', 'failed', 'ignored')),
  error_message text,
  created_at timestamptz not null,
  processed_at timestamptz
);

create index if not exists stripe_events_status_idx on stripe_events (processed_status);

create table if not exists stripe_payments (
  checkout_session_id text primary key,
  user_id text not null,
  stripe_customer_id text,
  payment_intent_id text,
  gross_amount_usd numeric(12,4) not null,
  app_credit_amount_usd numeric(12,4) not null,
  stripe_fee_usd numeric(12,4),
  stripe_net_usd numeric(12,4),
  status text not null,
  created_at timestamptz not null,
  updated_at timestamptz not null
);

create index if not exists stripe_payments_user_idx on stripe_payments (user_id);
create index if not exists stripe_payments_payment_intent_idx on stripe_payments (payment_intent_id);

create table if not exists managed_openrouter_keys (
  user_id text primary key,
  openrouter_key_hash text,
  encrypted_openrouter_key text,
  openrouter_name text,
  limit_total_usd numeric(12,4) not null default 0,
  limit_remaining_usd numeric(12,4),
  usage_total_usd numeric(12,4) not null default 0,
  usage_daily_usd numeric(12,4),
  usage_weekly_usd numeric(12,4),
  usage_monthly_usd numeric(12,4),
  limit_reset text,
  disabled boolean not null default false,
  last_synced_at timestamptz,
  created_at timestamptz not null,
  updated_at timestamptz not null
);

create table if not exists managed_run_receipts (
  council_run_id text primary key,
  user_id text not null,
  billing_mode text not null,
  profile_slug text,
  estimated_app_cost_low_usd numeric(12,4),
  estimated_app_cost_high_usd numeric(12,4),
  max_app_charge_usd numeric(12,4),
  reserved_amount_usd numeric(12,4),
  actual_raw_cost_usd numeric(12,4),
  actual_app_cost_usd numeric(12,4),
  service_multiplier numeric(8,4),
  remaining_balance_usd numeric(12,4),
  metadata_json jsonb not null default '{}'::jsonb,
  created_at timestamptz not null
);

create index if not exists managed_run_receipts_user_idx on managed_run_receipts (user_id);

create table if not exists openrouter_account_snapshots (
  id bigint generated always as identity primary key,
  total_credits_usd numeric(12,4),
  total_usage_usd numeric(12,4),
  available_credits_usd numeric(12,4),
  managed_raw_liability_usd numeric(12,4),
  operating_buffer_usd numeric(12,4),
  required_floor_usd numeric(12,4),
  coverage_ratio numeric(12,4),
  status text not null,
  created_at timestamptz not null
);

create index if not exists openrouter_snapshots_created_idx on openrouter_account_snapshots (created_at);

create table if not exists billing_config (
  key text primary key,
  value jsonb not null,
  updated_at timestamptz not null
);

create table if not exists admin_audit_events (
  id bigint generated always as identity primary key,
  admin_user_id text not null,
  action text not null,
  target_user_id text,
  target_object_type text,
  target_object_id text,
  before_json jsonb,
  after_json jsonb,
  reason text,
  created_at timestamptz not null
);

create index if not exists admin_audit_events_target_idx on admin_audit_events (target_user_id, target_object_type);
