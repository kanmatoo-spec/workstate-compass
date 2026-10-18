#!/usr/bin/env python3
"""Bounded observational evidence for explicitly selected local task files.

Python 3.10+, standard library only. Never evaluates checkpoint commands.
This is an observation helper, not a completion classifier or replay engine.
Git status may run configured clean filters when rehashing; this is not a sandbox.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import subprocess
import tempfile

MAX_PATHS = 32
MAX_FILE_BYTES = 8 * 1024 * 1024
MAX_OUTPUT_BYTES = 12 * 1024
TIMEOUT_SECONDS = 5


def selected_paths(root, names):
    """Validate all inputs before reading any selected file or starting Git."""
    root = Path(root).resolve(strict=True)
    if not root.is_dir():
        raise ValueError("workspace must be an existing directory")
    if not 1 <= len(names) <= MAX_PATHS:
        raise ValueError(f"select 1..{MAX_PATHS} explicit file paths")
    selected = []
    for name in dict.fromkeys(names):
        normalized = name.replace("\\", "/")
        parts = PurePosixPath(normalized).parts
        if (not parts or PurePosixPath(normalized).is_absolute()
                or ".." in parts or ":" in normalized or "\x00" in normalized
                or any(p.lower() == ".git" for p in parts)):
            raise ValueError("paths must be relative files within the workspace; no .git paths")
        relative = PurePosixPath(*parts).as_posix()
        target = root.joinpath(*parts)
        # Reject links/junctions even when they point back into the workspace.
        cursor = root
        for part in parts:
            cursor = cursor / part
            if cursor.is_symlink() or getattr(cursor, "is_junction", lambda: False)():
                raise ValueError("symlink and junction paths are not supported")
        resolved = target.resolve(strict=False)
        if resolved != target:
            raise ValueError("path resolves to a different location")
        if target.exists() and not target.is_file():
            raise ValueError("select files, not directories or special devices")
        selected.append((relative, resolved))
    return root, selected


def file_evidence(relative, target):
    try:
        before = target.stat()
        if not stat.S_ISREG(before.st_mode):
            return {"path": relative, "state": "unsupported"}
        if before.st_size > MAX_FILE_BYTES:
            return {"path": relative, "state": "too_large", "size": before.st_size}
        with target.open("rb") as stream:
            content = stream.read(MAX_FILE_BYTES + 1)
        after = target.stat()
        identity = lambda s: (s.st_size, s.st_mtime_ns, s.st_ctime_ns, s.st_ino)
        if len(content) > MAX_FILE_BYTES or identity(before) != identity(after):
            return {"path": relative, "state": "changed_during_read"}
        return {"path": relative, "state": "observed", "size": len(content),
                "sha256": hashlib.sha256(content).hexdigest()}
    except FileNotFoundError:
        return {"path": relative, "state": "missing"}
    except OSError as error:
        return {"path": relative, "state": "unavailable", "error": type(error).__name__}


def run_git(root, args):
    executable = shutil.which("git")
    if executable is None:
        return {"state": "unavailable", "reason": "git executable not found"}
    # Ignore inherited Git repository/config overrides; keep ordinary environment.
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith("GIT_")}
    env.update({"GIT_TERMINAL_PROMPT": "0", "GIT_LITERAL_PATHSPECS": "1"})
    command = [executable, "--no-optional-locks", "--no-pager", "-C", str(root),
               "-c", "core.fsmonitor=false", "-c", "core.untrackedCache=false",
               "-c", "core.quotePath=true", "-c", "color.ui=false", *args]
    # Temporary output is outside the target repo. Returned output is bounded;
    # a timeout also bounds command duration. The outer subprocess uses no shell.
    # collect() avoids diff-triggered clean filters by using status for filenames;
    # status can still invoke filters when rehashing. Git is not sandboxed here.
    try:
        with tempfile.TemporaryFile() as output, tempfile.TemporaryFile() as diagnostics:
            result = subprocess.run(command, stdout=output, stderr=diagnostics, env=env,
                                    timeout=TIMEOUT_SECONDS, check=False, shell=False)
            output.seek(0)
            raw = output.read(MAX_OUTPUT_BYTES + 1)
            diagnostics.seek(0)
            stderr = diagnostics.read(MAX_OUTPUT_BYTES + 1)
    except subprocess.TimeoutExpired:
        return {"state": "timeout"}
    except OSError as error:
        return {"state": "unavailable", "error": type(error).__name__}
    truncated = len(raw) > MAX_OUTPUT_BYTES or len(stderr) > MAX_OUTPUT_BYTES
    return {"state": "truncated" if truncated else ("ok" if result.returncode == 0 else "error"),
            "exit_code": result.returncode,
            "text": raw[:MAX_OUTPUT_BYTES].decode("utf-8", errors="replace"),
            "stderr": stderr[:MAX_OUTPUT_BYTES].decode("utf-8", errors="replace")}


def collect(root, names, no_git=False):
    root, selected = selected_paths(root, names)
    report = {"schema_version": 1, "scope": [name for name, _ in selected],
              "files": [file_evidence(name, path) for name, path in selected],
              "notice": "Partial, non-atomic observations; not proof of completion, test validity, or replay safety."}
    if no_git:
        report["git"] = {"state": "not_requested"}
        return report
    top = run_git(root, ["rev-parse", "--show-toplevel"])
    if top["state"] != "ok":
        report["git"] = {"state": "unavailable", "probe": top}
        return report
    if Path(top["text"].strip()).resolve() != root:
        report["git"] = {"state": "root_mismatch",
                         "reason": "workspace is not the Git root; use the intended root or --no-git"}
        return report
    # Windows resolves existing case aliases, but Git literal pathspecs retain
    # case. Include both spellings so modifications and case-only renames remain
    # visible, without discovering additional paths or discarding the old name.
    paths = list(dict.fromkeys(spelling for name, path in selected
                              for spelling in (name, path.relative_to(root).as_posix())))
    observations = {}
    for key, args in [
        ("head_before", ["rev-parse", "--verify", "HEAD"]),
        ("branch", ["symbolic-ref", "--quiet", "--short", "HEAD"]),
        ("status", ["status", "--porcelain=v1", "--untracked-files=all", "--", *paths]),
        ("head_after", ["rev-parse", "--verify", "HEAD"]),
    ]:
        observations[key] = run_git(root, args)
    report["git"] = {"state": "observed", "observations": observations,
                     "head_changed": observations["head_before"] != observations["head_after"]}
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True, help="exact Git root or non-Git workspace")
    parser.add_argument("--path", action="append", required=True, help="explicit relative file; repeat as needed")
    parser.add_argument("--no-git", action="store_true", help="inspect selected files only")
    args = parser.parse_args(argv)
    try:
        report = collect(args.repo, args.path, args.no_git)
    except (ValueError, OSError, RuntimeError) as error:
        parser.error(str(error))
    print(json.dumps(report, ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
