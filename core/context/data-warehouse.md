## Corner Booth Holdings Warehouse (Supabase)

Restaurant analytics warehouse for Corner Booth Holdings in Supabase (project: `zxqtclvljxvdxsnmsqka`). Raw tables stay source-native by system; CBH reporting happens in canonical fact views.

**Current tables:**

| Table | Rows | Source |
|-------|------|--------|
| order_items | ~323,000 | Toast CSV (historical) + Toast API (ongoing) |
| orders | ~673,000 | Toast API (ongoing). raw_data column dropped Feb 2026. |
| financials | ~10,700 | SystematIQ Excel workbooks + QBO API (P&L, Balance Sheet, Cash Flow). `source` column: `'systematiq'` or `'qbo'` |
| reviews | ~4,955 | BirdEye CSV (historical) + Outscraper/Google API (ongoing) |
| weather | ~465+ | Visual Crossing API (obs + 15-day forecast, `source_type` column: `obs` or `fcst`) |
| weather_normals | 366 | Visual Crossing statistical normals (historical averages, one row per day of year) |
| labor_daily | ~2,492 | 7shifts API (daily labor by department) |
| time_punches | ~7,669 | 7shifts API (individual clock in/out, 60 employees) |
| invoices | ~1,500 | MarginEdge API (PnT + Heap's, Nov 2024 - present) |
| invoice_items | ~11,000 | MarginEdge API (line items with GL categories) |
| dim_company / dim_brand / dim_site / dim_location / location_source_map | New | CBH org model + source-system location mappings |
| square_locations | New | Square Locations API landing table |
| square_orders | New | Square Orders API raw orders for Heap's |
| square_order_line_items | New | Square order line items |
| square_payments | New | Square Payments API landing table |
| square_refunds | New | Square refunds / payment refunds |
| square_customers | New | Square Customers API landing table |
| square_catalog_items / square_catalog_variations | New | Square catalog item + variation reference data |
| square_team_members | New | Square team member roster |
| square_shifts | New | Square Labor timecards / shifts |
| square_inventory_counts | Optional | Square inventory counts when inventory sync is enabled |
| square_gift_cards | Optional | Reserved for future Square gift card sync |
| square_loyalty_events | Optional | Reserved for future Square loyalty sync |
| transaction_detail | ~62,000 | SystematIQ xlsx + QBO API (FY2024-FY2026). `source` column: `'systematiq'` or `'qbo'` |
| fiscal_periods | 25 | SystematIQ (FY2024-FY2026 P1, 4-4-5 periods) |
| menu_items | 194 | Toast Menus API |
| customers | ~34,000 | Owner.com CSV export + DoorDash customer enrichment (email contacts, opt-ins, loyalty) |
| toast_customers | ~50,106 | Extracted from orders (3,797 real, 46,309 delivery proxies). Note: orders.raw_data column was dropped Feb 2026. |
| toast_guest_payments | — | Toast Analytics API guest payments (`payment_guid`, `order_guid`, `card_fingerprint`, `location_id`). Anonymous card-fingerprint layer for payment/order joins. |
| toast_payments | — | Check-level payments extracted from Toast Orders API (`payment_guid`, `check_guid`, `order_guid`, payment metadata). |
| billcom_se_transactions | 214 | Bill.com S&E API (credit card transactions, CLEAR only). 5 cardholders, $44.8K, Jun 2025 - present. |
| toast_guestbook | — | Toast Guestbook Excel export (export pipeline broken, needs fix — Toast did NOT remove the feature) |
| mailchimp_campaigns | — | Mailchimp sent campaigns with metadata, type tags, open/click rates |
| mailchimp_campaign_activity | — | Per-email per-campaign opens/clicks with URLs |
| mailchimp_engagement | — | Aggregate per-member Mailchimp stats (member_rating, avg_open/click rates) |
| doordash_storefront | 4,367 | DoorDash Merchant Portal CSV export (Storefront + Marketplace orders, Feb 2024 - present). Enables 1P PY comp and DoorDash marketplace-only adjustment. |
| toast_tables | 18 | Toast table configuration (name, section, GUID). Source: Toast Config API. Upsert key: table_guid, location_id |
| toast_reservations | — | Toast reservation confirmations parsed from forwarded emails. Upsert key: confirmation_number, location_id |
| weekly_food_cost | — | Inventory-based weekly COGS (MarginEdge Food Usage Report CSV or manual). Upsert key: location_id, week_start. Used by monday_report.py Prime Margin. |
| foot_traffic_events | — | Raw UniFi Protect smart-detection events for PnT Park Slope. One row per event id, with ET-derived event_date/hour, optional crossing line + direction, and raw JSON for audit/debug. |
| foot_traffic_hourly | — | Hourly street-line traffic rollup by camera/date/hour/direction. Door-threshold lines are excluded here and analyzed from raw events instead, so heatmaps/opportunity views stay storefront-focused. |
| foot_traffic_cameras | 4 | Camera dimension for PnT Park Slope, PnT Williamsburg door-only, and Heap's foot traffic (`flatbush_cam`, `stmarks_cam`, `williamsburg_front_door_cam`, `heaps_7thave_cam`), with UniFi device ids and crossing-line definitions when known. |
| customer_changes | — | Audit trail for Owner delta/CDC changes (DDL pending on Supabase) |
| pipeline_runs | — | ETL audit log |
| mv_customer_segments | ~32,475 | Materialized view joining customers + orders + order_items. Precomputed segment tiers (frequency, recency, spend), item affinity. Applied 2026-02-19. Refresh daily with CONCURRENTLY. |

**SQL views:** Existing PnT views remain in place. New CBH views: `fact_orders_cbh`, `fact_order_items_cbh`, `fact_payments_cbh`, `fact_customers_cbh`, `fact_labor_daily_cbh`, `fact_sales_daily_cbh`, `v_pnt_sales_daily`, `v_heaps_sales_daily`, `v_cbh_sales_daily`. New Park Slope / Heap's foot-traffic views: `v_foot_traffic_daily`, `v_capture_rate`, `v_store_entry_daily`, `v_store_entry_hourly`, `v_traffic_hourly_heatmap`, `v_traffic_opportunity`.

**Access control roles:** `marketing_readonly` (customer/order/review data), `finance_readonly` (financials/labor/transaction detail), `ownership_readonly` (curated dashboard views only)

**ETL scripts (all in `scripts/`):**

| Script | Status | What it does |
|--------|--------|-------------|
| `cbh_warehouse.py` | Live (shared config) | Canonical company/brand/location/site metadata, legacy alias normalization, and source-location map parsing for Toast/Square ETLs. |
| `toast_etl.py` | Live (daily) | Pulls orders + items from Toast Orders API. Uses canonical `williamsburg` location ids and supports `TOAST_RESTAURANT_MAP_JSON` for multi-location Toast mapping. |
| `square_etl.py` | Implemented (credentials pending) | Direct Square API sync for Heap's: locations, orders, line items, payments, refunds, catalog, customers, team members, timecards, and optional inventory counts. Default run is a rolling 3-day replay ending yesterday. |
| `toast_analytics_etl.py` | Ready | Pulls anonymous guest payments from Toast Analytics API into `toast_guest_payments`. Default run is a rolling 3-day replay ending yesterday; supports `--date`, `--backfill START END`, and `--full-backfill`. |
| `weather_etl.py` | Live (daily) | Pulls daily weather from Visual Crossing. Raw weather remains keyed to the shared `williamsburg` weather zone; CBH facts join through `dim_location.weather_zone_id`. |
| `test_unifi_api.py` | Ready | Validates Park Slope UniFi auth paths. Private API mode checks historical event access; native API-key mode checks camera metadata plus a short public events-websocket probe. Current `uiprotect` still needs direct host reachability for historical backfills. |
| `foot_traffic_etl.py` | Ready | Loads Park Slope UniFi Protect line-crossing events into `foot_traffic_events`, regenerates `foot_traffic_hourly`, supports `--date`, `--date_start/end`, `--rollup-only`, `--dry-run`, and logs every run to `pipeline_runs`. Poll mode still requires direct UNVR reachability; when the Cloudflare webhook path is live, schedule this script in `--rollup-only` mode. |
| `foot_traffic_rollup_hourly.sh` | Ready | Hourly wrapper around `foot_traffic_etl.py --rollup-only`. Intended for the Mac Mini so dashboards refresh throughout the day without rerunning the full daily warehouse sync. |
| `foot_traffic_dashboard.py` | Ready | Queries the foot-traffic views and writes self-contained HTML dashboards for `cbh-dashboards/pnt/`: overview, capture rate, traffic heatmap, and signage A/B template. |
| `workers/unifi-protect-webhook/` | Ready | Cloudflare Worker that receives outbound UniFi Protect Alarm Manager webhooks and writes normalized rows straight to Supabase `foot_traffic_events`. Preferred remote-ingest path when the Mac Mini cannot reach the restaurant LAN. Live mappings now cover PnT Park Slope plus Heap's 7th Ave directional alarms. |
| `sevenshifts_etl.py` | Live (daily) | Pulls labor data from 7shifts. Auto-detects plan tier (reports vs punches). `--list-locations` to verify mapping. |
| `google_reviews_etl.py` | Live (weekly) | Pulls Google reviews via Outscraper. `--full` for complete re-pull, `--dry-run` to preview. |
| `marginedge_etl.py` | Live (daily) | Food cost/invoices from MarginEdge API. PnT + Heap's. `--entity pnt\|heaps`, `--csv PATH` for CSV fallback |
| `billcom_etl.py` | Live (daily) | AP/expenses + S&E credit card transactions from Bill.com (PnT only). `--date`, `--date_start/end`, `--skip-ap`, `--skip-se`, `--dry-run` |
| `qbo_etl.py` | Live | P&L, Balance Sheet, Transaction Detail direct from QBO API (PnT only). `--setup`, `--current`, `--all-open`, `--period/--fiscal-year`, `--report pl\|bs\|detail\|all`, `--dry-run`, `--force` |
| `load_financials.py` | Working (manual) | Parses SystematIQ Excel workbooks (P&L). Supports `--entity pnt|heaps|cbh`, canonical location ids, and writes `source='systematiq'`. |
| `load_transaction_detail.py` | Working (manual) | Loads Transaction Detail by Account xlsx. `--file PATH --dry-run`. Supports 2024 and 2025+ formats. |
| `reviews_etl.py` | Working (manual) | BirdEye XLSX import. `--file PATH --dry-run` |
| `monday_report.py` | Working (manual) | Weekly narrative report. Includes Prime Margin (COGS + four-wall labor + prime cost vs PY) and multi-week trend detection (3+ week comp streak alerts). |
| `doordash_storefront_etl.py` | Working (manual) | Load DoorDash Merchant Portal CSV into `doordash_storefront`. `--file PATH --dry-run` |
| `doordash_customers_etl.py` | Working (manual) | Load DoorDash customer export into `customers` (enrich + insert). `--file PATH --dry-run` |
| `toast_customers_etl.py` | Legacy repo copy | Historical rebuild from `orders.raw_data`. Production `orders.raw_data` was dropped Feb 2026, so this script must be rewritten before it is scheduled again. |
| `toast_guestbook_export.py` | Live (daily) | Camoufox (patched Firefox) browser export of Toast CRM guestbook CSV. Bypasses Cloudflare Turnstile. Session-first login via saved cookies, auto-retrieves SMS 2FA codes from personal Gmail (Google Voice forwards). 10-min polling window for throttled SMS. `--headed`, `--dry-run`, `--export-only` |
| `toast_guestbook_etl.py` | Live (daily) | Load Toast Guestbook CSV into Supabase. `--file PATH --dry-run --location-id` |
| `toast_reservations_etl.py` | Ready (waiting on email forwarding) | Parses Toast reservation confirmation emails from Gmail IMAP. `--dry-run`, `--status`, `--reprocess` |
| `systematiq_monitor.py` | Live (daily 4:30 AM) | Auto-detect SystematiQ close emails from Gmail, download xlsx, classify by entity/type, load via load_financials.py or load_transaction_detail.py. PnT + Heap's + CBH. `--dry-run`, `--status`, `--reprocess` |
| `owner_export.py` | Live (daily, Mac Mini) | Downloads Owner.com customer CSV. |
| `owner_customers_etl.py` | Working (manual) | Loads Owner.com customer CSV. Laptop has newer delta/CDC version (only inserts new, updates changed, logs to customer_changes). `--file PATH --dry-run` |
| `catering_platforms_etl.py` | Ready (manual) | Loads Forkable/ParkDay/Dlivrd CSVs. `--file PATH --source forkable --dry-run` |
| `mailchimp_sync.py` | Live | Syncs customer segments + engagement scores to Mailchimp. `--dry-run`, `--status`, `--setup` |
| `mailchimp_engagement_etl.py` | Live (daily) | Pulls Mailchimp engagement data (campaigns, opens/clicks, member stats). `--dry-run`, `--status`, `--campaigns-only`, `--members-only` |
| `daily_sync.sh` | Repo snapshot only | Checked-in script now includes Park Slope foot traffic rollups after Toast. In webhook mode it runs `foot_traffic_etl.py --rollup-only`, and it prefers `.venv/bin/python` when present so the Mini can run `uiprotect` under Python 3.11+. Production Mini job list still needs reconciliation before assuming parity with the checked-in script. |
| `com.pnt.foot-traffic-rollup-hourly.plist` | Live on brain | Dedicated hourly launch agent that runs `foot_traffic_rollup_hourly.sh` at the top of each hour. Keeps `foot_traffic_hourly` fresh between daily sync runs. |
| `weekly_reviews_sync.sh` | Ready | Runs Google reviews ETL weekly. |
| `com.pnt.daily-sync.plist` | Installed | launchd on Mac Mini, runs daily at 4 AM |
| `com.pnt.weekly-se-sync.plist` | Retired | Was Sundays 4 AM S&E sync; moved to daily sync (volume is small, ~10s per run) |

**Credentials:** `.env.toast` in repo root (gitignored). Existing creds unchanged. New Square contract: `SQUARE_ACCESS_TOKEN`, `SQUARE_ENV`, `SQUARE_LOCATION_MAP_JSON`, optional `SQUARE_API_VERSION`, `SQUARE_WEBHOOK_SIGNATURE_KEY`, `SQUARE_BACKFILL_START`, `SQUARE_DEFAULT_LOCATION_ID`, `SQUARE_SYNC_INVENTORY`. Toast Analytics still expects `TOAST_ANALYTICS_CLIENT_ID`, `TOAST_ANALYTICS_CLIENT_SECRET`, `TOAST_ANALYTICS_API_HOST`, and `TOAST_RESTAURANT_MAP_JSON` (`{"<restaurantGuid>":"<location_id>"}`). Foot traffic adds `UNIFI_PROTECT_HOST`, `UNIFI_PROTECT_PORT`, `UNIFI_PROTECT_USERNAME`, `UNIFI_PROTECT_PASSWORD`, `UNIFI_PROTECT_VERIFY_SSL`, optional `UNIFI_CAMERA_MAP_JSON`, and currently assumes a repo-local Python 3.11+ virtualenv because `uiprotect` does not run on the Mini's stock Python 3.9.

**7shifts details:**
- Company ID: 272244, Location: 339083 (Pies'n'Thighs → williamsburg)
- Uses time_punches mode (Entree plan — no reports endpoint)
- 5 departments: BOH, FOH, PASTRY, PORTER, PREP
- Wages returned in cents by API, converted to dollars in ETL
- Backfilled Nov 2024 → present (461 days)

**Reviews details:**
- Google reviews: 4,302 loaded via Outscraper (Place ID: ChIJ2yfij9hbwokRokungtwEERU, 2010 → present, 4.37 avg rating)
- Yelp reviews: 200 loaded via Outscraper (pies-n-thighs-brooklyn)
- TripAdvisor: 332 from BirdEye CSV (Outscraper TripAdvisor endpoint needs separate activation)
- Also has: DoorDash (151), GrubHub (121), Direct Feedback (49)
- Weekly flash email shows Google + Yelp reviews with links to individual reviews and BirdEye dashboard
- Outscraper API ($10 paid, 500 reviews/month)

**Customer data notes:**
- Orders table has `customer_email`, `customer_phone`, `customer_name`, `customer_guid`, `is_catering` columns (backfilled Feb 10, 2026)
- Orders table has `table_guid` column (dine-in only, nullable). Links to `toast_tables` reference table. 89% of dine-in orders have table assignments. Added Feb 14, 2026.
- Customer identity fields (email, phone, name, guid) are populated directly during ETL from the Toast API response. The `orders.raw_data` JSONB column was dropped Feb 19, 2026 (was 2.3 GB / 59% of DB) to fix Disk IO Budget depletion.
- **toast_etl.py uses pure upsert** (no delete-before-insert). ON CONFLICT UPDATE handles idempotent daily loads.
- Card fingerprints stay anonymous in v1. Use `toast_guest_payments` + `toast_payments` + `v_card_fingerprint_orders` to attach them to existing order/customer fields without merging into `customers`.
- Toast Guests API does NOT exist. CRM API deprecated. Guestbook data only via Excel export from Toast web UI.
- 3P proxy emails are NOT marketable: DoorDash (`dd.toast.orders+*@gmail.com`), UberEats (`ubersupport*@uber.com`), GrubHub (`*@internal.grubhub.com`). Also: `@ezcater.com`, `@ritual.co`, `@forkable.com`
- toast_customers table: 50,106 total (3,797 real, 46,309 delivery proxies). 1,771 matched to Owner by email.
- `v_customer_segments` view provides frequency/recency/spend tiers and item affinity (auto-excludes proxy emails)
- `v_mailchimp_segments` view provides engagement scoring (recency 0-40, frequency 0-30, profile completeness 0-15, channel bonus 0-15) with warm-up tiers
- EZCater catering contacts (144 with real emails) available via `v_catering_contacts`

**Data notes:**
- **CRITICAL: orders table revenue columns.** When reporting revenue, ALWAYS use `net_sales` (food & bev sales, excludes tax and tips). This matches what Toast shows as "Revenue" in its dashboard. Never use `total_amount` for revenue reporting. Column definitions:
  - `net_sales` = food & bev sales (THIS IS REVENUE). Use for all revenue reporting, YoY comps, avg check calculations.
  - `total_amount` = net_sales + tax_amount + tip_amount - discount_amount (what the customer paid). Only use for per-check guest spend or payment analysis.
  - `subtotal` ≈ net_sales (before discounts)
  - `tax_amount` = sales tax collected
  - `tip_amount` = tips (mostly dine-in/takeout; 3P delivery tips are $0)
  - `discount_amount` = promo/comp discounts applied
- CSV-loaded orders use short numeric `toast_order_id` (e.g., "12345"). API-loaded orders use full GUIDs.
- Toast API ignores pagination params and returns all GUIDs in one response. The script handles this with dedup.
- Location mapping for Toast is now driven by `TOAST_RESTAURANT_MAP_JSON`. If that env var is absent, ETLs fall back to the canonical single-location mapping `TOAST_RESTAURANT_GUID -> williamsburg`.
- Shared-data rule: raw weather stays a single Brooklyn lookup keyed to `williamsburg`; CBH facts use `dim_location.weather_zone_id` so PnT Williamsburg, PnT Park Slope, and Heap's Park Slope can all join the same weather series without confusing brand-specific facts.
- SystematIQ uses a 4-4-5 fiscal calendar (not calendar months).
- **Financials table query notes:**
  - `statement` column uses `'P&L'` (not `'pl'` or `'p&l'`). Case-sensitive.
  - `fiscal_year` is integer (`2025`), not string (`'FY2025'`).
  - `channel` column has per-channel breakdowns AND aggregate rows. Use `channel = ''` (empty string) for totals. Do NOT use `channel = 'total'` or `channel IS NULL`.
  - `section` values: `'Sales'`, `'COGS'`, `'Labor'`, `'Occupancy'`, `'Other Store Expenses'`, `'Selling'`, `'G&A'`, `'Other Expenses'`.
  - `source` column: `'systematiq'` (audited close) or `'qbo'` (near-real-time). SystematIQ takes precedence.
  - `v_financials_best` is the owner-safe precedence layer. It prefers SystematIQ at `(fiscal_year, period_number, location_id, statement)`, falls back to QBO only for FY2025+ qbo-only statements, and excludes FY2024 qbo-only financial rows.
  - Always GROUP BY `fiscal_year, period_number` and use aggregate functions when querying, as channel breakdowns create multiple rows per line item.
- **Transaction detail coverage notes:**
  - Not all fiscal periods have transaction detail loaded. Check available periods before querying.
  - Both `systematiq` and `qbo` sources may exist for the same period, causing duplicate rows. Always filter by `source` when querying.
  - `v_transactions_best` is the owner-safe precedence layer. It prefers SystematIQ at `(fiscal_year, period_number, location_id)` and falls back to QBO only for FY2025+ qbo-only periods.
  - Management payroll entries use `name = 'Payroll Processing (Toast)'` and `memo = 'Labor Distribution by Job: [Title]'`.
  - Partner compensation (Sarah, Jason) does NOT flow through Toast payroll. Sarah's expenses appear as reimbursements; her health insurance is account 7630 (G&A).
- `v_data_freshness` provides one row per pipeline with latest run status, latest successful run, and staleness metrics for owner-facing BI.
- Weather uses Visual Crossing free tier (1,000 records/day limit). Daily sync fetches obs + 15-day forecast. `weather_normals` table has 366 rows of historical averages (loaded once via `--normals`).
- Both locations are in Brooklyn, so one weather station covers both.
- 1P Online was previously bundled under DoorDash (Storefront software). PY comps for 1P use `doordash_storefront` table data; PY DoorDash/3P is marketplace-only (Storefront subtracted). Weekly flash email and Metabase dashboard both apply this reclassification with footnotes. For delivery share analysis, use "All Delivery" (3P + 1P) to see the true trend.
- **Comp sales definition (ENFORCED):** Always single-day comp. Yesterday vs same day-of-week 52 weeks ago (364 days back). Never use rolling averages or multi-day windows for comp reporting. This must match what Toast and MarginEdge show. If a holiday (Valentine's, Mother's Day, etc.) shifts DOW between years, note the shift as context. Never cross-month for seasonality reasons.

---

**PnT Metric Definitions (Williamsburg)**

These are the authoritative definitions for how we calculate key business metrics. All skills, automations, and reports must use these definitions. Last verified: 2026-02-19.

**Revenue:**
- **Net Sales** = `orders.net_sales` (food & bev sales, excludes tax and tips). This is "Revenue" everywhere.
- Source: Toast API/CSV. Matches Toast dashboard.
- SystematIQ equivalent: `TOTAL NET SALES` line item in the Sales section of the P&L.
- QBO vs SystematIQ variance: ~0.7% ($3.11M vs $3.13M FY2025). SystematIQ reconciles Toast deposits to bank and adjusts revenue upward. SystematIQ is the audited number.

**Four-Wall Labor % (daily/trailing, used in health scorecard and daily digest):**
- Formula: `(7shifts hourly labor + imputed management + imputed taxes & benefits) / net_sales`
- **Hourly labor** = `labor_daily.actual_labor_cost` from 7shifts. Covers 5 departments: BOH, FOH, PASTRY, PORTER, PREP. This is gross wages from time punches only.
- **Imputed management** = daily rate from most recent closed SystematIQ period. Calculated as `(Management Wages Total - Social Media Manager) / days_in_period`. As of FY2026 P1:
  - General Manager: $1,852/week (salaried, on Toast payroll)
  - Manager: $1,288/week (salaried, on Toast payroll)
  - Social Media Manager: $137/week — **EXCLUDED** (corporate/marketing cost, not four-wall)
  - Daily management imputed: ~$449/day
- **Imputed taxes & benefits** = daily rate from most recent closed SystematIQ period. Calculated as `Taxes and Benefits Total / days_in_period`. Includes:
  - FICA/Medicare (account 6505): employer match on all restaurant wages
  - FUTA (6510): federal unemployment
  - SUI (6515): state unemployment (higher in Q1 before wage caps)
  - Local Tax (6520): NYC payroll tax
  - Disability Insurance (6525)
  - Workers' Compensation (6530)
  - EPLI Insurance (6535)
  - Health Insurance (6540): restaurant employee health insurance only
  - Meal Credit (6550): employee meal benefit (reduces total)
  - Daily taxes/benefits imputed: ~$370/day (varies seasonally)
- **Total daily imputed: ~$819/day** (auto-updates from latest SystematIQ close)
- Target: <33% is healthy (FY2025 average was ~32%)
- Scoring bands: <30% excellent, 30-33% healthy, 33-36% watch, >36% flag

**What is NOT in four-wall labor:**
- **Sarah Sanneh** (partner): no wages, taxes, or benefits in four-wall. Her health insurance ($2,276/month) is booked to account 7630 (G&A Health Insurance), not the Labor section.
- **Jason Hershfeld** (partner): no compensation at the restaurant level at all. Paid at holding company.
- **Social Media Manager** ($137/week): excluded per Matt's direction — corporate/marketing cost.
- **G&A Payroll Taxes** (account 7625): $0 at restaurant level.
- **G&A Health Insurance** (account 7630): Sarah's health insurance only, not in four-wall.
- **Bonuses** (account 6320): in P&L Labor section but variable and unpredictable. Not imputed daily. Shows up in SystematIQ monthly close only. FY2025 P12 had a $22K "Other Wages" anomaly (year-end bonuses).
- **Recruiting, Severance, Payroll Manual**: in P&L Labor section but sporadic. Not imputed.

**Four-Wall Labor % (monthly/period, from SystematIQ close):**
- Formula: `(FOH Wages Total + BOH Wages Total + Management Wages Total + Other Wages Total + Taxes and Benefits Total) / TOTAL NET SALES`
- Source: `financials` table, `source = 'systematiq'`, `section = 'Labor'`
- This is the audited number. Includes everything in the Labor section of the P&L.
- FY2025 range: 30.1% (P6, P11) to 38.4% (P1). Average ~32.3% excluding P12 bonus anomaly.
- P1/P2 always run high (winter, lower sales, same fixed management costs).

**7shifts Hourly Labor % (operational metric):**
- Formula: `labor_daily.actual_labor_cost / orders.net_sales`
- This is what 7shifts shows. Captures ~60% of total four-wall labor.
- Useful for: scheduling decisions, shift-level efficiency, department-level analysis.
- NOT useful for: comparing to SystematIQ close, P&L benchmarking, investor reporting.
- FY2025 typical range: 19-22%.

**Food Cost % (COGS):**
- Daily estimate: from `v_food_cost_daily` view (MarginEdge invoices / Toast net sales). Rolling 30-day average.
- Weekly actual (inventory-based): from `weekly_food_cost` table. True COGS = Beginning Inventory + Purchases - Ending Inventory. Source: MarginEdge Food Usage Report CSV export after Monday inventory count. Loaded via `marginedge_usage_etl.py`.
- Period actual: from financials, `COGS Food and Beverage Total / TOTAL NET SALES`.
- Target: 28-32%.
- MarginEdge data starts Nov 2024. Pre-Nov 2024 food cost is from SystematIQ only.

**Prime Cost:**
- Formula: `Food Cost + Total Labor` (all-in).
- Weekly: from `monday_report.py` Prime Margin section. COGS from `weekly_food_cost` (inventory-based, preferred) or `invoice_items` (purchase-based, fallback). Labor = 7shifts hourly + imputed management/taxes from SystematIQ.
- Period: from SystematIQ P&L.
- This is the single most important profitability metric.
- FY2025 range: ~60-70% of net sales depending on period.

**Comp Sales:**
- Single-day: yesterday vs same DOW 52 weeks ago (364 days back).
- Weekly: Mon-Sun current week vs same Mon-Sun 52 weeks ago.
- Must match Toast and MarginEdge methodology.
- Holiday shifts noted as context, never adjusted.

---

**Documentation:**
- Notion: "PnT Data Warehouse Architecture" (page ID: 30575b9d-f253-8171-81fa-d5e128d70b9a)
- Google Slides diagram: https://docs.google.com/presentation/d/1aRMzVwJEJZDmC70OqQBrBGygCRXMh1FBUK6mhuL_gcs
- Mac Mini cleanup/organization doc: Agent Workspace / 2026-02 / mac-mini-data-warehouse-cleanup.md

**Git / production status (Mar 11, 2026):**
- Mac Mini production repo is clean and tracked on GitHub.
- Active production branch on the Mini: `feature/pnt-production-baseline`
- `main` remains the integration branch and is not auto-deployed
- Health check: `~/Projects/automation-machine-config/bin/check-pnt-runtime.sh`
- Operator runbook: `core/architecture/pnt-operator-runbook.md`

**Optional service policy (Mar 11, 2026):**
- `com.pnt.backfill-monitor` is dormant by default. Enable it only during bounded backfill campaigns.
- `com.pnt.cloudflared-charts` and `com.pnt.cloudflared-metabase` are disabled by default. The named Cloudflare tunnel is the primary public ingress path.

**QBO API Integration (live as of Feb 12, 2026):**
- Pulls P&L, Balance Sheet, and Transaction Detail directly from QuickBooks Online API
- Eliminates the 17-19 day wait for SystematIQ workbooks for near-real-time financials
- PnT Williamsburg only. Realm ID: `9130352068658686`
- OAuth 2.0 tokens auto-refresh (access token 1hr, refresh token 100 days)
- Two-tier expense classification: exact account number map (50+ accounts) with keyword fallback
- Coexists with SystematIQ: `source` column distinguishes origin. SystematIQ takes precedence (audited close). QBO fills gaps for periods not yet closed.
- Data loaded: FY2024 P1-P12, FY2025 P1-P12, FY2026 P1 (3,469 financials rows, 20,172 transactions)
- FY2024 QBO data is unreliable (Toast handled POS, QBO only had adjusting entries). FY2025+ is solid.
- QBO vs SystematIQ variance: ~0.7% on sales ($3.11M vs $3.13M FY2025). SystematIQ reconciles Toast deposits to bank and adjusts revenue upward.
- Usage: `python3 scripts/qbo_etl.py --current` (pull current open period), `--all-open` (fill all gaps), `--dry-run` (preview)

**Remaining work:**
1. Review and eventually promote `feature/pnt-production-baseline` into `main` once the current production branch is considered stable enough to become the integration baseline
2. Owner delta/CDC: merge laptop version to Mac Mini, create customer_changes table in Supabase, test with `--dry-run`
3. Google Business Profile official API (pending application/approval - Outscraper working in meantime)
4. Park Slope location support when it opens (March 21)
5. Forkable/ParkDay/Dlivrd catering CSV exports (awaiting Matt to check platforms)
6. Add `qbo_etl.py --current` to daily or weekly automation (currently manual)
