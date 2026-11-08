# Auto-login, local only — design

**Status:** design approved 8 Nov 2026 ("approve", on the four-point proposal below). The details under
*Rulings* are this session's judgment and can be overruled.

**Asked:** the app opens with no login screen, signed in as the admin user, and is never reachable from another
machine on the LAN. Nobody uses it except this computer.

## The four points approved

1. A real user is signed in automatically, not `LOGIN_DISABLED`. The app reads `current_user.role` and
   `current_user.id` in many places, and an anonymous user has neither.
2. A request whose `Host` isn't this computer's address is refused (DNS rebinding).
3. A change sent from another site is refused (cross-site POSTs). Until now, the session cookie's SameSite=Lax
   was the only guard. With auto-login, a request with no cookie at all is signed in, so that guard is gone.
4. A request from any address other than this computer is refused, login or not. `serve.py` refuses to start on
   an address other than loopback.

## How

A new module, `ltv_app/local_only.py`, holds the checks as plain functions. `create_app()` registers one
`before_request` guard, ahead of the authentication hook, which refuses (403, a short text page) when any check
fails:

| Check | Refused when |
|---|---|
| Client address | `REMOTE_ADDR` is missing or not a loopback address (127.0.0.0/8, ::1, ::ffff:127.x) |
| Host | the `Host` header's name is not `localhost` or a loopback IP |
| Fetch metadata | `Sec-Fetch-Site` is sent and is neither `same-origin` nor `none` (`none` covers a typed URL, a bookmark, or the launcher opening the browser), unless the request is a GET opening a whole page (`Sec-Fetch-Mode: navigate`, `Sec-Fetch-Dest: document`) |
| Origin, on POST/PUT/PATCH/DELETE | `Origin` is sent and isn't this app's own origin (`null` included); if there is no `Origin`, `Referer` is sent and points elsewhere |

The guard runs on every request, under `LOGIN_DISABLED` too. A test client's defaults (`localhost`, 127.0.0.1,
no fetch headers) pass it.

The authentication hook then signs in the user named by the new setting `AUTO_LOGIN_USER` when nobody is
signed in. The default is `"admin"`, the app's superuser. `instance/config.py` can set it to `None` to bring the
login back. When the setting is `None` or names no user, the app is default-deny, as before.

With auto-login on, `/login` redirects to the home page and the navbar shows no Logout link. `/logout` signs the
user out and goes to the home page, which signs the admin in again.

## Rulings

- **Ruling, revised after the browser check on 8 Nov: a whole-page GET from elsewhere is served; anything else
  from elsewhere is refused.**
  - *What Chrome sends:* Claude in Chrome's navigations reach the app as `Sec-Fetch-Site: cross-site` even from
    the app's own page. The root session drives the app that way ("Driven through the user's browser", LTV's
    CLAUDE.md). The first rule, which refused every cross-site GET, would have refused all of that.
  - *What is still refused:* a cross-site frame, image, script, fetch or form post.
  - *The cost:* a page on another site can still send the browser to a GET route that changes data (lock,
    unlock, set active, delete). That is the same exposure SameSite=Lax left before, when Alvin was signed in, so
    it is no worse than before.
  - *The proper fix* is to turn those GET routes into POSTs, which this change doesn't do (BUGS.md).
- **Ruling: another port on this computer counts as another site.** Every `same-site` request except a
  whole-page GET is refused (for example from the legacy app on 9000), and so is an `Origin` with another port.
  Nothing in the legacy app links to 5001. If that's wrong, one value is added to the allowed set.
- **Ruling: a POST with neither `Origin` nor `Referer` is allowed.** Browsers send `Origin` on every cross-origin
  POST, so a missing header means a script or a test client on this computer, which already passes the client
  address check.
- **Ruling: the login code stays.** It is what `AUTO_LOGIN_USER = None` falls back to, and the default-deny
  harnesses still test it.
- **Ruling: the other users stay as they are.** You can't switch users from the page; nobody else uses it.

## Tests

- New `scripts/verify_local_only.py`, run on a copy of the development database:
  - auto-login, including after a restart;
  - `/login` and `/logout`, and the Logout link;
  - LAN clients refused on every GET route;
  - loopback forms, foreign `Host`, fetch metadata, `Origin` and `Referer`;
  - the missing-user and `None` fallbacks;
  - `serve.py`'s refusal of an address other than loopback.
- `verify_auth_default_deny.py` and `verify_bank_requires_login.py` boot with `AUTO_LOGIN_USER = None`. They keep
  testing the fallback: with auto-login off, every route is still denied to an anonymous caller.
