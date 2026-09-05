"""Coercion of submitted form values, kept in one place.

A quantity copied out of a broker statement or Excel carries a thousands
separator -- `-12,345`. `int()` rejects that with a ValueError, which in a view
with no guard is a hard 500 that loses everything the person typed. Passed
through to SQL unparsed it is worse than a crash: SQLite stores it as TEXT in
an INTEGER column, and `SUM()` then reads it as -44, so every balance derived
from it is silently wrong. See server/BUGS.md (2026-09-04).

Accessors collect rather than raise. Each returns None and records the first
problem in `.error`, so a view can finish reading the whole form, fall into the
`if not error:` guard it already has, and re-render with `.values` -- what the
person typed, with the fields that did parse replaced by their parsed values so
`<select>` options still match on identity.

    fields = FormFields(request.form)
    bank_ref = fields.integer("bank_ref", "Bank")
    quantity = fields.quantity()
    price = fields.price()
    error = fields.error
    form = fields.values
"""

# U+2212 MINUS SIGN: what a spreadsheet or a word processor can substitute for
# an ASCII hyphen. Normalised because it is unambiguous; en/em dashes are not
# (they are punctuation as often as they are a sign) and are left to fail.
_MINUS_SIGN = '−'
# Ordinary space, non-breaking space (a common paste artefact) and the comma
# are all thousands separators as far as a typed figure is concerned.
_SEPARATORS = (',', ' ', ' ', ' ')


def clean_number(raw) -> str:
    """The typed text reduced to what `int()`/`float()` can read: surrounding
    whitespace, thousands separators and a substituted minus sign removed.
    Anything else is left alone, so it still fails and is reported."""
    s = '' if raw is None else str(raw).strip()
    s = s.replace(_MINUS_SIGN, '-')
    for sep in _SEPARATORS:
        s = s.replace(sep, '')
    return s


def _label_for(name, label):
    return label or name.replace('_', ' ').strip().capitalize()


class FormFields:
    """One submitted form, read field by field, collecting the first problem."""

    def __init__(self, form):
        self._form = form
        self.error = ''
        # Seeded with the raw submission so a rejected form re-renders with
        # everything that was typed, not just the fields that parsed.
        self.values = dict(form)

    def _fail(self, message):
        if not self.error:      # report the first problem, not the last
            self.error = message
        return None

    def text(self, name):
        """A field used as-is. Recorded so `.values` stays complete."""
        value = self._form.get(name, '')
        self.values[name] = value
        return value

    def integer(self, name, label=None):
        """A whole-number field: share quantities, and the `ref_num` values the
        `<select>` menus post back."""
        label = _label_for(name, label)
        raw = self._form.get(name, '')
        s = clean_number(raw)
        if s == '':
            return self._fail(f"{label} is required.")
        try:
            value = int(s)
        except ValueError:
            # "44874.0" is a whole number spelled as a decimal -- accept it;
            # "44874.5" is not a share count -- reject it.
            try:
                as_float = float(s)
            except ValueError:
                return self._fail(f"{label} must be a whole number, not {raw!r}.")
            if as_float != int(as_float):
                return self._fail(f"{label} must be a whole number, not {raw!r}.")
            value = int(as_float)
        self.values[name] = value
        return value

    def number(self, name, label=None, default=None):
        """A decimal field: prices and the per-trade charges. `default` is
        returned when the field is absent or left blank, which is how the forms
        say a charge is zero; without one, blank is an error."""
        label = _label_for(name, label)
        raw = self._form.get(name, '')
        s = clean_number(raw)
        if s == '':
            if default is None:
                return self._fail(f"{label} is required.")
            self.values[name] = default
            return default
        try:
            value = float(s)
        except ValueError:
            return self._fail(f"{label} must be a number, not {raw!r}.")
        self.values[name] = value
        return value

    def quantity(self, name='quantity'):
        return self.integer(name, 'Quantity')

    def price(self, name='price'):
        return self.number(name, 'Price')

    def charge(self, name, label=None):
        """A per-trade charge: blank means zero."""
        return self.number(name, label, default=0.0)
