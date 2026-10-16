# Spatial pipeline implementation brief

Outcome: reusable World Labs environments with traceable visual, geometry and
physical representations, stable interactive rendering, and measured robotic
variation reports. Preserve the tested MuJoCo runtime and existing interface.

Audit (2026-10-13): text generation, asynchronous provider recovery, private
libraries, independent physics trials and measured replay already exist. Spark
2.3.1 is compatible with the installed Three.js stack, but LoD is disabled and
the loader buffers the entire 500k SPZ. Generated collider previews are bounded
subsamples; the original collider currently is not preserved. Physics uses an
explicit solid box proxy, not the splats or a reconstructed room interior.

Implementation order:
1. Owned, bounded capture uploads and documented text/image/multi-image/pano/
   video provider requests; retain input hashes and asynchronous job provenance.
2. Preserve collider bytes, thumbnails and both 100k/500k appearances; publish
   explicit geometry diagnostics and physical readiness without calibration claims.
3. Stream SPZ decoding, enable SDK view-dependent LoD, bounded device-aware
   quality controls and safe cancellation/disposal. Preserve the single render loop.
4. Seeded physical-condition cycles with a held-out partition and calculated
   failure-region report; optional time-aligned measurement comparison.
5. Contract/security tests, real provider generation, MuJoCo HTTP/WSS execution,
   browser switching/reloading/quality/failure checks, then deploy and recheck.

Constraints: Render Free is not always on, has ephemeral storage and permits
eight validation candidates per experiment. No supplied hardware observations,
automatic object segmentation, measured material inference or Atlas API access.
Never classify generated appearance or illustrative contact presets as calibrated.

Official references checked before implementation:
- https://docs.worldlabs.ai/api
- https://docs.worldlabs.ai/api/reference/media-assets/prepare-upload
- https://sparkjs.dev/docs/splat-mesh/
- https://sparkjs.dev/docs/spark-renderer/
- https://www.worldlabs.ai/blog/real-to-sim-to-real
- https://www.worldlabs.ai/blog/taxonomy-of-world-models
- https://www.worldlabs.ai/blog/spark-2.0
- https://www.worldlabs.ai/blog/announcing-the-world-api
- https://www.worldlabs.ai/blog/3d-as-code
- https://www.worldlabs.ai/blog/atlas

Marble is the implemented provider. Atlas research is not an advertised public
endpoint in the checked World API; keep it unavailable until an official contract
and account access can be verified. Uploaded captures are observations; the
returned scene is inferred/generated and requires independent physical validation.
