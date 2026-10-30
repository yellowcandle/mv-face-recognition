---
status: accepted
---

# Admin processing jobs run on the Worker, gated, dispatched to HF Jobs

The five admin processing endpoints move from `local_api.py` to the Worker. Each is a gated
write: Cloudflare Access verifies the caller, the job record lives in KV, and the pipeline
itself runs on HF Jobs. This supersedes the clause in [ADR 0005](0005-admin-writes-are-gated-on-the-worker.md)
saying pipeline runs only happen against `local_api.py`; its gate, its `no-store` rule and its
read-only test apply to these routes unchanged.

## Context

- The deployed `/admin` renders the job console and every button 404s: `/api/processing/jobs`
  and `/api/videos/local` answer 404 in production (probed 2026-10-22), while
  `/api/system/status` answers 200. The console is a dead affordance on the Worker.
- The contract is not in doubt. `local_api.py:398-495` defines all five endpoints and the admin
  SPA already reads them (`Processing.tsx:89,126,166,194,204`), including the wrapper shapes
  (`{jobs:[…]}`, bare job object) and the two different trigger responses.
- `MODAL_JOBS` is bound in `wrangler.toml:14-17` and referenced nowhere; the code that used it
  lived in retired Svelte routes. Modal itself is vestigial in this repo — the executor that
  actually ran the reels is HF Jobs (`scripts/hf/jobs/submit.py`, `docs/hf-jobs.md`).
- ADR 0005's reason applies here verbatim: review should not be synchronous with one machine.
  Triggering a reprocess from the train is the point, exactly as flagging was.

## Considered options

- **Keep jobs local-only and hide the console on the edge.** Rejected: it concedes that the
  admin's most expensive operation is tied to one laptop, and #78/#79/#80 are already scoped.
- **Dispatch to Modal.** Rejected: nothing in the live tree runs on Modal. The binding name is a
  fossil; the ADR renames it `JOB_STORE` rather than reimplementing a dead integration.
- **A Durable Object per job.** Deferred, not dismissed: KV with one document per job is
  sufficient while jobs are human-triggered and few. A DO returns when two callers must mutate
  one job concurrently, or when cancel must win a race against dispatch.
- **A Cloudflare Queue in front of the HF submission.** Deferred: no retry semantics are needed
  yet, and a queue hides dispatch failures that the reviewer should see immediately.
- **Route the console through `/admin/api/*`.** Chosen, matching flags and labels: the existing
  Access application covers `/admin`, so those calls arrive with `Cf-Access-Jwt-Assertion`
  stamped on them and the prefix is stripped before routing (`worker/src/index.ts:251-252`).

## Consequences

- **One secret, real money.** `HF_TOKEN` needs `job.write`. `GPU_MODES` decides the flavor per
  job kind and `HF_JOBS_GPU_FLAVOR` / `HF_JOBS_CPU_FLAVOR` tune it. Reels stay on CPU: a measured
  A/B gave ~2x wall clock for ~20x the hourly cost (1h39m for $0.05 against 50+ min for ~$0.70),
  because the detector's pre/post-processing stays on the CPU — 83 of the reel's 98 detection
  minutes are that work, not the encode (15 minutes). An embedding rebuild, which is unmeasured
  and reads only 831 photos, gets the GPU. A stuck queued record is a bill, so the UI must show
  a terminal state, and a dispatch failure must land as `failed` with the upstream message —
  never a silent `queued`.
- **No delete on the Hub.** HF Jobs exposes create, read and cancel, but no delete for regular
  jobs. `clear-completed` therefore removes local records only; Hub history persists and is not
  a source of truth for the console.
- **Unknown upstream states fail closed.** The Hub's vocabulary is wider than the five states
  the admin reads. Any unrecognised state maps to `failed`, because mapping it to `completed`
  would claim a pipeline run that may not have happened.
- **`/api/videos/local` is meaningless on the edge.** There is no local filesystem. The picker
  reads the published processed list instead; the local endpoint survives only for the Vite
  workflow.
- **`no-store` extends to `/processing/*`.** The allow-list in `routeHeaders`
  (`worker/src/index.ts:280-283`) covers flags and labels only; a cached job list would show a
  run that finished as still running, which is the stale-queue bug of ADR 0005 in a new coat.
- **The read-only test gains the group.** Literal cases are swept automatically; the
  parameterised `jobs/{id}` and `cancel/{id}` are sampled explicitly, and the gated list asserts
  401 with `no-store` for each unauthenticated call.
- **Any further write route reopens this ADR**, per ADR 0005.
