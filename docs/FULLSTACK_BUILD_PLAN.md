# Full application build record

Outcome: an investor can execute, inspect and replay genuine robot and scientific experiments in one branded workspace.

Existing evidence: preserved FastAPI/Pydantic, SQLite, independent MuJoCo forks, seeded IK/RRT, SciPy fit comparison and real replay. No frontend existed. The first test invocation collected the archived checkout in data and failed with five duplicate-module collection errors. pytest.ini now scopes collection to tests; all 57 original tests passed in 39.60 seconds. Real six-experiment HTTP/WS journey passed again. Both external UI hook entrypoints returned exit 0.

Brand inspected 2026-10-10: https://www.tryvivacity.com/ returned HTTP 200 and was inspected in the browser, including rendered screenshot and computed styles. Geist and Geist Mono; native fork logo; square rules/buttons; dark #08090b / light ink #f2efe6 / cobalt #557bff. Use its actual assets and typography, a large light engineering workcell in the dark workspace, and no decorative animated terminal. Brand reference HTML/CSS are retained locally in ignored data; reusable logo/font provenance is recorded with frontend assets.

Plan:
1. Preserve and reverify backend; scope test discovery rather than removing archival files.
2. Add Vite/React/TypeScript, Tailwind, generated OpenAPI types and shared runtime client.
3. Render compiled Panda geometry with measured body world transforms; orbit/reset camera; interpolate replay samples only.
4. Implement branches, measured failures, replay timeline, obstacle apply/replan, commit/reset, persisted IDs, retry keys and reconnect/poll fallback.
5. Chart observations and two executed SciPy hypotheses, residuals, held-out metrics, uncertainty and explicit generation/observation controls.
6. Responsive/keyboard/reduced-motion states, real errors/offline recovery and technical/architecture inspectors.
7. Run backend/build/Playwright/axe checks, inspect desktop/mobile screenshots, measure actual load/scene/playback timing, then write demo guide and limitations.

Risks: WebGL availability, coordinate conversion, race conditions on lab/job switching, stale replays after edits, accidental duplicate submissions, body-vs-geom frames, scientific truth leakage, and misleading job progress. Cancellation is absent from the backend; the UI must state this instead of inventing it. Local-only server/auth/LLM limitations remain explicit. No frontend should substitute recorded evidence fixtures for live computation.

Completed 2026-10-10: all seven steps implemented and exercised. Final evidence: 57 backend tests, six real Playwright journeys, strict production build, clean locked installation, live numerical/API/geometry verification, desktop/mobile screenshot inspection, keyboard/axe checks, startup/shutdown checks, and separate software/native browser performance samples. See `IMPLEMENTATION_STATUS.md`, `DEMO_GUIDE.md` and `DEMO_LIMITATIONS.md` for the final scope and evidence.
