> Current arm-fold revision: complete backend **86/86 passed in 416.81 s**; intermediate **85 passed/1 timing failure** retained. Exact reports and current custom-domain browser evidence are linked from [ROBOT_CLOTH_RELEASE.md](ROBOT_CLOTH_RELEASE.md). Earlier V2 measurements below describe the previous release.

The current custom-domain Panda cloth experiment ran eight real flex rollouts and completed in 460.49 seconds under local CPU contention. The original public checker had a 360-second terminal wait and timed out while the background worker kept running; its persisted job completed successfully. The corrected ten-minute checker was then rerun against that exact completed public experiment and passed its exact vertex/body-position/quaternion replay, release, export, desktop and mobile checks. This timing is not presented as a production responsiveness guarantee.

# Vivacity V2 executed verification

Verification environment: Windows, Python 3.12, MuJoCo 3.15.0, SciPy 1.18.1, Node 25.9.0, local Chromium/software rendering. Seeds are fixed. All numbers below are actual executed measurements, not hardware/production guarantees.

| Check | Executed result | Evidence |
| --- | --- | --- |
| Preserved original backend | 57 passed, 0 failed/error/skipped; 121.242 s | `artifacts/v2-baseline-backend.xml` |
| Initial original browser suite | 4 passed, 2 failed; 477.724 s | `artifacts/v2-baseline-browser-tests.json` |
| Event/history recovery | 2 passed; 15.80 s | Console run; `tests/test_event_history.py`, also included in final JUnit |
| Distinct search/physics/blocked scene | 3 passed; 68.54 s | `artifacts/v2-search-tests.xml` |
| Branch exports | 1 passed; 5.42 s | Console run; `tests/test_branch_exports.py`, also included in final JUnit |
| Reach/action hardening + original robotics | 13 passed; 50.93 s | `artifacts/v2-reach-tests.xml` |
| Scientific inference | 9 passed; 14.38 s | Console run; `tests/test_science.py`, also included in final JUnit |
| Cloth state/replay/search/failure/revision | 3 passed; 98.35 s | `artifacts/v2-cloth-tests.xml` |
| Import decode/persistence/security/API | 16 passed; 3.54 s | `artifacts/v2-import-tests.xml` |
| First complete V2 backend run | 84 passed, 0 failed/error/skipped; 92.67 s | `artifacts/v2-prerefinement-backend.xml` |
| Post-refinement complete backend | 84 passed, 0 failed/error/skipped; 302.63 s (JUnit 302.276 s) | `artifacts/v2-final-backend.xml` |
| Strict generated types/production build | Passed; latest local build 23.09 s | Executed `npm run generate:api`, `npm run build` |
| Python dependency/compilation checks | `pip check` and `compileall` passed | Executed with the locked local virtual environment |

The original browser failures were an overloaded one-worker journey exceeding its timeout and a software-GPU frame-sample threshold. The original suite is retained in `frontend/e2e-baseline`; V2 coverage updates changed labels/flows and records actual timing instead of assuming a frame-rate target. An initial cloth-test call passed a wrapper instead of the configuration and was corrected/rerun. An initial live cloth browser timeout (180 s vs job 182.92 s) was followed by a successful completed-result inspection. An initial mobile import canvas overflow was fixed/rerun. These intermediate failures remain disclosed; the final suite result is recorded below after execution.

Independent real browser checks passed for 1440/768/375 layouts, one measured inspector, all three robot JSON exports, autoplay/loop/exact robot endpoint, scientific predicted-position accuracy and zero-mass control, actual cloth vertices/release/export and safe visual upload/native staging. `artifacts/v2-journey.json`, `v2-science-journey.json`, `v2-cloth-journey.json`, `v2-import-journey.json` and `v2-opening.json` contain their evidence. Screenshots were actually opened for visual inspection.

Robot browser experiment: 5,000 distinct generated/screened paths, 104 screening rejections, 12 real episodes, 9 successes, job 68.31 s under shared workload. Selected measured episode 6.97 simulation seconds, 8.8 mm goal error, 2.36 rad sampled joint path. Cloth browser experiment: 5,000 distinct screened clamp motions, 2,984 screening rejections, 8 integrated episodes, 8 successes, job 182.92 s under concurrent workload; selected alignment approximately 0.44 mm, coverage 100%, duration 3.53 simulation seconds. Process CPU, step totals and payload sizes are retained in API/artifact records.

One upstream Starlette/httpx TestClient deprecation warning remains. Production builds report the lazy Three.js vendor chunk over 500 kB (roughly 933 kB / 249 kB gzip); this is recorded as a performance limitation, not a failed build. No hosted LLM calls were exercised.

## Final browser verification

The first V2 run completed **5 passed / 3 failed**, retained in `artifacts/v2-first-browser-tests.json`. It exposed a replay-payload arrival race, an ambiguous scientific-value selector, and a mobile offline assertion targeting a deliberately hidden header label. The UI now shows Loading recorded evidence and disables mutations until the actual replay arrives. Replay fetching occurs once at completion instead of downloading large branch traces on every progress event. The tests wait for replay readiness and inspect scoped/visible metrics and offline feedback.

The next full run completed **7 passed / 1 failed in 724.47 seconds**, retained in `artifacts/v2-final-browser-tests.json`. Science, actual lost-response retry, duplicate submission/WebSocket reconnect/history, replay loop/exact endpoint/performance, responsive/keyboard/offline/axe, cloth physics and imports passed. The remaining robot test stopped on a strict selector that matched three genuine collision outcomes; choosing the first failure fixes that test ambiguity.

The first dedicated rerun reached the clear-route replan but used a 30-second readiness assertion while genuine new physics was still running; it failed and is retained in `artifacts/v2-targeted-browser-first.json`. The completion helper now waits up to 240 seconds for the enabled Run control before asserting the terminal status, avoiding matching the previous experiment's transient status. The repaired robot journey then **passed, 1/1, 371.36 seconds** (`artifacts/v2-targeted-browser-tests.json`). It verified all body transforms, all three distinct JSON exports, failed-branch commit prevention, committing the selected alternative, reset, fresh clear-route results and blocked-scene no-result behavior. **All eight distinct journeys have passed across the full run and targeted rerun; there was no single clean 8/8 full run.** No failed test is counted as a pass.

The accessibility journey returned zero axe violations at 1440/768/375 widths for the tested WCAG tags (`artifacts/v2-browser/accessibility.json`), with no horizontal overflow and keyboard/reduced-motion/offline feedback checks. This is not a screen-reader usability certification.

Software rendering in this run measured 17 frame samples, mean **506.51 ms**, p95 **1661.90 ms** and robot asset-load time **4555 ms** (`artifacts/v2-browser/performance.json`). This is slow and does not meet a smooth-animation performance target. The verification asserts actual looping, bounded evidence, exact endpoints and elapsed-time behavior rather than pretending to establish 60 FPS or production Core Web Vitals.

## Public release verification

`node scripts/check-v2-public.mjs` passed against **https://vivacity-investor-demo.vercel.app/** and the actual HTTPS API tunnel, in **410.45 seconds**. It created fresh worlds and ran real jobs through the deployed browser; it did not substitute stored trajectories or expected winners. Evidence is `artifacts/v2-public-verification.json`, with actual downloads and viewed screenshots in `artifacts/v2-public-*`.

| Public experiment | Actual search / execution | Job wall / process CPU | Steps or integration calls | Replay bytes |
| --- | --- | --- | --- | --- |
| Original Panda obstacle | 5,000 distinct screened, 104 screening rejections, 12 integrated, 9 feasible / 3 real collisions | 49.65 / 47.69 s | 38,153 steps | 4,346,875 |
| Changed clear route | 5,000 distinct screened, 0 screening rejections, 12 integrated / 12 feasible | 59.07 / 32.63 s | 41,799 steps | 4,752,164 |
| Scientific hypotheses | Two actual training fits / held-out evaluations | 1.32 / 1.08 s | 30 integration calls | 40,519 |
| Constrained cloth | 5,000 distinct screened, 2,984 screening rejections, 8 integrated / 8 feasible | 125.33 / 106.38 s | 14,152 steps | 2,126,436 |

The public selected robot episode reached with 8.827 mm error in 6.966 simulation seconds. Changing the obstacle generated a new experiment, invalidated the original, and rejected its stale commit with HTTP 409. The public scientific fit estimated mass **0.11987185 ± 0.00023288** (local linearized uncertainty), with training RMSE **0.00085770** and held-out RMSE **0.00102039**; the baseline's held-out RMSE was approximately **0.30751**. The actual solver prediction was rendered and downloaded, and the world response contained no hidden generating mass. Selected cloth alignment was **0.4375 mm**, measured vertex coverage **100%**, with released final clamps and actual 49-vertex replay.

Robot/science rendered endpoints matched actual records to 1e-8; cloth float32 vertices to 1e-6. Export frames equaled stored branch traces. The deployed upload decoded and displayed a real GLB; mobile import layout had no overflow and exactly one inspector. Seven WSS connections opened and **108 real versioned events** were captured, including terminal completion. There were **zero captured page/console errors and zero adapter/job errors**. Expected collision failures are measured outcomes, not job errors. These are four executed jobs, not a reliability or latency guarantee.

Visual review of the blocked fixture found repetitive contact-pair labels. The final small display refinement preserves the actual contact count and full exports, while showing at most three unique body pairs. An actual persisted 49-contact failed branch was inspected locally and selected successfully at mobile width (`artifacts/v2-failure-inspector-local.json`/`.png`). Strict types and production build passed after this text refinement. The final public build also passed actual failed-branch selection, concise summary, one inspector and mobile overflow checks (`artifacts/v2-failure-inspector-public.json`/`.png`). These checks refetched actual persisted records; they did not launch additional physics jobs. The complete public physics journey above preceded only this display-text change.

Final Vercel deployment **`dpl_G35QMphXwA9k8n2hRo87pUN4cfEV`** is Ready and aliased to the public URL. Vercel's strict build passed (3.73 s Vite build). The full public physics journey used preceding deployment `dpl_BikShrcNkTrcpfjT77oKpAqQhHJ5`; its simulator/backend logic is unchanged in the final display refinement. Deployment metadata: `artifacts/v2-deployment.json`. No independent durable backend host or complete security/availability guarantee is asserted.

Final external health returned `ok`. The public `/openapi.json` exactly matched the freshly exported local specification, with **16 REST paths and the WebSocket extension**. The historical hook failure and executed Windows wrapper repair remain documented in `docs/HOOK_DIAGNOSTICS.md`; it never affected backend execution. The current design hook also executed successfully on the inspector refinement.
