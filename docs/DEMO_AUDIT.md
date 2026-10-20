# Private World Laboratory: pre-change audit

Date: 2026-10-21. Scope: the existing public UI at `https://demo.tryvivacity.com/` and the repository at `P:\VIVACITY\DEMO-`. This audit distinguishes direct observation in this work from source inspection and historical release records.

## Observed starting point

The public page opened directly into the Factory workspace. It showed an interactive Panda sorting cell, production controls, and saved results from an earlier browser session. It did **not** start a new experiment on load. The first viewport led with “Carton sorting” and technical controls; it did not explain a concrete failure, a single intervention, or a measured before/after journey. The existing dark shell and light industrial scene were functional but had a stronger tool-workspace character than the requested private laboratory character. The motion reference was inspected only for pacing and atmosphere; its layout and imagery were not copied.

The local repository contains unrelated untracked artifacts and an application transcript. They are left untouched. The tracked working tree was clean before this transformation.

## Capability inventory and evidence boundary

| Capability | State before this change | Evidence and constraint |
| --- | --- | --- |
| Factory world and physical production | Implemented | `vivacity/factory.py`, `factory_controller.py`, `factory_service.py` use MuJoCo state, contacts, collision checks, controller commands and recorded frames. A direct one-carton sweep found `dropped_object` at force scale 0.008 after 4,148 native steps; the same world at full gripper force delivered one carton after 17,083 steps. |
| World state, fork and saved runs | Implemented | Factory cell initial states and run initial/final states are stored by the service. Benchmark trials create owned cells from frozen configurations; recorded samples are paginated from SQLite. A capability token scopes factory records; it is not a user account. |
| Controlled comparison | Implemented | `factory_benchmark.py` builds matched-seed training trials and separate held-out starting-position trials. Selection uses training success rate, then mean successful simulation duration. Small samples do not establish hardware reliability or statistical significance. |
| Telemetry, plotting and replay | Implemented | `FactoryAnalysis.tsx` requests saved samples, provides an inspection cursor, plots six groups, and exports CSV/JSON. `FactoryDiscovery.tsx` fits descriptive approximations to sampled trajectories. The browser view reflects saved backend frames; it is not a video or live hardware. |
| Mathematical equations | Implemented with a boundary | Fitted LaTeX is rendered by KaTeX. An official Desmos embed requires an authorized commercial API key; the measured fallback plot works without it. Desmos scratch edits do not alter authoritative measurements. |
| Import/export and collaboration records | Implemented with limits | Factory definitions, run evidence, PDF/ZIP reports and project versions are stored/exported. Imports create an idle cell and do not launder uploaded results into verified evidence. There is no account-based collaboration. |
| Other robot worlds and operations | Implemented with bounded adapters | The robotics workspace has multiple modeled arms, worlds and tasks. These are preserved but are not the focus of the first-visit Factory journey. Capability varies by robot and task. |
| First-visit guided narrative | Missing | The first screen did not connect problem → controlled intervention → measured comparison. Advanced details were visible before a visitor understood the decision. |
| Cinematic introduction | Missing | There was no skippable, reduced-motion-aware opening tied to actual recorded simulator behavior. |
| Explore/Research depth | Missing as a mode | Technical panels could be expanded, but there was no first-time mode that simplified the same experiment state. |
| Hardware validation, causal scientific discovery and large campaigns | Not demonstrated | Factory evidence is simulated. Per-run fits are descriptive; this does not establish causal laws. A 5,000-definition campaign is not implemented. |

## Main risks and decision

The highest-value slice is a one-carton grip-force challenge, because a fixed-seed weak-grip failure and full-grip completion were measured with otherwise identical MuJoCo configuration. The intro can replay a short, labelled excerpt from those **recorded** frames. It must not feed its fixture into live results. The Explore flow will launch new backend trials only after a user click, and Research will expose the same saved state and existing analysis/export tools.

The existing public backend has previously run on Render Free. Free hosting can cold-start and its SQLite disk is ephemeral across deployment; no always-on or durable-production claim follows from this change. The frontend build also has a large world-preview chunk and a WebGL factory view. The opening should load lazily, be skippable immediately, and avoid continuous particle effects or a second permanent render loop. Browser acceptance must check the exact route, reduced motion, narrow width, keyboard access, console errors, and a real baseline/comparison run.

Acceptance: a fresh visitor sees the guided challenge without an automatically launched experiment; clicks run a real baseline and a backend comparison; the UI reports the measured failure and training/held-out delivery counts, then opens recorded analysis and exports in Research. Changing world conditions must continue to create a new cell rather than silently rewriting old evidence.
