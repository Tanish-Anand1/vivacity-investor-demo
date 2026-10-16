# Varied 5,000-trial MuJoCo audit

The authoritative requested run **completed successfully** in the backend's
cloud Docker image on 2026-10-11. Its measured progress and final verification
are in the [GitHub Actions log](https://github.com/Tanish-Anand1/vivacity-runtime/actions/runs/38175668423/job/114577414902).
The [30-day cloud artifact](https://github.com/Tanish-Anand1/vivacity-runtime/actions/runs/38175668423/artifacts/11715639246)
contains the aggregate report, 5,000-row catalog, replay exports and SQLite
state database. An earlier complete local run is retained as separate evidence.
The public Render Free service currently
allows eight trials per web request; the cloud audit has a 2 GB container limit
and cannot be presented as a 5,000-trial Render Free performance measurement.
The deployed physics source is byte-identical to the validated release: the
private source export added only this audit script and its manual workflow.

## Scope

The requested run is 50 reproducible physical configurations, each receiving
100 distinct timed commands: **5,000 full native MuJoCo trials** in total.
Each command starts from an independently restored full `mjSTATE_INTEGRATION`
snapshot and owns independent `MjData`. Results come from measured per-step
collision/contact sensors, actual dynamics, joint limits and goal evaluations.

The seeded configuration distribution varies cube pickup and placement positions,
mass (0.03–0.12 kg), and Coulomb friction (0.4–1.3). It includes clear scenes,
enabled obstacles outside the route, and intentionally blocked controls. The
blocked controls physically intersect the pickup region; their results must be
reported honestly, with no successful candidate fabricated.

Within each configuration, the existing planner uses eight lift/IK templates
and varies movement speed and grasp/release dwell. **5,000 distinct commands
does not mean 5,000 unrelated path topologies or 5,000 different environments.**
The audit checks uniqueness of actual control hashes as well as configuration
plus intervention hashes. All trials must have positive integration steps and
persisted full final simulator state. Selected candidates run again through the
existing authoritative execution path; those additional steps are counted
separately from the 5,000 validation trials.

This is bounded synthetic testing, not calibrated hardware validation or a
general reliability claim. It does not test 5,000 cloth or SciPy experiments.
No LLM calls, recorded videos or fabricated physics outputs are used.

## Evidence and progress

- **Completed cloud result:** 5,000 distinct positive-step trials across 50
  configurations, with 4,000 measured successes and 1,000 collision failures.
  Validation integrated **29,625,840 MuJoCo steps**; fresh selected executions
  bring the total to **29,880,282 steps**. The run took **894.512 s** wall time
  and **870.533 s** process CPU time in a 2 GB Docker container on a hosted
  runner. MuJoCo was version 3.15.0. Both a measured success and a measured
  failure reproduced their evaluation and full final state exactly. These
  counts are from the downloaded cloud report, not the earlier local run.
- **Persisted verification:** the downloaded catalog has exactly 5,000 rows,
  5,000 unique control hashes and a matching SHA-256 digest. Every row records
  positive simulation steps. SQLite contains 50 worlds, 50 experiments and
  5,000 trial records. Three successful branches have full replay exports.
  The hosted workflow independently checked the report, catalog digest and
  SQLite counts before uploading the artifact. The 80% success proportion
  reflects this deliberately mixed, bounded test distribution, including ten
  blocked configurations; it is not a general robot reliability estimate.
- **Cloud backend:** `.github/workflows/backend-physics-5000.yml` runs the
  backend Docker image. It logs measured per-scenario physics progress and
  verifies 5,000 catalog rows and SQLite trial records before upload. Run
  38175668423 completed with every workflow step successful. Artifact copies
  downloaded afterward are evidence from that cloud run, not additional local
  simulations.
- **Local control run:** `artifacts/varied-physics-5000.json` records 5,000
  trials across 50 configurations, 4,000 successes, 1,000 collision failures,
  29,625,840 validation steps, 29,880,282 total steps, 2,382.123 s elapsed,
  5,000 distinct commands and exact native repetition of one success and one
  failure. It is not evidence that the cloud job has finished.
- `artifacts/varied-physics-5000.json`: atomic progress and final aggregate report.
  `status: running` is not completion. Only the finished audit records `passed`.
- `artifacts/varied-physics-5000-trials.jsonl`: one measured catalog entry per
  trial, with configuration/control/state fingerprints, metrics and evaluation.
- `data/run/varied-physics-5000.sqlite3`: persisted worlds, all full trial actions
  and final integration states, events and retained full replay branches.
- `artifacts/varied-physics-5000-top-{1,2,3}.json`: best measured successful
  branches, exported only after completion. They retain full replay frames.
  Every trial has a final state; full replay frames are retained for the best
  branches rather than every one of the 5,000 trials.

Exact native repetition is verified for a measured success and failure when
available. The parent initial-state fingerprint is checked for every scenario.
Failure counts are separate from whether the audit itself completed correctly.

The initial ten-trial smoke executed five scenarios covering the three layout
classes: eight successes, two collisions, with exact repeated states and
evaluations. Its first report mistakenly included `execution_success` in the
failure-status dictionary; the catalog and success/failure counts were correct.
The reporting filter was corrected before starting the full run. The original
smoke evidence is retained without rewriting its output.

## Reproduce

From `P:\VIVACITY\DEMO-` in PowerShell:

```powershell
$env:OMP_NUM_THREADS='1'
$env:OPENBLAS_NUM_THREADS='1'
$env:MKL_NUM_THREADS='1'
$env:VIVACITY_IMMUTABLE_MODEL_FORKS='1'
$env:VIVACITY_MAX_PHYSICS_TRIALS='5000'
.venv/Scripts/python.exe scripts/audit-varied-physics.py --trials 5000 --scenarios 50 --seed 20261011 --output artifacts/varied-physics-5000.json --database data/run/varied-physics-5000.sqlite3
```

For another run, provide new output and database paths. The script refuses to
overwrite previous evidence. It prints real progress while executing and saves
failure information if an invariant or simulator job fails. This audit does not
increase the resource budget of the free Render service.
