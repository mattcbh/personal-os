## Data Visualization Style Guide

Comprehensive rules for all data presentation across CBH. Based on Edward Tufte's "The Visual Display of Quantitative Information." Load and follow when generating any chart, graph, dashboard, scorecard, or visual data presentation.

### Source & Philosophy

These principles come from Tufte's foundational work on data graphics. The dual aphorism that governs everything:

> "Graphical excellence is that which gives to the viewer the greatest number of ideas in the shortest time with the least ink in the smallest space."

> "Simplicity of design and complexity of data."

### The Five Principles (Tufte Ch. 4, p.105)

1. Above all else, show the data
2. Maximize the data-ink ratio
3. Erase non-data-ink, within reason
4. Erase redundant data-ink, within reason
5. Revise and edit

---

### Mandatory Rules

#### Data-Ink Ratio

- Every pixel of color must encode data
- No decorative fills, ghost blocks, background tracks
- A single bar encodes height 6 redundant ways (top line, bottom line, left line, right line, shading, height number). Erase 5 of 6.
- Bars end where the data ends. No cream rectangles behind unfilled bar portions.

#### Grids & Axes

- Dark grid lines are chartjunk. Mute or suppress entirely.
- Gray grids preferred over dark. Implicit grids (white gaps in bars) are best.
- Range-frames: frame lines extend only to measured data limits. Show actual min/max, not round numbers.
- Dot-dash-plot: marginal distributions replace frame ticks when useful.
- Data-based labels: show actual data values at axis endpoints, not round numbers.

#### Color

- Gray shades provide natural visual hierarchy. Prefer over color for encoding quantity.
- 10 shades of gray work effectively. Color ordering is ambiguous (except red = higher).
- If color is used, 5-10% of viewers are color-deficient. Blue can be distinguished by most. Never use red/green as the sole distinguishing contrast.
- Cross-hatching is chartjunk. Replace with shades of gray or direct labels.

#### Chartjunk Taxonomy (things that must never appear)

- Moire vibration (hatching patterns, herringbone fills)
- Dark grid lines
- The duck (decorative forms overtaking data structure)
- 3D/perspective effects ("boutique data graphics")
- Bilateral symmetry that doubles space without new information

#### Labels & Text

- Direct labeling on or adjacent to data elements. Minimize legends.
- Words spelled out (no abbreviations).
- Left-to-right reading direction (avoid vertical axis text when possible).
- Little messages on the graphic explain the data.
- Upper-and-lower case with serifs (not ALL CAPS sans-serif).
- Integrate text and graphic. Don't segregate them.

#### Never Use

- Pie charts ("a table is nearly always better than a dumb pie chart")
- 3D effects on any chart type
- Decorative background fills on chart regions
- Red/green as the sole distinguishing contrast
- Alphabetical ordering when data-value ordering is possible

---

### Chart Selection Guide

#### When to use a table instead of a graphic

- Exact values matter more than patterns (e.g., a P&L where the reader needs specific line-item dollars)
- Few numbers with many words (reference lookups, contact lists, schedules)
- Data presentation requires reference-like quality (supertable)
- Always order rows by data values, not alphabetically
- **Bias toward graphics.** Even small data sets (5-20 numbers) are often better as a bar chart or slope chart than a table. A table of quarterly revenue is less useful than a bar chart of the same data. Default to the graphic and only fall back to a table when exact values are the primary purpose.

#### When to use a graphic

- **Any time series data** (revenue, costs, margins over time). Always horizontal, length > height.
- Comparisons across categories (locations, channels, line items)
- Composition data (channel mix, cost breakdown). Use stacked bars.
- Trend detection (is this going up, down, or flat?)
- When the eye needs to detect relationships the mind can't hold
- **When in doubt, use a graphic.** A bar chart with direct labels gives the reader both the pattern AND the exact values.

#### Text-tables (hybrid)

- For 2-5 numbers with explanatory text
- Arrange type to facilitate comparison
- Order by data values or content, never alphabetically

---

### Specific Chart Patterns

#### Time Series

- Always horizontal orientation (greater length than height)
- Thin data lines, heavier than structural lines
- Money series: always use deflated/standardized units (real dollars, per capita)
- Show the data variation, not design variation
- If multiple series, each should have its own clear line of sight

#### Bar Charts

- Two thin bars for comparison (budget above, actual below). Not overlapping fills.
- White grid technique: gaps in bars serve as coordinate lines, more precise than ticks.
- Erase the box, vertical axis (except ticks), baseline where possible.
- No background fill on bar tracks. Bars render against white.

#### Small Multiples

- Same design, same scales across all frames
- All attention on data shifts, not design differences
- Shrunken, high-density. Use the Shrink Principle aggressively.
- Inevitably comparative, deftly multivariate

#### Slope Charts / Paired Comparisons

- Data spaced proportionally to values (not evenly)
- Connecting lines show direction and magnitude of change
- Names/labels directly on the chart, not in a legend

---

### Data Density

- Data density = number of entries in data matrix / area of graphic
- Most published graphics are data-thin (~10 numbers/sq inch)
- Target: maximize within reason. Maps achieve 100K+ bits/sq inch.
- The Shrink Principle: graphics can be reduced to half their published size with no loss in legibility
- "More information is better than less information"

---

### Graphical Integrity

- **Lie Factor** = size of effect in graphic / size of effect in data. Should be between 0.95 and 1.05. Above 1.05 or below 0.95 = substantial distortion.
- Show data variation, not design variation
- Deflate currency (always use real/constant dollars for time series)
- Number of information-carrying dimensions should not exceed dimensions in the data
- Don't quote data out of context
- Label all axes and cite data sources

---

### The Friendly Data Graphic (Tufte's Summary Table)

| Friendly | Unfriendly |
|----------|-----------|
| Words spelled out | Abbreviations requiring decoding |
| Left-to-right reading | Vertical text, multiple directions |
| Messages explain the data | Cryptic, repeated text references |
| Labels on graphic itself | Requires going back and forth to legend |
| Attracts, provokes curiosity | Repellent, chartjunk-filled |
| Color-blind accessible (blue distinguishable) | Red/green for essential contrast |
| Clear, precise type; serifs | Clotted, overbearing type |
| Upper-and-lower case | All capitals, sans serif |

---

### Aesthetics

- Good design = simplicity of design + complexity of data
- Lines should be thin (copper-plate engraving weight)
- Heavier line weight for data measures, lighter for structure/connectors
- Graphical elements in visual balance and proportion
- Three viewing depths: (1) distance: overall structure, (2) close: fine data, (3) implicit: what's behind the graphic

---

### CBH-Specific Applications

#### Health Scorecard / Weekly Flash

- Use small multiples for multi-metric comparisons (sales, labor, food cost)
- Range-frames showing actual data bounds, not round numbers
- Direct labeling of all KPIs. No legend decoding.
- Gray for structural elements, brand color (oxblood) for data-ink only

#### Financial Analysis (P&L, Balance Sheet)

- **Default to graphics, not tables.** Revenue trajectories, cost trends, and margin evolution are best shown as bar charts, line graphs, or stacked bars. Tables should be the exception, not the rule.
- Use tables only when exact figures matter more than patterns (e.g., a detailed P&L where the reader needs specific line-item values), or for small reference data (5-10 numbers).
- For time series data (revenue by quarter, NOI trajectory, channel mix over time): always use a graphic. Bar charts for absolute values, line graphs for trends, stacked bars for composition.
- Order by magnitude, not chart of accounts number
- Deflate to real dollars for multi-year comparisons
- Time periods as columns, reading left-to-right (oldest to newest). Never stack periods as rows reading top-to-bottom.
- **Balance rule:** A financial presentation should have at least as many graphics as tables. If you find yourself with 5+ tables and no charts, something is wrong.

#### Campaign Reports

- Paired bars for YoY comp (this year above, last year below)
- Direct labeling of delta (amount and percentage)
- No decorative fills. Bars against white background.

#### Budget Trackers

- See budget-tracker skill for detailed patterns
- Waterfall charts with transparent spacers (no ghost blocks)
- White grid technique for precise value reading

---

### When This File Applies

Load and follow when:
- Generating any chart, graph, or data visualization (HTML, Excalidraw, or inline)
- Building dashboards or scorecards
- Creating financial reports with visual elements
- The budget-tracker, health-scorecard, cfo-agent, or frontend-design skills are active
- Any skill outputs data in visual form
