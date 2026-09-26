# Architecture

*How the system is put together, and why each decision went the way it did.*

<sub>[← Back to the README](../README.md) &middot; [Architecture](ARCHITECTURE.md) &middot; [Audit](AUDIT.md) &middot; [AWS migration](AWS_MIGRATION.md) &middot; [Free tier](FREE_TIER.md)</sub>

---

## Why ports and adapters

The brief asks for something that runs locally now and moves to AWS later. The
risk in that is a codebase that grows local assumptions — a filesystem path
here, a thread there — until "move to AWS" means a rewrite.

So the three concerns that actually differ between the two environments are
defined as interfaces in `cre/ports/`, and nothing above that layer knows which
implementation is in play:

| Port | Local adapter | AWS adapter |
|---|---|---|
| `Storage` | `LocalStorage` — keys become paths under `data/` | `S3Storage` — keys become objects, with a download cache because ffmpeg and OpenCV need a seekable local file |
| `JobQueue` | `InMemoryQueue` — thread pool; media work releases the GIL inside OpenCV and ffmpeg | `SQSQueue` — long polling, DLQ redrive |
| `Repository` | `SQLiteRepository` | same class, PostgreSQL DSN (Aurora) |

`cre/container.py` is the only module that picks. Everything else receives its
collaborators.

## Pipeline stages

```
ingest → analyse (once) → per-profile render → validate → publish | quarantine
```

Analysis is separated from rendering for two reasons. It is the expensive part,
and regenerating one variant must not re-run face detection over 90 seconds of
video. And it keeps the crop solver honest: it consumes a detection record it
did not produce.

### Image path

`analyze_image` → faces (multi-scale tiled detection, mesh-verified) + bodies
(pose) + saliency → `build_subject_map` → `solve_crop` per profile → JPEG →
validate.

### Video path

`analyze_video` walks the source at `analysis_fps` (rendering is always
full-rate), running shot detection, face detection, mouth-aperture measurement
and tracking. Audio is extracted once to a mono WAV and reduced to speech and
energy envelopes on the same timebase.

Then per profile:

- **reel** — select window → active-speaker timeline → per-frame crop solve
  (anchored to the previous solution) → two-pass smoothing → full-rate render →
  mux audio → normalise codec
- **still** — score candidate frames on sharpness, face size, exposure and
  distance from a cut → crop the winner with the same solver the stills use

## Design decisions worth knowing

**Multi-scale tiled face detection.** The MediaPipe Tasks API publishes only the
short-range BlazeFace bundle, which misses small faces in a large master — on
the 4000x4000 test image it found nothing but a false positive on the floor.
Running detection over a pyramid of overlapping tiles puts a small face at a
workable scale relative to its tile. Both real faces are then found at 0.92-0.97
confidence.

**Face-mesh verification.** At tile scale, a real face and a patch of texture
can both score around 0.7, so detector confidence alone cannot separate them.
The landmarker can: false positives yield no mesh at any padding. Verification
is enabled for stills and for the validator, where a false positive near a frame
edge would otherwise quarantine a good asset.

**Tracks are retired, not erased, at a cut.** Identity must not cross a cut, but
the speaker detector reasons over the whole clip. Clearing the track table at
each boundary silently left it with only the final shot's history — and the reel
fell back to "no speaker" with no error raised anywhere.

**Closed-form spring integration.** The smoother is a critically damped spring.
Stepped with Euler it is only stable while `omega*dt` stays well under 1;
analysis runs as low as 6 fps, which pushes `omega*dt` to about 2.7 on the
faster switch frequency. The filter rang instead of settling and the crop
strobed 400px between two subjects on alternate frames. Integrating the exact
solution removes the dependence on `dt` entirely. Measured on the same 15 s
window before and after, speaker framing went from 53% to 83% on this change
alone; the shipped 30 s reel sits at 78%, over a window containing 12 shot cuts
and 13 speaker changes.

**Clipping is judged on the facial core, not the padded head.** The head box
pads outward to include hair, and on a close-up it routinely runs off the top of
the *source* frame — so no crop could contain it, every subject-centred
candidate took the full clipping penalty, and excluding the subject entirely
became the cheaper option. The solver was correctly optimising a penalty defined
wrongly. Judging the core, clamped to the frame, also makes the solver agree
with the validator, which already scored the core: the two halves had been
disagreeing about what "clipped" meant.

**Adaptive shot detection.** Within-shot histogram correlation depends entirely
on content: a locked-off dialogue scene sits at 0.99, handheld action much
lower. A fixed threshold tuned for one shreds the other. The detector tracks a
running median and calls a cut on a sharp *relative* drop, capped by an absolute
ceiling, with a conservative warm-up so a continuous clip does not register a
cut in its opening frames.

## The publication gate

```python
report = validator.validate(rendered, profile, variant.id, hints)
if report.verdict is Verdict.PASS:
    variant.status = VariantStatus.PUBLISHED
else:
    variant.status = VariantStatus.QUARANTINED
```

This exists once, in `services/reformat_service.py`. `GET /library` returns only
`PUBLISHED`. Quarantined renders are retained (configurable) with their report
attached, because the failure is usually more informative than the file.

The validator receives "hints" from the pipeline for facts not recoverable from
a single file — the reframe path, the speaker timeline. Every hint-based rule is
written so a missing or dishonest hint yields SKIP or FAIL, never PASS.

## Scaling

Renders are CPU-bound and bursty. The worker tier therefore scales on SQS
backlog per running task rather than on CPU: by the time CPU rises the queue is
already deep. Scale-in is deliberately slow (10 minutes) because a render in
flight is expensive to lose.

The SQS visibility timeout must exceed the slowest job, or SQS redelivers work
still in progress and the same asset renders twice. It is set to 15 minutes
against a worst case of a few minutes.

---

<div align="center">

**Creative Reformatting Engine** — built by [Aritro Saha](https://openworld.aritro.cloud)

[openworld.aritro.cloud](https://openworld.aritro.cloud)

</div>
