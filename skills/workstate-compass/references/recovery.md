# Recovery: reconcile only the uncertain state

## Locate the work

Match the known workspace, task, branch/worktree and relevant files to the current
environment. A different branch is a mismatch to investigate, not a reason to
checkout/reset automatically. If the last process may still be running, inspect
its existing session/job ID first. Avoid simultaneous edits to files it writes.

For Git, inspect targeted status and both unstaged and staged diffs. Use known task
paths with `--` for every diff that returns patch bodies. If the relevant paths
are not known, discover names using status or `diff --name-only` first, then select
task-related paths before requesting patch bodies. Do not start with an unscoped
patch dump merely because the example repository looks small. Broaden only when
a concrete dependency or inconsistency requires it. For example, substitute known
paths as separate, shell-quoted arguments:

```text
git -C REPO status --short --branch -- src/feature.py tests/test_feature.py
git -C REPO diff --no-ext-diff --no-textconv -- src/feature.py tests/test_feature.py
git -C REPO diff --cached --no-ext-diff --no-textconv -- src/feature.py tests/test_feature.py
```

Read the relevant file sections too: a committed implementation may have no diff;
untracked files are absent from ordinary diffs. Inspect a few relevant commits only
when needed to resolve a discrepancy. A scoped clean result says nothing about the
rest of the repository. With no Git, use actual files, output artifacts and logs.

Optional helper: [evidence.py](../scripts/evidence.py) reports hashes and scoped Git
metadata without editing the project. It is not needed for every recovery, and it
does not read diff bodies, run tests, recover conversations or prove completion.
See [helper.md](helper.md) only if using it.

## Classify each remaining item

| State | Sufficient evidence and action |
| --- | --- |
| Implemented and verified | Relevant code/output exists and applicable successful checks exist; reuse. |
| Implemented, verification pending | Preserve implementation; run the missing check. |
| Missing or partial | Inspect the partial result; complete only the missing part. |
| Unknown or blocked | Name the exact uncertainty; resolve it or hold the dependent action. |

A test result is reusable only for the code and inputs it actually tested. Record
the command, exit status, scope, file hashes or revision plus dirty-state evidence,
dependency/config identity and relevant environment. HEAD alone is insufficient
with uncommitted changes. Changed test inputs invalidate affected checks; unrelated
documentation edits need not invalidate all tests. If coverage is unknown, run the
smallest meaningful check instead of claiming a previous pass still applies.

## Reconcile interrupted operations

| Observed state | Next step |
| --- | --- |
| Running with a matching session/job | Follow that job, bounded waits; do not start a duplicate. |
| Success with matching output/resource | Reuse the output; verify remaining acceptance criteria. |
| Failed or partially applied | Preserve completed parts; inspect logs and current state before a safe retry. |
| Unknown | Read operation-specific state; do not equate timeout with failure. |

For a PR creation timeout, look up the exact repository, head branch and base branch
and reuse a matching existing PR. For deployment, inspect the operation ID and the
deployed version. For migrations, read the migration ledger and actual schema.
These are examples of evidence, not permissions to access unrelated systems.

An idempotency key helps only if the service supports it, the same request/key is
reused, its scope and retention are known, and repeating it is already authorized.
Do not invent a fresh key to "recover" an unknown request. If the service cannot be
queried and replay is not demonstrably safe, leave the mutation unresolved.

Retry only after new evidence supports safety or a transient cause has changed.
Repeated unchanged errors are a blocker, not a reason for an infinite retry loop.
Fix a failed check and rerun its relevant checks; do not retry successful unrelated
operations. Record the next actionable step and any still-running ID at handoff.
