# Secret Key and Session Hardening — Design

**Date:** 2026-08-15
**Status:** Approved for planning
**Area:** `ltv_app` app factory, `data_model`, `term_sheet`/`dividends`/`fixings`/`transactions` route converters

## Goal

Close four small, independent security/robustness gaps found while auditing `ltv_app`
for the first time since the legacy feature port landed:

1. `SECRET_KEY` is regenerated on every process start, so every restart and every
   PythonAnywhere reload logs all users out.
2. `data_model.Model.save()` interpolates `ref_num` directly into SQL.
3. Route converters are inconsistently typed — 24 untyped ref params against 21
   correctly typed `<int:ref_num>` ones.
4. Session cookies carry no `SameSite` attribute and are not marked `Secure`, on an
   app served over HTTPS with no global CSRF protection.

None of these are user-visible features. Items 1 and 3 fix real day-to-day annoyances
(surprise logouts, HTTP 500s on a malformed URL); items 2 and 4 remove latent risk.

## Non-goals

- No global CSRF protection. `CSRFProtect` is not registered anywhere in
  `create_app()`, which is a genuine gap, but retrofitting it touches every form
  template in ~30 blueprints and deserves its own spec. Logged separately.
- No sweep for other request-data-into-SQL paths beyond the ones this audit surfaced.
  Explicitly descoped by the user.
- No change to password handling. `auth/views.py` already uses
  `werkzeug.security.check_password_hash` correctly.

---

## Item 1: Persist `SECRET_KEY`

### Current behaviour

`ltv_app/__init__.py` sets a per-process fallback:

```python
app.config.from_mapping(
    SECRET_KEY=secrets.token_hex(32),
    DATABASE=os.path.join(app.instance_path, "LTV Stocks.db"),
)
if test_config is None:
    app.config.from_pyfile('config.py', silent=True)
```

`create_app()` builds the app with `instance_relative_config=True`, so
`from_pyfile('config.py')` resolves against `instance_path`, **not** the package root.
Verified at runtime:

```
instance_path : C:\envs\LTV-ai\server\instance
config root   : C:\envs\LTV-ai\server\instance
=> from_pyfile('config.py') reads: C:\envs\LTV-ai\server\instance\config.py
SECRET_KEY set from fallback? True
```

The 2026-07-17 maintenance-backlog plan (Task 1, Step 2) instructed creating
`server/config.py`. That path is never read. Neither file exists today, so the fallback
is always in force and the signing key changes on every boot.

### Change

- Create `server/instance/config.py`, untracked, containing a single generated
  `SECRET_KEY`. Confirmed gitignored: `server/.gitignore` re-includes `/instance/` but
  then excludes `/instance/*`, un-ignoring only `excel_templates/` and `gmail_setup.py`.
- Correct the comment at `ltv_app/__init__.py:46-48`, which currently points readers at
  the wrong path.
- The same file must be created on PythonAnywhere at
  `/home/larrylilia/ltv_app/instance/config.py`. It is deployment state, not code, so
  it cannot ride along in a git pull — this is a manual step in the deploy, and the plan
  must call it out rather than assume it.

### Why not an environment variable

PythonAnywhere web apps do not read the shell environment of a console session, so an
env var would need to be set in the WSGI file — which *is* tracked. A gitignored
`instance/config.py` keeps the secret out of git with no extra moving parts, and matches
the pattern `instance/gmail_token.json` already uses.

### Verification

Boot the app twice in separate processes and confirm `app.config['SECRET_KEY']` is
identical, and that it differs from `secrets.token_hex(32)`'s 64-char fallback shape
only by being loaded rather than generated. Then log in, restart, and confirm the
session survives.

---

## Item 2: Parameterise `ref_num` in `Model.save()`

### Current behaviour

`ltv_app/blueprints/data_model/__init__.py:47`:

```python
self.db.execute(f"UPDATE {self.table_name} set {', '.join(fields)} WHERE ref_num={self.ref_num};", values)
```

`{self.table_name}` is safe — it is always a class-level constant set in `__post_init__`,
never request data. `{self.ref_num}` is not: `term_sheet/views.py:234` assigns it
straight from an untyped URL segment.

```python
@bp.route("/edit/<contract_ref>", methods=["GET", "POST"])
def edit(contract_ref, view_only=False):
    ...
    ts.ref_num = contract_ref          # raw string from the URL
    ...
    ts.save()
```

### Exploitability — currently blocked, but only by accident

`save()` places `ref_num` in the parameterised `SET` clause *as well as* the
interpolated `WHERE`, so a payload must also bind successfully to the `ref_num` column.
`tbl_stock_contract.ref_num` is `INTEGER PRIMARY KEY`, which rejects a non-integer.
Confirmed against an in-memory database with the same code path:

```
INTEGER PRIMARY KEY (as deployed)  BLOCKED -- IntegrityError: datatype mismatch
plain INTEGER column               EXPLOITED -- 3 of 3 rows overwritten
```

So the deployed app is not exploitable today. The protection is incidental to the column
type, not intended by the code — it would silently disappear if a model were ever backed
by a table whose `ref_num` is a plain `INTEGER`, or if `ref_num` were dropped from the
`SET` clause. That is too fragile to leave in place for the sake of one line.

The same interpolation also means a malformed ref produces an
`sqlite3.IntegrityError` → HTTP 500 rather than a clean 404.

### Change

```python
self.db.execute(
    f"UPDATE {self.table_name} set {', '.join(fields)} WHERE ref_num=?;",
    values + [self.ref_num],
)
```

`values` is built as a list comprehension, so `+ [...]` is safe. `get()` on line 65 is
already parameterised and needs no change — its `{", ".join(clause)}` interpolates
filter *keys*, which are always code-supplied keyword names.

### Verification

Re-run the in-memory proof-of-concept against both column types and confirm the plain
`INTEGER` case now reports BLOCKED rather than EXPLOITED. This is the one case where the
test must exercise a plain column, since the deployed schema masks the bug.

---

## Item 3: Type the route converters

### Current behaviour

| Converter | Count |
|---|---|
| `<int:ref_num>` | 21 |
| `<ref_num>` | 13 |
| `<contract_ref>` | 10 |
| `<period_ref>` | 1 |

Every caller already passes a database integer — `row.ref_num`, `accu.ref_num`,
`decu.ref_num`, `ts.id` — checked across templates and `url_for` calls in
`term_sheet`, `lock`, and `transactions`. Nothing passes a non-numeric ref.

### Change

Convert the 24 untyped params to `<int:...>`. A malformed URL then returns 404 at
routing time instead of reaching a view and raising a 500. This is what makes item 2's
fix belt-and-braces rather than load-bearing.

`<source>` (12 occurrences, in `lock`/`charges`) stays a string — it is a deliberate
enum-like segment resolved through a hardcoded dict, and typing it as `int` would be
wrong. A bad value currently raises `KeyError` → 500; converting those lookups to return
404 is worth doing but is a behaviour change beyond this item's scope. Noted, not done.

### Verification

Boot the app and confirm each converted route still resolves for a valid integer ref,
and returns 404 (not 500) for `abc`. `url_for` calls need no change — Flask's `int`
converter accepts the integers already being passed.

---

## Item 4: Session cookie attributes

### Current behaviour

Probed at runtime:

```
SESSION_COOKIE_HTTPONLY: True
SESSION_COOKIE_SECURE  : False
SESSION_COOKIE_SAMESITE: None
PERMANENT_SESSION_LIFETIME: 31 days
```

`HttpOnly` is already correct. Two observations shape the change:

- **The 31-day lifetime is inert.** `auth/views.py:35` calls `login_user(user)` without
  `remember=True`, and nothing anywhere sets `session.permanent`. Sessions are therefore
  browser-session cookies that die when the browser closes;
  `PERMANENT_SESSION_LIFETIME` never applies. **Shortening it would be a no-op**, so
  this design does not touch it — an earlier draft proposed to, wrongly.
- **`SameSite` matters more than usual here.** No `CSRFProtect` is registered in
  `create_app()`, so `SameSite=Lax` is the only thing standing between a cross-site POST
  and a state-changing route. Flask leaving the attribute unset means browsers apply
  their own Lax default, which is weaker and version-dependent.

### Change

- Set `SESSION_COOKIE_SAMESITE='Lax'` in the `from_mapping` defaults in
  `create_app()`. Safe for this app: every cross-page navigation is a same-site link or
  form, and Lax still permits top-level GET navigation.
- Do **not** set `SESSION_COOKIE_SECURE=True` in code — it would stop the session cookie
  being sent over `http://127.0.0.1:5001` and break local development login. Set it in
  PythonAnywhere's `instance/config.py` instead, alongside the `SECRET_KEY` from item 1,
  where the app is genuinely HTTPS-only.

### Verification

Log in locally and confirm the session still works over plain HTTP with `SameSite=Lax`
set. Inspect the `Set-Cookie` header for `SameSite=Lax; HttpOnly` and confirm `Secure`
is absent locally and present on PythonAnywhere.

---

## Task sequencing

Four independent commits, in this order:

1. `SECRET_KEY` persistence + comment fix (highest user-visible value, no code risk)
2. `Model.save()` parameterisation (one line, has a real test)
3. Route converter typing (mechanical, broadest file count)
4. `SameSite=Lax` (one line)

No task depends on code introduced by an earlier one, so any can be reviewed and landed
alone. Items 1 and 4 both add keys to PythonAnywhere's `instance/config.py` and should
be applied to the server in a single visit at the end.

## Constraints

- `server/instance/LTV Stocks.db` is real client data. No task in this plan reads or
  writes it. Item 2's test uses an in-memory database exclusively.
- Never commit a real secret. `instance/config.py` is untracked and must stay that way;
  the generated key goes in that file only, never into a plan, spec, or commit message.
- Run everything with `server/.venv/Scripts/python.exe`, cwd `server/`.
- Verification follows the existing `scripts/verify_*.py` convention — this copy has no
  pytest suite.

## Risks

- **Item 3 is the only one that could break a working page.** If any route is reached
  with a non-integer ref by a path not found in this audit, it will start 404ing.
  Mitigated by verifying each converted route boots and resolves before committing.
- **Item 1 changes nothing until `instance/config.py` exists on PythonAnywhere.**
  Deploying the code alone leaves the logout behaviour exactly as it is now. The plan
  must treat the PA file as a required step, not a follow-up.
