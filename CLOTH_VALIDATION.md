# Cloth validation

Current public verification (2f61389) actually executed three constrained flex
validations and a fresh fold. Alignment **0.923365 mm**, coverage **100%**, clamp
error **0.673552 mm**, quality **0.969221**, maximum penetration **1.981481 mm**.
It received actual vertices and Panda transforms over WSS. Evidence:
`artifacts/render-final-labs-long.json`; eight checked browser behaviors passed,
with 113 live frames and 27 events across cloth/science, no page errors or axe
violations in the checked scope. Current deployment-image tests rerun cloth
under the unchanged simulator and pass. See `docs/FINAL_VERIFICATION.md`.

This remains **experimental**: the arm carries a pre-attached bar with seven
cloth constraints and a fixed hinge. It does not acquire a loose fabric grasp
with ordinary fingers. No calibrated textile/contact model or general folding
capability is claimed. Earlier failed timeout reports remain preserved.

Existing experimental benchmark: actuated Panda carries a pre-attached folding bar through a 7 × 7 MuJoCo flex sheet, releases its seven ideal edge constraints and allows settling. Actual integrated vertex/body states supply alignment RMSE, vertex coverage, constraint error and contact/limit/controller failure checks. The fixed hinge, pre-attached fixture and disabled bar collision mask are explicit limitations. There is no autonomous frictional cloth-grasp acquisition or general garment folding.

The original-code baseline executed cloth checks within 86/86 passes. The final full backend regression passed **101/101** in 290.66 s (`artifacts/master-release-backend.xml`). Prior release evidence remains historical in `ROBOT_CLOTH_RELEASE.md`.

## Separate reliability benchmark — actually executed

`python -m scripts.benchmark_cloth --runs 5` independently restored the full fixed snapshot and integrated the actuated fixture five times: **5 successes / 0 failures**, **26.6677 s total**, **4.78–5.80 s physics per execution**, 2,501 integration steps each. Alignment RMSE was **0.0003588456 m**, vertex coverage **1.0**, fold-quality score **0.9880385**, and maximum robot joint tracking error **0.1008178 rad**. Per-run measured evaluations, configuration, seed and model hash are in `artifacts/cloth-reliability.json`. Identical fixed repeats demonstrate reproducibility; they do not establish general garment robustness.

The complete new local browser journey executed 5,000 distinct proposals, rejected 2,984 through bounded geometric screening, physically validated three, and executed the selected command again in fresh MuJoCo state. The selected live fold measured **0.0009233651 m** alignment error, **1.0** coverage and **2.024586 rad** robot displacement. Final renderer vertices matched all actual measured vertices within 1e-6; final edge constraints were released. Evidence: `artifacts/master-live-verification.json`, `artifacts/master-live-cloth.png`, `artifacts/master-measurements.json`. A disabled-actuator regression fails with `controller_failure`, rather than folding through arbitrary frontend motion.

No flex vertices are animated by the frontend as simulation input. The sheet evolves through MuJoCo elasticity, contact, gravity, the fixed hinge and explicit bar attachments; the backend actuators move the arm. This remains **experimental constrained single-fold manipulation**, not autonomous cloth grasping, dual-arm folding, friction-only fabric retention, realistic material calibration or arbitrary clothing handling. Native cloth garment imports cannot execute.

Current public browser journey also passed fresh actuated execution, >0.1 rad measured arm displacement, released constraints, and all 49 rendered vertices matching the final actual integrated frame within 1e-6. Its three validation rollouts plus fresh selected execution performed 11,032 steps and took 109.183 s under concurrent software graphics. Evidence: `artifacts/master-public-verification.json`, `artifacts/master-public-cloth.png`, `artifacts/master-public-measurements.json`.
