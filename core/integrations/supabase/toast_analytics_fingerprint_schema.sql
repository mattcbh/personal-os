-- Toast Analytics fingerprint ingest v1
-- Creates guest payment storage, Toast payment storage, and a join view.

create table if not exists public.toast_guest_payments (
  payment_guid text primary key,
  order_guid text not null,
  restaurant_guid text not null,
  location_id text not null,
  restaurant_name text,
  payment_date date not null,
  card_fingerprint uuid,
  request_time_range text not null,
  request_start_date date not null,
  request_end_date date not null,
  report_request_guid text not null,
  synced_at timestamptz not null default now()
);

create index if not exists idx_toast_guest_payments_order
  on public.toast_guest_payments (order_guid, location_id);

create index if not exists idx_toast_guest_payments_payment_date
  on public.toast_guest_payments (payment_date, location_id);

create index if not exists idx_toast_guest_payments_fingerprint
  on public.toast_guest_payments (card_fingerprint);


create table if not exists public.toast_payments (
  payment_guid text primary key,
  check_guid text not null,
  order_guid text not null,
  restaurant_guid text not null,
  location_id text not null,
  type text,
  amount numeric(12,2),
  tip_amount numeric(12,2),
  card_type text,
  card_entry_mode text,
  payment_status text,
  paid_date timestamptz,
  paid_business_date integer,
  synced_at timestamptz not null default now()
);

create index if not exists idx_toast_payments_order
  on public.toast_payments (order_guid, location_id);

create index if not exists idx_toast_payments_check
  on public.toast_payments (check_guid);

create index if not exists idx_toast_payments_paid_business_date
  on public.toast_payments (paid_business_date, location_id);


create or replace view public.v_card_fingerprint_orders as
select
  gp.payment_guid,
  gp.order_guid,
  gp.restaurant_guid,
  gp.location_id,
  gp.restaurant_name,
  gp.payment_date,
  gp.card_fingerprint,
  gp.request_time_range,
  gp.request_start_date,
  gp.request_end_date,
  gp.report_request_guid,
  gp.synced_at as guest_payment_synced_at,
  tp.check_guid,
  tp.type as payment_type,
  tp.amount as payment_amount,
  tp.tip_amount as payment_tip_amount,
  tp.card_type,
  tp.card_entry_mode,
  tp.payment_status,
  tp.paid_date,
  tp.paid_business_date,
  tp.synced_at as toast_payment_synced_at,
  o.toast_order_id,
  o.order_date,
  o.order_time,
  o.opened_at,
  o.closed_at,
  o.channel,
  o.channel_group,
  o.daypart,
  o.order_source,
  o.subtotal,
  o.discount_amount,
  o.tax_amount,
  o.tip_amount,
  o.net_sales,
  o.total_amount,
  o.guest_count,
  o.item_count,
  o.customer_guid,
  o.customer_name,
  o.customer_email,
  o.customer_phone,
  o.is_catering,
  o.table_guid
from public.toast_guest_payments gp
left join public.toast_payments tp
  on tp.payment_guid = gp.payment_guid
 and tp.location_id = gp.location_id
left join public.orders o
  on o.toast_order_id = gp.order_guid
 and o.location_id = gp.location_id;
