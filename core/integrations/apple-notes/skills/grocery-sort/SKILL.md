---
name: grocery-sort
description: Use when the user has a grocery list, recipe ingredients, or asks to organize items for shopping at the co-op. Also use when user says "grocery list", "sort by aisle", "shopping list", or "add to groceries note".
---

# Grocery Sort

Sort grocery items by co-op aisle and push to Apple Notes with native checkboxes.

## Co-op Aisle Layout

| Aisle | Items |
|-------|-------|
| 1 | Produce, Milk, Kombucha, Cream (fresh dairy, fruits, vegetables, herbs, butter, cheese, yogurt, sour cream, eggs) |
| 2 | Coffee, Nuts, Dried Fruit, Bread, Baking supplies (flour, sugar, salt), Juice, Seltzer |
| 3 | Frozen Foods, Bagels, Soy/Rice/Oat Milk, Beer, Oils, Vinegars |
| 4 | Vitamins, Supplements, Natural Remedies, Household Items, Pet Supplies |
| 5 | Pastas, Sauces, Tea, Body Care, Office Supplies, Dried beans/lentils/grains |
| 6 | Honey, Syrups, Soup, Condiments, Crackers, Canned Fish/Tuna, Seaweed, Baby Food, Broth, Tomato paste |
| 7 | Energy Bars, Cereal, Cookies, Baked Goods, Candy, Chips, Snacks |

Items that don't fit go in **Other** at the end.

## Instructions

### Step 1: Get the grocery items

Source can be:
- User pastes a list directly
- A recipe URL (fetch and extract ingredients)
- A text message or link from Beeper (search messages for recipe/link)
- A recipe image (read and extract)

If a recipe, extract only the **ingredients** (not instructions). If user asks to double/triple, apply the multiplier to all quantities.

### Step 2: Sort by aisle

Assign each item to the correct aisle using the table above. Use judgment for items not explicitly listed (e.g., tahini -> Aisle 6, tortillas -> Aisle 2). Sort alphabetically within each aisle. Omit common pantry staples (salt, pepper, oil) unless the user specifically asks for them or the quantities are large.

### Step 3: Write to Apple Notes

Create or update the **Groceries** note in Apple Notes. Use this exact process — it is the only way to get native checkboxes:

**3a. Write content as plain `<div>` elements (no `<ul>`, `<li>`, or `<h2>`):**

```javascript
// Aisle headers as bold divs, items as plain divs, separated by <br> divs
'<div><b>Aisle 1</b></div>' +
'<div>Carrots, 4 medium</div>' +
'<div>Garlic, 4 cloves</div>' +
'<div><br></div>' +
'<div><b>Aisle 2</b></div>' +
'<div>Flour, 2 cups</div>'
```

Use JXA (`osascript -l JavaScript`) to find or create the note and set its `body` property.

**3b. Apply checklist format via GUI automation:**

```javascript
// Show the note, then use System Events menu clicks
Notes.activate();
Notes.show(groceryNote);
delay(1.5);

const SE = Application("System Events");
const np = SE.processes.byName("Notes");
// Select All via Edit menu
np.menuBars[0].menuBarItems.byName("Edit").menus[0].menuItems.byName("Select All").click();
delay(0.3);
// Apply Checklist via Format menu
np.menuBars[0].menuBarItems.byName("Format").menus[0].menuItems.byName("Checklist").click();
delay(0.5);
```

**Why this two-step process:** Apple Notes does not expose checklist creation through its scripting `body` property — it strips all checklist-specific HTML. The only way to create native tappable checkboxes is through the Format > Checklist menu. System Events menu clicks work even when keystroke sending is blocked by accessibility permissions.

### Step 4: Confirm

Tell the user the note is ready. Show a summary of what's in each aisle.

## Output Format

Aisle headers: just **Aisle 1**, **Aisle 2**, etc. No category labels in parentheses.

Items: ingredient name, then quantity. E.g., `Carrots, 4 medium`.

Blank line between aisle sections.

## Common Mistakes

- Using `<h2>` or `<ul>/<li>` in the body HTML — these get converted to checkboxes too or lose formatting
- Setting the body AFTER applying checklist — this resets everything to plain text
- Trying `keystroke` via System Events — blocked without accessibility permissions. Use menu clicks only.
- Forgetting `delay()` between GUI actions — Notes needs time to process
