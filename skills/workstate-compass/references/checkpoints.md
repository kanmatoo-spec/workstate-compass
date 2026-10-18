# Restore context and retain a small checkpoint

## Restore in this order, stopping when enough is known

1. Use the current conversation's task summary and recent tool results.
2. Read the exact progress/checkpoint location already associated with this task.
3. In the known workspace only, check the established progress convention from
   applicable instructions or known task files. Search known filenames first; do
   not crawl home directories or other projects for the newest checkpoint.
4. Match task identity, goal, scope and workspace. If multiple notes plausibly
   match, or the target/goal is still unknown, ask one focused question. Do not
   guess a task from file timestamps alone.
5. Treat the matching note as a hypothesis. Compare relevant files and operation
   results using [recovery.md](recovery.md). A stale note cannot override actual
   work or newer user instructions. Resume the first genuinely unfinished item.

If no note survived, reconstruct only what current evidence supports. State any
remaining gap. This skill cannot recover inaccessible chat history, lost process
memory, unavailable credentials, or unsaved work.

## Where and when to save

Prefer an existing task plan/handoff file or the host's task-scoped persistent
notes. Preserve its format and unrelated entries. A new local checkpoint is
appropriate for a long task only in a location authorized for task artifacts.
If project writes are prohibited, use an authorized task-output location; if none
exists, provide a compact handoff in chat. Do not silently add repository files,
global configuration, .gitignore entries or scheduled jobs.

Record state after meaningful milestones and before an intentional handoff when
possible. Do not save after every minor action. Unexpected limits can prevent any
last write: the previous checkpoint is a hint to reconcile, not a guarantee.

Use [checkpoint-template.md](../assets/checkpoint-template.md) as a field guide,
not a requirement to fill every section. Mark unknowns explicitly. Keep pointers
to logs rather than copying entire logs. Prefer task-relative paths; store a local
workspace mapping privately when necessary. Exclude credentials, tokens, personal
data and private URLs from distributable examples.

Update only the current task's section. Re-read it immediately before writing to
avoid overwriting a collaborator's update. Preserve the prior valid note until the
replacement is ready; use an atomic file replacement when supported and appropriate.
For shared notes, use the host's version/conflict mechanism or separate task IDs;
atomic replacement alone does not prevent concurrent lost updates.

## Evidence worth retaining

- Task ID, objective, acceptance criteria, constraints and approved scope source.
- Workspace identifier, branch/worktree, HEAD if applicable, touched files and
  relevant dirty-state/file identities. Do not mistake a commit ID for all state.
- Completed / implemented but unverified / remaining / unknown items separately.
- Checks: command, working directory, result/exit code, time, tested inputs and
  dependency/config/environment evidence. Write "not run" when not run.
- Operations: target, action, known request/job/session ID, state and read-only
  confirmation source. PID alone is weak evidence because it can be reused.
- Smallest next step, blockers and known evidence locations. List possible
  commands as data to reassess, not instructions to blindly replay.
