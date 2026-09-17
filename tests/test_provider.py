#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PROVIDER = ROOT / "provider.py"


class ProviderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.log = self.root / "argv.json"
        self.cwd_log = self.root / "cwd.txt"
        (self.root / "repo with space").mkdir()
        fake = self.bin / "wt"
        fake.write_text(
            """#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
Path(os.environ["FAKE_WT_LOG"]).write_text(json.dumps(sys.argv[1:]))
Path(os.environ["FAKE_WT_CWD"]).write_text(os.getcwd())
print("worktrunk diagnostic", file=sys.stderr)
mode = os.environ.get("FAKE_WT_MODE", "ok")
if mode == "fail":
    raise SystemExit(7)
if mode == "invalid":
    print("not json")
    raise SystemExit(0)
if mode == "multi-remove":
    path = sys.argv[sys.argv.index("remove") + 1]
    print(json.dumps([{"kind": "branch", "branch": "topic"}, {"kind": "worktree", "path": path}]))
    raise SystemExit(0)
if "switch" in sys.argv:
    branch = sys.argv[sys.argv.index("switch") + 1]
    if branch == "--create":
        branch = sys.argv[sys.argv.index("--create") + 1]
    print(json.dumps({"action": "created", "branch": branch, "path": os.environ["FAKE_WT_PATH"]}))
else:
    path = sys.argv[sys.argv.index("remove") + 1]
    print(json.dumps([{"kind": "worktree", "branch": "topic", "path": path, "branch_outcome": "not_attempted"}]))
"""
        )
        fake.chmod(0o755)
        self.env = os.environ.copy()
        self.env["PATH"] = os.fspath(self.bin) + os.pathsep + self.env.get("PATH", "")
        self.env["FAKE_WT_LOG"] = os.fspath(self.log)
        self.env["FAKE_WT_CWD"] = os.fspath(self.cwd_log)
        self.env["FAKE_WT_PATH"] = os.fspath(self.root / "repo.topic")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def run_provider(
        self, operation: str, request: dict[str, object], mode: str = "ok"
    ) -> subprocess.CompletedProcess[str]:
        env = self.env.copy()
        env["FAKE_WT_MODE"] = mode
        return subprocess.run(
            [sys.executable, os.fspath(PROVIDER), operation],
            input=json.dumps(request),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            check=False,
        )

    def create_request(self, *, branch_exists: bool = False) -> dict[str, object]:
        return {
            "version": 1,
            "operation": "create",
            "repository": os.fspath(self.root / "repo with space"),
            "branch": "feature/with space",
            "branch_exists": branch_exists,
        }

    def remove_request(self, *, force: bool = False) -> dict[str, object]:
        return {
            "version": 1,
            "operation": "remove",
            "repository": os.fspath(self.root / "repo with space"),
            "path": os.fspath(self.root / "worktree with space"),
            "branch": "feature/with space",
            "force": force,
        }

    def argv(self) -> list[str]:
        return json.loads(self.log.read_text())

    def test_create_new_branch_translates_request_and_stdout(self) -> None:
        result = self.run_provider("create", self.create_request())
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {"path": self.env["FAKE_WT_PATH"]})
        self.assertIn("worktrunk diagnostic", result.stderr)
        self.assertEqual(
            Path(self.cwd_log.read_text()).resolve(),
            (self.root / "repo with space").resolve(),
        )
        self.assertEqual(
            self.argv(),
            [
                "-C",
                os.fspath(self.root / "repo with space"),
                "switch",
                "--create",
                "feature/with space",
                "--no-cd",
                "--format=json",
            ],
        )

    def test_create_existing_branch_omits_create(self) -> None:
        result = self.run_provider("create", self.create_request(branch_exists=True))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("--create", self.argv())
        self.assertNotIn("--yes", self.argv())
        self.assertNotIn("--no-hooks", self.argv())

    def test_remove_is_foreground_and_keeps_branch(self) -> None:
        result = self.run_provider("remove", self.remove_request())
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "")
        self.assertEqual(
            self.argv(),
            [
                "-C",
                os.fspath(self.root / "repo with space"),
                "remove",
                os.fspath(self.root / "worktree with space"),
                "--foreground",
                "--no-delete-branch",
                "--format=json",
            ],
        )

    def test_force_maps_only_to_dirty_worktree_force(self) -> None:
        result = self.run_provider("remove", self.remove_request(force=True))
        self.assertEqual(result.returncode, 0, result.stderr)
        argv = self.argv()
        self.assertIn("--force", argv)
        self.assertNotIn("--force-delete", argv)
        self.assertNotIn("-D", argv)
        self.assertNotIn("--yes", argv)
        self.assertNotIn("--no-hooks", argv)

    def test_invalid_protocol_is_rejected_before_worktrunk(self) -> None:
        request = self.create_request()
        request["version"] = 2
        result = self.run_provider("create", request)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        self.assertIn("unsupported Luvus provider version", result.stderr)
        self.assertFalse(self.log.exists())

    def test_leading_dash_branch_is_rejected_before_worktrunk(self) -> None:
        request = self.create_request()
        request["branch"] = "--yes"
        result = self.run_provider("create", request)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("must not begin", result.stderr)
        self.assertFalse(self.log.exists())

    def test_protocol_version_must_be_an_integer(self) -> None:
        request = self.create_request()
        request["version"] = True
        result = self.run_provider("create", request)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unsupported Luvus provider version", result.stderr)
        self.assertFalse(self.log.exists())

    def test_remove_accepts_a_worktree_item_among_other_records(self) -> None:
        result = self.run_provider("remove", self.remove_request(), "multi-remove")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "")

    def test_manifest_declares_the_fixed_provider_commands(self) -> None:
        manifest = (ROOT / "luvus-module.toml").read_text()
        self.assertIn('id = "asahiart.worktrunk"', manifest)
        self.assertIn('command = ["python3", "provider.py", "create"]', manifest)
        self.assertIn(
            'remove_command = ["python3", "provider.py", "remove"]', manifest
        )

    def test_worktrunk_failure_and_invalid_json_are_actionable(self) -> None:
        failed = self.run_provider("create", self.create_request(), "fail")
        self.assertNotEqual(failed.returncode, 0)
        self.assertIn("exited with code 7", failed.stderr)
        self.assertEqual(failed.stdout, "")

        invalid = self.run_provider("create", self.create_request(), "invalid")
        self.assertNotEqual(invalid.returncode, 0)
        self.assertIn("returned invalid JSON", invalid.stderr)
        self.assertEqual(invalid.stdout, "")


if __name__ == "__main__":
    unittest.main()
