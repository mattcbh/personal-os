# Figma Integration Setup Status

**Last Updated:** 2026-02-03

## Completed

- [x] Added `figma-read` MCP (official Figma MCP for read access)
- [x] Created `/figma-design` skill at `~/Obsidian/personal-os/core/integrations/figma/skills/figma-design/SKILL.md`
- [x] Created symlink at `~/.claude/skills/figma-design`
- [x] Installed Figma Console plugin in Figma Desktop
- [x] Set up Figma Console MCP OAuth at https://figma-console-mcp.southleft.com
- [x] **Fixed figma-console MCP connection** (was not properly added before)
  - Used mcp-remote workaround due to Claude Code SSE/OAuth bug
  - Command: `claude mcp add figma-console -s user -- npx -y mcp-remote@latest https://figma-console-mcp.southleft.com/sse`
  - OAuth completed successfully

## Current MCP Status (as of 2026-02-03)

All three Figma MCPs are connected:
- `figma-console` - Write capabilities (create variables, execute plugin code, manipulate nodes)
- `figma-read` - Official Figma MCP (read-only)
- `figma` - Official Figma MCP (read-only, duplicate of figma-read)

## Next Steps

1. **Restart Claude Code session** to load figma-console write tools
   - Tools like `figma_create_variable`, `figma_execute` won't be available until restart

2. **Create P&T Brand Guidelines file in Figma:**
   - Either create manually in Figma, or use figma-console tools after restart
   - Brand assets are in Google Drive: `Corner Booth Holdings/2- Pies n Thighs/PIES Brand/`
   - Brand PDF (25MB): `PiesNThighs-Brand-Guide.pdf`
   - Graphic assets folder: `PiesNThighs-Graphic Assets/`

3. **Once brand file exists, configure the skill:**
   - Provide the Figma file URL
   - Extract file key and update skill config

## Brand Assets Inventory

Located at: `~/Library/CloudStorage/GoogleDrive-matt@cornerboothholdings.com/My Drive/Corner Booth Holdings/2- Pies n Thighs/PIES Brand/PiesNThighs-Graphic Assets/`

- **FONTS/** - E-phemera Mooseheart.otf, Metallophile Sp8 1.005
- **PNT-LOGOS/** - Primary stacked logo, horizontal logo, secondary variations
- **ILLUSTRATION/** - Pig illustrations, decorative elements, food imagery
- **LETTERING/** - Happy hour, menu lettering, brush titles
- **PNT-CHARACTERS/** - Character illustrations
- **PNT-STOREFRONT/** - Storefront graphics
- **PNT-TAPE-STICKERS-LABELS/** - Label designs
- **MENUS/** - Menu designs
- **PNT-ACCOLADES/** - Press/awards graphics
- **PNT-BROCHURE-TENT/** - Brochure designs
- **PNT-EXTERIOR-SIGN/** - Signage

## Brand Colors (from logo)

- **Coral Red** - Primary accent (exact hex TBD from brand guide)
- **Warm Brown** - Main text/shadow color (exact hex TBD from brand guide)
- **White/Cream** - Background

## Completed (2026-02-04)

- [x] Create brand guidelines Figma file
- [x] Extract exact hex colors from brand guide PDF
- [x] Upload fonts to Figma
- [x] Import key assets as components
- [x] Set up Figma Variables for brand colors
- [x] Renamed all accolades with quote + source format
- [x] Added FIGMA_ACCESS_TOKEN to figma-console MCP config

## API Access Setup

Token added to `~/.claude.json` under `mcpServers.figma-console.env.FIGMA_ACCESS_TOKEN`

**Important:** File must be shared ("Anyone with link can view") for API to access it.

**Test after restart:**
```
Test the Figma API access by getting the brand colors from the PnT brand guidelines file
```

## MCP Commands Reference

```bash
# Check MCP status
claude mcp list

# The correct command for figma-console (uses mcp-remote workaround):
claude mcp add figma-console -s user -- npx -y mcp-remote@latest https://figma-console-mcp.southleft.com/sse

# DO NOT use native SSE transport (has OAuth reconnect bug):
# claude mcp add figma-console --transport sse https://figma-console-mcp.southleft.com/sse
```
