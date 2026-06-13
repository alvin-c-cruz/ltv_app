# Fixings Date Arrows + Trades Tablet Responsiveness Design

**Date:** 2026-06-13
**Status:** Approved

## Overview

Two small UI improvements:
1. Add prev/next date arrow buttons to the Fixings page toolbar, identical to the existing pattern on the Trades Done page.
2. Hide the Action column in all Trades Done tables at tablet width (≤1024px) so the data columns fit within the viewport without horizontal overflow.

---

## Feature 1 — Fixings Date Arrows

### Current state

`fixings/pages/fixings/home.html` toolbar:
```html
<input type="date" name="trade_date" id="trade_date" value="{{ trade_date }}">
```
No arrow buttons. User must type or use the browser date picker.

### Change

Wrap the date input in a flex container and add `‹` / `›` buttons, exactly mirroring the trades toolbar:

```html
<div style="display:flex;align-items:center;gap:4px">
    <button type="button" class="btn btn-outline" style="padding:0.25rem 0.6rem;font-size:1.1rem" onclick="shiftDate(-1)">&#8249;</button>
    <input type="date" name="trade_date" id="trade_date" value="{{ trade_date }}">
    <button type="button" class="btn btn-outline" style="padding:0.25rem 0.6rem;font-size:1.1rem" onclick="shiftDate(1)">&#8250;</button>
</div>
```

Add `shiftDate()` JS (same as trades) inside a `<script>` tag immediately after the toolbar form — it references `trade_date` by ID and submits the form by ID `fixings-date-form`. The form element needs `id="fixings-date-form"` added.

```javascript
function shiftDate(days) {
    var p = document.getElementById('trade_date').value.split('-');
    var d = new Date(+p[0], +p[1] - 1, +p[2] + days);
    document.getElementById('trade_date').value =
        d.getFullYear() + '-' +
        String(d.getMonth() + 1).padStart(2, '0') + '-' +
        String(d.getDate()).padStart(2, '0');
    document.getElementById('fixings-date-form').submit();
}
```

### Files changed
- `ltv_app/blueprints/fixings/pages/fixings/home.html`

### No backend changes needed
The fixings view already accepts `trade_date` from a GET param (`request.args.get('trade_date')`) and from a POST form. Arrow clicks submit the existing POST form, so the CSRF token is included automatically.

---

## Feature 2 — Trades Tablet Responsiveness

### Current state

At ≤1024px, the transaction tables overflow the viewport: the **Net Amount** and **Action** columns are clipped off the right edge. The `table-wrap { overflow-x: auto }` container adds a scrollbar, but the Action column is not visible without scrolling.

### Change

Add a `<style>` block inside `{% block content %}` at the top of `transactions/pages/transactions/home.html`:

```css
@media (max-width: 1024px) {
    /* Hide Action column (always last th/td) in all transaction tables */
    .table-wrap th:last-child,
    .table-wrap td:last-child { display: none; }
}
```

This targets every table inside a `.table-wrap` on this page:
- **Accumulators** (9 columns → 8 visible): hides the Action column (9th)
- **Decumulators** (9 columns → 8 visible): hides the Action column (9th)
- **Regular transactions** (8 columns → 7 visible): hides the Action column (8th)
- **Short transactions** (similar to regular): hides the Action column

The `<style>` block is scoped to this template only (other pages with `.table-wrap` are unaffected since the style is in this page's block).

On desktop (>1024px) nothing changes — Action column remains fully visible.

### Files changed
- `ltv_app/blueprints/transactions/pages/transactions/home.html`

---

## Testing

No automated tests — verify visually in browser:

**Fixings arrows:**
- Visit `/fixings/` and confirm `‹` and `›` buttons appear flanking the date input
- Click `‹` — page reloads with the previous date
- Click `›` — page reloads with the next date
- Verify date arithmetic works across month boundaries (e.g. June 1 → May 31)

**Trades responsiveness:**
- Visit `/trades/?trade_date=2026-06-12` at viewport width ≤1024px
- Confirm Action column is hidden and all data columns (Account, Stock, Quantity, Price, Amount, Charges, Net Amount) are fully visible without horizontal scroll
- Resize to >1024px and confirm Action column reappears

## Files Changed

| File | Change |
|---|---|
| `ltv_app/blueprints/fixings/pages/fixings/home.html` | Add arrow buttons + `shiftDate()` JS |
| `ltv_app/blueprints/transactions/pages/transactions/home.html` | Add `@media (max-width:1024px)` style block |
