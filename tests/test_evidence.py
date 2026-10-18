"""Real filesystem/Git tests, using temporary repositories only."""
import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

SCRIPT = Path(__file__).resolve().parents[1] / "skills/workstate-compass/scripts/evidence.py"
spec = importlib.util.spec_from_file_location("evidence", SCRIPT)
evidence = importlib.util.module_from_spec(spec)
spec.loader.exec_module(evidence)


class FileTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="smart-resume-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        (self.root / "sample.txt").write_text("first", encoding="utf-8")

    def test_hash_detects_change_and_does_not_modify_files(self):
        p = self.root / "sample.txt"
        before = p.stat().st_mtime_ns
        result = evidence.collect(self.root, ["sample.txt"], True)
        self.assertEqual(result["files"][0]["sha256"], hashlib.sha256(b"first").hexdigest())
        self.assertEqual(p.stat().st_mtime_ns, before)
        self.assertEqual({f.name for f in self.root.iterdir()}, {"sample.txt"})
        p.write_text("second", encoding="utf-8")
        self.assertNotEqual(result["files"], evidence.collect(self.root, ["sample.txt"], True)["files"])

    def test_missing_is_not_success(self):
        self.assertEqual(evidence.collect(self.root, ["missing.txt"], True)["files"][0]["state"], "missing")

    def test_invalid_paths_are_rejected_before_git(self):
        for name in ["../outside", "/etc/passwd", "C:\\outside", ".git/config", ".GIT/config", "sample.txt:stream", ".", ""]:
            with self.subTest(name=name), mock.patch.object(evidence, "run_git") as git:
                with self.assertRaises(ValueError):
                    evidence.collect(self.root, [name])
                git.assert_not_called()

    def test_links_are_rejected(self):
        link = self.root / "linked.txt"
        try:
            link.symlink_to(self.root / "sample.txt")
        except OSError as error:
            self.skipTest(f"symlinks unavailable: {error}")
        with self.assertRaises(ValueError):
            evidence.collect(self.root, ["linked.txt"], True)

    def test_oversized_file_has_no_partial_hash(self):
        with mock.patch.object(evidence, "MAX_FILE_BYTES", 3):
            item = evidence.collect(self.root, ["sample.txt"], True)["files"][0]
        self.assertEqual(item["state"], "too_large")
        self.assertNotIn("sha256", item)

    def test_no_git_does_not_invoke_git(self):
        with mock.patch.object(evidence, "run_git") as git:
            evidence.collect(self.root, ["sample.txt"], True)
            git.assert_not_called()

    def test_missing_git_is_reported(self):
        with mock.patch.object(evidence.shutil, "which", return_value=None):
            report = evidence.collect(self.root, ["sample.txt"])
        self.assertEqual(report["git"]["state"], "unavailable")

    def test_timeout_is_not_a_clean_result(self):
        with mock.patch.object(evidence.shutil, "which", return_value="git"), mock.patch.object(
                evidence.subprocess, "run", side_effect=subprocess.TimeoutExpired("git", 5)):
            self.assertEqual(evidence.run_git(self.root, ["status"]), {"state": "timeout"})

    def test_temporary_output_failure_preserves_file_report(self):
        output = io.StringIO()
        with mock.patch.object(evidence.shutil, "which", return_value="git"), mock.patch.object(
                evidence.tempfile, "TemporaryFile", side_effect=PermissionError("temporary output unavailable")), mock.patch.object(
                evidence.subprocess, "run") as git, contextlib.redirect_stdout(output):
            self.assertEqual(evidence.main(["--repo", str(self.root), "--path", "sample.txt"]), 0)
        git.assert_not_called()
        report = json.loads(output.getvalue())
        self.assertEqual(report["files"][0]["state"], "observed")
        self.assertEqual(report["files"][0]["sha256"], hashlib.sha256(b"first").hexdigest())
        self.assertEqual(report["git"]["state"], "unavailable")
        self.assertEqual(report["git"]["probe"]["error"], "PermissionError")

    def test_status_diagnostics_are_separate_from_stdout(self):
        def result_with_warning(command, **kwargs):
            kwargs["stdout"].write(b" M sample.txt\n")
            kwargs["stderr"].write(b"warning: fixture diagnostic\n")
            return subprocess.CompletedProcess(command, 0)
        with mock.patch.object(evidence.shutil, "which", return_value="git"), mock.patch.object(
                evidence.subprocess, "run", side_effect=result_with_warning):
            result = evidence.run_git(self.root, ["status", "--porcelain=v1", "--", "sample.txt"])
        self.assertEqual(result["state"], "ok")
        self.assertEqual(result["text"], " M sample.txt\n")
        self.assertEqual(result["stderr"], "warning: fixture diagnostic\n")

    def test_stderr_truncation_is_explicit_and_does_not_replace_stdout(self):
        def result_with_warning(command, **kwargs):
            kwargs["stdout"].write(b"ok\n")
            kwargs["stderr"].write(b"warning: a longer diagnostic\n")
            return subprocess.CompletedProcess(command, 0)
        with mock.patch.object(evidence, "MAX_OUTPUT_BYTES", 8), mock.patch.object(
                evidence.shutil, "which", return_value="git"), mock.patch.object(
                evidence.subprocess, "run", side_effect=result_with_warning):
            result = evidence.run_git(self.root, ["status"])
        self.assertEqual(result["state"], "truncated")
        self.assertEqual(result["text"], "ok\n")
        self.assertEqual(result["stderr"], "warning:")

    def test_path_count_bound(self):
        with self.assertRaises(ValueError):
            evidence.collect(self.root, [f"{n}.txt" for n in range(33)], True)

    def test_cli_json(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(evidence.main(["--repo", str(self.root), "--path", "sample.txt", "--no-git"]), 0)
        self.assertEqual(json.loads(output.getvalue())["scope"], ["sample.txt"])


@unittest.skipUnless(shutil.which("git"), "Git is not installed")
class GitTests(unittest.TestCase):
    def git(self, *args):
        env = {k: v for k, v in os.environ.items() if not k.upper().startswith("GIT_")}
        return subprocess.run(["git", "-C", str(self.root), *args], env=env,
                              check=True, capture_output=True).stdout.decode("utf-8")

    def setUp(self):
        FileTests.setUp(self)
        self.git("init", "--quiet")
        self.git("config", "user.name", "Fixture")
        self.git("config", "user.email", "fixture@example.invalid")
        self.git("config", "core.autocrlf", "false")
        self.git("config", "core.fsmonitor", "false")
        self.git("config", "core.hooksPath", str(self.root / "no-hooks"))
        self.git("add", "sample.txt")
        self.git("-c", "commit.gpgsign=false", "commit", "--quiet", "-m", "fixture")

    def test_hash_detects_change_and_does_not_modify_files(self):
        # File-only invariant is tested by FileTests; here preserve the index too.
        index = (self.root / ".git/index").read_bytes()
        evidence.collect(self.root, ["sample.txt"])
        self.assertEqual(index, (self.root / ".git/index").read_bytes())

    def test_staged_unstaged_untracked_and_committed_work(self):
        (self.root / "sample.txt").write_text("staged", encoding="utf-8")
        self.git("add", "sample.txt")
        (self.root / "sample.txt").write_text("unstaged", encoding="utf-8")
        (self.root / "new.txt").write_text("new", encoding="utf-8")
        index = (self.root / ".git/index").read_bytes()
        before = self.git("status", "--porcelain")
        report = evidence.collect(self.root, ["sample.txt", "new.txt"])
        obs = report["git"]["observations"]
        self.assertIn("MM sample.txt", obs["status"]["text"])
        self.assertIn("?? new.txt", obs["status"]["text"])
        self.assertEqual(before, self.git("status", "--porcelain"))
        self.assertEqual(index, (self.root / ".git/index").read_bytes())
        self.assertEqual((self.root / "sample.txt").read_text(), "unstaged")

    def test_scoped_clean_does_not_include_unrelated_file(self):
        (self.root / "unrelated.txt").write_text("private", encoding="utf-8")
        report = evidence.collect(self.root, ["sample.txt"])
        self.assertEqual(report["git"]["observations"]["status"]["text"], "")
        self.assertNotIn("unrelated.txt", json.dumps(report))
        self.assertEqual(report["files"][0]["state"], "observed")

    @unittest.skipUnless(os.name == "nt", "Windows path-casing regression")
    def test_existing_file_case_alias_keeps_git_change_visible(self):
        if not (self.root / "SAMPLE.TXT").is_file():
            self.skipTest("requires a case-insensitive worktree")
        (self.root / "sample.txt").write_bytes(b"changed file contents")
        report = evidence.collect(self.root, ["SAMPLE.TXT"])
        self.assertEqual(report["files"][0]["state"], "observed")
        self.assertIn(" M sample.txt", report["git"]["observations"]["status"]["text"])

    @unittest.skipUnless(os.name == "nt", "Windows path-casing regression")
    def test_deleted_file_parent_case_alias_keeps_deletion_visible(self):
        parent = self.root / "parent"
        parent.mkdir()
        if not (self.root / "PARENT").is_dir():
            self.skipTest("requires a case-insensitive worktree")
        deleted = parent / "deleted.txt"
        deleted.write_bytes(b"tracked contents")
        self.git("add", "parent/deleted.txt")
        self.git("-c", "commit.gpgsign=false", "commit", "--quiet", "-m", "tracked child")
        deleted.unlink()
        report = evidence.collect(self.root, ["PARENT/deleted.txt"])
        self.assertEqual(report["files"][0]["state"], "missing")
        self.assertIn(" D parent/deleted.txt", report["git"]["observations"]["status"]["text"])

    @unittest.skipUnless(os.name == "nt", "Windows path-casing regression")
    def test_case_only_rename_keeps_original_and_resolved_paths(self):
        if not (self.root / "SAMPLE.TXT").is_file():
            self.skipTest("requires a case-insensitive worktree")
        self.git("mv", "-f", "sample.txt", "Sample.txt")
        (self.root / "Sample.txt").write_bytes(b"worktree modification after rename")
        before = self.git("status", "--porcelain=v1", "--untracked-files=all")
        index = (self.root / ".git/index").read_bytes()
        report = evidence.collect(self.root, ["sample.txt"])
        self.assertEqual(report["git"]["observations"]["status"]["text"], before)
        self.assertEqual(index, (self.root / ".git/index").read_bytes())
        self.assertEqual((self.root / "Sample.txt").read_bytes(), b"worktree modification after rename")

    def test_parent_repo_is_not_silently_selected(self):
        nested = self.root / "nested"
        nested.mkdir()
        (nested / "local.txt").write_text("local", encoding="utf-8")
        self.assertEqual(evidence.collect(nested, ["local.txt"])["git"]["state"], "root_mismatch")

    def test_inherited_git_dir_cannot_redirect_probe(self):
        with mock.patch.dict(os.environ, {"GIT_DIR": str(self.root / "nonexistent")}):
            self.assertEqual(evidence.collect(self.root, ["sample.txt"])["git"]["state"], "observed")

    def test_detached_head_is_visible(self):
        self.git("checkout", "--quiet", "--detach")
        obs = evidence.collect(self.root, ["sample.txt"])["git"]["observations"]
        self.assertEqual(obs["head_before"]["state"], "ok")
        self.assertEqual(obs["branch"]["state"], "error")

    def test_git_output_truncation_is_explicit(self):
        with mock.patch.object(evidence, "MAX_OUTPUT_BYTES", 8):
            result = evidence.run_git(self.root, ["rev-parse", "HEAD"])
        self.assertEqual(result["state"], "truncated")
        self.assertEqual(len(result["text"]), 8)

    def test_shell_metacharacters_are_only_file_names(self):
        name = "literal;echo INJECTED.txt"
        (self.root / name).write_text("literal", encoding="utf-8")
        report = evidence.collect(self.root, [name])
        self.assertEqual(report["files"][0]["sha256"], hashlib.sha256(b"literal").hexdigest())
        self.assertIn("INJECTED.txt", report["git"]["observations"]["status"]["text"])

    def test_changed_size_clean_filter_is_not_run_by_collection(self):
        # The filter and marker are outside the repo but inside an isolated temp
        # directory. A direct diff is the positive control for this regression.
        audit_temp = tempfile.TemporaryDirectory(prefix="smart-resume-filter-", dir=self.root.parent)
        self.addCleanup(audit_temp.cleanup)
        audit = Path(audit_temp.name).resolve()
        marker = audit / "filter-ran.txt"
        script = audit / "clean_filter.py"
        script.write_text(
            "import sys\nfrom pathlib import Path\n"
            "sys.stdin.buffer.read()\n"
            "Path(__file__).with_name('filter-ran.txt').write_text('ran', encoding='utf-8')\n"
            "sys.stdout.buffer.write(b'first')\n", encoding="utf-8")
        command = shlex.join([Path(sys.executable).as_posix(), script.as_posix()])
        self.git("config", "filter.audit.clean", command)
        self.git("config", "filter.audit.required", "true")
        (self.root / ".gitattributes").write_text("sample.txt filter=audit\n", encoding="utf-8")
        (self.root / "sample.txt").write_bytes(b"changed content with a different byte length")
        # The old collector's diff path invokes this filter and suppresses the
        # filename because the filter emits the indexed content, b'first'.
        self.assertEqual(self.git("diff", "--no-ext-diff", "--no-textconv", "--name-status", "--", "sample.txt"), "")
        self.assertTrue(marker.exists(), "positive control must invoke the configured filter")
        marker.unlink()

        def worktree():
            return {str(p.relative_to(self.root)): (p.read_bytes(), p.stat().st_mtime_ns)
                    for p in self.root.rglob("*") if p.is_file() and ".git" not in p.relative_to(self.root).parts}
        index = self.root / ".git/index"
        before_files = worktree()
        before_index = (index.read_bytes(), index.stat().st_mtime_ns)
        report = evidence.collect(self.root, ["sample.txt"])
        self.assertFalse(marker.exists(), "collection must not invoke the diff-triggered clean filter")
        self.assertEqual(report["git"]["observations"]["status"]["state"], "ok")
        self.assertIn(" M sample.txt", report["git"]["observations"]["status"]["text"])
        self.assertEqual(before_files, worktree())
        self.assertEqual(before_index, (index.read_bytes(), index.stat().st_mtime_ns))

    def test_autocrlf_warning_does_not_contaminate_change_names(self):
        path = self.root / "sample.txt"
        path.write_bytes(b"first\nsecond\n")
        index = self.root / ".git/index"
        before = (path.read_bytes(), path.stat().st_mtime_ns, index.read_bytes(), index.stat().st_mtime_ns)
        # Deliberately call diff only as a diagnostic fixture; collect() must not
        # use diff. This produces the real warning on Git for Windows as well.
        with mock.patch.dict(os.environ, {"LC_ALL": "C"}):
            result = evidence.run_git(self.root, ["-c", "core.autocrlf=true", "-c", "core.safecrlf=warn",
                                                 "diff", "--no-ext-diff", "--no-textconv", "--name-status", "--", "sample.txt"])
        self.assertEqual(result["state"], "ok")
        self.assertEqual(result["text"], "M\tsample.txt\n")
        self.assertIn("warning:", result["stderr"])
        self.assertIn("LF will be replaced by CRLF", result["stderr"])
        self.assertEqual(before, (path.read_bytes(), path.stat().st_mtime_ns, index.read_bytes(), index.stat().st_mtime_ns))


if __name__ == "__main__":
    unittest.main()
