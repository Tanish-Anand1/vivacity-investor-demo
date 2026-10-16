# Factory mathematical discovery — implementation and handoff

The factory records MuJoCo frames first. A separate numerical worker projects
eight measured time series into SQLite and fits descriptive equations without
blocking the physics lane. It starts at 25 recorded samples and refreshes in
100-sample batches with constant, linear and quadratic models. On completion it tries constant, linear,
quadratic, cubic, exponential, sinusoidal, damped sinusoidal and piecewise
linear models. Fitting starts after 25 finite samples. This is trajectory
description within a run, not physical-law discovery or a causal estimate.
R² is `null` when held-out standard deviation is less than 5% of training standard deviation;
RMSE and MAE remain available instead of displaying an unstable quotient.

## API

All factory requests require `X-Workspace-Token`, the same opaque owner token
used to create the cell. The canonical measurements are the paginated run
samples; fitted data is a separate read-only derived record.

```text
POST /v1/factory/cells                         -> 201 cell
POST /v1/factory/cells/{cell_id}/runs           -> 202 run
GET  /v1/factory/runs/{run_id}                  -> run status
GET  /v1/factory/runs/{run_id}/samples?after=-1 -> paged MuJoCo frames
GET  /v1/factory/runs/{run_id}/discovery        -> persisted equations
GET  /v1/factory/runs                           -> saved runs for comparison
```

Start with `{"mode":"conveyor"}` for a short physical run or
`{"mode":"production"}` for the pick, transfer and delivery sequence. A
discovery response has this shape; numbers below illustrate the schema only,
and are **not** an experiment result:

```json
{
  "schema_version": "vivacity.factory-discoveries/1.0",
  "run_id": "<owned run UUID>",
  "sample_count": 174,
  "processing": false,
  "source": "Measured MuJoCo frames; fitted curves are descriptive approximations.",
  "series": {
    "z": {
      "quantity": "z", "unit": "m", "x_unit": "s",
      "sample_count": 174, "train_count": 139, "held_out_count": 35,
      "fit_stage": "final", "status": "poor_fit",
      "selected_model": "linear", "updated_at": 0,
      "models": [
        {
          "model": "linear", "parameters": [],
          "validation_status": "poor_fit",
          "equation_latex": "<Desmos expression with a time-domain restriction>",
          "display_latex": "<typeset equation with t, normalized time, domain and cases where needed>",
          "editable_latex": "<Desmos expression using adjustable a_1, a_2 ...>",
          "equation_text": "<human-readable equation>",
          "training": {"rmse": 0, "mae": 0, "r2": null},
          "validation": {"rmse": 0, "mae": 0, "r2": null},
          "predicted_curve": [[0, 0]], "domain_s": [0, 0]
        }
      ],
      "provenance": {"source": "MuJoCo factory frames", "run_id": "<owned run UUID>"}
    }
  },
  "relationships": []
}
```

Use `openapi.json` for all required fields and types. The response can be
temporarily empty while fewer than 25 samples have been recorded. Poll it
while the run or `processing` is active. A restart resumes incomplete final
fits from saved scalar measurements. Existing runs created before this feature
do not contain scalar projections and cannot be fitted through this endpoint.

The same response includes a separate `joint_1_torque_vs_dynamics`
relationship when final data is available. It fits measured torque against
measured angular acceleration and velocity with a chronological held-out
fifth. It reports `insufficient_signal` when the joint did not vary enough.
Both series and relationship provenance include the saved run configuration,
which identifies the experimental conditions behind the measurement.
Even a validated association is controller-specific, not an inertia or
friction identification. The backend intentionally does not fit mass versus
force, throughput versus speed or workload versus energy from one run when
there is insufficient variation or no electrical power model.

## Frontend connection

`frontend/src/FactoryDiscovery.tsx` is mounted below the existing factory
analysis. It polls the owned discovery endpoint, overlays original sample
points and the selected backend curve, exposes family selection and a saved-run
comparison, and shows train/held-out metrics and fit status. The measured CSV
and JSON snapshot downloads are client-generated from the received canonical
samples. The snapshot includes the selected backend model and, if an embedded
calculator is active, its `getState()` output. Editing that calculator is an
exploratory scratch operation and never writes to the physical experiment.
With an authorized calculator key, the user can reopen that opaque state with
`setState()` from a saved Vivacity snapshot. The import is limited to 1 MiB and
requires the same run and measured quantity to be selected. A snapshot saved
without an active calculator has no editable state to restore. Original
MuJoCo samples and persisted fits are never replaced by imported expressions.
The UI typesets `display_latex` with KaTeX and accessible MathML. This is a
presentation of the same fitted parameters as `equation_latex`, which remains
the Desmos-compatible expression. The conventional display uses simulation
time `t`, explicit domains and a `cases` layout for piecewise fits. Older
saved models without `display_latex` fall back to their Desmos LaTeX.
The Copy LaTeX action copies the displayed source; snapshots retain both forms.
Long equations scroll inside their card on narrow screens.

Desmos uses the [official Graphing Calculator API v1.12](https://www.desmos.com/api/v1.12/docs/index.html?lang=en):
`GraphingCalculator`, `setExpression`/table columns, `setMathBounds`,
`updateSettings`, `observeEvent`, `getState`, and `destroy`. The build-time
variable `VITE_DESMOS_API_KEY` enables the adapter. Browser API keys are sent
to Desmos in the script URL and are visible to visitors by design, so use only
a vendor-authorized, origin-restricted browser key. There is no configured key
in this repository. Under the [Desmos API terms](https://www.desmos.com/api-terms),
the public commercial embed needs the appropriate agreement; a trial key is
not a production substitute. Until one is provided, the local measured graph,
equations, comparison and exports remain usable, and the page clearly says the
interactive Desmos embed is unavailable. The actual Desmos edit interaction
cannot be accepted as working until tested with an authorized key.
Both backend equations and browser parameter values expand scientific
notation into plain decimal literals before being sent to Desmos.
Completed run reports include the persisted equation snapshot available when
the report is prepared. The PDF labels provisional and poor fits, shows the
selected descriptive equations and held-out errors, and the ZIP includes that
same snapshot as `discovery.json`. A report prepared before background fitting
finishes may contain provisional or no fitted series; it does not invent a
final result.

## Verification and limits

Focused Python tests cover measured-value projection, numerical parameter
recovery, poor-fit classification, nonlinear families, multivariable fit,
owner-scoped persistence and restart. The local production-build browser was
observed receiving 200 live samples while physics continued, 174 final
samples in one conveyor run and 236 in a second. Both saved eight series.
The second run's carton Y piecewise fit had 0.009114 m held-out RMSE and
0.9504 held-out R²; its carton height fit was correctly marked poor. A controlled
single-pair 4,225-step conveyor measurement was 6.599 s without discovery
and 6.606 s with it. These are local observations, not a representative
throughput guarantee. Final nonlinear fits run after physics, on one worker.

The 5,000–6,000 **experiment-definition campaign** target is not implemented
by this feature. Existing physics trial limits are unrelated to that target.
The free 512 MiB backend can sleep and has ephemeral storage; it cannot be
claimed always-on or durable. No live Desmos key, public edit test, calibrated
hardware, or cross-run causal inference is present.

## Release verification, 2026-10-14

Backend commit `5e481e9` passed the full deployment-image Linux gate:
297 backend tests and four hard-512 MiB tests, with zero failures, errors or
skips ([GitHub Actions run](https://github.com/Tanish-Anand1/vivacity-runtime/actions/runs/38485502046)).
It is live in Render deploy `dep-db7c6le7bikc73ab2gqg`; frontend deployment
`dpl_2DKas6D8YaLo4PdvL4UAKjGVkjpt` is live on Vercel. The production
OpenAPI path and health endpoint returned HTTP 200. In the deployed browser,
a new one-carton conveyor run recorded 43 MuJoCo frames. At frame 25 the UI
received a provisional model; after completion it received the final eight
series. The selected height model remained `poor_fit`, and the held-out R²
was correctly undefined at both stages because future variation was too
small for a stable quotient. The same public page rendered the backend's
conventional `cases` LaTeX and accessible MathML, changed equations on model
selection, and copied the LaTeX source. Its browser logged zero console errors.
Sixteen backend-generated display/Desmos expressions across the available
families and joint association passed KaTeX parsing. At 390 px the equation
scrolled inside its card without page-level horizontal overflow.
