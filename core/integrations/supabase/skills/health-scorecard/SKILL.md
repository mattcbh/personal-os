---
name: health-scorecard
description: Business health vital signs in a 30-second read. Sales, labor, reviews, EBITDA, and weather. Invoke with /health.
---

# Business Health Scorecard (`/health`)

A single-page business vital signs report. Think of it as the CFO agent compressed to a 30-second read.

**Supabase project:** `zxqtclvljxvdxsnmsqka`
**All queries via:** `mcp__supabase__execute_sql`

---

## Invocation

- `/health` — Generate scorecard for today
- Natural language: "How's the business?", "Health score", "Business pulse"

---

## Step 1: Data Freshness Check

```sql
SELECT
  (SELECT MAX(order_date) FROM orders) AS latest_order,
  (SELECT MAX(labor_date) FROM labor_daily) AS latest_labor,
  (SELECT MAX(review_date::date) FROM reviews) AS latest_review;
```

If latest_order is more than 2 days ago, warn prominently.

---

## Step 2: Run All Queries (parallel)

**A. Sales (single-day comp: yesterday vs same DOW last year)**

**Methodology:** Always compare yesterday to the same day of week 52 weeks ago (364 days back). This matches Toast and MarginEdge. Never use rolling averages for comp reporting.

```sql
WITH yesterday_sales AS (
  SELECT order_date,
    TRIM(TO_CHAR(order_date, 'Day')) AS dow_name,
    TO_CHAR(order_date, 'Mon DD ''YY') AS date_label,
    ROUND(SUM(net_sales), 0) AS net_sales,
    COUNT(*) AS order_count
  FROM orders WHERE location_id = 'williamsburg'
    AND order_date = CURRENT_DATE - INTERVAL '1 day'
  GROUP BY order_date
),
wow_sales AS (
  SELECT order_date, ROUND(SUM(net_sales), 0) AS net_sales
  FROM orders WHERE location_id = 'williamsburg'
    AND order_date = CURRENT_DATE - INTERVAL '8 days'
  GROUP BY order_date
),
py_sales AS (
  SELECT order_date,
    TRIM(TO_CHAR(order_date, 'Day')) AS dow_name,
    TO_CHAR(order_date, 'Mon DD ''YY') AS date_label,
    ROUND(SUM(net_sales), 0) AS net_sales
  FROM orders WHERE location_id = 'williamsburg'
    AND order_date = (CURRENT_DATE - INTERVAL '1 day') - INTERVAL '364 days'
  GROUP BY order_date
)
SELECT
  y.order_date AS yesterday_date, y.dow_name AS yesterday_dow,
  y.date_label AS yesterday_label, y.net_sales AS yesterday_sales, y.order_count,
  w.net_sales AS wow_sales,
  ROUND(100.0 * (y.net_sales - w.net_sales) / NULLIF(w.net_sales, 0), 1) AS wow_pct,
  py.order_date AS py_date, py.dow_name AS py_dow, py.date_label AS py_label,
  py.net_sales AS py_sales,
  ROUND(100.0 * (y.net_sales - py.net_sales) / NULLIF(py.net_sales, 0), 1) AS yoy_pct
FROM yesterday_sales y, wow_sales w, py_sales py;
```

**Holiday awareness (must check after running the query):**

After getting the comp numbers, check whether yesterday or the PY comp date falls within 1 day of a major restaurant holiday. **"Within 1 day" includes the day AFTER a holiday** — day-after effects are real (e.g., the Tuesday after Presidents Day is not a normal Tuesday). **Do not call a date "normal" without checking the list below.**

In NYC, federal holidays where schools close significantly affect restaurant traffic (reduced office lunch, increased family/tourist traffic). Always check BOTH the current date AND the PY comp date.

Key holidays to check:
- MLK Day (3rd Monday of January)
- Presidents Day (3rd Monday of February)
- Valentine's Day (Feb 14)
- Easter Sunday (varies)
- Mother's Day (2nd Sunday of May)
- Memorial Day (last Monday of May)
- Father's Day (3rd Sunday of June)
- July 4th
- Labor Day (1st Monday of September)
- Super Bowl Sunday (1st Sunday of Feb)
- NYC Marathon Sunday (1st Sunday of Nov)
- Thanksgiving (4th Thursday of Nov)
- Christmas Eve / Christmas Day
- New Year's Eve / New Year's Day

Example callout: "Note: V-Day was Sat this year vs Fri last year, which shifts weekend traffic."
Example callout: "Note: PY comp date (Feb 18 '25) was the day after Presidents Day — not a normal Tuesday."

The goal is to **drive toward insight**. A -11% comp on the day after Valentine's means something completely different depending on when Valentine's fell. Surface that context automatically.

**B. Labor % (trailing 7 days, four-wall)**

This query calculates **four-wall labor %**, not just hourly wages. It takes 7shifts hourly labor and adds imputed daily costs for management salaries and payroll taxes/benefits, sourced from the most recent closed SystematIQ period.

**Why:** 7shifts only captures hourly clock-in wages (~19-20% of sales). Actual four-wall labor is ~30-33% when you include management salaries ($449/day for GM + Manager), payroll taxes (FICA, SUI, FUTA), and benefits (workers comp, health insurance, meal credits). These are real restaurant-level costs that don't change day to day, so we impute a daily rate from the most recent closed period.

**Note:** Social Media Manager wages ($137/week) are excluded from the management imputation because that's a corporate/marketing cost, not four-wall labor.

```sql
WITH sales AS (
  SELECT SUM(net_sales) AS net_sales FROM orders
  WHERE location_id = 'williamsburg'
    AND order_date > CURRENT_DATE - INTERVAL '7 days' AND order_date <= CURRENT_DATE
),
labor AS (
  SELECT SUM(actual_labor_cost) AS labor_cost, SUM(actual_hours) AS hours,
    SUM(COALESCE(overtime_hours, 0)) AS ot_hours
  FROM labor_daily WHERE location_id = 'williamsburg'
    AND labor_date > CURRENT_DATE - INTERVAL '7 days' AND labor_date <= CURRENT_DATE
),
-- Most recent closed SystematIQ period for imputed costs
latest_closed AS (
  SELECT f.fiscal_year, f.period_number, fp.num_weeks,
    SUM(CASE WHEN f.line_item = 'Management Wages Total' THEN f.amount END) AS mgmt_total,
    SUM(CASE WHEN f.line_item = 'Taxes and Benefits Total' THEN f.amount END) AS tax_ben_total
  FROM financials f
  JOIN fiscal_periods fp ON f.fiscal_year = fp.fiscal_year AND f.period_number = fp.period_number
  WHERE f.source = 'systematiq' AND f.location_id = 'williamsburg'
    AND f.statement = 'P&L' AND f.section = 'Labor'
    AND f.line_item IN ('Management Wages Total', 'Taxes and Benefits Total')
    AND f.channel = ''
  GROUP BY f.fiscal_year, f.period_number, fp.num_weeks
  ORDER BY f.fiscal_year DESC, f.period_number DESC
  LIMIT 1
)
SELECT
  -- Four-wall labor % (headline number)
  ROUND(100.0 * (l.labor_cost + 7 * (lc.mgmt_total - 137.0 * lc.num_weeks + lc.tax_ben_total) / (lc.num_weeks * 7))
    / NULLIF(s.net_sales, 0), 1) AS labor_pct,
  -- Hourly-only for operational context
  ROUND(100.0 * l.labor_cost / NULLIF(s.net_sales, 0), 1) AS hourly_labor_pct,
  ROUND(s.net_sales / NULLIF(l.hours, 0), 2) AS splh,
  l.ot_hours,
  -- Imputation source for transparency
  lc.fiscal_year AS imputed_from_fy,
  lc.period_number AS imputed_from_period
FROM sales s, labor l, latest_closed lc;
```

The `labor_pct` is the four-wall number to display. `hourly_labor_pct` is shown in parentheses for operational context (scheduling decisions). For the daily digest, do not render raw fiscal shorthand like `FY2025 P12`; if provenance matters, explain it in plain English.

**C. Food Cost % — REMOVED (Feb 2026)**

Food cost is excluded from the daily scorecard. MarginEdge invoice data is too lumpy and laggy for daily tracking (deliveries != consumption). Matt will revisit after inventory processes are established.

**D. Reviews (7-day trailing)**
```sql
SELECT COUNT(*) AS review_count,
  ROUND(AVG(rating), 2) AS avg_rating,
  COUNT(*) FILTER (WHERE rating <= 2) AS negative_count,
  COUNT(*) FILTER (WHERE rating >= 4) AS positive_count
FROM reviews
WHERE location_id = 'williamsburg'
  AND review_date::date > CURRENT_DATE - INTERVAL '7 days';
```

Also get 30-day trend for comparison:
```sql
SELECT ROUND(AVG(rating), 2) AS avg_rating_30d
FROM reviews
WHERE location_id = 'williamsburg'
  AND review_date::date > CURRENT_DATE - INTERVAL '30 days';
```

**D2. Reviews (daily digest variant — last 24 hours)**

When called from the daily digest, use a 24-hour window for the "new" count:
```sql
SELECT COUNT(*) AS review_count_24h,
  ROUND(AVG(rating), 2) AS avg_rating_24h,
  COUNT(*) FILTER (WHERE rating <= 2) AS negative_count_24h
FROM reviews
WHERE location_id = 'williamsburg'
  AND review_date::date = CURRENT_DATE - INTERVAL '1 day';
```

Still run the 7-day query (D) for the average rating and trend comparison. But report the COUNT as yesterday's reviews only. The daily digest should only show what's genuinely new since the last digest.

**E. EBITDA (MTD estimate from v_weekly_pl_summary or financials)**
```sql
SELECT fiscal_year, period_number,
  SUM(CASE WHEN line_item = 'TOTAL NET SALES' THEN amount END) AS net_sales,
  SUM(CASE WHEN line_item ILIKE '%ebitda%' OR line_item = '4-Wall EBITDA' THEN amount END) AS ebitda,
  ROUND(100.0 * SUM(CASE WHEN line_item ILIKE '%ebitda%' OR line_item = '4-Wall EBITDA' THEN amount END) /
    NULLIF(SUM(CASE WHEN line_item = 'TOTAL NET SALES' THEN amount END), 0), 1) AS ebitda_margin
FROM financials
WHERE location_id = 'williamsburg' AND channel IS NULL
GROUP BY fiscal_year, period_number
ORDER BY fiscal_year DESC, period_number DESC LIMIT 1;
```

**F. Weather (today + conditions)**
```sql
SELECT weather_date, temp_high_f, temp_low_f, precip_inches, conditions, description
FROM weather
WHERE location_id = 'williamsburg'
  AND weather_date >= CURRENT_DATE
ORDER BY weather_date LIMIT 3;
```

---

## Step 3: Calculate Health Score

**Total: 100 points**

### Sales Trend (30 points) — based on single-day comps
- WoW (yesterday vs same DOW prior week): +12 if >+5%, +6 if 0-5%, 0 if -5 to 0%, -5 if < -5%
- YoY (yesterday vs same DOW 52 weeks ago): +18 if >+5%, +12 if 0-5%, +6 if -5 to 0%, 0 if < -5%
- If a major holiday shift affects the comp, note it but still score on the raw number
- No YoY data available: use 10 (neutral)

### Labor Efficiency (25 points)
- Four-wall labor % vs 33% target (based on FY2025 average of ~32%):
  - <30%: 25 (excellent, only in high-sales periods)
  - 30-33%: 18 (healthy)
  - 33-36%: 10 (watch)
  - >36%: 5 (flag)
- Adjust -3 for OT hours > 20/week

### Customer Satisfaction (25 points)
- Review rating: +12 if avg >= 4.3, +8 if 4.0-4.3, +4 if 3.5-4.0, 0 if < 3.5
- Trend: +6 if 7d avg >= 30d avg, +3 if within 0.1, 0 if declining
- Negative reviews: +7 if 0, +4 if 1, 0 if 2+
- No reviews in 7 days: use 12 (neutral)

### Operational Health (20 points)
- OT hours < 10/week: +12, 10-20: +6, >20: 0
- Weather-adjusted: +8 if no adverse weather, +4 if minor, 0 if severe (heavy rain/snow)

---

## Step 4: Format Output

```
BUSINESS HEALTH — {Day} {Month} {Date}, {Year}
Data through: {latest_order_date}

SALES      ${yesterday_sales} yesterday ({yesterday_dow})  {arrow} {yoy_pct}% YoY (vs {py_dow} {py_label})
           {arrow} {wow_pct}% WoW
           {holiday_note_if_any}
LABOR %    {labor_pct}% four-wall ({hourly_labor_pct}% hourly)  {status} (target: <33%)
REVIEWS    {avg_rating} avg (7d, {count} new)  {trend}
EBITDA     ${ebitda} (P{XX}, {margin}%)   {status}
WEATHER    {conditions} {high}F/{low}F    {impact}

HEALTH SCORE: {score}/100
{One sentence: what matters most right now}
```

**Arrow symbols:**
- Up trend (positive): use "^" or "up"
- Down trend (negative): use "v" or "down"
- Flat: use "~" or "flat"

**Status labels:**
- HEALTHY: metric within target
- WATCH: metric near boundary
- FLAG: metric outside target

**Trend labels for reviews:**
- IMPROVING: 7d avg > 30d avg
- STABLE: within 0.1
- DECLINING: 7d avg < 30d avg

**EBITDA status:**
- AHEAD: margin > 18%
- ON TRACK: margin 15-18%
- BEHIND: margin < 15%

**Weather impact:**
- "No impact expected" if clear and moderate temps
- "Minor impact" if light rain or cold (<35F)
- "Sales impact likely" if heavy rain, snow, or extreme cold (<25F)

---

## Step 5: The One Sentence

Write a single sentence that captures the most important thing for Matt to know right now. Examples:

- "Sales momentum is strong but labor is creeping up — watch scheduling this week."
- "Reviews took a hit with 2 negatives on service wait times — may need floor coverage."
- "Solid across the board. Keep doing what you're doing."
- "Rain forecast Wed-Fri will likely dip dine-in 10-15% — lean into delivery marketing."

This sentence is the most valuable part of the scorecard. Be specific and actionable.

---

## Compact Mode (for Daily Digest)

When called from the daily digest automation, output the compact version:

``` 
**Sales** ${yesterday_sales} yesterday ({yesterday_dow})
{arrow}{yoy_pct}% YoY vs {py_dow} {py_label}
{one short context line only when relevant: holiday adjacency, weather distortion, or one clear outlier driver}

**Labor** {labor_pct}% four-wall · {hourly_labor_pct}% hourly
{status} (target <33%) or a plain-English freshness warning if labor inputs are stale}

**Reviews** {avg_rating_7d} avg · {count_24h} new yesterday · {negative_count_24h} negative
{TREND vs 30d: IMPROVING/STABLE/DECLINING}

**Weather** {conditions} {high}F/{low}F today
{include only if weather is operationally unusual}

---

**Health Score: {score}/100**
Sales {x}/30 · Labor {x}/25 · Reviews {x}/25 · Ops {x}/20

{1-2 short lines max. Keep the Health Score section to 3-4 lines total.}
```

The sales line must show the **single-day comp** (yesterday vs same DOW 52 weeks ago), NOT a 7-day rolling average. This must match what Toast and MarginEdge show. Do not include WoW by default.

The average rating uses the 7-day window (more stable). The "new" count uses the 24-hour window (D2 query). This way the digest only reports what's genuinely new since the last digest.

If a holiday shift is relevant, add a one-line note (e.g., "V-Day was Sat this year vs Fri last year"). Only include when a holiday is within 1 day of either comp date.

If the YoY move is large, keep the diagnosis to one concise line and name the dominant driver from the comp-driver data: catering, large order, channel mix, or weather distortion.

For negative reviews: if there are negatives in the 24h window, add the top complaint theme on the trend line, e.g., "STABLE (1 negative on service wait time)". If no negatives, just show the trend.

---

## Error Handling

- If Supabase is unreachable, report "Data unavailable — Supabase connection failed"
- If a specific query fails, use neutral scores for that category and note which metric is unavailable
- If no reviews in the last 7 days, say "No new reviews (7d)" and use 30d data for the score
- If EBITDA financials are stale (>45 days), note the period and say "Financials through P{XX}"
