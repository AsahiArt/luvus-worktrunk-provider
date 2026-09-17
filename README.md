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

In **Settings → Modules → Worktrunk Worktrees**, **Worktrunk hook policy** controls project hooks during creation:

| Policy | Worktrunk option | Behavior |
| --- | --- | --- |
| `prompt` | none | Default. Require prior interactive approval and show a recovery command if approval is missing. |
| `approve` | `--yes` | Skip the approval prompt for this invocation and run repository-declared hooks. Use only with trusted repositories. |
| `skip` | `--no-hooks` | Do not run lifecycle hooks for this creation. |

The `approve` command is `wt -C <repository> --yes switch ...`; the `skip` command is `wt -C <repository> switch --no-hooks ...`. The policy affects creation only and is never added to removal.

Explicit removal maps to:

```text
wt -C <repository> remove <path> [--force] --foreground --no-delete-branch --format=json
```

Removal is foregrounded because Luvus verifies that the directory and Git worktree registration are gone before it updates workspace state. The branch is retained to match Luvus's existing `worktree.remove` contract. `force: true` affects dirty-worktree removal only; the module never passes Worktrunk's `--force-delete` option.

With the default `prompt` policy, the module does **not** pass `--yes` or `--no-hooks`. If Worktrunk requires approval for project hooks, press `Esc` to close **New Git Worktree**, run the copyable `wt -C <repository> config approvals add` command from the end of the error in a terminal, review every command, and retry creation. The module never edits `approvals.toml` or records approvals on your behalf.

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
