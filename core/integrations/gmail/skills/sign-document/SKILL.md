# sign-document

Sign a PDF document, fill any required flat-form fields, and draft a reply email with the completed version attached.

## Usage

```
/sign-document
```

Then describe what you need, e.g.:
- "Sign the document from Darragh and send it back"
- "Sign the PDF from the latest OSD email"
- "Sign page 2 of the quote from Darragh near the bottom"

## Workflow

### Step 1: Find the email

Ask the user which email has the document, or search Gmail:

```
gmail_search with query like:
  - "from:darragh has:attachment filename:pdf" (most common case)
  - "from:<sender> has:attachment filename:pdf"
  - Or use a specific subject/thread the user mentions
```

Pick the most recent matching email. Show the user the subject, sender, and date to confirm.

### Step 2: Download the PDF attachment

```
gmail_read — get the email details including attachments
gmail_download_attachment — download the PDF to /tmp/sign-document/original.pdf
```

Save to a temp location: `/tmp/sign-document/original.pdf`

```bash
mkdir -p /tmp/sign-document
```

### Step 3: Inspect the PDF

Before signing, open and inspect the PDF to understand its layout:

```bash
python3 -c "
import fitz
doc = fitz.open('/tmp/sign-document/original.pdf')
for i, page in enumerate(doc):
    text = page.get_text()
    print(f'=== Page {i+1} ({page.rect.width}x{page.rect.height}) ===')
    print(text[:500])
    print()
"
```

Look for:
- Which page has a signature area
- Whether the PDF is a simple sign-only document or a flat form that needs typed fields
- Text like "Signature", "Sign here", "Authorized by", underlines
- Whether the user specified a page or location

### Step 3b: Gather context before filling anything

Read only the context you need:
- `core/context/family-form-profile.md` for canonical household form data, including legal names, address, DOBs, passports, and driver's licenses
- `core/context/people.md` for family relationships
- `core/context/health-insurance.md` for legal names / dependents
- The relevant project brief when the form is school-, camp-, or project-specific

Use Obsidian context to determine who the form is about. For example:
- Berkeley Carroll school forms usually point to Lily
- Family waivers may require Matt and/or Ellen as guardian names
- Passport and driver's license values should come from `family-form-profile.md` first, and only fall back to the referenced source documents there if needed

Guardrails:
- Never invent address, DOB, driver's license number, passport number, insurance IDs, or notary details
- Never sign for Ellen, Lily, Max, or anyone else unless the user explicitly asked and you have a real signature asset for that person
- If a form still requires manual fields after context lookup, stop and show Matt exactly what is missing before drafting any reply

### Step 4: Fill flat-form fields when needed

If the PDF needs typed fields beyond a basic signature/date, use the template-driven helper first:

```bash
FILL="~/Obsidian/personal-os/core/integrations/gmail/skills/sign-document/fill_form_pdf.py"

# See supported templates
python3 $FILL --list-templates

# Example: Berkeley Carroll waiver
python3 $FILL /tmp/sign-document/original.pdf /tmp/sign-document/filled.pdf \
  --template berkeley-carroll-wheels \
  --field student_name="Lily Lieber" \
  --field guardian_1_name="Matt Lieber" \
  --field guardian_1_email="matt@cornerboothholdings.com" \
  --field guardian_1_signature="~/Obsidian/personal-os/core/assets/signature.png"

# Example: Substance skate waiver
python3 $FILL /tmp/sign-document/original.pdf /tmp/sign-document/filled.pdf \
  --template substance-skate-park-waiver \
  --field participant_name="Lily Lieber" \
  --field street_address="..." \
  --field city="Brooklyn" \
  --field state="NY" \
  --field zip_code="11215" \
  --field phone="..." \
  --field email="..." \
  --field participant_signature="~/Obsidian/personal-os/core/assets/signature.png"
```

The helper prints a JSON report:
- `is_complete: true` means all required template fields were filled
- `missing_required_fields` means stop and show Matt what still needs to be provided or signed

Do not draft the reply while required fields are still missing unless Matt explicitly says to send back a partial form.

### Step 5: Sign simple PDFs (or fallback when no form template applies)

Run the signing script. **ALWAYS include `--add-date`** to stamp today's date on the document.

```bash
SCRIPT="~/Obsidian/personal-os/core/integrations/gmail/skills/sign-document/sign_pdf.py"

# Auto-detect signature location + stamp today's date
python3 $SCRIPT /tmp/sign-document/original.pdf /tmp/sign-document/signed.pdf --add-date

# Or with specific page
python3 $SCRIPT /tmp/sign-document/original.pdf /tmp/sign-document/signed.pdf --page 2 --add-date

# Or with explicit coordinates
python3 $SCRIPT /tmp/sign-document/original.pdf /tmp/sign-document/signed.pdf --coords 300,600,200,60 --add-date

# Or search for text
python3 $SCRIPT /tmp/sign-document/original.pdf /tmp/sign-document/signed.pdf --search "Signature" --add-date

# Explicit date coordinates (if auto-detect picks the wrong "Date:" field)
python3 $SCRIPT /tmp/sign-document/original.pdf /tmp/sign-document/signed.pdf --coords 370,470,180,54 --add-date --date-coords 384,577

# Reuse a saved template
python3 $SCRIPT /tmp/sign-document/original.pdf /tmp/sign-document/signed.pdf --template "darragh-quote" --add-date

# Save placement for future use
python3 $SCRIPT /tmp/sign-document/original.pdf /tmp/sign-document/signed.pdf --save-template "darragh-quote" --add-date
```

The `--add-date` flag auto-detects the "Date:" field closest to the signature's x-position and stamps today's date (e.g., "2/13/26"). Use `--date-coords x,y` to override if auto-detection picks the wrong field.

The script outputs JSON with the placement coordinates used:
```json
{"page": 2, "x": 350.0, "y": 620.0, "width": 180.0, "height": 54.0, "date": {"date_text": "2/13/26", "x": 384.2, "y": 576.8}}
```

If Step 4 produced `/tmp/sign-document/filled.pdf`, use that as the input file for any additional signature work. Otherwise sign `/tmp/sign-document/original.pdf` directly.

Keep track of the actual final file path:
- Flat-form only: `/tmp/sign-document/filled.pdf`
- Flat-form + extra signature pass: `/tmp/sign-document/signed.pdf`
- Simple sign-only document: `/tmp/sign-document/signed.pdf`

### Step 6: Verify the completed document

Read the completed PDF to visually confirm the text and signature placement look correct:

```bash
python3 -c "
import fitz
doc = fitz.open('/tmp/sign-document/signed.pdf')  # or filled.pdf if no extra signature step
for i, page in enumerate(doc):
    print(f'Page {i+1}: {page.rect.width}x{page.rect.height}, images={len(page.get_images())}')
"
```

Also read the completed PDF file directly to show Matt the result visually. Tell Matt what was filled, what was signed, and whether anything is still missing before drafting the reply.

### Step 6b: Save completed copy to Personal Downloads

**ALWAYS save the completed PDF to Google Drive** so Matt can access it:

```bash
GDRIVE=~/Library/CloudStorage/GoogleDrive-matt@cornerboothholdings.com/My\ Drive/Corner\ Booth\ Holdings/9-\ Personal\ Downloads
cp <completed_pdf_path> "$GDRIVE/<descriptive_filename>_signed.pdf"
```

Use a descriptive filename based on the document (e.g., `EA07_Painting_Upholstery_Millwork_2-11-26_signed.pdf`).

### Step 7: Draft the reply email

**IMPORTANT: Always draft, never send directly.** This skill is an exception to the normal "all drafts via Superhuman" rule because it needs to attach a signed PDF. Superhuman keyboard automation cannot handle file attachments, so we use `gmail_draft_reply` here. The draft will appear in Gmail (not in Superhuman's drafts folder), but Matt can still find it via the thread URL.

```
gmail_draft_reply(
    message_id=[original message ID from Step 1],
    body="Hi [name],\n\nSigned copy attached.\n\nBest,\nMatt",
    attachment=[completed PDF path from Step 6]
)
```

Keep the reply body short and casual (Matt's style).

The tool returns a `threadUrl` — share it so Matt can review the draft in the full thread context. Note: this draft lives in Gmail, not Superhuman, because of the attachment.

## Flat-Form Rules

- Prefer `fill_form_pdf.py` whenever the document has blanks for names, address, school info, guardian info, DOB, or license details
- Prefer `sign_pdf.py` only for simple sign/date overlays or when there is no known flat-form template yet
- Current supported flat-form templates:
  - `berkeley-carroll-wheels`
  - `substance-skate-park-waiver`
- If a new recurring form appears, add a template instead of hardcoding ad hoc coordinates in the skill text

## Required Stop Conditions

Do not proceed to drafting if any of the following are true:
- Required fields are still missing from the helper report
- The document requires a notary block, witness block, or ID number that is not already available
- The form needs another person's signature and you do not have an approved signature asset for that person
- The placement looks visually wrong on review

## Signature Placement Guide

The script tries these strategies in order:

1. **Text search** — Looks for "Signature", "Sign here", "Authorized by", underlines
2. **Underline detection** — Finds long `______` lines and centers signature on them
3. **Default** — Bottom-right of the last page (common for quotes/invoices)

**User overrides:**
- "Sign on page 2" → use `--page 2`
- "Sign near the bottom left" → use `--coords 60,700,180,54`
- "Sign next to where it says Approved" → use `--search "Approved"`

**Coordinate reference (Letter size page = 612 x 792 points):**
- Top-left: (0, 0)
- Bottom-right: (612, 792)
- Typical signature area: y between 600-750

## Templates

After signing a document type for the first time, save the placement:

```bash
python3 $SCRIPT input.pdf output.pdf --save-template "darragh-quote"
```

Future documents of the same type can reuse the placement:

```bash
python3 $SCRIPT input.pdf output.pdf --template "darragh-quote"
```

Templates are stored in `templates.json` next to the script.

## Dependencies

- Python 3 with PyMuPDF (`fitz`) — already installed
- Signature PNG at `~/Obsidian/personal-os/core/assets/signature.png`
- Flat-form helper at `~/Obsidian/personal-os/core/integrations/gmail/skills/sign-document/fill_form_pdf.py`
- Flat-form templates at `~/Obsidian/personal-os/core/integrations/gmail/skills/sign-document/form_templates.json`
- Custom Google MCP server (`~/mcp-servers/google/`) for Gmail tools
