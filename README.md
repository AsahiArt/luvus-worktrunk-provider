# Luvus Worktrunk Provider

A [Luvus](https://github.com/RizRiyz/luvus) module that delegates worktree creation and explicit removal to [Worktrunk](https://worktrunk.dev).

## Requirements

- Luvus `0.15.0` or newer
- Python 3.9 or newer
- Worktrunk (`wt`) available on `PATH` (tested with `v0.77.0`)
- macOS or Linux

## Install

The module targets the worktree-provider API proposed in [Luvus PR #387](https://github.com/RizRiyz/luvus/pull/387). Its manifest is conservatively gated to Luvus `0.15.0`; update this requirement if the API ships under a different release number.

After that API is available in a Luvus release:

```sh
luvus module install AsahiArt/luvus-worktrunk-provider
```

For local development:

```sh
git clone https://github.com/AsahiArt/luvus-worktrunk-provider.git
luvus module link ./luvus-worktrunk-provider
```

Select the module in `~/.luvus/config.json`:

```json
{
  "worktree": {
    "provider": "asahiart.worktrunk"
  }
}
```

Restart or reload the relevant Luvus session after changing configuration.

## Behavior

Creation maps the Luvus request to:

```text
wt -C <repository> switch [--create] <branch> --no-cd --format=json
```

`--create` is included only when Luvus reports that the local branch does not already exist. Worktrunk chooses the checkout path from its normal configuration and runs its normal lifecycle hooks.

### Hook policy setting

In **Settings → Modules → Worktrunk Worktrees**, **Worktrunk hook policy** controls project hooks during creation and removal:

| Policy | Worktrunk option | Behavior |
| --- | --- | --- |
| `prompt` | none | Default. Require prior interactive approval and show a short recovery hint if approval is missing. |
| `approve` | `--yes` | Skip the approval prompt for this invocation and run repository-declared hooks. Use only with trusted repositories. |
| `skip` | `--no-hooks` | Do not run lifecycle hooks for this creation. |

The `approve` commands place global `--yes` before `switch` or `remove`; the `skip` commands place `--no-hooks` after the subcommand. The policy never changes Luvus's per-request dirty-worktree `force` value.

### Branch removal setting

**Branch after worktree removal** controls whether Worktrunk may remove the branch:

| Policy | Behavior |
| --- | --- |
| `keep` | Default. Pass `--no-delete-branch` and always retain the branch. |
| `delete_if_merged` | Let Worktrunk delete the branch only when its safe integration checks pass. |
| `force_delete` | Pass `--force-delete`, allowing Worktrunk to delete an unmerged branch. This can permanently discard unique commits. |

`force_delete` is an explicit, provider-specific override of Luvus's normal branch-retention behavior. It is independent from `--force`: the latter only permits removal of a dirty worktree.

Explicit removal maps to:

```text
wt -C <repository> [--yes] remove [--no-hooks] <path> [--force] --foreground [--no-delete-branch|--force-delete] --format=json
```

Removal is foregrounded because Luvus verifies that the directory and Git worktree registration are gone before it updates workspace state. `force: true` affects dirty-worktree removal only. Branch handling follows **Branch after worktree removal**; only the explicit `force_delete` policy passes Worktrunk's `--force-delete` option.

With the default `prompt` policy, the module does **not** pass `--yes` or `--no-hooks`. If Worktrunk requires approval for project hooks, the **New Git Worktree** error ends with: `Press Esc. Approve Worktrunk hooks, then retry.` The module never edits `approvals.toml` or records approvals on your behalf.

## Protocol

The fixed commands in `luvus-module.toml` read one versioned JSON request from stdin. Creation emits only the Luvus result object on stdout; removal is silent on success. Worktrunk diagnostics are inherited on stderr so Luvus can surface actionable errors.

## Development

Run the tests without installing Worktrunk:

```sh
python3 -m unittest discover -s tests -v
```

The test suite places a fake `wt` executable first on `PATH` and asserts the exact argv, working directory, manifest commands, and protocol translation.

## License

Apache-2.0. Copyright 2026 AsahiArt. See [LICENSE](LICENSE).
