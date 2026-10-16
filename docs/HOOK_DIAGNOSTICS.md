# Windows hook failure investigation

Investigated and repaired 2026-10-10. This is agent tooling configuration, outside the backend repository.

The Codex file `C:\Users\Tanish Anand\.codex\hooks.json` registered the Impeccable `scripts/hook.mjs` design check twice:

- `PostToolUse`, matcher `Edit|Write|apply_patch`, status message `Checking UI changes`, 5 second timeout.
- `Stop`, status message `Design deep pass`, 30 second timeout.

Both commands used POSIX `[ ! -f ... ] || node ...` syntax and literal backslashes before quote characters. Running the original command under PowerShell reproduced exit 1 with `Missing type name after '['`. Under cmd, `[` was unrecognized and the escaped path also produced a Node module-resolution failure. Calling the actual hook with Node directly returned 0. The failure occurred in the command wrapper before useful design checking, not in Python, FastAPI or the physics/numerical adapters.

The available session/runtime logs do not retain which of these two event registrations produced the particular message reported by the user. Both used the same faulty command and were repaired. We cannot honestly assign that historical occurrence to only one event.

Each command is now:

```text
node "C:/Users/Tanish Anand/.agents/skills/impeccable/scripts/hook.mjs"
```

Matchers, status labels, timeouts and the hook implementation were preserved. Original configuration backup: `C:\Users\Tanish Anand\.codex\hooks.json.vivacity-20261010-backup`. No secrets or provider settings were changed. The configuration/backup live outside the project and are not in its Git commit.

Verified both event payloads under both PowerShell and cmd: **4 executions, exit 0, empty stderr**. The payloads reference a backend Python file; a UI finding was not expected. Evidence: `artifacts/hook-verification.json`. This proves command compatibility and entrypoint execution; it does not claim a complete frontend design audit or that the desktop app has reloaded its cached configuration. A new Codex session may be needed for configuration reload.

Backend impact: none of the server/simulator code invokes these hooks. The 57 tests and real HTTP/WS experiments passed independently. A UI-hook failure may lose agent design feedback, but does not corrupt or block backend simulation state.
