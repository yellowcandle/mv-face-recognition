---
status: accepted
---

# Admin writes are allowed on the Worker, behind Access

The deployed Worker now accepts flag and label writes, and only those. Every request to
`/api/faces/flag*` or `/api/labels*` must carry a Cloudflare Access RS256 token; the token is
verified against the team's published JWKS before storage is touched. All other routes stay
read-only. The viewer stays read-only in every sense: it never renders a write affordance and
every write route answers `401` to it.

This supersedes [ADR 0003](0003-the-deployed-worker-is-read-only.md) in two places: the Worker
is no longer read-only, and the admin is no longer local-only.

> Amended by [ADR 0006](0006-admin-jobs-run-on-the-worker.md): the processing job routes are
> gated writes on the Worker too, dispatched to HF Jobs. The gate, the `no-store` rule and the
> read-only test described below govern them unchanged.

## Context

ADR 0003 deleted the flag routes because they were protected by a function that returned
`verified: true` unconditionally, and because no deployed client called them. Both premises
changed:

- Access verification is real now. `requireAccess` rejects a token whose shape is wrong before
  any outbound fetch, answers `503` when `CF_ACCESS_AUD`/`CF_ACCESS_TEAM_DOMAIN` are unset,
  and answers `401` otherwise. The read-only test asserts zero KV writes, zero R2 writes and
  zero outbound fetches for every route × method without a token.
- The admin is deployed at `/admin` behind the same Access application, so its writes need a
  home that survives the laptop being closed. Flagging from the train is the point.

Two details were decided while implementing, and both are load-bearing:

- **One KV key per flag** (`flag_<id>`). The single `flagged_faces` array was read-modify-write,
  so two reviewers acting at the same moment silently dropped one flag. The legacy array is
  still read and is claimed by the first mutation.
- **Gated responses are `Cache-Control: no-store`.** Without it the browser reused the cached
  queue: accepting a flag wrote to KV and the list never changed. Identity-dependent data is
  not cacheable.

## Considered options

- **Keep the Worker read-only and run the admin against `local_api.py` forever.** Rejected:
  it makes review synchronous with one machine, and the read model is already published.
- **Gate with a service token instead of a user JWT.** Rejected: it replaces a per-person
  identity in `flagged_by` / `labelled_by` with one shared secret, and tests would need a
  credential to exercise the same code path a browser does.
- **D1 instead of KV.** Deferred, not dismissed: KV is acceptable at review-queue scale, and
  per-flag keys remove the lost-update bug. D1 returns when queries need indexes (ticket 007).
- **Route admin writes through `/admin/api/*`.** Chosen. The existing Access application covers
  `/admin`, so those calls are authorised by Access and arrive with `Cf-Access-Jwt-Assertion`
  stamped on them. The prefix is stripped before routing; public reads stay unprefixed.

## Consequences

- **The rule from ADR 0003 still holds for everything else**: a route with no deployed caller
  is deleted, not gated. `/api/admin/*`, `/api/settings` and `/api/embeddings/sync` remain gone.
- **The viewer's `canFlag` guard is now a security boundary**, not just a UI convenience. If it
  ever flips, the viewer's writes still fail closed — but the intent is that it never renders.
- **Flag data now outlives the machine.** It lives in production KV. The local API's
  `flagged_faces.json` remains a separate store; they are not synchronised.
- **Any new write route reopens this ADR.** It needs a reason, a gate, and a line in the
  read-only test.
- **Browsers cache aggressively by default.** Every future identity-dependent response needs
  `no-store`, or the UI will show a queue that disagrees with storage.
