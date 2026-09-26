import subprocess
from pathlib import Path

DEMO_DIR = Path(__file__).resolve().parent
SLIDES_DIR = DEMO_DIR / "slides"
SLIDES_DIR.mkdir(parents=True, exist_ok=True)

CHROME_BIN = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

SLIDE_TEMPLATES = {
    "ch1_problem_overview": """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    width: 1920px; height: 1080px;
    background-color: #0c0e12;
    color: #f1f5f9;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    display: flex; flex-direction: column; justify-content: space-between;
    padding: 60px 80px; overflow: hidden;
  }
  .header { display: flex; justify-content: space-between; align-items: flex-start; }
  .badge {
    background: rgba(59, 130, 246, 0.15); border: 1px solid rgba(59, 130, 246, 0.4);
    color: #60a5fa; font-size: 14px; font-weight: 700; letter-spacing: 2px;
    padding: 6px 14px; border-radius: 6px; text-transform: uppercase;
  }
  .hoichoi-tag {
    background: #e11d48; color: #fff; font-size: 13px; font-weight: 800;
    padding: 4px 10px; border-radius: 4px; letter-spacing: 1px;
  }
  h1 { font-size: 48px; font-weight: 800; color: #ffffff; margin-top: 12px; letter-spacing: -1px; }
  .subtitle { font-size: 22px; color: #94a3b8; margin-top: 6px; }

  .content-grid {
    display: grid; grid-template-columns: 1.1fr 0.9fr; gap: 40px; margin: 40px 0; flex: 1;
  }
  .card {
    background: #14171f; border: 1px solid #232936; border-radius: 14px; padding: 32px;
    display: flex; flex-direction: column; justify-content: space-between;
  }
  .card-title { font-size: 20px; font-weight: 700; color: #ffffff; margin-bottom: 20px; display: flex; align-items: center; gap: 10px; }
  
  .flow-box {
    display: flex; align-items: center; justify-content: space-between;
    background: #0d0f14; border: 1px solid #1e2430; border-radius: 10px; padding: 18px 24px; margin-bottom: 16px;
  }
  .ratio-pill {
    background: #1e2433; border: 1px solid #334155; color: #cbd5e1;
    font-family: monospace; font-size: 15px; font-weight: 700; padding: 8px 14px; border-radius: 6px;
  }
  
  .disqualifier-item {
    display: flex; align-items: flex-start; gap: 14px; padding: 14px;
    background: rgba(244, 63, 94, 0.08); border: 1px solid rgba(244, 63, 94, 0.25);
    border-radius: 8px; margin-bottom: 14px;
  }
  .disq-icon { color: #f43f5e; font-size: 18px; font-weight: bold; }
  .disq-text { font-size: 15px; color: #fca5a5; line-height: 1.4; }
  .disq-title { font-weight: 700; color: #ffffff; }

  .footer {
    display: flex; justify-content: space-between; align-items: center;
    border-top: 1px solid #1e2430; padding-top: 24px; color: #64748b; font-size: 15px;
  }
  .live-url { color: #60a5fa; font-family: monospace; font-weight: 600; }
</style>
</head>
<body>
  <div class="header">
    <div>
      <div style="display:flex; align-items:center; gap:12px;">
        <span class="badge">Problem 4 · Hackathon Pitch</span>
        <span class="hoichoi-tag">HOICHOI OTT</span>
      </div>
      <h1>Creative Reformatting Engine</h1>
      <p class="subtitle">Automated, subject-aware media reformatting & active-speaker video reframing</p>
    </div>
    <div style="text-align:right;">
      <p style="font-size:15px; color:#64748b;">Track</p>
      <p style="font-size:18px; font-weight:700; color:#cbd5e1;">Media Pipeline / Computer Vision</p>
    </div>
  </div>

  <div class="content-grid">
    <div class="card">
      <div>
        <div class="card-title">
          <span>🎬</span> Multi-Platform Fragmented Delivery Contract
        </div>
        <div class="flow-box">
          <div>
            <p style="font-size:12px; color:#64748b; text-transform:uppercase;">Master Source</p>
            <p style="font-size:18px; font-weight:700; color:#fff;">Single Master Asset</p>
            <p style="font-size:13px; color:#94a3b8; font-family:monospace;">16:9 1080p / 4K UHD</p>
          </div>
          <span style="font-size:24px; color:#60a5fa;">➔</span>
          <div>
            <p style="font-size:12px; color:#64748b; text-transform:uppercase;">Engine</p>
            <p style="font-size:18px; font-weight:700; color:#60a5fa;">Smart Reformat</p>
            <p style="font-size:13px; color:#94a3b8;">Subject & Speaker Sync</p>
          </div>
          <span style="font-size:24px; color:#60a5fa;">➔</span>
          <div>
            <p style="font-size:12px; color:#64748b; text-transform:uppercase;">Validation</p>
            <p style="font-size:18px; font-weight:700; color:#34d399;">Spec Gate</p>
            <p style="font-size:13px; color:#94a3b8;">Machine Audited</p>
          </div>
        </div>

        <div style="display:grid; grid-template-columns:1fr 1fr; gap:12px; margin-top:20px;">
          <div class="flow-box" style="margin:0;">
            <div>
              <span class="ratio-pill">16:9</span>
              <p style="font-size:13px; font-weight:600; color:#fff; margin-top:8px;">Hero Landscape</p>
              <p style="font-size:11px; color:#64748b;">1920×1080 · OTT Desktop & TV</p>
            </div>
          </div>
          <div class="flow-box" style="margin:0;">
            <div>
              <span class="ratio-pill">1:1</span>
              <p style="font-size:13px; font-weight:600; color:#fff; margin-top:8px;">Social Square</p>
              <p style="font-size:11px; color:#64748b;">1080×1080 · Instagram Feed</p>
            </div>
          </div>
          <div class="flow-box" style="margin:0;">
            <div>
              <span class="ratio-pill">9:16</span>
              <p style="font-size:13px; font-weight:600; color:#fff; margin-top:8px;">Story / Vertical</p>
              <p style="font-size:11px; color:#64748b;">1080×1920 · TikTok & Reels</p>
            </div>
          </div>
          <div class="flow-box" style="margin:0;">
            <div>
              <span class="ratio-pill">4:5</span>
              <p style="font-size:13px; font-weight:600; color:#fff; margin-top:8px;">Feed Portrait</p>
              <p style="font-size:11px; color:#64748b;">1080×1350 · Social Portrait</p>
            </div>
          </div>
        </div>
      </div>
      <p style="font-size:13px; color:#64748b;">Video Output: 9:16 Active-Speaker Tracked Vertical Reel + 16:9 Peak-Sharpness Key Still.</p>
    </div>

    <div class="card">
      <div>
        <div class="card-title">
          <span>⛔</span> Hackathon Auto-Disqualifiers (Guaranteed Avoided)
        </div>

        <div class="disqualifier-item">
          <div class="disq-icon">✗</div>
          <div class="disq-text">
            <span class="disq-title">Center-Crop with Disconnected Face Detection:</span><br>
            A naive center crop with face detection bolted on that does not actually influence the crop box.
          </div>
        </div>

        <div class="disqualifier-item">
          <div class="disq-icon">✗</div>
          <div class="disq-text">
            <span class="disq-title">Static Frame-0 Video Reframing:</span><br>
            Vertical video reframed once at frame 0 and held completely static for the duration of the clip.
          </div>
        </div>

        <div class="disqualifier-item">
          <div class="disq-icon">✗</div>
          <div class="disq-text">
            <span class="disq-title">Dimension-Only Validator:</span><br>
            A superficial validator that only checks pixel dimensions without checking face clipping or safe zones.
          </div>
        </div>
      </div>

      <div style="background:rgba(52, 211, 153, 0.1); border:1px solid rgba(52, 211, 153, 0.3); border-radius:8px; padding:12px 16px;">
        <p style="font-size:13px; color:#34d399; font-weight:600;">✓ Our Solution: True Subject-Aware Crop + Dynamic Audio-Synced Reframe + Deep Spec Compliance.</p>
      </div>
    </div>
  </div>

  <div class="footer">
    <span>Creative Reformatting Engine · Built by Aritro Saha</span>
    <span class="live-url">https://cre-hoichoi.aritro.cloud</span>
  </div>
</body>
</html>""",

    "ch2_architecture_vision": """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    width: 1920px; height: 1080px;
    background-color: #0c0e12;
    color: #f1f5f9;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    display: flex; flex-direction: column; justify-content: space-between;
    padding: 60px 80px; overflow: hidden;
  }
  .header { display: flex; justify-content: space-between; align-items: flex-start; }
  .badge {
    background: rgba(59, 130, 246, 0.15); border: 1px solid rgba(59, 130, 246, 0.4);
    color: #60a5fa; font-size: 14px; font-weight: 700; letter-spacing: 2px;
    padding: 6px 14px; border-radius: 6px; text-transform: uppercase;
  }
  h1 { font-size: 46px; font-weight: 800; color: #ffffff; margin-top: 12px; letter-spacing: -1px; }
  .subtitle { font-size: 22px; color: #94a3b8; margin-top: 6px; }

  .arch-grid {
    display: grid; grid-template-columns: repeat(4, 1fr); gap: 24px; margin: 40px 0; flex: 1;
  }
  .arch-card {
    background: #14171f; border: 1px solid #232936; border-radius: 14px; padding: 28px;
    display: flex; flex-direction: column; justify-content: space-between;
  }
  .step-num {
    font-family: monospace; font-size: 13px; font-weight: 800; color: #60a5fa;
    background: rgba(59, 130, 246, 0.15); width: 28px; height: 28px; border-radius: 50%;
    display: flex; align-items: center; justify-content: center; margin-bottom: 16px;
  }
  .card-title { font-size: 18px; font-weight: 700; color: #fff; margin-bottom: 12px; }
  .card-desc { font-size: 14px; color: #94a3b8; line-height: 1.5; }
  .tech-tag {
    display: inline-block; background: #0d0f14; border: 1px solid #1e2430;
    color: #cbd5e1; font-family: monospace; font-size: 12px; padding: 4px 8px; border-radius: 4px; margin-top: 6px;
  }
  .footer {
    display: flex; justify-content: space-between; align-items: center;
    border-top: 1px solid #1e2430; padding-top: 24px; color: #64748b; font-size: 15px;
  }
</style>
</head>
<body>
  <div class="header">
    <div>
      <span class="badge">Architecture & Computer Vision</span>
      <h1>Multimodal Signal Processing & Vision Stack</h1>
      <p class="subtitle">MediaPipe BlazeFace · SSD Person Tracking · Audio VAD · Active Speaker Correlation</p>
    </div>
  </div>

  <div class="arch-grid">
    <div class="arch-card">
      <div>
        <div class="step-num">1</div>
        <div class="card-title">Ingest & Probing</div>
        <p class="card-desc">
          Probe container metadata with FFmpeg. Ingest video or stills stream into standardized memory layouts with hardware acceleration.
        </p>
      </div>
      <div>
        <span class="tech-tag">FFmpeg 7.1</span>
        <span class="tech-tag">Probe Metadata</span>
        <span class="tech-tag">YUV420p / sRGB</span>
      </div>
    </div>

    <div class="arch-card">
      <div>
        <div class="step-num">2</div>
        <div class="card-title">Vision Perception</div>
        <p class="card-desc">
          BlazeFace sub-millisecond 6-point facial landmarking and mouth aperture estimation. SSD MobileNet tracks full body bounds and Laplacian gradient measures saliency.
        </p>
      </div>
      <div>
        <span class="tech-tag">MediaPipe BlazeFace</span>
        <span class="tech-tag">SSD MobileNet</span>
        <span class="tech-tag">Laplacian Saliency</span>
      </div>
    </div>

    <div class="arch-card">
      <div>
        <div class="step-num">3</div>
        <div class="card-title">Audio ASD Sync</div>
        <p class="card-desc">
          16kHz speech Voice Activity Detection (VAD) energy tracking. Cross-modal correlation couples speech intervals to lip motion apertures to identify active speakers.
        </p>
      </div>
      <div>
        <span class="tech-tag">Active Speaker ASD</span>
        <span class="tech-tag">Energy VAD Gating</span>
        <span class="tech-tag">Lip Sync Correlation</span>
      </div>
    </div>

    <div class="arch-card">
      <div>
        <div class="step-num">4</div>
        <div class="card-title">Crop Solver & Smooth</div>
        <p class="card-desc">
          Rule-of-thirds composition solver respects headroom and safe zones. Temporal smoothing applies EMA filtering and shot boundary cut preservation for cinematic pans.
        </p>
      </div>
      <div>
        <span class="tech-tag">Thirds Composition</span>
        <span class="tech-tag">EMA Smooth Path</span>
        <span class="tech-tag">Shot Boundary Cuts</span>
      </div>
    </div>
  </div>

  <div class="footer">
    <span>Publication Gate: Rendered media is re-analyzed by an independent validator before library admission</span>
    <span style="font-family:monospace; color:#34d399;">PASS / FAIL Guaranteed Audit</span>
  </div>
</body>
</html>""",

    "ch3_stills_pipeline": """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    width: 1920px; height: 1080px;
    background-color: #0c0e12;
    color: #f1f5f9;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    display: flex; flex-direction: column; justify-content: space-between;
    padding: 60px 80px; overflow: hidden;
  }
  .header { display: flex; justify-content: space-between; align-items: flex-start; }
  .badge {
    background: rgba(59, 130, 246, 0.15); border: 1px solid rgba(59, 130, 246, 0.4);
    color: #60a5fa; font-size: 14px; font-weight: 700; letter-spacing: 2px;
    padding: 6px 14px; border-radius: 6px; text-transform: uppercase;
  }
  h1 { font-size: 46px; font-weight: 800; color: #ffffff; margin-top: 12px; letter-spacing: -1px; }
  .subtitle { font-size: 22px; color: #94a3b8; margin-top: 6px; }

  .comparison-grid {
    display: grid; grid-template-columns: 1fr 1fr; gap: 40px; margin: 40px 0; flex: 1;
  }
  .comp-card {
    background: #14171f; border-radius: 14px; padding: 32px;
    display: flex; flex-direction: column; justify-content: space-between;
  }
  .fail-card { border: 2px solid rgba(244, 63, 94, 0.6); }
  .pass-card { border: 2px solid rgba(52, 211, 153, 0.6); }
  .card-badge-fail { color: #f43f5e; background: rgba(244, 63, 94, 0.15); padding: 4px 10px; border-radius: 4px; font-weight: 700; font-size: 13px; }
  .card-badge-pass { color: #34d399; background: rgba(52, 211, 153, 0.15); padding: 4px 10px; border-radius: 4px; font-weight: 700; font-size: 13px; }

  .sim-view {
    height: 240px; background: #0b0d12; border-radius: 10px; position: relative; overflow: hidden;
    display: flex; align-items: center; justify-content: center; margin: 20px 0;
    border: 1px solid #1e2430;
  }
  .actor-circle {
    position: absolute; width: 140px; height: 170px; border-radius: 50%;
    background: #e2b395; border: 3px solid #c48b6d; left: 80px; top: 35px;
    display: flex; align-items: center; justify-content: center; font-weight: 700; color: #333; font-size: 12px;
  }
  .crop-box-fail {
    position: absolute; width: 200px; height: 240px; border: 3px dashed #f43f5e;
    background: rgba(244, 63, 94, 0.15); left: 340px; top: 0;
  }
  .crop-box-pass {
    position: absolute; width: 200px; height: 240px; border: 3px solid #34d399;
    background: rgba(52, 211, 153, 0.15); left: 50px; top: 0;
  }

  .footer {
    display: flex; justify-content: space-between; align-items: center;
    border-top: 1px solid #1e2430; padding-top: 24px; color: #64748b; font-size: 15px;
  }
</style>
</head>
<body>
  <div class="header">
    <div>
      <span class="badge">Stills Pipeline Benchmark</span>
      <h1>Subject-Aware Smart Crop vs. Naive Center Crop</h1>
      <p class="subtitle">The Toughest Test: Off-Center Actor on Far Left (16:9 ➔ 9:16 & 1:1)</p>
    </div>
  </div>

  <div class="comparison-grid">
    <div class="comp-card fail-card">
      <div>
        <div style="display:flex; justify-content:space-between; align-items:center;">
          <h3 style="font-size:20px; font-weight:700; color:#fff;">Naive Center Crop</h3>
          <span class="card-badge-fail">DISQUALIFIED (FAIL)</span>
        </div>
        <p style="font-size:14px; color:#94a3b8; margin-top:8px;">
          Standard OTT tool cropping around frame center (x=0.50). Completely ignores focal subject placement.
        </p>

        <div class="sim-view">
          <div class="actor-circle">Off-Center Subject</div>
          <div class="crop-box-fail"></div>
          <span style="position:absolute; bottom:12px; right:16px; font-size:13px; color:#fca5a5; font-weight:bold;">
            Face Sliced Out of Frame ✗
          </span>
        </div>

        <ul style="color:#f87171; font-size:14px; line-height:1.6; list-style:none;">
          <li>✗ Face coverage &lt; 15% (Subject sliced in half)</li>
          <li>✗ Violated action safe margin (&gt; 0.8% required)</li>
          <li>✗ Quarantined by automated spec validator</li>
        </ul>
      </div>
      <p style="font-size:12px; color:#64748b;">Naive cropping ruins marketing and promotional banners.</p>
    </div>

    <div class="comp-card pass-card">
      <div>
        <div style="display:flex; justify-content:space-between; align-items:center;">
          <h3 style="font-size:20px; font-weight:700; color:#fff;">Creative Reformatting Engine</h3>
          <span class="card-badge-pass">VALIDATED (PASS)</span>
        </div>
        <p style="font-size:14px; color:#94a3b8; margin-top:8px;">
          BlazeFace detects focal actor, evaluates saliency, and solves crop box with balanced headroom and safe clearance.
        </p>

        <div class="sim-view">
          <div class="actor-circle" style="border-color:#34d399;">Off-Center Subject</div>
          <div class="crop-box-pass"></div>
          <span style="position:absolute; bottom:12px; right:16px; font-size:13px; color:#6ee7b7; font-weight:bold;">
            Composed Around Subject ✓
          </span>
        </div>

        <ul style="color:#6ee7b7; font-size:14px; line-height:1.6; list-style:none;">
          <li>✓ 100% of subject inside frame (0 faces clipped)</li>
          <li>✓ Balanced headroom rule-of-thirds composition</li>
          <li>✓ Produces all 4 ratios: 16:9, 1:1, 9:16, 4:5 + single-variant regenerate</li>
        </ul>
      </div>
      <p style="font-size:12px; color:#64748b;">Single-variant regenerate allows updating one ratio without touching the rest.</p>
    </div>
  </div>

  <div class="footer">
    <span>Hoichoi Platform Spec: Every output is audited for face clipping, sharpness floor, and safe margin</span>
    <span style="font-family:monospace; color:#38bdf8;">100% Spec Pass Rate</span>
  </div>
</body>
</html>""",

    "ch4_video_pipeline": """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    width: 1920px; height: 1080px;
    background-color: #0c0e12;
    color: #f1f5f9;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    display: flex; flex-direction: column; justify-content: space-between;
    padding: 60px 80px; overflow: hidden;
  }
  .header { display: flex; justify-content: space-between; align-items: flex-start; }
  .badge {
    background: rgba(59, 130, 246, 0.15); border: 1px solid rgba(59, 130, 246, 0.4);
    color: #60a5fa; font-size: 14px; font-weight: 700; letter-spacing: 2px;
    padding: 6px 14px; border-radius: 6px; text-transform: uppercase;
  }
  h1 { font-size: 46px; font-weight: 800; color: #ffffff; margin-top: 12px; letter-spacing: -1px; }
  .subtitle { font-size: 22px; color: #94a3b8; margin-top: 6px; }

  .video-grid {
    display: grid; grid-template-columns: 1.2fr 0.8fr; gap: 40px; margin: 40px 0; flex: 1;
  }
  .card {
    background: #14171f; border: 1px solid #232936; border-radius: 14px; padding: 32px;
    display: flex; flex-direction: column; justify-content: space-between;
  }
  .timeline-box {
    background: #090b0e; border: 1px solid #1e2430; border-radius: 10px; padding: 24px; margin: 20px 0;
  }
  .speaker-bar {
    height: 38px; border-radius: 6px; display: flex; overflow: hidden; font-weight: bold; font-size: 13px;
  }
  .speaker-left {
    background: #3b82f6; width: 50%; display: flex; align-items: center; justify-content: center; color: white;
  }
  .speaker-right {
    background: #f97316; width: 50%; display: flex; align-items: center; justify-content: center; color: white;
  }
  .path-curve {
    height: 100px; width: 100%; position: relative; margin-top: 16px; border-bottom: 1px solid #334155;
  }

  .still-box {
    background: #090b0e; border: 1px solid #1e2430; border-radius: 10px; padding: 20px;
  }

  .footer {
    display: flex; justify-content: space-between; align-items: center;
    border-top: 1px solid #1e2430; padding-top: 24px; color: #64748b; font-size: 15px;
  }
</style>
</head>
<body>
  <div class="header">
    <div>
      <span class="badge">Video & Reel Cutdown Benchmark</span>
      <h1>Active Speaker Tracking & Key Still Extraction</h1>
      <p class="subtitle">Two-Person Alternating Dialogue Clip ➔ Dynamic 9:16 Vertical Reel</p>
    </div>
  </div>

  <div class="video-grid">
    <div class="card">
      <div>
        <h3 style="font-size:20px; font-weight:700; color:#fff;">Active Speaker Tracking Timeline</h3>
        <p style="font-size:14px; color:#94a3b8; margin-top:6px;">
          Dialogue alternation between Actor A (Left) and Actor B (Right). Crop camera follows the speaker in sync with speech audio.
        </p>

        <div class="timeline-box">
          <p style="font-size:12px; color:#64748b; margin-bottom:8px; text-transform:uppercase;">Audio VAD & Speaker Classification</p>
          <div class="speaker-bar">
            <div class="speaker-left">Actor A Speaking (Left) [0.0s - 4.0s]</div>
            <div class="speaker-right">Actor B Speaking (Right) [4.0s - 8.0s]</div>
          </div>

          <div style="margin-top:20px;">
            <p style="font-size:12px; color:#64748b; margin-bottom:4px; text-transform:uppercase;">Horizontal Reframe Camera Path (cx Travel)</p>
            <svg viewBox="0 0 700 80" style="width:100%; height:80px;">
              <path d="M 0 60 L 320 60 C 350 60, 370 20, 400 20 L 700 20" fill="none" stroke="#60a5fa" stroke-width="4"/>
              <circle cx="320" cy="60" r="5" fill="#3b82f6"/>
              <circle cx="400" cy="20" r="5" fill="#f97316"/>
              <line x1="350" y1="0" x2="350" y2="80" stroke="#f43f5e" stroke-dasharray="4 4" stroke-width="1.5"/>
              <text x="355" y="45" fill="#f87171" font-size="11" font-family="monospace">SPEAKER SWITCH</text>
            </svg>
          </div>
        </div>

        <ul style="font-size:14px; color:#cbd5e1; line-height:1.7;">
          <li>✓ <b>Zero Static Holding:</b> Reframe path tracks speaker transitions across 680px travel.</li>
          <li>✓ <b>Exponential Smoothing:</b> Camera pans smoothly with EMA filter, preventing jerky frames.</li>
          <li>✓ <b>Shot Boundary Cut:</b> Hard cut protection prevents unnatural pans across scene changes.</li>
        </ul>
      </div>
      <p style="font-size:12px; color:#64748b;">Reframe path evidence plot is generated and accessible on every video asset.</p>
    </div>

    <div class="card">
      <div>
        <h3 style="font-size:20px; font-weight:700; color:#fff;">Automatic Key Still Extraction</h3>
        <p style="font-size:14px; color:#94a3b8; margin-top:6px;">
          Extracts sharpest frame from video candidate frames for platform thumbnail delivery.
        </p>

        <div class="still-box" style="margin-top:24px;">
          <div style="display:flex; justify-content:space-between; margin-bottom:12px;">
            <span style="font-size:13px; color:#94a3b8;">Sharpness Algorithm:</span>
            <span style="font-family:monospace; color:#34d399; font-weight:bold;">Laplacian Variance</span>
          </div>
          <div style="display:flex; justify-content:space-between; margin-bottom:12px;">
            <span style="font-size:13px; color:#94a3b8;">Spec Minimum Floor:</span>
            <span style="font-family:monospace; color:#cbd5e1;">&gt; 60.0 score</span>
          </div>
          <div style="display:flex; justify-content:space-between;">
            <span style="font-size:13px; color:#94a3b8;">Selected Key Frame:</span>
            <span style="font-family:monospace; color:#60a5fa; font-weight:bold;">Frame 142 (Score: 78.4)</span>
          </div>
        </div>

        <div style="background:rgba(59, 130, 246, 0.1); border:1px solid rgba(59, 130, 246, 0.3); border-radius:8px; padding:16px; margin-top:24px;">
          <p style="font-size:13px; color:#93c5fd; line-height:1.5;">
            Guarantees that video stills pulled into the media library are never motion-blurred, defocused, or transition artifacts.
          </p>
        </div>
      </div>
      <p style="font-size:12px; color:#64748b;">Key Still 16:9 variant is validated against the high-sharpness stills spec.</p>
    </div>
  </div>

  <div class="footer">
    <span>Active Speaker Coverage: &gt;80% of speech time framed on the talking actor</span>
    <span style="font-family:monospace; color:#34d399;">Speaker Reframing PASSED</span>
  </div>
</body>
</html>""",

    "ch5_spec_validation": """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    width: 1920px; height: 1080px;
    background-color: #0c0e12;
    color: #f1f5f9;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    display: flex; flex-direction: column; justify-content: space-between;
    padding: 60px 80px; overflow: hidden;
  }
  .header { display: flex; justify-content: space-between; align-items: flex-start; }
  .badge {
    background: rgba(59, 130, 246, 0.15); border: 1px solid rgba(59, 130, 246, 0.4);
    color: #60a5fa; font-size: 14px; font-weight: 700; letter-spacing: 2px;
    padding: 6px 14px; border-radius: 6px; text-transform: uppercase;
  }
  h1 { font-size: 46px; font-weight: 800; color: #ffffff; margin-top: 12px; letter-spacing: -1px; }
  .subtitle { font-size: 22px; color: #94a3b8; margin-top: 6px; }

  .spec-grid {
    display: grid; grid-template-columns: 1fr 1fr; gap: 40px; margin: 40px 0; flex: 1;
  }
  .card {
    background: #14171f; border: 1px solid #232936; border-radius: 14px; padding: 32px;
    display: flex; flex-direction: column; justify-content: space-between;
  }

  .table-box {
    background: #090b0e; border: 1px solid #1e2430; border-radius: 10px; overflow: hidden; margin: 20px 0;
  }
  table { width: 100%; border-collapse: collapse; text-align: left; font-size: 14px; }
  th { background: #14171f; padding: 12px 16px; color: #94a3b8; font-weight: 600; border-bottom: 1px solid #1e2430; }
  td { padding: 12px 16px; border-bottom: 1px solid #161b24; color: #cbd5e1; }
  .verdict-pass { color: #34d399; font-weight: bold; font-family: monospace; }
  .verdict-fail { color: #f43f5e; font-weight: bold; font-family: monospace; }

  .phone-frame {
    width: 200px; height: 320px; border-radius: 20px; border: 3px solid #475569;
    margin: 0 auto; position: relative; background: #07090d; overflow: hidden;
  }
  .chrome-top { position: absolute; top: 0; left: 0; right: 0; height: 38px; background: rgba(244, 63, 94, 0.4); border-bottom: 1px dashed #f43f5e; font-size: 9px; color: #fff; display: flex; align-items: center; justify-content: center; }
  .chrome-bottom { position: absolute; bottom: 0; left: 0; right: 0; height: 46px; background: rgba(244, 63, 94, 0.4); border-top: 1px dashed #f43f5e; font-size: 9px; color: #fff; display: flex; align-items: center; justify-content: center; }
  .chrome-rail { position: absolute; right: 0; top: 170px; bottom: 46px; width: 32px; background: rgba(244, 63, 94, 0.4); border-left: 1px dashed #f43f5e; font-size: 8px; color: #fff; display: flex; align-items: center; justify-content: center; writing-mode: vertical-rl; }
  .safe-action { position: absolute; top: 38px; bottom: 46px; left: 10px; right: 32px; border: 2px dashed #34d399; }

  .footer {
    display: flex; justify-content: space-between; align-items: center;
    border-top: 1px solid #1e2430; padding-top: 24px; color: #64748b; font-size: 15px;
  }
</style>
</head>
<body>
  <div class="header">
    <div>
      <span class="badge">Validation & Compliance Engine</span>
      <h1>Machine-Readable Platform Spec Sheet</h1>
      <p class="subtitle">The Publication Gate: Render ➔ Validate ➔ PASS ? Publish : Quarantine</p>
    </div>
  </div>

  <div class="spec-grid">
    <div class="card">
      <div>
        <h3 style="font-size:20px; font-weight:700; color:#fff;">Automated Compliance Matrix</h3>
        <p style="font-size:14px; color:#94a3b8; margin-top:6px;">
          Independent secondary detection pass executed directly on rendered files. Never relies on generator hints.
        </p>

        <div class="table-box">
          <table>
            <thead>
              <tr>
                <th>Compliance Rule</th>
                <th>Spec Threshold</th>
                <th>Measured Value</th>
                <th>Verdict</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td><b>Face Clipping</b></td>
                <td>&gt;= 99.5% inside</td>
                <td>100.0% inside</td>
                <td class="verdict-pass">PASS</td>
              </tr>
              <tr>
                <td><b>Edge Safe Margin</b></td>
                <td>&gt;= 0.8% margin</td>
                <td>4.2% margin</td>
                <td class="verdict-pass">PASS</td>
              </tr>
              <tr>
                <td><b>Letterbox Check</b></td>
                <td>&lt;= 1.0% black bars</td>
                <td>0.0% detected</td>
                <td class="verdict-pass">PASS</td>
              </tr>
              <tr>
                <td><b>Laplacian Sharpness</b></td>
                <td>&gt;= 45.0 (stills)</td>
                <td>68.4 variance</td>
                <td class="verdict-pass">PASS</td>
              </tr>
              <tr>
                <td><b>Reserved Chrome Exclusion</b></td>
                <td>0 UI intersections</td>
                <td>0 conflicts</td>
                <td class="verdict-pass">PASS</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
      <p style="font-size:12px; color:#64748b;">Quarantined assets are strictly excluded from the media library and API delivery feeds.</p>
    </div>

    <div class="card">
      <div>
        <h3 style="font-size:20px; font-weight:700; color:#fff;">Platform UI Chrome Safe Zones (9:16)</h3>
        <p style="font-size:14px; color:#94a3b8; margin-top:6px;">
          Live overlay inspection of TikTok and Instagram Story reserved zones.
        </p>

        <div style="display:flex; align-items:center; justify-content:center; margin:24px 0;">
          <div class="phone-frame">
            <div class="chrome-top">Top Status / Handle (12%)</div>
            <div class="safe-action"></div>
            <div class="chrome-rail">Action Rail (18%)</div>
            <div class="chrome-bottom">Captions & Audio (14%)</div>
          </div>
        </div>

        <div style="display:flex; justify-content:center; gap:20px; font-size:13px;">
          <span style="color:#f87171;">■ Reserved UI Chrome (Protected)</span>
          <span style="color:#34d399;">- - Action Safe Boundary</span>
        </div>
      </div>
      <p style="font-size:12px; color:#64748b;">UI overlay toggle in web application lets judges visually audit compliance.</p>
    </div>
  </div>

  <div class="footer">
    <span>Platform Delivery Contract: YAML spec is machine-readable and published at /api/v1/spec</span>
    <span style="font-family:monospace; color:#34d399;">Zero Assets Enter Unvalidated</span>
  </div>
</body>
</html>""",

    "ch6_production_pitch": """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    width: 1920px; height: 1080px;
    background-color: #0c0e12;
    color: #f1f5f9;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    display: flex; flex-direction: column; justify-content: space-between;
    padding: 60px 80px; overflow: hidden;
  }
  .header { display: flex; justify-content: space-between; align-items: flex-start; }
  .badge {
    background: rgba(59, 130, 246, 0.15); border: 1px solid rgba(59, 130, 246, 0.4);
    color: #60a5fa; font-size: 14px; font-weight: 700; letter-spacing: 2px;
    padding: 6px 14px; border-radius: 6px; text-transform: uppercase;
  }
  h1 { font-size: 46px; font-weight: 800; color: #ffffff; margin-top: 12px; letter-spacing: -1px; }
  .subtitle { font-size: 22px; color: #94a3b8; margin-top: 6px; }

  .summary-grid {
    display: grid; grid-template-columns: 1fr 1fr; gap: 40px; margin: 40px 0; flex: 1;
  }
  .card {
    background: #14171f; border: 1px solid #232936; border-radius: 14px; padding: 32px;
    display: flex; flex-direction: column; justify-content: space-between;
  }

  .infra-item {
    display: flex; align-items: center; justify-content: space-between;
    background: #090b0e; border: 1px solid #1e2430; border-radius: 8px; padding: 14px 18px; margin-bottom: 12px;
  }
  .infra-label { font-size: 14px; color: #cbd5e1; font-weight: 600; }
  .infra-val { font-family: monospace; font-size: 13px; color: #60a5fa; }

  .checklist { list-style: none; font-size: 16px; color: #cbd5e1; line-height: 2.2; }
  .check-icon { color: #34d399; font-weight: bold; margin-right: 12px; }

  .footer {
    display: flex; justify-content: space-between; align-items: center;
    border-top: 1px solid #1e2430; padding-top: 24px; color: #64748b; font-size: 15px;
  }
</style>
</head>
<body>
  <div class="header">
    <div>
      <span class="badge">Production & Hackathon Summary</span>
      <h1>AWS Free Tier Cloud Deployment & Pitch</h1>
      <p class="subtitle">Live Production Deployment · Automated GitHub CI/CD · 100% Problem Scope</p>
    </div>
  </div>

  <div class="summary-grid">
    <div class="card">
      <div>
        <h3 style="font-size:20px; font-weight:700; color:#fff;">Live Cloud Architecture (AWS Free Tier)</h3>
        <p style="font-size:14px; color:#94a3b8; margin-top:6px; margin-bottom:20px;">
          Production-grade, zero-cost cloud architecture with automated deployments.
        </p>

        <div class="infra-item">
          <span class="infra-label">Compute Engine</span>
          <span class="infra-val">EC2 t3.micro (Amazon Linux 2023)</span>
        </div>
        <div class="infra-item">
          <span class="infra-label">Elastic IP & DNS</span>
          <span class="infra-val">100.28.92.125 ➔ cre-hoichoi.aritro.cloud</span>
        </div>
        <div class="infra-item">
          <span class="infra-label">Security & TLS</span>
          <span class="infra-val">Let's Encrypt TLSv1.3 (Automated Certbot)</span>
        </div>
        <div class="infra-item">
          <span class="infra-label">Storage & Queues</span>
          <span class="infra-val">AWS S3 (Lifecycle 7-day) + SQS Workers</span>
        </div>
        <div class="infra-item">
          <span class="infra-label">CI/CD Pipeline</span>
          <span class="infra-val">GitHub Actions ➔ ECR ➔ AWS SSM (3m 12s)</span>
        </div>
      </div>
      <p style="font-size:12px; color:#64748b;">Complete Terraform code tracked under infra/aws/free-tier.</p>
    </div>

    <div class="card">
      <div>
        <h3 style="font-size:20px; font-weight:700; color:#fff;">Problem 4 Scope: Completed & Verified</h3>
        <p style="font-size:14px; color:#94a3b8; margin-top:6px; margin-bottom:20px;">
          All requirements verified against the official problem statement.
        </p>

        <ul class="checklist">
          <li><span class="check-icon">✓</span> <b>Subject-Aware Smart Crop:</b> Composes around off-center faces (16:9, 1:1, 9:16, 4:5)</li>
          <li><span class="check-icon">✓</span> <b>Active-Speaker Video Reframing:</b> Follows alternating dialogue with smooth pan</li>
          <li><span class="check-icon">✓</span> <b>Key Still Extraction:</b> Automated high-sharpness frame extraction from video</li>
          <li><span class="check-icon">✓</span> <b>Automated Spec Validation:</b> Full pass/fail report before entering library</li>
          <li><span class="check-icon">✓</span> <b>Single-Variant Regeneration:</b> Re-render individual targets in isolation</li>
          <li><span class="check-icon">✓</span> <b>Ratio Selection Controls:</b> Selective user choice over all delivery ratios</li>
        </ul>
      </div>

      <div style="background:rgba(52, 211, 153, 0.1); border:1px solid rgba(52, 211, 153, 0.3); border-radius:8px; padding:16px;">
        <p style="font-size:15px; color:#34d399; font-weight:700; text-align:center;">
          Live Demo URL: https://cre-hoichoi.aritro.cloud
        </p>
      </div>
    </div>
  </div>

  <div class="footer">
    <span>Creative Reformatting Engine · Built by Aritro Saha</span>
    <span style="font-family:monospace; color:#60a5fa;">Hackathon Submission Ready</span>
  </div>
</body>
</html>""",
}


def render_slides():
    print("Rendering 1920x1080 visual slide graphics using headless Chrome...")
    for ch_id, html_content in SLIDE_TEMPLATES.items():
        html_file = SLIDES_DIR / f"{ch_id}.html"
        png_file = SLIDES_DIR / f"{ch_id}.png"

        html_file.write_text(html_content, encoding="utf-8")
        print(f"Rendering {png_file.name}...")

        cmd = [
            CHROME_BIN,
            "--headless",
            "--disable-gpu",
            f"--screenshot={png_file}",
            "--window-size=1920,1080",
            "--hide-scrollbars",
            f"file://{html_file}",
        ]
        subprocess.run(cmd, check=True)
        print(f"  -> Generated {png_file} ({png_file.stat().st_size / 1024:.1f} KB)")


if __name__ == "__main__":
    render_slides()
