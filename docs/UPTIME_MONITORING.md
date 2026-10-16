# Vivacity public uptime monitoring

Verified on 2026-10-12 (Asia/Kolkata).

| Surface | Public URL | UptimeRobot monitor | Check |
| --- | --- | --- | --- |
| Frontend | https://demo.tryvivacity.com/ | [Vivacity demo frontend](https://dashboard.uptimerobot.com/monitors/804249013) | HTTP HEAD, every 5 minutes |
| Backend | https://vivacity-runtime.onrender.com/health | [Vivacity backend /health](https://dashboard.uptimerobot.com/monitors/804249160) | HTTP HEAD, every 5 minutes |

Both monitors use the existing UptimeRobot email alert contact. The backend's
`HEAD /health` route returns HTTP 200 with an empty body; `GET /health` retains
the JSON status and backend versions. No simulation is run by either health
probe. The backend monitor was created after Render deployed source
`a133a56ea7d51f48303e8690633b08af2b4a98b1` as
`dep-db6hm2c9v7es73ffs8vg`. The public backend HEAD and GET requests and
frontend HEAD request each returned HTTP 200 after deployment. The CI run
for this backend revision passed 139 Docker tests and the separate 512 MB
lab check passed one test. UptimeRobot's first independent checks reported
**Up** for both monitors; the backend detail showed a completed check and
"Checked every 5m". Evidence: `artifacts/uptime-backend-up.png`.

The monitors help prevent **idle** spin-down because their five-minute interval
is shorter than Render Free's 15-minute idle window. They do not guarantee
continuous availability: Render can restart a free instance, monitoring can
miss checks, the service can crash, and deployment interrupts requests. Render
Free's filesystem is ephemeral, so SQLite experiment history may disappear on
restart or redeploy. UptimeRobot reports reachability; it does not verify
MuJoCo, SciPy, WebSockets, replay, or experiment persistence. See
[Render Free limitations](https://render.com/docs/free) and
[UptimeRobot monitoring intervals](https://help.uptimerobot.com/en/articles/11360876-what-is-a-monitoring-interval-in-uptimerobot).

If the backend monitor reports Down, inspect the [Render service deployment and
logs](https://dashboard.render.com/web/srv-db5p7pjbc2fs739lnl6g/deploys).
Verify `HEAD /health` returns 200, then `GET /health` reports `status: ok`.
For application-level failures, use the actual UI and API experiment flow.
Moving to truly always-on and durable hosting requires a paid always-on
instance with a persistent database or disk; the current service remains Free.
