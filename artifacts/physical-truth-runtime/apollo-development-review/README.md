# Failed Apollo wide-door development evidence

These are actual development outcomes, not an acceptance cohort or completed
cabinet-service result. `review.json` covers R38 through R53, with differing
models and controller revisions. All 16 wide requests failed.

`r53-report.json.gz` retains the final state, contact forces, goals, phase and
planning events, actual native frames, commands, model identity and source
hashes. `r53-sources.zip` contains the exact ten simulation modules used by R53.
The report refers to a content-addressed MJB retained in the local evidence
tree; the large model binary is not included in this Git archive.

Reproduce R53 from the matching source using the locked runtime dependencies:

```powershell
$env:OPENBLAS_NUM_THREADS='1'
$env:OMP_NUM_THREADS='1'
python -m scripts.verify_apollo_door --front-x .65 --finger-stiffness 2400 --opening-angle 1.1 --output data/apollo-wide-r53.json
```

The command returns nonzero because the trial failed. It writes the newly
compiled model, matching sources and actual replay frames. Compare simulator
version and hashes before claiming identical continuation. Cross-platform
numerical differences do not turn a failed result into a pass.

The regression suite separately validates the existing partial-door primitive:

```powershell
python -m pytest --noconftest tests/test_apollo_door.py tests/test_cabinet_route.py tests/test_cabinet_tooling.py tests/test_joint_reserve_ik.py tests/test_cabinet_mechanism.py tests/test_simulated_tooling.py -q
```

Its final local execution passed 35 tests. No source or trace here establishes
full opening, cartridge exchange, hardware validation or a production release.
