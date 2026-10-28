# Bounded queue and retry recovery - 28 October 2026

## Diagnosis boundaries

The reported message corresponds to the server's admission limit: at most three
accepted jobs, executed by one worker. It does not prove that Groq hit its quota.
No live queue credentials or new worker logs were provided, so the exact jobs
occupying the hosted queue were not inspected.

Code review confirmed two gaps: a frontend timeout did not retain the accepted
job for resumption, and running Python threads had no hard workflow-wide deadline.
Repeated manual submissions could create additional jobs while older ones were
still executing. Increasing the queue would only delay the admission failure.

## Changes

- A per-session request ID and accepted job ID survive frontend wait timeouts.
- Retry of an unfinished identical question resumes the existing job.
- The backend deduplicates an Idempotency-Key before acquiring another slot.
- Reusing that key for a different question returns a conflict instead of a wrong
  result. Keys expire with their retained job records.
- An uncertain submission is never blindly repeated against an older backend.
- Production jobs execute in spawned child processes, allowing a real hard stop.
- The default execution budget is 300 seconds; timeout cleanup stops the child
  before releasing its slot. A provider request already sent may still count
  toward provider usage.
- One bounded supervisor and inter-job pacing preserve sequential execution.
- Specific queue-full responses include counts; provider limits have a separate
  failure category. Queue diagnostics do not list private questions.

## Deployment

Keep the current start/build commands and keys. Deploy the latest backend and
reboot the Streamlit frontend. Restarting Render discards existing in-memory
jobs. On the updated app, submit once; if frontend polling times out, use Run /
retry with the same question to resume. Avoid opening a new browser session or
changing the question merely to retry, because those are distinct requests.

The limit still applies to genuinely different simultaneous jobs. This is a
single-instance in-memory queue, not a durable distributed worker service.

## Observed validation

- 60 regression tests passed on Windows and Linux with the current source.
- The Linux run used an unmodified locked-dependency image with read-only mounts
  for the current source, app and tests; no local `.env` was mounted.
- A real spawned child was stopped at the test deadline, and a subsequent job
  completed through the same manager, checking slot recovery rather than merely
  checking for a timeout label.
- Tests cover replaying the same request key, conflicting question/key pairs,
  resuming a known job, recovering a lost submission response, and preventing an
  older frontend request from overwriting a newer question's session state.
- No new model requests were required for these tests. The exact hosted queue
  contents and the user's next cloud result remain unverified until rollout.
