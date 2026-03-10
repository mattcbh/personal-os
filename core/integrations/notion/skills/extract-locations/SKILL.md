---
name: extract-locations
description: Use when Matt asks to pull locations from email into the Notion location tracker, add real estate leads, or process broker emails from TSCG or other real estate contacts. Triggers on "pull in locations", "add to tracker", "location from email".
---

# Extract Locations from Email to Notion Tracker

Extract real estate location leads from Gmail and add them to the Notion Retail Locations database with attachments.

## Notion Target

- **Database:** Retail Locations (inside "Heap's & Pies Location Tracker Pipeline")
- **Data Source ID:** `985f6a0f-6656-43ae-be77-e0a14fe5d23b`
- **Tracker page:** `https://www.notion.so/10575b9df25380caa093f8e6f287cc56`

## Property Schema

| Property | Type | Notes |
|----------|------|-------|
| Address | title | Full address with cross-street |
| Brand | select | "Pies n Thighs" or "Heap's" |
| Borough | select | Manhattan, Brooklyn, Queens, Bronx, Staten Island |
| Neighborhood | select | Must match existing options (see database) |
| SqFt (Ground Floor) | number | |
| Basement | number | SF |
| Price / mo | number | Dollars |
| Status | status | Lead, Scheduling Visit, Visited, Offer, Closed, Declined |
| Owner | text | Broker name / firm |
| Key Money | number | If applicable |
| Origination Batch | date | Date email received |
| Place | place | If known |
| Price / Sq ft | number | Auto-calculated |
| Annual Rent | formula | Auto-calculated |
| AUV Target | formula | Auto-calculated |

## Workflow

1. **Search Gmail** for the email thread. Common senders: `@tscg.com` (Graci Goldstein), `@mrgrealestate.com` (Moshe Farhi), Jacqueline Klinger. Use `mcp__google__gmail_users_messages_list`.

2. **Read the email(s)** with `mcp__google__gmail_users_messages_get` to extract location details: address, sqft, rent, broker, neighborhood, and any commentary.

3. **Deduplicate thread images.** Email threads carry inline CID images forward from earlier messages. The same image can appear as an attachment in multiple emails with identical file sizes. **Compare attachment sizes across emails in the thread.** If two emails have images with the same byte count, they are the same image. Only download unique images and attribute each to the correct property/location.

4. **Download attachments** (photos, PDFs) with `mcp__google__gmail_users_messages_attachments_get`. Save to Google Drive `8- Agent Workspace/YYYY-MM/pnt-locations/`. Check file sizes to distinguish real property photos (>100KB) from email signature images (<10KB). Name files by address (e.g., `2740-broadway-1.png`, not `image002.png`).

5. **Read PDFs** for additional details (sqft, floor plans, broker info) not in the email body. PDFs often contain property photos (exterior, interior, floor plans) that may be the only photos available for that listing.

6. **Search for additional context.** For locations mentioned by name (e.g., "Jing Fong"), search Gmail history and `Knowledge/TRANSCRIPTS/` for prior conversations, tour notes, or forwarded listings that have more details or photos.

7. **Upload to Google Drive** via `mcp__google__drive_files_create` to get file IDs. Use `parentFolderId: "/Corner Booth Holdings/8- Agent Workspace/YYYY-MM/pnt-locations"`. Upload max 2-3 files per batch to avoid rate limits.

8. **Make files publicly accessible.** After uploading, set sharing permissions to "anyone with link can view" using the Google Drive API. Without this, embedded images in Notion won't render.

9. **Create Notion pages** with `mcp__notion__notion-create-pages`:
   - Parent: `{"data_source_id": "985f6a0f-6656-43ae-be77-e0a14fe5d23b"}`
   - Set all known properties from the schema above
   - Date format: `"date:Origination Batch:start": "YYYY-MM-DD"`, `"date:Origination Batch:is_datetime": 0`
   - Page content: Property details, broker contact, source attribution, embedded images/PDFs

10. **Embed images** in page content using Notion enhanced markdown.
    - **Images** (Drive): Use `lh3.googleusercontent.com/d/FILE_ID` — serves image content directly.
    - **PDFs** (Drive): Use `drive.google.com/uc?export=view&id=FILE_ID` — `lh3.googleusercontent.com` does NOT work for PDFs in Notion.
    - **External images** (e.g., Mailchimp CDN `mcusercontent.com`): use the direct URL.
    ```
    ![Caption](https://lh3.googleusercontent.com/d/FILE_ID)
    <pdf src="https://drive.google.com/uc?export=view&id=FILE_ID">Caption</pdf>
    ```

11. **Verify each page.** Fetch every created Notion page and confirm: (a) photos match the correct property, (b) property details are accurate, (c) images render.

## Page Content Template

```markdown
## Property Details

- **Former tenant:** [name]
- **Frontage:** [X] FT [wraparound/linear]
- **Ceiling height:** [X] FT
- **Vented:** Yes/No
- **Ground floor:** [X] SF
- **Basement:** [X] SF
- [Other notable features]

## Broker Contact

[Name], [Firm]

## Source

[Sender name] ([company]) email, [date]

## Photos

![Address - Description](https://lh3.googleusercontent.com/d/FILE_ID)
```

If the only photos are in a PDF setup sheet, embed the PDF and note it:

```markdown
## Setup Sheet (PDF)

<pdf src="https://drive.google.com/uc?export=view&id=FILE_ID">Address - Broker Setup Sheet</pdf>

## Photos

See Setup Sheet PDF above for exterior, interior, and neighborhood photos.
```

## Common Issues

- **Neighborhood not in select options:** Omit the property and note it in page content. Valid neighborhoods change; check the database schema first.
- **Email signature images:** Inline CID images under 10KB are usually logos/signatures. Only download images >100KB.
- **Google Drive rate limits:** Upload 2-3 files at a time, not all at once.
- **Multiple locations in one thread:** Read all emails in the thread. Matt may add locations in replies (e.g., "also check out Jing Fong").
- **Thread image duplication (CRITICAL):** Email threads carry forward inline images from earlier messages. A reply about Location B will have Location A's images as attachments with identical byte sizes. Always compare file sizes across emails to avoid putting the wrong photos on the wrong property page.
- **Google Drive URL formats:** Use `https://lh3.googleusercontent.com/d/FILE_ID` for **images** only. For **PDFs**, use `https://drive.google.com/uc?export=view&id=FILE_ID` — the `lh3.googleusercontent.com` format does not render PDFs in Notion even when publicly shared.
- **Files must be publicly shared:** After uploading to Drive, set "anyone with link" read permission. Otherwise Notion cannot display the embedded images.
- **Locations mentioned by name only:** When a location is referenced by business name (e.g., "Jing Fong") rather than address, search Gmail history and `Knowledge/TRANSCRIPTS/` for prior emails, tour notes, or listings with the correct address and details. Do not guess the address.
- **External image sources:** Broker newsletters (Mailchimp, Constant Contact) often have publicly accessible property photos at CDN URLs (e.g., `mcusercontent.com`). These can be embedded directly without uploading to Drive.
