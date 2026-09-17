#!/usr/bin/env python3
"""Luvus worktree provider backed by the Worktrunk CLI."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any, NoReturn

PROTOCOL_VERSION = 1


class ProviderError(Exception):
    """An actionable provider error safe to print to stderr."""


def fail(message: str) -> NoReturn:
    print(message, file=sys.stderr)
    raise SystemExit(1)


def require_string(request: dict[str, Any], key: str) -> str:
    value = request.get(key)
    if not isinstance(value, str) or not value:
        raise ProviderError(f"request field {key!r} must be a non-empty string")
    return value


def require_bool(request: dict[str, Any], key: str) -> bool:
    value = request.get(key)
    if not isinstance(value, bool):
        raise ProviderError(f"request field {key!r} must be a boolean")
    return value


def read_request(expected_operation: str) -> dict[str, Any]:
    try:
        request = json.load(sys.stdin)
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise ProviderError(f"invalid Luvus provider request: {error}") from error
    if not isinstance(request, dict):
        raise ProviderError("Luvus provider request must be a JSON object")
    version = request.get("version")
    if type(version) is not int or version != PROTOCOL_VERSION:
        raise ProviderError(f"unsupported Luvus provider version: {version!r}")
    if request.get("operation") != expected_operation:
        raise ProviderError(
            f"expected operation {expected_operation!r}, got {request.get('operation')!r}"
        )
    return request


def worktrunk_binary() -> str:
    executable = shutil.which("wt")
    if executable is None:
        raise ProviderError(
            "Worktrunk executable 'wt' was not found on PATH; install it from "
            "https://worktrunk.dev"
        )
    return executable


def run_worktrunk(arguments: list[str], repository: Path) -> Any:
    command = [worktrunk_binary(), *arguments]
    try:
        completed = subprocess.run(
            command,
            cwd=os.fspath(repository),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=None,
            text=True,
            check=False,
        )
    except OSError as error:
        raise ProviderError(f"could not run Worktrunk: {error}") from error
    if completed.returncode != 0:
        raise ProviderError(f"Worktrunk exited with code {completed.returncode}")
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise ProviderError(f"Worktrunk returned invalid JSON: {error}") from error


def create() -> None:
    request = read_request("create")
    repository = Path(require_string(request, "repository"))
    branch = require_string(request, "branch")
    branch_exists = require_bool(request, "branch_exists")
    if branch.startswith("-"):
        raise ProviderError("branch must not begin with '-'")
    if not repository.is_absolute():
        raise ProviderError("repository must be an absolute path")

    arguments = ["-C", os.fspath(repository), "switch"]
    if not branch_exists:
        arguments.append("--create")
    arguments.extend([branch, "--no-cd", "--format=json"])
    result = run_worktrunk(arguments, repository)
    if not isinstance(result, dict):
        raise ProviderError("Worktrunk switch result must be a JSON object")
    path = result.get("path")
    if not isinstance(path, str) or not Path(path).is_absolute():
        raise ProviderError("Worktrunk switch result did not contain an absolute path")
    json.dump({"path": path}, sys.stdout, separators=(",", ":"))
    sys.stdout.write("\n")


def remove() -> None:
    request = read_request("remove")
    repository = Path(require_string(request, "repository"))
    path = Path(require_string(request, "path"))
    force = require_bool(request, "force")
    if not repository.is_absolute() or not path.is_absolute():
        raise ProviderError("repository and path must be absolute paths")

    arguments = ["-C", os.fspath(repository), "remove", os.fspath(path)]
    if force:
        arguments.append("--force")
    arguments.extend(["--foreground", "--no-delete-branch", "--format=json"])
    result = run_worktrunk(arguments, repository)
    if not isinstance(result, list) or not any(
        isinstance(item, dict) and item.get("kind") == "worktree" for item in result
    ):
        raise ProviderError("Worktrunk did not report a worktree removal")


def main() -> None:
    if len(sys.argv) != 2 or sys.argv[1] not in {"create", "remove"}:
        fail("usage: provider.py create|remove")
    try:
        if sys.argv[1] == "create":
            create()
        else:
            remove()
    except ProviderError as error:
        fail(str(error))
    except KeyboardInterrupt:
        raise SystemExit(130) from None
    except BrokenPipeError:
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
