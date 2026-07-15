# Handoff: Reconcile `main` vs `group-d-confirm-migration`, then resume Group D

## Context

Workspace: `C:\envs\LTV-ai\server\` — this is `ltv_app`, a live Flask app for a real
client (Larry Villareal). It has its own git repo here (currently on branch `main`, 16
commits ahead of `origin/main`). **Note:** the workspace-root `C:\envs\LTV-ai\CLAUDE.md`
claims "server/ has no git repo of its own anymore" — that claim is now stale/wrong;
correct it as part of this task (see "Also fix" below).

Two design/plan docs already exist and were executed by prior sessions:
- `server/docs/superpowers/plans/2026-07-14-group-a-bug-fixes.md` — 5-task bug-fix plan,
  fully committed on `main` already. Nothing to do here.
- `server/docs/superpowers/plans/2026-07-14-group-d-confirm-modal-migration.md` — 12-task
  plan to migrate every native browser `confirm()`/`prompt()` dialog in the app to a
  custom modal (`showConfirmModal`). This is the one still in progress.

There's also a stale `server/BUGS.md` that still marks several bugs as `Status: Open`
even though Group A's commits already fixed them (Unlock 405, fixings redirect, bank-ref
indicator, print-modal, To-Decu live-recalc). Fix this too (see "Also fix" below).

## The problem: two sessions collided on Group D

After the shared commit `97db99a` ("docs: add Group D implementation plan"), two
sessions independently worked the same 12-task plan without coordinating:

- **`group-d-confirm-migration`** (a git worktree at
  `server/.worktrees/group-d-confirm-migration/`) did it properly, task-by-task, in
  plan order. Commits (oldest→newest): `878edaf` (confirm-modal component, Task 1),
  `f9aeaf9` (macros, Task 2), `fa205ee` (fixings, Task 3), `b3c3549` (charges/workflow,
  Task 4), `09e75f6` (lock, Task 5), `723b46d` (bank-accounts, Task 6), `4219745`
  (review, Task 7), `c3df9aa` (upload, Task 8), `c5757a1` (users, Task 9). Tasks 10–12
  (transactions, term_sheet, dividends) are NOT yet committed — the worktree currently
  has an uncommitted, in-progress edit to
  `ltv_app/blueprints/transactions/pages/transactions/home.html` (Task 10, unfinished).

- **`main`** did a separate, incomplete attempt: `6499a69` (macros) immediately
  reverted by `e3dff49` (net effect: zero), then `7d20540` (bank-accounts) — skipping
  fixings/charges/lock/review/upload/users entirely.

**I already verified (do not redo this — it's settled, just act on it):**
- `main`'s `7d20540` (bank-accounts) is a **strict subset** of the worktree branch's
  equivalent point `723b46d` — confirmed via `git diff 7d20540 723b46d`, which shows
  `723b46d`'s tree contains everything `7d20540` touched (charges/home.html identical)
  PLUS fixings (3 files), lock, workflow, main.js, base.html, macros.html that `main`
  never got to.
- `main`'s working tree currently has 6 files showing as uncommitted-modified:
  `charges/home.html`, `lock/home.html`, `review/home.html`, `upload/inspect.html`,
  `workflow/home.html`, `static/js/main.js`. I ran `git diff group-d-confirm-migration --
  <file>` for each: **5 of 6 are byte-identical** to the worktree branch's already-
  committed content. The 6th (`upload/inspect.html`) differs only by a stray UTF-8 BOM
  prefix and a missing trailing newline — a whitespace/encoding artifact, not a real
  code difference.
- **Conclusion: nothing on `main` is unique or worth preserving.** `main`'s 3 divergent
  commits (`6499a69`, `e3dff49`, `7d20540`) and its uncommitted working-tree state are
  fully superseded by `group-d-confirm-migration`'s properly-sequenced work.

## What to do

**The user (workspace owner) has already reviewed and approved this exact plan in a
prior conversation — you do not need to re-ask before doing step 1, but do report back
what you did before moving on to step 2+, since discarding commits/uncommitted state is
inherently a one-way action worth confirming succeeded cleanly.**

1. From `C:\envs\LTV-ai\server\` (the `main` worktree, not the `group-d-confirm-migration`
   one): confirm the working tree still matches what's described above
   (`git status --short`, `git diff group-d-confirm-migration -- <each of the 6 files>`)
   before touching anything — if the state has changed since this handoff was written,
   stop and re-diagnose rather than assuming this doc is still accurate.
2. Make `main` point at `group-d-confirm-migration`'s tip (`c5757a1`), discarding
   `main`'s 3 redundant commits. A fast-forward-style reset is the cleanest way:
   `git reset --hard c5757a1` while on `main`. This also resolves the 6 "uncommitted"
   files as a byproduct (they already match `c5757a1`'s content, so the working tree
   ends up clean).
3. Verify: `git status --short` should show a clean working tree; `git log --oneline -5`
   on `main` should show `c5757a1` at the tip; `git branch --all --contains c5757a1`
   should include both `main` and `group-d-confirm-migration`.
4. Decide whether to keep the now-redundant `group-d-confirm-migration` worktree/branch
   around (it's now an ancestor-equal pointer to the same commit as `main`) or remove
   it with `git worktree remove` — either is fine; if removing, use
   `git worktree remove server/.worktrees/group-d-confirm-migration` (don't manually
   `rm -rf` the directory, it'll leave stale worktree metadata).

## Resume Group D (Tasks 10–12)

Once `main` is at `c5757a1` and clean, use `superpowers:subagent-driven-development`
(or `executing-plans` in a fresh worktree — your call, but if you use a worktree, use a
**new** one so this doesn't collide with anything else) against
`server/docs/superpowers/plans/2026-07-14-group-d-confirm-modal-migration.md`, resuming
at **Task 10** (transactions/home.html — note there was unfinished, uncommitted work on
this file in the old worktree; treat it as reference only, don't assume it's correct or
complete — re-derive from the task brief). Tasks 11 (term_sheet) and 12 (dividends)
follow after.

## Also fix (small, can do anytime during this work)

- `C:\envs\LTV-ai\CLAUDE.md`: remove/correct the claim that `server/` has no git repo —
  it has one now, on branch `main`.
- `server/BUGS.md`: mark these 5 entries `Status: Fixed` (not `Open`) with their commit
  hashes, since Group A already fixed them:
  - "Unlock" 405 error → `fc7d62e`
  - "Record Fixings" redirects to today → `ce79e58`
  - Bank Reference No. optional/no indicator → `ff7d0ca`
  - "Print Trades Done" button does nothing → `8598cb4`
  - Period Schedule totals don't recalc live → `020b969`

## Constraints / reminders

- This is `ltv_app` for a real client — treat schema/data changes as
  destructive-until-proven-safe (per `C:\envs\LTV-ai\CLAUDE.md`), though this task is
  pure git history/template work, not a data change.
- Never `git push --force` without separately asking the user first (this handoff
  covers the local reconciliation only, not publishing it).
- If anything in "What to do" doesn't match what you observe on disk, stop and ask
  rather than pushing forward on a stale assumption.
