## Email Contacts — Sender Classification

Single source of truth for email sender tiers. Referenced by `/cos triage` and `email-triage-prompt.md`.

**Matching rules (in order):**
1. Exact email match
2. Domain match (any sender @domain)
3. Content analysis for unknown senders (check project briefs, meeting history)

**Identity guardrails (mandatory):**
- Never merge people using first name only.
- Email address is the canonical identity key.
- If two records have different emails/domains, treat them as different people unless explicit evidence proves they are the same.

| Ambiguous Name | Canonical Email(s) | Correct Identity |
|---|---|---|
| Amit Shah | amitmshah74@gmail.com | Engineer introduced by Alex Blumberg (not Kern + Lead) |
| Amit Savyon | amit@kernandlead.com | Kern + Lead (marketing/customer segmentation) |
| Mav Placino | mav@cornerboothholdings.com, mav@heapsicecream.com | Matt's executive assistant |

---

### Tier 1 — Inner Circle

ACTION NEEDED only when there is an explicit ask, question, or request. Status updates and informational emails are FYI (or COURTESY RESPONSE). Sender tier alone never auto-upgrades classification. Alert in monitor only if urgency signals present.

| Name | Email / Domain | Context |
|------|---------------|---------|
| Ellen McCrum | ellen.mccrum@gmail.com | Matt's wife |
| Sarah Sanneh | sarah@piesnthighs.com | PnT partner |
| Jason Hershfeld | jason@cornerboothholdings.com | CBH partner |
| Jeff Phillips | jeff@piesnthighs.com | PnT operations lead |
| Mav Placino | mav@cornerboothholdings.com, mav@heapsicecream.com | Matt's executive assistant |
| Max Lieber | — | Matt's son |
| Lily Lieber | — | Matt's daughter |
| Bubba & Jiji (Ellen's parents) | — | Family |

---

### Tier 2 — Key Business

ACTION NEEDED only when there is an explicit ask, question, or request. Informational emails and status updates are FYI regardless of sender tier. Alert in monitor if urgency signals present. (Exception: Tier 2 Personal contacts below — implicit action patterns like overdue balances, payment due, enrollment deadlines also qualify as ACTION NEEDED.)

**Legal & Tax**

| Name | Email / Domain | Context |
|------|---------------|---------|
| Freedman Wang | freedman.wang@integrusfirm.com | Primary tax contact (Integrus) |
| Regan Dally | regan.dally@integrusfirm.com | Estimated taxes (Integrus) |
| Jay Anand | jay.anand@integrusfirm.com | Managing Partner (Integrus) |
| John Heintz | — | Senior Associate (Integrus, personal tax docs) |
| *@integrusfirm.com | Domain match | Integrus firm (tax/accounting) |

**Construction & Architecture (Park Slope)**

| Name | Email / Domain | Context |
|------|---------------|---------|
| Darragh O'Sullivan | — | GC, OSD Builders (Park Slope buildout) |
| *@osdbuilders.com | Domain match | OSD Builders |
| Marc McQuade | — | Architect, Background Office (ABO) |
| Abraham | — | ABO, works with Marc |
| *@backgroundoffice.com | Domain match | Background Office architecture |
| Phil | — | Singer equipment |

**Real Estate**

| Name | Email / Domain | Context |
|------|---------------|---------|
| Jacqueline Klinger | — | TSCG, strategic real estate advisor |
| Ian Rice | — | TSCG, space sourcing |
| Graci Goldstein | — | TSCG, active listings and tours |
| Kyle Francis | kyle@picnicgroup.com | Picnic Group (restaurant strategy, acquisition advisor, DC market) |
| Alan Clifford | — | Picnic Group (forwarded UWS lead) |
| Eric Beegun | — | Retail Development Partners (former Sweetgreen director of RE development) |
| *@tscg.com | Domain match | The Shopping Center Group |

**Marketing & Creative**

| Name | Email / Domain | Context |
|------|---------------|---------|
| Sophie Jardine | — | Mona Creative, press/marketing lead |
| Emily Koh | — | Mona Creative VP |
| Ali Goldberg | — | Mona Creative |
| Park Slope Living | — | Local Park Slope media contact/outlet. Coverage and interview coordination are FYI unless there is a direct ask for Matt. |
| *@monacreative.com | Domain match | Mona Creative agency |
| Andrew Tupper | andrew@kernandlead.com | Kern + Lead (email/digital marketing) |
| Amit Savyon | amit@kernandlead.com | Kern + Lead (customer segmentation) |
| *@kernandlead.com | Domain match | Kern + Lead agency |

**Brown Bag Sandwich Co.**

| Name | Email / Domain | Context |
|------|---------------|---------|
| Gilli Rozynek | — | Brown Bag owner |
| Tony (Antonio Barbieri) | — | Brown Bag founder |
| Daniel Gulati | — | Deal advisor |

**Project Carroll / Court Street Grocers**

| Name | Email / Domain | Context |
|------|---------------|---------|
| Alec Sottosanti | alec@courtstreetgrocers.com | CEO, Back-House (CSG financial review lead) |
| Matt Ross | matt@courtstreetgrocers.com | CSG co-owner |
| Eric Finkelstein | eric@courtstreetgrocers.com | CSG co-owner |
| Matt Wagman | — | Former CSG employee/consultant |
| Shannon | — | Back-House team (works with Alec) |
| *@courtstreetgrocers.com | Domain match | Court Street Grocers |

**Investments**

| Name | Email / Domain | Context |
|------|---------------|---------|
| William Gadsden | gadsden@garnettstation.com | Garnett Station Partners COO, investor relations |
| *@garnettstation.com | Domain match | Garnett Station Partners (investor fund). Always important, never FYI/marketing. PDFs are must-reads. |

**Finance & Insurance**

| Name | Email / Domain | Context |
|------|---------------|---------|
| *@cornerboothholdings.com | Domain match | CBH team |
| *@piesnthighs.com | Domain match | PnT team |

**Vendors & Services**

| Name | Email / Domain | Context |
|------|---------------|---------|
| Austin Thompson | — | Former automation contractor (engagement ended Feb 2026) |
| Tara Fdaee | tara.fdaee@toasttab.com | Toast account representative (PnT Park Slope). Human vendor reply, not marketing. |
| Toast support | *@toasttab.com | POS system |
| 7shifts | *@7shifts.com | Labor scheduling |
| MarginEdge | *@marginedge.com | Food cost platform |
| Bill.com | *@bill.com | AP/expenses |

**Personal (Home)**

**Implicit action classification:** Same rule as Personal (Bat Mitzvah / School / Camp) above — emails with implicit action patterns (overdue, past due, balance due, payment required, payment due, etc.) are ACTION NEEDED even without an explicit ask.

| Name | Email / Domain | Context |
|------|---------------|---------|
| Franklin Goldsmith | — | Friend (Tania's husband). Social invitations are important, never FYI. |
| Sasha Tsakh | sasha@gthvacp.com | Absolute Mechanical (633 2nd St HVAC/boiler maintenance) |
| *@gthvacp.com | Domain match | Absolute Mechanical / GTH VACP |
| *@tradifyhq.com | Domain match | Tradify (Absolute Mechanical quoting system) |

**Personal (Bat Mitzvah / School / Camp)**

**Implicit action classification:** Emails from these Personal contacts that contain implicit action patterns (overdue, past due, balance due, outstanding balance, amount due, payment required, payment due, tuition due, fee due, unpaid, enrollment deadline, registration deadline, forms to complete, forms due, response required, confirm attendance, RSVP by) should be classified as ACTION NEEDED even without an explicit ask. Newsletters, calendars, and general updates remain FYI.

| Name | Email / Domain | Context |
|------|---------------|---------|
| Rana Bickel | rbickel@cbebk.org | B'nei Mitzvah coordinator |
| Zach Rolf | zrolf@cbebk.org | Director of Yachad |
| Leslie Goldberg | lgoldberg@cbebk.org | Cantorial intern (bat mitzvah prep) |
| Celia Tedde | cmtedde@gmail.com | Weekly tutor |
| *@cbebk.org | Domain match | Congregation Beth Elohim |
| Kate Mollica | kmollica@berkeleycarroll.org | Music teacher, Berkeley Carroll (LaGuardia prep) |
| Emily Schoelzel | emily@keewaydin.org | Keewaydin camp director |
| John Frazier | john@keewaydin.org | Keewaydin asst director |
| Annette Franklin | annette@keewaydin.org | Keewaydin office manager |
| Ann Greenamyre | ann@keewaydin.org | Keewaydin business manager |
| Rebecca Black | — | CBE Mitzvah Project coordinator |
| Miranda Sielaff | mirandasielaff@gmail.com | Viola teacher (Diller-Quaile), LaGuardia prep |
| Earl Maneein | earlmaneein@gmail.com | Viola teacher (LaGuardia alum) |
| *@keewaydin.org | Domain match | Keewaydin camp |

**Trip Planning (Downing Mountain — P1 through March 27)**

| Name | Email / Domain | Context |
|------|---------------|---------|
| John Lehrman | johnlehrman@gmail.com | Downing Mountain Lodge owner |
| Morgan Comey | morgan.comey@gmail.com | Touring mentor (ski trip) |
| Ben Pomeroy | — | Ski trip participant, experienced backcountry skier |
| Willy Oppenheim | — | Ski trip participant |
| Willing Davidson | — | Ski trip participant |

---

### Tier 3 — Professional Network

FYI unless addressed directly to Matt. No monitor alerts.

| Name | Email / Domain | Context |
|------|---------------|---------|
| David Rager | — | Weekends Studio (CBH brand design) |
| Ben Pomeroy | — | Friend, ski trip (temporarily elevated to Tier 2 Trip Planning through March 27) |
| Willy Oppenheim | — | Friend, ski trip (temporarily elevated to Tier 2 Trip Planning through March 27) |
| Willing Davidson | — | Friend, ski trip (temporarily elevated to Tier 2 Trip Planning through March 27) |
| Moshe Farhi | — | MRG real estate |
| *@mrgrealestate.com | Domain match | MRG Real Estate |
| Alec Sottosanti | — | Court Street Grocers (see Tier 2 — Project Carroll) |
| Birbal Kaikini | birbal75@yahoo.com | BC parent, daughter Zahrah at LaGuardia |
| Bryan Timko | bryan@lifealive.com | Life Alive founder (Jason intro) |
| David Tomczak | tomczak@robinhood.org | Robin Hood board placement |
| Emily Sundberg | emilysundberg@substack.com | "Feed Me" newsletter (food media & hospitality culture). Important, not just a newsletter. Overrides *@substack.com Tier 4 match. |
| Reed MacNaughton | — | Substack/newsletter source. Treat as newsletter unless there is a direct ask outside the publication. |
| Joshua Schiller | — | Airway proposal |
| Amit Shah | amitmshah74@gmail.com | Engineer intro from Alex Blumberg (code review / technical help). Distinct from Amit Savyon. |

---

### Tier 4 — Tracked Sources

Bundle in daily digest, skip interactive triage. Never alert.

| Sender / Domain | Category |
|----------------|----------|
| *@cora.io, *@withcora.com | Cora briefs (legacy) |
| *@linkedin.com | LinkedIn notifications |
| *@figma.com | Figma comments |
| *@notion.so | Notion notifications |
| *@github.com | GitHub notifications |
| *@substack.com | Newsletter platforms |
| *@nrn.com | Nation's Restaurant News |
| *@franchisetimes.com | Franchise Times |
| *@eater.com | Eater newsletters |
| *@grubstreet.com | Grub Street |
| *@restaurantbusinessonline.com | Restaurant Business |
| *@mailchimp.com | Mailchimp notifications |
| *@stripe.com | Stripe receipts |
| *@square.com | Square receipts |
| *@dropbox.com | Dropbox notifications |
| *@google.com (automated) | Google Workspace notifications |
| *@calendar.google.com | Calendar invites (already confirmed) |
| *@doordash.com | DoorDash notifications |
| *@ubereats.com | UberEats notifications |
| *@grubhub.com | GrubHub notifications |
| *@owner.com | Owner.com notifications |
| *@campsite.bio | Camp management |
| *@campminder.com | CampMinder notifications |
| Toast payroll notifications | Toast automated |
| Cora daily briefs | Legacy service |

---

### How to Update This File

Add new contacts when:
- A new project starts with new key people
- Matt begins corresponding regularly with someone new
- A sender gets misclassified in triage more than once

Move contacts between tiers when:
- A Tier 3 contact becomes actively involved in a deal or project (promote to Tier 2)
- A project completes and its contacts are no longer active (demote to Tier 3 or remove)

---

### Project Match Signals

Used during triage scoring to match emails to active projects. See `projects/README.md` for full project list.

| Project | Match signals (sender names, domains, keywords) |
|---------|------------------------------------------------|
| PnT Park Slope (P0) | OSD, Darragh, Marc McQuade, 244 Flatbush, Background Office, ABO, construction, buildout, fixtures, Singer equipment, Phil |
| Brown Bag Sandwich Co. (P0) | Gilli, Tony, Antonio Barbieri, Brown Bag, BBS, Stripes, chopped sandwich, Daniel Gulati |
| Project Carroll / CSG (P0) | Court Street Grocers, CSG, Project Carroll, Alec Sottosanti, Matt Ross, Eric Finkelstein, Matt Wagman, Shannon, Back-House |
| CBH Cash Flow (P0) | Integrus, Freedman Wang, Regan Dally, Jay Anand, John Heintz, Kevin Matthews, SystematIQ, cash flow, capital, funding, FY26, burn rate, estimated taxes, Betaworks |
| Automation Platform (P1) | Austin Thompson, automation, data warehouse, technical director, Lakeside Strategy, Athena Labs |
| Park Slope Marketing (P1) | Mona Creative, Sophie Jardine, Emily Koh, Ali Goldberg, Kern + Lead, K+L, andrew@kernandlead.com, amit@kernandlead.com, Andrew Tupper, Amit Savyon, press, launch, marketing, Mailchimp, campaign, 20th anniversary |
| PnT Real Estate (P1) | Moshe Farhi, MRG, Jacqueline Klinger, TSCG, real estate, expansion, lease, Ian Rice, Graci Goldstein, Alan Clifford, Picnic Group |
| Lily High School (P1) | LaGuardia, Berkeley Carroll, Kate Mollica, Birbal Kaikini, Miranda Sielaff, Earl Maneein, Chloe D'Amico, audition, viola, ISEE, SSAT, Brearley, Chapin, Spence, Horace Mann |
| Lily Bat Mitzvah (P1) | Leslie Goldberg, CBEBK, CBE, bat mitzvah, tutoring, Rana Bickel, Celia Tedde, Zach Rolf, B'nei Mitzvah |
| Downing Mountain Trip (P1) | Downing, Montana, Hamilton, John Lehrman, Morgan Comey, Ben Pomeroy, Willy Oppenheim, Willing Davidson, ski trip, backcountry, Missoula |
| Summer Camp 2026 (P2) | Keewaydin, camp, Emily Schoelzel, John Frazier, Annette Franklin, Ann Greenamyre, Wyonegonic, CampMinder, Temagami |

*Match signals are compiled from each project brief's `Match Signals` field. When updating a project's signals, update both the brief and this table.*
