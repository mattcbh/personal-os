---
name: budget-tracker
description: Generate a standalone HTML budget tracker dashboard with Tufte-compliant data visualizations. Use when Matt asks to create, update, or rebuild a budget tracker for a construction project or any cost-tracking scenario.
---

# Budget Tracker Dashboard Skill

## When to Use

Trigger on: "budget tracker", "budget dashboard", "cost tracker", "build a tracker for [project]", or when updating an existing budget tracker HTML file.

## Core Principles (Tufte Data-Ink Ratio)

For the complete data visualization style guide (all Tufte principles), see `core/context/data-visualization.md`. The rules below are budget-tracker-specific applications.

Every pixel of color on a chart MUST encode data. No exceptions.

### Rules

1. **No decorative fills.** Never use background colors on bar tracks, chart areas, or unfilled portions of bars. If a region doesn't represent a data value, it should be transparent or white.
2. **No ghost blocks.** In waterfall charts, the space below a floating increment is empty (transparent), not a faded version of a previous bar.
3. **No cream rectangles.** A bar that extends beyond its data fill is chartjunk. The bar ends where the data ends.
4. **Direct labeling.** Label data points directly on or adjacent to the visual element. Minimize reliance on legends. When a legend is used, every item must correspond to a visible data encoding.
5. **Two bars, not three layers.** For budget-vs-actual comparisons, use two distinct thin bars (budget above, actual below) rather than overlapping fills on a single bar.

## Chart Patterns

### 1. Paired Bar Chart (Budget vs Actual)

Each row shows two thin horizontal bars stacked vertically:

```
Trade Name    [████████████] $18.5K Budget
              [████████████████] $19.0K Actual    +$500 (+3%)
```

- **Budget bar:** Light fill (e.g., `rgba(brand-color, 0.25)`). Labeled "Budget" at right edge.
- **Actual bar:** Color-coded by variance severity (green/amber/red). Labeled "Actual" at right edge.
- **No background** on either bar track. Bars render against the white card.
- **New scope items** (no budget to compare): Show single bar labeled "New Scope."
- **Grid:** `[name] [bars] [delta]` — fold completion status into the trade name as a `<small>` note.

### 2. Waterfall Chart (Cost Bridge)

Each increment bar floats at the correct running total level:

```
[First bar: solid from 0 to base amount]
[Increment bars: colored delta floating above transparent spacer]
[Final bar: solid from 0 to total]
```

- **First and last bars:** Solid fill from baseline (0) to their value.
- **Increment bars:** Two elements stacked in a flex column:
  1. Colored delta block (top) — the increment amount
  2. Transparent spacer (bottom) — height equals the running total before this increment
- **Connector lines:** Thin dashed horizontal lines between bars at the running total level.
- **No ghost blocks.** The old pattern of fading previous values as background is banned.
- **Animation:** Use opacity fade-in (`bridgeReveal`), not `scaleY` (which distorts floating blocks).

### 3. Comparison Bars

Simple filled rectangles on a white background:

```
OSD $315K     [████████████████████]
Cocozza $452K [██████████████████████████████]
```

- **No background fill** on the bar track. Bar ends where the fill ends.
- **Primary bar:** Solid brand color (oxblood).
- **Reference bar:** Solid muted color (e.g., `var(--border)` gray).
- **Labels:** Directly inside or adjacent to each bar.

### 4. Spectrum/Range Bar

A gradient fill showing where a value sits on a scale:

- **Track:** Transparent with a subtle 1px border. NOT a thick colored rectangle.
- **Fill:** Gradient from green to amber (or appropriate range colors).
- **Markers:** Positioned absolutely with direct labels (no legend needed).

## Brand Defaults

Default to **Corner Booth Holdings** brand unless specified otherwise:

- **Primary:** Oxblood `#492216`
- **Background:** Oatmilk `#FFFBF2`
- **Headings:** EB Garamond (600 weight)
- **Body:** DM Sans or Inter
- **Status colors:** Green `#2d6a4f`, Amber `#c77d14`, Red `#b5291a`, Blue `#2a6f97`
- **Budget fill:** `rgba(73,34,22,0.25)` (light oxblood)

To override, read the appropriate brand file from `~/Obsidian/personal-os/brands/`.

## Input Format

The skill accepts either:
1. **A markdown tracker file** (e.g., `Knowledge/WORK/244-Flatbush-OSD-Project-Tracker.md`) — parse budget lines, EAs, invoices into structured data.
2. **Structured budget data** provided inline — trade names, budget amounts, actual amounts, status.
3. **An existing HTML dashboard** — read and update with new data while preserving the Tufte-compliant chart patterns.

## Output

A single standalone HTML file with:
- Embedded CSS (no external dependencies except Google Fonts)
- KPI summary cards
- Paired bar chart for trade-by-trade comparison
- Waterfall chart for cost bridge analysis
- Any additional comparison visualizations relevant to the data
- Key takeaways section
- Subtle animations (bar growth, fade-in) that don't distract from data

Save to: `Google Drive > 8- Agent Workspace > YYYY-MM/`

## Checklist

Before delivering the dashboard:
- [ ] Zero uses of decorative background fills on bar tracks
- [ ] All bars render against white/transparent backgrounds
- [ ] Waterfall increments float with transparent spacers (no ghost blocks)
- [ ] Every value label sits directly on or adjacent to its data element
- [ ] Legend items map 1:1 to visible data encodings
- [ ] Brand colors applied correctly
- [ ] File is self-contained (opens in any browser with no dependencies)
