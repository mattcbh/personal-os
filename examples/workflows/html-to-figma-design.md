---
name: html-to-figma-design
description: Build visual designs (presentations, email templates, dashboards) as HTML, capture to Figma via Code to Canvas, and deliver a shareable Figma link. Invoke when any design, deck, or visual output is requested.
---

# HTML-to-Figma Design Pipeline

Build any visual output as HTML, capture it into Figma, and deliver a shareable, commentable, exportable Figma file. The HTML is the source code. Figma is the compiled output.

## When to Use

- Slide decks and presentations (financial reviews, pitch decks, board materials)
- Email templates (Mailchimp campaigns, automated sequences)
- Visual designs (Wi-Fi capture pages, landing pages, one-pagers)
- Dashboards and scorecards
- Any visual that Matt needs to share, comment on, or export as PDF/PPTX

## Pipeline Overview

```
Matt: "Make the deck" / "Build the email template" / "Design the page"
    ↓
Step 1: Build HTML (source — saved to Agent Workspace)
    ↓
Step 2: Serve on localhost
    ↓
Step 3: Capture to Figma via Code to Canvas MCP
    ↓
Step 4: Deliver Figma link to Matt
    ↓
Matt: shares, comments, presents, exports from Figma
```

## Step-by-Step

### Step 1: Build the HTML

Create a standalone HTML file with everything self-contained (inline CSS, embedded fonts, SVG charts). No external dependencies except Google Fonts.

**File location:** Save to Google Drive Agent Workspace:
```
~/Library/CloudStorage/GoogleDrive-matt@cornerboothholdings.com/My Drive/
  Corner Booth Holdings/8- Agent Workspace/YYYY-MM/<descriptive-name>.html
```

**Design rules:**
- Load the appropriate brand guidelines before building. Default to CBH (`brands/cbh.md`). Use PnT (`brands/pnt.md`) or Heap's (`brands/heap's.md`) for portfolio company materials. Each brand file includes a Visual Asset Library section with Figma file keys and Google Drive paths -- use these to pull logos, characters, illustrations, and other visual elements.
- Follow the Tufte data visualization style guide (`core/context/data-visualization.md`) for any charts or data displays.
- Use Google Fonts (EB Garamond 600, Inter) loaded via `<link>` tag.
- Use SVG for charts (converts to native Figma elements better than canvas).
- High-contrast, clean layouts. No animations or hover states.

**For slide decks specifically:**
- **Start from the template:** Copy `examples/workflows/cbh-slide-template.html` and replace placeholder content. The template has all brand CSS, polygon shapes, and example layouts ready to go.
- Build each slide as a fixed-size div: `width: 1920px; height: 1080px`
- Give each slide a sequential ID: `id="slide-1"`, `id="slide-2"`, etc.
- Presentation-scale typography (headings 44-72px, body 18-22px, tables 16-20px)
- Page breaks between slides: `page-break-after: always`

**Figma capture rules (critical):**
- **No pseudo-elements.** The capture tool does not serialize `::before` or `::after` pseudo-elements. They are invisible in Figma.
- **No CSS transforms.** `transform: rotate()` and similar CSS transforms do not render in Figma.
- **No CSS backgrounds on empty divs.** Background colors/gradients on empty `<div>` elements may not capture. Use inline SVG instead.
- **Inline SVG works.** SVG elements (`<svg>`, `<polygon>`, `<rect>`, etc.) convert to native Figma vector nodes. This is the reliable method for decorative shapes.
- **Bounding box = frame size.** The capture tool measures the full DOM bounding box, ignoring `overflow: hidden` and `clip-path`. Any element positioned outside the slide bounds will expand the Figma frame beyond 1920x1080. Keep all elements within bounds.
- For the CBH diagonal accent shapes, use inline SVG polygons. See the template at `examples/workflows/cbh-slide-template.html` for the exact polygon coordinates derived from David Rager's brand source files.

**For email templates:**
- The HTML is also the final deliverable (emails are HTML). Figma is the review/approval layer.
- Follow email-safe HTML conventions (tables for layout, inline styles, 600px max-width).
- After approval in Figma, the HTML gets loaded into Mailchimp.

### Step 2: Serve on Localhost

Start a Python HTTP server from the Agent Workspace directory:

```bash
cd "~/Library/CloudStorage/GoogleDrive-matt@cornerboothholdings.com/My Drive/Corner Booth Holdings/8- Agent Workspace/YYYY-MM/"
python3 -m http.server 8888 &
```

Verify the file is accessible at `http://localhost:8888/<filename>.html`.

### Step 3: Capture to Figma

**3a. Inject the capture script** into the HTML file (temporarily):

Add before `</body>`:
```html
<script src="https://mcp.figma.com/mcp/html-to-design/capture.js" async></script>
```

**3b. Call `generate_figma_design`** with these parameters:
- `url`: `http://localhost:8888/<filename>.html`
- `outputMode`: `newFile`
- `figmaDelay`: `3000` (gives Google Fonts time to load)

**3c. Poll for completion.** The tool returns a capture ID. Poll status every 5 seconds until complete.

**3d. Retrieve the Figma claim URL.** Open it once to claim the file into Matt's Figma workspace.

**3e. Remove the capture script** from the HTML file. The script is only needed during capture.

### Step 4: Deliver

Provide Matt with:
1. **Figma link** — the shareable, commentable, presentable file
2. **File location** — where the HTML source lives in Agent Workspace (for reference)

If the design is part of a project, update the project brief's "Where Things Live" section with both the Figma link and HTML source path.

## Making Changes

**When Matt requests changes** (text edits, new data, layout tweaks):
1. Edit the HTML source file
2. Re-capture to Figma (creates a new Figma file)
3. Update the Figma link in the project brief if applicable
4. Deliver the new Figma link

Matt never needs to edit HTML directly. He describes the change, I handle the rest.

**If Matt edits directly in Figma:** Those changes live only in Figma and won't survive a re-capture. This is fine for one-off tweaks, but if the deck needs a full refresh later (new quarter's data, etc.), the HTML is the starting point and Figma-only edits won't carry over.

## Exporting from Figma

Matt handles exports from Figma when needed:
- **PDF:** File > Export slides to > PDF (for distribution)
- **PPTX:** File > Export slides to > PPTX (for Google Slides or PowerPoint)
- **Share link:** Click Share, set "Anyone with the link" to "can view"

These are manual steps in Figma (2-3 clicks each). The MCP tools don't support programmatic export.

## Sharing & Collaboration

Figma Slides supports:
- **Shareable links** — set "Anyone with the link" to "can view" for people without Figma accounts
- **Commenting** — team members can leave comments on specific slides
- **Co-presenting** — multiple people can present together
- **Real-time editing** — if collaborators have edit access

## File Hygiene

| File | Location | Purpose | Who maintains it |
|------|----------|---------|-----------------|
| HTML source | `8- Agent Workspace/YYYY-MM/` | Source code, used for iteration | Claude (never delete) |
| Figma file | Matt's Figma workspace | Shareable output | Claude creates, Matt shares/exports |
| PDF export | Project folder in Google Drive | Distribution copy | Matt exports from Figma |
| Project brief | `projects/<project>.md` | Links to all of the above | Claude updates |

## Figma Account Requirements

Matt's Figma Pro plan allows 200 MCP tool calls per day. Each capture uses a handful of calls. No practical constraint for normal use.

## Templates

| Template | File | Usage |
|----------|------|-------|
| CBH Slide Deck | `examples/workflows/cbh-slide-template.html` | Default for all CBH presentations. Includes brand polygons, typography, and 7 layout patterns (cover, two-column, three-column, pipeline, grid, code block). |

## Known Limitations

- **One-way pipeline.** Figma edits cannot flow back to HTML. The HTML is the source of truth for data and content.
- **No programmatic export.** PDF/PPTX export must be done manually in Figma.
- **Claim URLs.** Each capture generates a claim URL that must be opened once to add the file to Matt's workspace. The file can't be appended to via `existingFile` mode until claimed.
- **Font rendering.** Use `figmaDelay: 3000` (or higher) to ensure Google Fonts load before capture. Without the delay, text may render in fallback fonts.
- **Re-capture creates a new file.** Each capture produces a new Figma file. Old versions remain in Matt's workspace (can be deleted manually).
