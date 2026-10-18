# Optional evidence helper

Requires Python 3.10+; Git is optional. All dependencies are in the standard
library. Use the interpreter installed in the current environment.

```text
python /installed/workstate-compass/scripts/evidence.py --repo /task/repo --path src/feature.py --path tests/test_feature.py
python /installed/workstate-compass/scripts/evidence.py --repo /task/files --path draft.txt --no-git
```

Replace sample paths and quote paths with spaces. On Windows, a usable interpreter
may be `py -3` instead of `python`. The helper writes JSON to stdout and temporary
files for Git output. Its own code does not write task files or the index, save a
checkpoint, inspect other chats, execute tests, access the network, or retry
operations. Git subprocesses are subject to the filter caveat below.

- Supply 1–32 explicit task-relative file paths. No directory scan by default.
- Absolute paths, parent traversal, `.git`, symlinks and junctions are rejected.
- Git receives both the supplied and filesystem-resolved path spelling when
  they differ only in case, preserving Windows case aliases and case-only
  renames. Missing components cannot recover their original spelling from disk;
  use the exact Git path spelling for fully deleted paths.
- Selected regular files up to 8 MiB receive a SHA-256 fingerprint. Larger,
  missing, changing, or inaccessible files have explicit non-success states.
- Git observes branch/HEAD and scoped `status --porcelain=v1`. Changed filenames
  come only from `observations.status.text`: its `XY` columns distinguish index
  (`X`) and worktree (`Y`) changes, with `??` for untracked files. There are no
  separate `staged` / `unstaged` diff observations or patch bodies.
- Git stdout is returned in `text`, and diagnostics in `stderr`, so warnings do
  not become changed-file entries. `ok` means exit 0 without truncation, not an
  absence of warnings.
- Git commands have a 5-second timeout each and a 12 KiB cap per returned stream.
  Truncation/timeout/errors are explicit; they are not evidence of a clean tree.
  Temporary-output I/O failures produce `unavailable` while retaining the file
  evidence already collected.
- A parent repository is not silently accepted: `--repo` must be the Git root.
  For a deliberate nested non-Git workspace, use `--no-git`.
- An unborn HEAD, detached branch, missing Git or unsafe-directory failure stays
  visible. The helper does not change Git trust settings to suppress failures.
- Exit 0 means a report was produced, including partial or unavailable states.
  Exit 2 means invalid input. Always inspect the JSON states.

The helper does not call `git diff`, avoiding its clean-filter execution path.
The changed-size regression fixture confirms that collection does not run the
configured clean filter and preserves worktree files and the index in that case.
This does **not** guarantee that `git status` never runs filters: its content
rehashing paths have not been tested here. Configured filters may start a shell,
write files, or access the network. `shell=False`, `--no-optional-locks`, and the
disabled pager/fsmonitor are not isolation from such Git subprocesses. Use
`--no-git` when Git configuration and filters cannot be trusted.

This is a best-effort observation of a trusted local workspace. It is not an
atomic snapshot, a sandbox for adversarial concurrent filesystem mutation, or a
validator of test coverage. A change between observations can invalidate the
report. HEAD stability does not prove worktree or dependency stability. Do not
share reports publicly without reviewing file names, branches and diagnostics.
