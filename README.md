# Creative Reformatting Engine

A media pipeline that takes one master image or video and produces every
platform-ready ratio — **16:9, 1:1, 9:16, 4:5** — with subject-aware smart crop,
a clean still pulled from video, and a subject-tracked, active-speaker-aware
vertical reel. **No derived asset enters the library until it passes an
automated compliance report against a machine-readable spec sheet.**

---

## What it actually does

| Stage | Behaviour |
|---|---|
| **Crop** | Detects faces and bodies, builds a weighted *subject importance map*, and solves for the crop window that maximises retained subject importance under hard face-integrity and safe-zone constraints. The centre of the frame carries no special status. |
| **Reframe** | Tracks faces across analysis frames, measures per-face mouth articulation, correlates it against the audio envelope, and pans the crop to whoever is speaking — with hysteresis so it does not oscillate, and hard cuts at shot boundaries. |
| **Validate** | Re-detects subjects **in the rendered output** and checks 18 rules covering geometry, container, codecs, quality, face integrity, safe zones, platform UI chrome, crop motion and speaker framing. PASS publishes; FAIL quarantines with evidence. |

---

## Quick start

Requires Python 3.11–3.12 and Node 20+. `ffmpeg` is bundled via pip, so nothing
needs to be on `PATH`.

```bash
make setup                     # venv + deps + vision models + npm install
cp .env.example .env

# headless, end to end
make process FILE=test_sample/input_image.png
make process FILE=test_sample/input_video.mp4

# or the full stack
make api                       # :8000  API + in-process worker
make web                       # :5173  UI (proxies /api and /media)
```

Docker, if you prefer: `make up` → UI on `:8080`, API on `:8000`.

### Results on the supplied test assets

```
input_image.png  (4000×4000, two small off-centre faces)   4/4 variants PASS
input_video.mp4  (1920×1080, 190s, 25fps, fast-cut drama)  2/2 variants PASS
```

---

## How the crop works

Cropping is posed as constrained optimisation, not a heuristic.

A **subject importance map** is built per frame by layering an anisotropic
Gaussian per face (weighted by size, confidence and speaking score), broader
low-weight blobs for bodies, and a weak spectral-residual saliency base that
only dominates when there is no person in frame.

The solver then searches `(scale, x, y)` coarse-to-fine, reading box sums from
an integral image, and maximises:

```
score = 1.00 · subject coverage        # importance retained
      + 0.55 · composition             # rule of thirds, eye line, headroom
      + 0.22 · scale                   # prefer keeping more of the master
      − 3.00 · clipped-face penalty    # a sliced face is near-fatal
      − 0.22 · dropped-face penalty    # excluding an extra is legitimate
      − safe-zone / UI-chrome penalties
```

The asymmetry between the clip and drop penalties is the important part: when
two faces cannot both fit a 9:16 window, **excluding one is correct and slicing
one is not.**

Every decision is persisted with a plain-English rationale, visible in the UI
and in `cre process` output:

```
crop  x=1126 y=1094 w=1543 h=2743  coverage=83.8% faces_intact=2 clipped=0
- crop centre offset from frame centre by 2.6% horizontally, 11.6% vertically
  to compose around the detected subject
- retains 83.8% of subject importance
- composition score 0.76 (rule of thirds, eye line, headroom)
```

---

## How speaker-aware reframing works

1. **Window selection** — score the timeline on speech, subject dominance,
   crowding and shot changes, preferring a span *inside a single shot*. A
   7-second cut that holds one speaker beats a 15-second montage.
2. **Track** — Hungarian assignment over IoU, centre distance and scale, with a
   short coast so a head turn does not mint a new identity. Tracks are retired
   (not erased) at cuts, because identity must not cross a cut but the history
   still matters.
3. **Detect the speaker** — per-track mouth aperture from the face mesh →
   articulation energy → windowed normalised cross-correlation against the
   audio envelope, gated by a speech detector, softmaxed across candidates,
   then hysteresis plus a minimum dwell before the frame is handed over.
4. **Smooth** — dead zone, then a **closed-form critically damped spring**,
   then a two-pass forward/backward filter to cancel lag. Hard reset at cuts.
5. **Render** at full frame rate, interpolating the path between analysis
   steps, then mux the original audio and normalise to the spec codec.

The reframe path is exposed at `/api/v1/variants/{id}/reframe-path` and drawn in
the UI, coloured by active speaker with shot cuts marked — so "does the crop
follow the talker?" is answerable by looking, not by trusting us.

---

## The validator

The spec sheet (`specs/platform_specs.yaml`) is the single source of truth and
is served verbatim at `/api/v1/spec`, so a reviewer can check our verdicts
against the same document the validator used.

Rules **re-measure from the rendered file** and never consult the crop decision
that produced it. If the cropper claims a face is intact and the validator
disagrees, the validator wins.

| Group | Rules |
|---|---|
| Technical | dimensions, aspect ratio, container/codec/pixel format, audio codec & channels & rate, frame rate, duration, bitrate, file size |
| Quality | sharpness, letterboxing, exposure |
| Subject | face integrity, subject presence, action-safe zone, platform UI chrome, reframe motion, active-speaker framing, crop provenance |

Two rules exist specifically to catch the stated auto-disqualifiers:

- **`subject.crop_provenance`** flags a crop that stays centred while the
  subject sits off-centre — the signature of a centre crop with a detector
  bolted on.
- **`subject.reframe_motion`** fails a vertical video whose crop never moves
  while the subject does — the signature of reframing once at frame 0.

A rule that raises an exception is recorded as **FAIL**, never silently skipped.

### Calibration notes

Several thresholds are deliberately not the obvious value, and the spec file
says why inline:

- **Video sharpness floor is 6.0, versus 45 for stills.** A 9:16 reel carries
  only ~607px of real horizontal detail from a 1080p master and is upscaled to
  1080 wide. Normal output measures 12–20 where the HD source measures ~70; a
  genuinely defocused frame still measures under 2.
- **Face integrity is judged on the facial core, not the padded head box.**
  Trimming a hairline is ordinary close-up framing. Slicing through the eyes is
  the defect this system exists to prevent.
- **Clipped *background* faces warn; clipped *subjects* fail.** A wide crowd
  shot reframed to 9:16 unavoidably cuts extras.
- **Subject presence is judged on the longest unbroken absence, not total
  coverage.** Scattered misses are the detector losing a profile view; a
  two-second run is the crop following the wrong thing.

---

## Architecture

Ports and adapters, so moving to AWS is a configuration change:

```
backend/src/cre/
├── domain/         models, enums, geometry primitives
├── ports/          Storage · JobQueue · Repository  (interfaces)
├── adapters/       local|s3 · inmemory|sqs · sqlite
├── vision/         face detection, mesh, pose, tracking, shots, audio, saliency
├── asd/            active-speaker detection (audio-visual correlation)
├── crop/           subject map, crop solver, temporal smoothing
├── pipeline/       analysis, image, video, still extraction
├── validation/     spec loader, rule engine, 18 rules
├── services/       ingest, reformat orchestration + the publication gate
├── worker/         job runner and standalone entrypoint
└── api/            FastAPI v1
```

The publication gate lives in exactly one place
(`services/reformat_service.py`): render → validate → PASS ? publish :
quarantine. "No asset enters unvalidated" is structural, not conventional.

| Concern | Local | AWS |
|---|---|---|
| Storage | `data/` directory | S3 + CloudFront |
| Queue | thread pool | SQS + DLQ |
| Metadata | SQLite | Aurora Serverless v2 |
| Worker | in-process | separate ECS service, scaled on queue depth |

Switching is environment only — see `.env.example` and `infra/aws/`.

---

## Testing

```bash
make test        # 74 unit tests, no media fixtures needed
make test-all    # adds the slow end-to-end media tests
make lint
```

Synthetic clips are generated in `conftest.py` rather than committed, so the
ground truth is exact: we know precisely who is speaking when and where they
are. The suite asserts the properties the brief names, including:

- an off-centre face moves the crop away from the frame centre, in all 4 ratios
- a narrow ratio drops a secondary face rather than slicing it
- a two-person alternating-speaker clip pans left, then right, in sync
- a moving subject produces a crop path that moves with it
- a **sliced face still fails** validation after the close-up relaxations
- the smoother is stable at every analysis frame rate from 6 to 30 fps

---

## API

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/v1/spec` | the machine-readable spec sheet |
| `POST` | `/api/v1/assets` | upload a master, auto-queue the render set |
| `GET` | `/api/v1/assets/{id}/variants` | every variant, published or quarantined |
| `GET` | `/api/v1/assets/{id}/library` | **only** variants that passed |
| `POST` | `/api/v1/assets/{id}/variants/regenerate` | re-render a single variant |
| `GET` | `/api/v1/variants/{id}/report` | full compliance report with evidence |
| `GET` | `/api/v1/variants/{id}/reframe-path` | the solved crop path |
| `GET` | `/api/v1/jobs/{id}` | job progress |

Interactive docs at `/docs`.

---

## Known limitations

- **Frontal-face detection** (BlazeFace) is the subject signal. Faces in deep
  profile are missed; tracking bridges short gaps, but a subject who stays
  turned away for seconds will be reported as absent.
- **Active-speaker detection is audio-visual correlation**, not a trained ASD
  model. It is reliable when mouths are resolvable and speech is reasonably
  clean; it degrades on very small faces, heavy music beds, or dubbed audio
  where lips and sound genuinely disagree.
- **A 9:16 crop of a 16:9 master is full-height by construction**, so vertical
  safe-zone violations can only be resolved by zooming in, and for a face low
  in the master they may be unresolvable.
- The **Terraform has not been run through `validate` or `plan`** — Terraform
  was not available in the authoring environment. Review before applying.
- The **UI was verified through the API and the Vite proxy**, not visually in a
  browser; no browser automation was available in this environment.
