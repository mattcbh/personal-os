## Financial Analysis Methodology

### Core Principle: Numbers First, Narrative Never

**Do not build a narrative.** Do not search for a story. Do not organize findings around themes. Start with the numbers, trace them across time, flag anomalies, and present what the data shows. Any narrative that emerges should be the reader's conclusion, not the analyst's framing.

The Project Carroll failure (Feb 2026) demonstrated what happens when five analysis agents build narratives instead of doing forensic work: $656K in credit card debt was hidden by artificially separating line items to fit a story, stale quarterly data was used because the "right" number wasn't checked, and a $1.2M coordinated balance sheet event was dismissed in one sentence because it didn't fit the narrative being constructed.

---

### Mandatory Rules for All Financial Analysis

#### 1. Always Use the Most Recent Data

Never use a stale quarterly snapshot when a more recent one exists. For every material figure reported:
- State which quarter/period the figure comes from
- Confirm it is the most recent available
- If using an older period for comparison, label it explicitly

#### 2. Trace Every Material Line Item Across All Available Periods

For any balance sheet item > $25K or any P&L line item > 5% of revenue:
- Show the value at every available time period (quarterly, monthly, whatever the data provides)
- Calculate the period-over-period change
- Flag any change > 25% in a single period
- Flag any sign reversal (positive to negative or vice versa)
- Flag any value that goes to zero from a material balance

**This is the single most important rule.** Snapshot analysis hides trends. The Q4 FY24 credit card zeroing was invisible in a Q4 FY25 snapshot but obvious in a time series.

#### 3. Use Totals Rows, Not Component Decomposition

When a source document (QuickBooks, Excel, etc.) provides a "Total for [Category]" row:
- **Always report the total row as-is.** Do not decompose it into sub-components and re-aggregate.
- If you need to show components, show them UNDER the total, not instead of it.
- Never separate a sub-item (e.g., "Amex") from its parent total (e.g., "Total Credit Cards") and report them as independent categories. This is how debt gets understated.

#### 4. Flag Anomalies Before Explaining Them

When you find something unusual:
- **Flag it prominently** with the raw numbers
- **Do NOT dismiss it** with a plausible explanation ("a large payment was made")
- **Do NOT minimize it** by framing it as routine
- List what COULD explain it, but mark each explanation as unverified
- Add it to the diligence question list

An unexplained anomaly is more valuable than a wrong explanation.

#### 5. Cross-Entity Pattern Detection

When analyzing multiple entities in the same corporate family:
- Look for simultaneous events across entities (e.g., all checking accounts zeroing in the same quarter)
- Look for amounts that net to zero across entities (intercompany transfers)
- Check if a pattern at one entity (e.g., Account 5800 at F&R) also appears at other entities
- Treat simultaneous cross-entity events as a single coordinated event requiring explanation

#### 6. Adversarial Posture for Due Diligence

When analyzing a potential acquisition or external party's financials:
- **Assume nothing is as presented.** Verify every material figure against the source data.
- **The seller's framing is not your framing.** If they call something "Amex Revolving Credit" and it's actually a sub-item of "Total Credit Cards," use the total.
- **Look for what's missing,** not just what's there. Missing line items, missing periods, missing entities are all signals.
- **Trace cash:** If a liability disappears, where did the cash come from to pay it? If cash appears, where did it come from?
- **Check sign conventions:** QuickBooks uses negative for some liabilities (credit cards, AP) and positive for others (long-term debt). Don't assume. Look at the account section.

#### 7. Present Periods Left-to-Right

Financial tables must present time periods as columns reading left-to-right (oldest to newest), not as rows reading top-to-bottom. This mirrors how financials are naturally read and compared. Every quarterly, monthly, or annual table should flow horizontally with the most recent period on the right.

#### 8. Separate Verified Facts from Inferences

In every analysis output, clearly distinguish:
- **VERIFIED:** Directly read from source data with citation (file, line number, column)
- **CALCULATED:** Derived from verified figures with formula shown
- **INFERRED:** Conclusions drawn from patterns (mark confidence level)
- **UNKNOWN:** Things we need but don't have

---

### Report Structure for Financial Analysis

When producing any financial analysis (due diligence, investment memo, acquisition review):

1. **Data Inventory** - What source files exist, what periods they cover, what's missing
2. **Time Series Tables** - Every material line item across all available periods, with changes
3. **Anomaly Register** - Every discontinuity, sign reversal, or unexplained event
4. **Cross-Entity Matrix** - How entities interact (intercompany, simultaneous events)
5. **Verified Debt/Liability Schedule** - Using totals rows from most recent period
6. **Open Questions** - What we can't determine from the data alone
7. **Summary** - Only AFTER all of the above is complete

The summary comes LAST. Not first. Writing the summary first creates the narrative bias that causes analytical errors.

---

### Specific Lessons from Project Carroll (Feb 2026)

These errors must never be repeated:

| Error | What Happened | Rule That Prevents It |
|-------|--------------|----------------------|
| Amex separated from CC total | Agent C reported "Amex Revolving" ($304K) and "Credit Cards" ($93K) as separate categories, hiding $656K | Rule 3: Use totals rows |
| Stale quarterly data | Used Q2/Q3 FY25 values in a Q4 FY25 analysis | Rule 1: Always use most recent |
| Dismissed anomaly | $1.2M credit card swing noted but explained away in one sentence | Rule 4: Flag before explaining |
| Missed cross-entity pattern | All checking accounts across 4 entities zeroed simultaneously | Rule 5: Cross-entity detection |
| Narrative over forensics | Five agents built stories instead of tracing numbers | Core Principle: Numbers first |
| Snapshot over time series | Reported single-quarter values without 8-quarter trend | Rule 2: Trace across all periods |

### Specific Lessons from V-Day Campaign Report (Feb 2026)

| Error | What Happened | Rule That Prevents It |
|-------|--------------|----------------------|
| Used `total_amount` instead of `net_sales` | Reported V-Day revenue as $19,700 (includes tax + tips) instead of $16,669 (net sales). Matt caught it because Toast dashboard showed $16,624. | **Always verify which column you're summing.** Toast `net_sales` = revenue. `total_amount` = what the customer paid (incl. tax/tip). See data-warehouse.md for full column definitions. |
| Presented numbers without cross-checking source | The $19,700 was never validated against what Matt sees in Toast. A 2-second sanity check would have caught a $3,000 discrepancy. | **Cross-check material figures against the source system.** If Toast says $16K and your query says $19K, something is wrong. |

---

### When This Context File Applies

Load and follow these rules whenever:
- Analyzing financial statements (P&L, Balance Sheet, Cash Flow) from any source
- Conducting due diligence on an acquisition target
- Reviewing QuickBooks, Excel, or CSV financial data
- Building investment memos or financial summaries
- The CFO agent is analyzing anomalies in PnT data

These rules complement, not replace, the CFO Agent's Financial Doctrine (which covers operational analysis philosophy). This file covers analytical methodology - HOW to look at numbers.
