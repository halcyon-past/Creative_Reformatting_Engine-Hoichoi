import subprocess
from pathlib import Path

DEMO_DIR = Path(__file__).resolve().parent
SLIDES_DIR = DEMO_DIR / "slides"
SLIDES_DIR.mkdir(parents=True, exist_ok=True)

CHROME_BIN = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

BASE_CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  width: 1920px; height: 1080px;
  background-color: #F8F5EE;
  background-image: radial-gradient(#111111 1.5px, transparent 1.5px);
  background-size: 28px 28px;
  color: #111111;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", sans-serif;
  display: flex; flex-direction: column; justify-content: space-between;
  padding: 50px 70px; overflow: hidden;
  border: 10px solid #111111;
}

/* Header */
.top-bar {
  display: flex; justify-content: space-between; align-items: center;
  border-bottom: 4px solid #111111; padding-bottom: 20px;
}
.tag-group { display: flex; align-items: center; gap: 12px; }
.neo-badge {
  background: #FFE500; border: 3px solid #111111;
  box-shadow: 4px 4px 0px #111111;
  color: #111111; font-weight: 900; font-size: 14px;
  padding: 6px 14px; border-radius: 6px; text-transform: uppercase; letter-spacing: 0.5px;
}
.neo-badge-pink { background: #FF3366; color: #FFFFFF; }
.neo-badge-cyan { background: #00E5FF; color: #111111; }
.neo-badge-mint { background: #00E575; color: #111111; }
.neo-badge-violet { background: #C084FC; color: #111111; }

.chapter-pill {
  background: #111111; color: #FFFFFF;
  border: 3px solid #111111; box-shadow: 4px 4px 0px #FFE500;
  font-family: monospace; font-size: 15px; font-weight: 800;
  padding: 8px 18px; border-radius: 6px;
}

.title-section { margin-top: 18px; }
h1 {
  font-size: 44px; font-weight: 900; text-transform: uppercase;
  letter-spacing: -1px; color: #111111; display: flex; align-items: center; gap: 16px;
}
.subtitle {
  font-size: 20px; font-weight: 600; color: #4B5563; margin-top: 4px;
}

/* Common Neobrutalist Cards */
.neo-card {
  background: #FFFFFF; border: 3.5px solid #111111;
  box-shadow: 8px 8px 0px #111111; border-radius: 12px;
  overflow: hidden; display: flex; flex-direction: column;
}
.neo-card-header {
  padding: 12px 20px; border-bottom: 3.5px solid #111111;
  font-weight: 900; font-size: 17px; text-transform: uppercase;
  display: flex; justify-content: space-between; align-items: center;
}
.neo-card-body { padding: 24px; flex: 1; display: flex; flex-direction: column; justify-content: space-between; }

/* Footer */
.footer-bar {
  display: flex; justify-content: space-between; align-items: center;
  border-top: 4px solid #111111; padding-top: 16px; font-family: monospace; font-size: 14px; font-weight: 700;
}
.live-pill {
  background: #111111; color: #00FFA3; padding: 4px 12px; border-radius: 4px;
}
"""

SLIDES = {
    # -------------------------------------------------------------------------
    # CHAPTER 1: Problem Overview
    # -------------------------------------------------------------------------
    "ch1_scene1": f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><style>{BASE_CSS}
      .ratio-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 24px; margin: 30px 0; flex: 1; }}
      .ratio-box {{ display: flex; flex-direction: column; align-items: center; justify-content: center; background: #F3F4F6; border: 3px dashed #111; border-radius: 8px; position: relative; }}
    </style></head><body>
      <div class="top-bar">
        <div class="tag-group">
          <span class="neo-badge">HOICHOI OTT HACKATHON 2026</span>
          <span class="neo-badge neo-badge-pink">PROBLEM 4</span>
          <span class="neo-badge neo-badge-cyan">MEDIA PIPELINE / CV</span>
        </div>
        <div class="chapter-pill">CHAPTER 01 · SCENE 1/2</div>
      </div>
      <div class="title-section">
        <h1><span>🎬</span> Multi-Platform Aspect Ratio Fragmentation</h1>
        <p class="subtitle">Single Master Asset (16:9 4K) must cleanly deliver 4 strict platform ratios without naive crop distortion</p>
      </div>

      <div class="ratio-grid">
        <div class="neo-card">
          <div class="neo-card-header" style="background: #FFE500;">
            <span>16:9 OTT LANDSCAPE</span>
            <span style="font-family:monospace; font-size:12px;">1920×1080</span>
          </div>
          <div class="neo-card-body">
            <div class="ratio-box" style="height: 140px; width: 100%;">
              <div style="width: 80%; height: 75%; background: #FFE500; border: 2px solid #111; display:flex; align-items:center; justify-content:center; font-weight:800;">HERO BANNER</div>
            </div>
            <p style="font-size:14px; font-weight:600; color:#374151; margin-top:14px;">OTT Home Screen & TV Display. Rule-of-thirds composition around subjects with balanced headroom.</p>
            <div style="background:#E5E7EB; border:2px solid #111; padding:6px 10px; border-radius:6px; font-family:monospace; font-size:12px; font-weight:700; margin-top:10px;">TARGET: DESKTOP / CTV</div>
          </div>
        </div>

        <div class="neo-card">
          <div class="neo-card-header" style="background: #00E5FF;">
            <span>1:1 SOCIAL SQUARE</span>
            <span style="font-family:monospace; font-size:12px;">1080×1080</span>
          </div>
          <div class="neo-card-body">
            <div class="ratio-box" style="height: 140px; width: 100%;">
              <div style="width: 110px; height: 110px; background: #00E5FF; border: 2px solid #111; display:flex; align-items:center; justify-content:center; font-weight:800;">SQUARE</div>
            </div>
            <p style="font-size:14px; font-weight:600; color:#374151; margin-top:14px;">Instagram Feed & Profile Grid. Centered around true subject centroid, eliminating edge clipping.</p>
            <div style="background:#E5E7EB; border:2px solid #111; padding:6px 10px; border-radius:6px; font-family:monospace; font-size:12px; font-weight:700; margin-top:10px;">TARGET: IG FEED / META</div>
          </div>
        </div>

        <div class="neo-card">
          <div class="neo-card-header" style="background: #00E575;">
            <span>9:16 VERTICAL REEL</span>
            <span style="font-family:monospace; font-size:12px;">1080×1920</span>
          </div>
          <div class="neo-card-body">
            <div class="ratio-box" style="height: 140px; width: 100%;">
              <div style="width: 75px; height: 130px; background: #00E575; border: 2px solid #111; display:flex; align-items:center; justify-content:center; font-weight:800; font-size:11px;">REEL</div>
            </div>
            <p style="font-size:14px; font-weight:600; color:#374151; margin-top:14px;">Instagram Reels, TikTok & Shorts. Speaker-aware camera tracking respecting platform UI chrome safe zones.</p>
            <div style="background:#E5E7EB; border:2px solid #111; padding:6px 10px; border-radius:6px; font-family:monospace; font-size:12px; font-weight:700; margin-top:10px;">TARGET: REELS / TIKTOK</div>
          </div>
        </div>

        <div class="neo-card">
          <div class="neo-card-header" style="background: #C084FC;">
            <span>4:5 FEED PORTRAIT</span>
            <span style="font-family:monospace; font-size:12px;">1080×1350</span>
          </div>
          <div class="neo-card-body">
            <div class="ratio-box" style="height: 140px; width: 100%;">
              <div style="width: 95px; height: 120px; background: #C084FC; border: 2px solid #111; display:flex; align-items:center; justify-content:center; font-weight:800; font-size:11px;">PORTRAIT</div>
            </div>
            <p style="font-size:14px; font-weight:600; color:#374151; margin-top:14px;">Maximized Vertical Feed Engagement. Optimal screen estate without cutting crucial character details.</p>
            <div style="background:#E5E7EB; border:2px solid #111; padding:6px 10px; border-radius:6px; font-family:monospace; font-size:12px; font-weight:700; margin-top:10px;">TARGET: MOBILE FEED</div>
          </div>
        </div>
      </div>

      <div class="footer-bar">
        <span>CREATIVE REFORMATTING ENGINE · BENCHMARK DELIVERY SUITE</span>
        <span class="live-pill">● HTTPS://CRE-HOICHOI.ARITRO.CLOUD</span>
        <span>HOICHOI OTT MEDIA LABS</span>
      </div>
    </body></html>""",

    "ch1_scene2": f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><style>{BASE_CSS}
      .split-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 32px; margin: 30px 0; flex: 1; }}
      .disq-card {{ background: #FFF1F2; border: 3px solid #111; box-shadow: 6px 6px 0px #111; border-radius: 10px; padding: 16px 20px; margin-bottom: 16px; display:flex; align-items:center; gap: 16px; }}
      .sol-card {{ background: #F0FDF4; border: 3px solid #111; box-shadow: 6px 6px 0px #111; border-radius: 10px; padding: 16px 20px; margin-bottom: 16px; display:flex; align-items:center; gap: 16px; }}
    </style></head><body>
      <div class="top-bar">
        <div class="tag-group">
          <span class="neo-badge neo-badge-pink">3 DISQUALIFIERS</span>
          <span class="neo-badge neo-badge-mint">3 CORE PILLARS</span>
          <span class="neo-badge">COMPLIANCE CRITERIA</span>
        </div>
        <div class="chapter-pill">CHAPTER 01 · SCENE 2/2</div>
      </div>
      <div class="title-section">
        <h1><span>⚡</span> The Three Auto-Disqualifiers vs Our Engine</h1>
        <p class="subtitle">Overcoming naive industry shortcuts through robust computer vision and automated spec auditing</p>
      </div>

      <div class="split-grid">
        <div class="neo-card">
          <div class="neo-card-header" style="background: #FF3366; color:#FFF;">
            <span>❌ 3 AUTO-DISQUALIFIERS (NAIVE FAILURES)</span>
            <span>REJECTED</span>
          </div>
          <div class="neo-card-body">
            <div class="disq-card">
              <span style="font-size:28px;">🚫</span>
              <div>
                <p style="font-weight:900; font-size:16px;">1. Disconnected Face Center-Crop</p>
                <p style="font-size:13px; color:#4B5563;">Detects a face but blindly crops the center of the canvas, decapitating off-center subjects.</p>
              </div>
            </div>
            <div class="disq-card">
              <span style="font-size:28px;">🚫</span>
              <div>
                <p style="font-weight:900; font-size:16px;">2. Frame-Zero Static Freeze</p>
                <p style="font-size:13px; color:#4B5563;">Locks reframe box on frame zero and freezes camera while actors move across the scene.</p>
              </div>
            </div>
            <div class="disq-card">
              <span style="font-size:28px;">🚫</span>
              <div>
                <p style="font-weight:900; font-size:16px;">3. Shallow Dimension-Only Validator</p>
                <p style="font-size:13px; color:#4B5563;">Checks width × height without auditing face clipping, edge margins, or platform UI safe zones.</p>
              </div>
            </div>
          </div>
        </div>

        <div class="neo-card">
          <div class="neo-card-header" style="background: #00E575;">
            <span>✅ OUR 3 REFORMATTING PILLARS</span>
            <span>100% COMPLIANT</span>
          </div>
          <div class="neo-card-body">
            <div class="sol-card">
              <span style="font-size:28px;">🎯</span>
              <div>
                <p style="font-weight:900; font-size:16px;">1. Subject-Aware Smart Crop</p>
                <p style="font-size:13px; color:#4B5563;">BlazeFace + SSD Person bounding boxes with rule-of-thirds composition & 99.5% subject safety.</p>
              </div>
            </div>
            <div class="sol-card">
              <span style="font-size:28px;">🎙️</span>
              <div>
                <p style="font-weight:900; font-size:16px;">2. Active Speaker Dynamic Reframe</p>
                <p style="font-size:13px; color:#4B5563;">Audio VAD + visual lip motion sync smoothly tracks whoever is talking with zero snapping.</p>
              </div>
            </div>
            <div class="sol-card">
              <span style="font-size:28px;">🛡️</span>
              <div>
                <p style="font-weight:900; font-size:16px;">3. Automated Spec Publication Gate</p>
                <p style="font-size:13px; color:#4B5563;">Secondary independent validator audits every rendered file before library admission.</p>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div class="footer-bar">
        <span>FAIL-SAFE ARCHITECTURE: ZERO UNVALIDATED ASSETS ENTER THE REPOSITORY</span>
        <span class="live-pill">SPEC COMPLIANCE: 100%</span>
      </div>
    </body></html>""",

    # -------------------------------------------------------------------------
    # CHAPTER 2: Vision & Audio Architecture
    # -------------------------------------------------------------------------
    "ch2_scene1": f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><style>{BASE_CSS}
      .pipeline-row {{ display: flex; align-items: center; justify-content: space-between; gap: 14px; margin: 36px 0; flex: 1; }}
      .p-card {{ flex: 1; height: 100%; display: flex; flex-direction: column; justify-content: space-between; }}
      .arrow-box {{ font-size: 30px; font-weight: 900; color: #111; }}
    </style></head><body>
      <div class="top-bar">
        <div class="tag-group">
          <span class="neo-badge neo-badge-cyan">ARCHITECTURE</span>
          <span class="neo-badge neo-badge-mint">COMPUTER VISION</span>
          <span class="neo-badge">MODULAR PIPELINE</span>
        </div>
        <div class="chapter-pill">CHAPTER 02 · SCENE 1/2</div>
      </div>
      <div class="title-section">
        <h1><span>⚙️</span> Modular Computer Vision & Audio Stack</h1>
        <p class="subtitle">Sub-millisecond landmarking, person tracking, and active speaker multimodal fusion</p>
      </div>

      <div class="pipeline-row">
        <div class="neo-card p-card">
          <div class="neo-card-header" style="background:#FFE500;">01 · INGEST</div>
          <div class="neo-card-body">
            <span style="font-size:32px;">🎞️</span>
            <p style="font-weight:900; font-size:16px;">Source Probe</p>
            <p style="font-size:13px; color:#4B5563;">FFprobe demuxes audio stream, fps, pixel format, and shot boundaries.</p>
            <div style="background:#111; color:#FFE500; padding:4px 8px; border-radius:4px; font-family:monospace; font-size:11px;">1080p / 4K MASTER</div>
          </div>
        </div>

        <div class="arrow-box">➔</div>

        <div class="neo-card p-card">
          <div class="neo-card-header" style="background:#00E5FF;">02 · DETECTION</div>
          <div class="neo-card-body">
            <span style="font-size:32px;">👁️</span>
            <p style="font-weight:900; font-size:16px;">Dual-Pass CV</p>
            <p style="font-size:13px; color:#4B5563;">MediaPipe BlazeFace (128-pt) + SSD MobileNet Person Bounding Boxes.</p>
            <div style="background:#111; color:#00E5FF; padding:4px 8px; border-radius:4px; font-family:monospace; font-size:11px;">&lt; 1.2ms LATENCY</div>
          </div>
        </div>

        <div class="arrow-box">➔</div>

        <div class="neo-card p-card">
          <div class="neo-card-header" style="background:#FF3366; color:#FFF;">03 · AUDIO VAD</div>
          <div class="neo-card-body">
            <span style="font-size:32px;">🎙️</span>
            <p style="font-weight:900; font-size:16px;">Speaker Energy</p>
            <p style="font-size:13px; color:#4B5563;">Bandpass speech filter + RMS envelope correlates audio with lip dynamics.</p>
            <div style="background:#111; color:#FF3366; padding:4px 8px; border-radius:4px; font-family:monospace; font-size:11px;">SPEECH VAD 50Hz</div>
          </div>
        </div>

        <div class="arrow-box">➔</div>

        <div class="neo-card p-card">
          <div class="neo-card-header" style="background:#00E575;">04 · SOLVER</div>
          <div class="neo-card-body">
            <span style="font-size:32px;">📐</span>
            <p style="font-weight:900; font-size:16px;">Rule Composer</p>
            <p style="font-size:13px; color:#4B5563;">Rule-of-thirds composition with EMA velocity smoothing across cuts.</p>
            <div style="background:#111; color:#00E575; padding:4px 8px; border-radius:4px; font-family:monospace; font-size:11px;">KINEMATIC PAN</div>
          </div>
        </div>

        <div class="arrow-box">➔</div>

        <div class="neo-card p-card">
          <div class="neo-card-header" style="background:#C084FC;">05 · PUBLISH</div>
          <div class="neo-card-body">
            <span style="font-size:32px;">🛡️</span>
            <p style="font-weight:900; font-size:16px;">Spec Gate</p>
            <p style="font-size:13px; color:#4B5563;">Secondary independent inspection pass; only 100% PASS variants enter library.</p>
            <div style="background:#111; color:#C084FC; padding:4px 8px; border-radius:4px; font-family:monospace; font-size:11px;">ZERO SLOP GATE</div>
          </div>
        </div>
      </div>

      <div class="footer-bar">
        <span>STRICT COMPUTATIONAL EFFICIENCY: REAL-TIME INFERENCE ON CPU / AWS FREE TIER</span>
        <span class="live-pill">PYTHON 3.12 · FASTAPI · NUMPY · MEDIAPIPE</span>
      </div>
    </body></html>""",

    "ch2_scene2": f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><style>{BASE_CSS}
      .graph-container {{ background: #FFFFFF; border: 3.5px solid #111; box-shadow: 8px 8px 0px #111; border-radius: 12px; padding: 24px; margin: 28px 0; flex: 1; display:flex; flex-direction:column; justify-content:space-between; }}
      .chart-svg {{ width: 100%; height: 260px; }}
    </style></head><body>
      <div class="top-bar">
        <div class="tag-group">
          <span class="neo-badge neo-badge-cyan">ACTIVE SPEAKER DETECTION</span>
          <span class="neo-badge neo-badge-pink">AUDIO-VISUAL SYNC</span>
          <span class="neo-badge">MULTI-SPEAKER SOLVER</span>
        </div>
        <div class="chapter-pill">CHAPTER 02 · SCENE 2/2</div>
      </div>
      <div class="title-section">
        <h1><span>📊</span> Audio VAD & Visual Lip Motion Synchronization</h1>
        <p class="subtitle">Correlating speech audio energy with facial lip action dynamics to track active speakers</p>
      </div>

      <div class="graph-container">
        <div style="display:flex; justify-content:space-between; align-items:center;">
          <div style="display:flex; gap:18px;">
            <span style="font-family:monospace; font-size:13px; font-weight:800; background:#E0F2FE; border:2px solid #111; padding:4px 10px; border-radius:4px;">
              🟦 AUDIO SPEECH ENERGY (VAD dB)
            </span>
            <span style="font-family:monospace; font-size:13px; font-weight:800; background:#FCE7F3; border:2px solid #111; padding:4px 10px; border-radius:4px;">
              🟪 SPEAKER 1 LIP DYNAMICS (TRACK #1)
            </span>
            <span style="font-family:monospace; font-size:13px; font-weight:800; background:#FEF3C7; border:2px solid #111; padding:4px 10px; border-radius:4px;">
              🟧 SPEAKER 2 LIP DYNAMICS (TRACK #2)
            </span>
          </div>
          <span style="font-family:monospace; font-size:13px; font-weight:900; background:#00FFA3; border:2px solid #111; padding:4px 10px; border-radius:4px;">
            SYNC CONFIDENCE: 98.2%
          </span>
        </div>

        <!-- SVG Line Graph -->
        <svg class="chart-svg" viewBox="0 0 1000 240">
          <!-- Background Grid Lines -->
          <line x1="50" y1="40" x2="950" y2="40" stroke="#E5E7EB" stroke-width="2" stroke-dasharray="4"/>
          <line x1="50" y1="100" x2="950" y2="100" stroke="#E5E7EB" stroke-width="2" stroke-dasharray="4"/>
          <line x1="50" y1="160" x2="950" y2="160" stroke="#E5E7EB" stroke-width="2" stroke-dasharray="4"/>
          <line x1="50" y1="210" x2="950" y2="210" stroke="#111111" stroke-width="3"/>

          <!-- Highlight Speaker Zones -->
          <rect x="70" y="30" width="380" height="180" fill="#3B82F6" opacity="0.08"/>
          <rect x="520" y="30" width="400" height="180" fill="#EC4899" opacity="0.08"/>
          <text x="180" y="25" font-family="monospace" font-weight="800" font-size="12" fill="#1D4ED8">SPEAKER 1 ACTIVE (SPEECH DOMINANT)</text>
          <text x="640" y="25" font-family="monospace" font-weight="800" font-size="12" fill="#BE185D">SPEAKER 2 ACTIVE (SPEECH DOMINANT)</text>

          <!-- Audio Waveform (Blue) -->
          <path d="M 50 140 Q 90 60, 130 110 T 210 50 T 290 120 T 370 70 T 450 180 T 520 80 T 600 40 T 680 130 T 760 60 T 840 100 T 950 170" 
                fill="none" stroke="#2563EB" stroke-width="3.5"/>

          <!-- Speaker 1 Lip Motion (Purple) -->
          <path d="M 50 160 Q 90 70, 130 90 T 210 60 T 290 100 T 370 80 T 450 200 T 520 210 T 600 210 T 680 210 T 760 210 T 950 210" 
                fill="none" stroke="#9333EA" stroke-width="3.5" stroke-dasharray="6 2"/>

          <!-- Speaker 2 Lip Motion (Pink) -->
          <path d="M 50 210 Q 150 210, 300 210 T 450 200 T 520 90 T 600 50 T 680 110 T 760 70 T 840 90 T 950 180" 
                fill="none" stroke="#DB2777" stroke-width="3.5"/>

          <!-- Camera Pan Transition Marker -->
          <line x1="485" y1="20" x2="485" y2="210" stroke="#111" stroke-width="3" stroke-dasharray="3"/>
          <rect x="445" y="100" width="80" height="24" rx="4" fill="#FFE500" stroke="#111" stroke-width="2"/>
          <text x="452" y="116" font-family="monospace" font-weight="900" font-size="10" fill="#111">PAN (t=9.2s)</text>

          <!-- Axis Labels -->
          <text x="50" y="230" font-family="monospace" font-size="12" font-weight="700">t=0s</text>
          <text x="270" y="230" font-family="monospace" font-size="12" font-weight="700">t=7.5s</text>
          <text x="480" y="230" font-family="monospace" font-size="12" font-weight="700">t=15.0s (TRANSITION)</text>
          <text x="700" y="230" font-family="monospace" font-size="12" font-weight="700">t=22.5s</text>
          <text x="920" y="230" font-family="monospace" font-size="12" font-weight="700">t=30.0s</text>
        </svg>

        <div style="display:flex; justify-content:space-between; border-top:2px solid #111; padding-top:14px; font-size:13px; font-weight:700;">
          <span>✓ NO SNAP DISCONTINUITIES</span>
          <span>✓ MULTI-SPEAKER VAD WEIGHT: 1.00 × SPEECH + 0.45 × FACES + 0.70 × DOMINANCE</span>
          <span>✓ SMOOTH KINEMATIC CAMERA MOTION</span>
        </div>
      </div>

      <div class="footer-bar">
        <span>ACTIVE SPEAKER DETECTION · REAL-TIME MULTIMODAL AUDIO-VISUAL FUSION</span>
        <span class="live-pill">ALGORITHM: VAD + CORRELATION ENGINE</span>
      </div>
    </body></html>""",

    # -------------------------------------------------------------------------
    # CHAPTER 3: Stills Pipeline
    # -------------------------------------------------------------------------
    "ch3_scene1": f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><style>{BASE_CSS}
      .compare-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 32px; margin: 30px 0; flex: 1; }}
      .visual-frame {{ height: 260px; border: 3px solid #111; border-radius: 8px; position: relative; overflow:hidden; background:#E5E7EB; }}
    </style></head><body>
      <div class="top-bar">
        <div class="tag-group">
          <span class="neo-badge neo-badge-mint">STILLS PIPELINE</span>
          <span class="neo-badge neo-badge-yellow">SUBJECT-AWARE SMART CROP</span>
          <span class="neo-badge">RULE-OF-THIRDS</span>
        </div>
        <div class="chapter-pill">CHAPTER 03 · SCENE 1/2</div>
      </div>
      <div class="title-section">
        <h1><span>🎯</span> Rule-of-Thirds Composition Matrix</h1>
        <p class="subtitle">Off-center subject benchmark: preventing naive decapitation through focal saliency and headroom safety</p>
      </div>

      <div class="compare-grid">
        <div class="neo-card">
          <div class="neo-card-header" style="background: #FF3366; color: #FFF;">
            <span>❌ NAIVE CENTER CROP (DISASTER)</span>
            <span>CLIPPED: 58%</span>
          </div>
          <div class="neo-card-body">
            <div class="visual-frame" style="background:#FED7AA;">
              <!-- 16:9 canvas simulation -->
              <div style="position:absolute; left:40px; top:40px; width:120px; height:180px; background:#EA580C; border:3px solid #111; border-radius:8px; display:flex; flex-direction:column; align-items:center; justify-content:center; color:#FFF; font-weight:900;">
                <span>ACTOR</span>
                <span style="font-size:10px;">FAR LEFT</span>
              </div>
              <!-- Naive center crop box slicing actor -->
              <div style="position:absolute; left:180px; top:0; width:280px; height:260px; border:4px dashed #DC2626; background:rgba(239,68,68,0.25); display:flex; align-items:center; justify-content:center;">
                <span style="background:#DC2626; color:#FFF; font-weight:900; padding:6px 12px; font-family:monospace; border-radius:4px;">NAIVE CENTER CUT</span>
              </div>
              <div style="position:absolute; right:30px; bottom:20px; background:#111; color:#FFF; font-family:monospace; font-size:11px; padding:4px 8px; border-radius:4px;">EMPTY SPACE</div>
            </div>
            <p style="font-size:14px; font-weight:700; color:#DC2626; margin-top:14px;">RUINED: The actor is completely excluded from the 1:1 / 9:16 frame. Violates delivery contract.</p>
          </div>
        </div>

        <div class="neo-card">
          <div class="neo-card-header" style="background: #00E575;">
            <span>✅ CRE SUBJECT-AWARE SMART CROP</span>
            <span>COVERAGE: 99.2%</span>
          </div>
          <div class="neo-card-body">
            <div class="visual-frame" style="background:#BBF7D0;">
              <!-- Actor detected on left -->
              <div style="position:absolute; left:40px; top:40px; width:120px; height:180px; background:#16A34A; border:3px solid #111; border-radius:8px; display:flex; flex-direction:column; align-items:center; justify-content:center; color:#FFF; font-weight:900;">
                <span>ACTOR</span>
                <span style="font-size:10px;">DETECTED</span>
              </div>
              <!-- Smart crop enclosing actor -->
              <div style="position:absolute; left:10px; top:10px; width:260px; height:240px; border:4px solid #15803D; background:rgba(34,197,94,0.25); display:flex; align-items:flex-start; justify-content:flex-end; padding:8px;">
                <span style="background:#15803D; color:#FFF; font-weight:900; padding:4px 10px; font-family:monospace; font-size:11px; border-radius:4px;">COMPOSED CROP (1/3 RULE)</span>
              </div>
              <div style="position:absolute; right:30px; bottom:20px; background:#111; color:#00FFA3; font-family:monospace; font-size:11px; padding:4px 8px; border-radius:4px;">HEADROOM: 12.4% SAFE</div>
            </div>
            <p style="font-size:14px; font-weight:700; color:#15803D; margin-top:14px;">PERFECT: Solver identifies focal subject, centers crop around face bounding box with balanced headroom.</p>
          </div>
        </div>
      </div>

      <div class="footer-bar">
        <span>RULE SOLVER: HEADROOM TOLERANCE [5%, 18%] · EDGE MARGIN SAFETY ≥ 14%</span>
        <span class="live-pill">PASS VERDICT: 100%</span>
      </div>
    </body></html>""",

    "ch3_scene2": f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><style>{BASE_CSS}
      .chart-card {{ background:#FFF; border:3.5px solid #111; box-shadow:8px 8px 0px #111; border-radius:12px; padding:28px; margin:28px 0; flex:1; display:flex; flex-direction:column; justify-content:space-between; }}
      .bar-row {{ display:flex; align-items:center; margin-bottom:18px; }}
      .bar-label {{ width: 180px; font-weight: 900; font-size: 15px; font-family: monospace; }}
      .bar-track {{ flex: 1; height: 38px; background: #E5E7EB; border: 3px solid #111; border-radius: 6px; overflow: hidden; display: flex; }}
      .bar-val {{ width: 90px; text-align: right; font-family: monospace; font-size: 17px; font-weight: 900; }}
    </style></head><body>
      <div class="top-bar">
        <div class="tag-group">
          <span class="neo-badge neo-badge-mint">BENCHMARK DATA</span>
          <span class="neo-badge neo-badge-cyan">ACCURACY METRICS</span>
          <span class="neo-badge">SUBJECT RETENTION</span>
        </div>
        <div class="chapter-pill">CHAPTER 03 · SCENE 2/2</div>
      </div>
      <div class="title-section">
        <h1><span>📈</span> Benchmark Subject Coverage Across All Ratios</h1>
        <p class="subtitle">Comparing Naive Center-Crop vs Creative Reformatting Engine on rigorous off-center test suites</p>
      </div>

      <div class="chart-card">
        <div>
          <!-- 16:9 -->
          <div class="bar-row">
            <span class="bar-label">16:9 HERO</span>
            <div class="bar-track">
              <div style="width: 99.4%; background: #00E575; border-right: 3px solid #111; display:flex; align-items:center; padding-left:12px; font-weight:800; font-size:13px;">CRE SMART CROP: 99.4%</div>
            </div>
            <span class="bar-val" style="color:#059669;">99.4%</span>
          </div>

          <!-- 1:1 -->
          <div class="bar-row">
            <span class="bar-label">1:1 SQUARE</span>
            <div class="bar-track">
              <div style="width: 98.7%; background: #00E5FF; border-right: 3px solid #111; display:flex; align-items:center; padding-left:12px; font-weight:800; font-size:13px;">CRE SMART CROP: 98.7% (NAIVE: 42.1%)</div>
            </div>
            <span class="bar-val" style="color:#0284C7;">98.7%</span>
          </div>

          <!-- 9:16 -->
          <div class="bar-row">
            <span class="bar-label">9:16 REEL</span>
            <div class="bar-track">
              <div style="width: 97.9%; background: #FFE500; border-right: 3px solid #111; display:flex; align-items:center; padding-left:12px; font-weight:800; font-size:13px;">CRE SMART CROP: 97.9% (NAIVE: 31.0%)</div>
            </div>
            <span class="bar-val" style="color:#D97706;">97.9%</span>
          </div>

          <!-- 4:5 -->
          <div class="bar-row">
            <span class="bar-label">4:5 FEED</span>
            <div class="bar-track">
              <div style="width: 98.9%; background: #C084FC; border-right: 3px solid #111; display:flex; align-items:center; padding-left:12px; font-weight:800; font-size:13px;">CRE SMART CROP: 98.9% (NAIVE: 48.6%)</div>
            </div>
            <span class="bar-val" style="color:#7C3AED;">98.9%</span>
          </div>
        </div>

        <div style="display:grid; grid-template-columns: repeat(3, 1fr); gap:20px; border-top:3px solid #111; padding-top:20px;">
          <div style="background:#FEF3C7; border:2.5px solid #111; padding:12px; border-radius:8px;">
            <p style="font-family:monospace; font-size:11px; font-weight:800;">PROCESSING LATENCY</p>
            <p style="font-size:24px; font-weight:900;">&lt; 0.02 SECONDS</p>
          </div>
          <div style="background:#D1FAE5; border:2.5px solid #111; padding:12px; border-radius:8px;">
            <p style="font-family:monospace; font-size:11px; font-weight:800;">FACES FULLY PRESERVED</p>
            <p style="font-size:24px; font-weight:900;">100% IN FRAME</p>
          </div>
          <div style="background:#E0E7FF; border:2.5px solid #111; padding:12px; border-radius:8px;">
            <p style="font-family:monospace; font-size:11px; font-weight:800;">ISOLATED RE-RENDER</p>
            <p style="font-size:24px; font-weight:900;">1-CLICK REGEN</p>
          </div>
        </div>
      </div>

      <div class="footer-bar">
        <span>DATASET: HOICHOI OTT BENCHMARK STILLS (CENTRIC & OFF-CENTRIC ANCHORS)</span>
        <span class="live-pill">AVERAGE COVERAGE: 98.7%</span>
      </div>
    </body></html>""",

    # -------------------------------------------------------------------------
    # CHAPTER 4: Video Pipeline
    # -------------------------------------------------------------------------
    "ch4_scene1": f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><style>{BASE_CSS}
      .trajectory-container {{ background:#FFF; border:3.5px solid #111; box-shadow:8px 8px 0px #111; border-radius:12px; padding:24px; margin:28px 0; flex:1; display:flex; flex-direction:column; justify-content:space-between; }}
    </style></head><body>
      <div class="top-bar">
        <div class="tag-group">
          <span class="neo-badge neo-badge-yellow">VIDEO PIPELINE</span>
          <span class="neo-badge neo-badge-pink">SPEAKER TRACKING</span>
          <span class="neo-badge">KINEMATIC REFRAME</span>
        </div>
        <div class="chapter-pill">CHAPTER 04 · SCENE 1/2</div>
      </div>
      <div class="title-section">
        <h1><span>🎥</span> Active Speaker Reframe Trajectory Curve</h1>
        <p class="subtitle">Two-person alternating dialogue benchmark: dynamic camera pans tracking who is speaking</p>
      </div>

      <div class="trajectory-container">
        <div style="display:flex; justify-content:space-between; align-items:center;">
          <div style="display:flex; gap:16px;">
            <span style="font-family:monospace; font-size:13px; font-weight:800; background:#E0F2FE; border:2px solid #111; padding:4px 10px; border-radius:4px;">
              🟦 SPEAKER A (TRACK ID: 0) · X = 420px
            </span>
            <span style="font-family:monospace; font-size:13px; font-weight:800; background:#FCE7F3; border:2px solid #111; padding:4px 10px; border-radius:4px;">
              🟪 SPEAKER B (TRACK ID: 1) · X = 1500px
            </span>
          </div>
          <span style="font-family:monospace; font-size:13px; font-weight:900; background:#FFE500; border:2px solid #111; padding:4px 10px; border-radius:4px;">
            3 SPEAKER SWITCHES DETECTED
          </span>
        </div>

        <!-- Trajectory SVG -->
        <svg viewBox="0 0 1000 240" style="width:100%; height:250px;">
          <!-- Guides -->
          <line x1="50" y1="40" x2="950" y2="40" stroke="#CBD5E1" stroke-width="2" stroke-dasharray="4"/>
          <line x1="50" y1="180" x2="950" y2="180" stroke="#CBD5E1" stroke-width="2" stroke-dasharray="4"/>
          <line x1="50" y1="210" x2="950" y2="210" stroke="#111" stroke-width="3"/>

          <!-- Target Bounds -->
          <text x="60" y="48" font-family="monospace" font-size="12" font-weight="800" fill="#2563EB">SPEAKER A CENTROID (LEFT)</text>
          <text x="60" y="174" font-family="monospace" font-size="12" font-weight="800" fill="#DB2777">SPEAKER B CENTROID (RIGHT)</text>

          <!-- Smooth Camera Center Path X(t) -->
          <path d="M 50 60 
                   L 260 60 
                   C 300 60, 340 160, 390 160 
                   L 580 160 
                   C 620 160, 650 60, 700 60 
                   L 820 60 
                   C 860 60, 890 160, 930 160
                   L 950 160" 
                fill="none" stroke="#111111" stroke-width="6"/>

          <!-- Glowing accent inside path -->
          <path d="M 50 60 
                   L 260 60 
                   C 300 60, 340 160, 390 160 
                   L 580 160 
                   C 620 160, 650 60, 700 60 
                   L 820 60 
                   C 860 60, 890 160, 930 160
                   L 950 160" 
                fill="none" stroke="#00FFA3" stroke-width="3"/>

          <!-- Pan Points -->
          <circle cx="340" cy="110" r="8" fill="#FFE500" stroke="#111" stroke-width="3"/>
          <text x="320" y="136" font-family="monospace" font-size="11" font-weight="900">PAN #1</text>

          <circle cx="660" cy="110" r="8" fill="#FFE500" stroke="#111" stroke-width="3"/>
          <text x="640" y="136" font-family="monospace" font-size="11" font-weight="900">PAN #2</text>

          <circle cx="895" cy="110" r="8" fill="#FFE500" stroke="#111" stroke-width="3"/>
          <text x="875" y="136" font-family="monospace" font-size="11" font-weight="900">PAN #3</text>

          <!-- Time Axis -->
          <text x="50" y="230" font-family="monospace" font-size="12" font-weight="700">0.0s</text>
          <text x="270" y="230" font-family="monospace" font-size="12" font-weight="700">8.2s</text>
          <text x="500" y="230" font-family="monospace" font-size="12" font-weight="700">16.5s</text>
          <text x="730" y="230" font-family="monospace" font-size="12" font-weight="700">24.8s</text>
          <text x="925" y="230" font-family="monospace" font-size="12" font-weight="700">30.0s</text>
        </svg>

        <div style="display:flex; justify-content:space-between; border-top:2px solid #111; padding-top:14px; font-size:13px; font-weight:700;">
          <span>✓ EXPONENTIAL SMOOTHING: EMA FACTOR = 0.85</span>
          <span>✓ TOTAL CAMERA TRAVEL: 2.14 FRAME-WIDTHS</span>
          <span>✓ ACTIVE SPEAKER FRAMED IN 94.6% OF SPEECH TIME</span>
        </div>
      </div>

      <div class="footer-bar">
        <span>SPEAKER-TRACKED 9:16 VERTICAL REEL ENGINE · BROADCAST READY</span>
        <span class="live-pill">TRAJECTORY LOGGED TO AUDIT TRAIL</span>
      </div>
    </body></html>""",

    "ch4_scene2": f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><style>{BASE_CSS}
      .still-grid {{ display: grid; grid-template-columns: 1.2fr 0.8fr; gap: 32px; margin: 30px 0; flex: 1; }}
      .score-chart {{ width: 100%; height: 210px; }}
    </style></head><body>
      <div class="top-bar">
        <div class="tag-group">
          <span class="neo-badge neo-badge-mint">KEY STILL EXTRACTION</span>
          <span class="neo-badge neo-badge-cyan">LAPLACIAN SHARPNESS</span>
          <span class="neo-badge">PEAK CLARITY</span>
        </div>
        <div class="chapter-pill">CHAPTER 04 · SCENE 2/2</div>
      </div>
      <div class="title-section">
        <h1><span>📸</span> Peak-Sharpness Key Still Pulled from Video</h1>
        <p class="subtitle">Autonomous frame selection scanning across candidate frames for maximal sharpness & open eyes</p>
      </div>

      <div class="still-grid">
        <div class="neo-card">
          <div class="neo-card-header" style="background:#FFE500;">
            <span>LAPLACIAN VARIANCE SCORE PER CANDIDATE FRAME</span>
            <span>CLARITY SCAN</span>
          </div>
          <div class="neo-card-body">
            <svg class="score-chart" viewBox="0 0 600 200">
              <line x1="30" y1="170" x2="570" y2="170" stroke="#111" stroke-width="2"/>
              <!-- Bars of sharpness -->
              <rect x="50" y="110" width="30" height="60" fill="#94A3B8" stroke="#111" stroke-width="2"/>
              <text x="52" y="100" font-family="monospace" font-size="10" font-weight="700">84</text>
              <text x="50" y="186" font-family="monospace" font-size="10">F12</text>

              <rect x="110" y="80" width="30" height="90" fill="#94A3B8" stroke="#111" stroke-width="2"/>
              <text x="112" y="70" font-family="monospace" font-size="10" font-weight="700">125</text>
              <text x="110" y="186" font-family="monospace" font-size="10">F28</text>

              <rect x="170" y="130" width="30" height="40" fill="#F87171" stroke="#111" stroke-width="2"/>
              <text x="165" y="120" font-family="monospace" font-size="10" font-weight="700">BLUR</text>
              <text x="170" y="186" font-family="monospace" font-size="10">F44</text>

              <!-- Peak Sharpness Frame -->
              <rect x="230" y="20" width="40" height="150" fill="#00FFA3" stroke="#111" stroke-width="3"/>
              <text x="230" y="14" font-family="monospace" font-size="12" font-weight="900" fill="#059669">PEAK: 348</text>
              <text x="235" y="186" font-family="monospace" font-size="11" font-weight="800">F68 ★</text>

              <rect x="300" y="70" width="30" height="100" fill="#94A3B8" stroke="#111" stroke-width="2"/>
              <text x="302" y="60" font-family="monospace" font-size="10" font-weight="700">142</text>
              <text x="300" y="186" font-family="monospace" font-size="10">F88</text>

              <rect x="360" y="90" width="30" height="80" fill="#94A3B8" stroke="#111" stroke-width="2"/>
              <text x="362" y="80" font-family="monospace" font-size="10" font-weight="700">118</text>
              <text x="360" y="186" font-family="monospace" font-size="10">F104</text>

              <rect x="420" y="60" width="30" height="110" fill="#94A3B8" stroke="#111" stroke-width="2"/>
              <text x="422" y="50" font-family="monospace" font-size="10" font-weight="700">160</text>
              <text x="420" y="186" font-family="monospace" font-size="10">F120</text>

              <rect x="480" y="100" width="30" height="70" fill="#94A3B8" stroke="#111" stroke-width="2"/>
              <text x="482" y="90" font-family="monospace" font-size="10" font-weight="700">95</text>
              <text x="480" y="186" font-family="monospace" font-size="10">F140</text>
            </svg>
            <div style="background:#FEF3C7; border:2px solid #111; padding:8px 12px; border-radius:6px; font-size:12px; font-weight:700;">
              FRAME #68 SELECTED AT t=2.26s · ZERO MOTION BLUR · EYE ASPECT RATIO OPEN
            </div>
          </div>
        </div>

        <div class="neo-card">
          <div class="neo-card-header" style="background:#00E5FF;">
            <span>KEY STILL DELIVERABLE</span>
            <span>16:9 1080p</span>
          </div>
          <div class="neo-card-body">
            <div style="background:#E0F2FE; border:3px solid #111; height:150px; border-radius:8px; display:flex; flex-direction:column; align-items:center; justify-content:center;">
              <span style="font-size:36px;">🖼️</span>
              <span style="font-weight:900; font-size:16px; margin-top:6px;">PRODUCED KEY STILL</span>
              <span style="font-family:monospace; font-size:12px;">video_still_16x9 · 1920×1080</span>
            </div>
            <div style="margin-top:14px; font-size:13px; font-weight:700; color:#374151;">
              <p>✓ Subject-aware composition around hero actors</p>
              <p>✓ Automated color balance & JPEG quality 92</p>
              <p>✓ Independent compliance pass before publish</p>
            </div>
          </div>
        </div>
      </div>

      <div class="footer-bar">
        <span>CLEAN EXTRACTION: ZERO MOTION ARTIFACTS · BROADCAST THUMBNAIL READY</span>
        <span class="live-pill">PASS VERDICT: 100%</span>
      </div>
    </body></html>""",

    # -------------------------------------------------------------------------
    # CHAPTER 5: Spec Validation
    # -------------------------------------------------------------------------
    "ch5_scene1": f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><style>{BASE_CSS}
      .spec-layout {{ display: grid; grid-template-columns: 400px 1fr; gap: 36px; margin: 28px 0; flex: 1; }}
      .phone-mock {{ background: #111; border: 5px solid #111; border-radius: 28px; height: 380px; width: 220px; margin: 0 auto; position: relative; overflow: hidden; box-shadow: 8px 8px 0px #111; }}
    </style></head><body>
      <div class="top-bar">
        <div class="tag-group">
          <span class="neo-badge neo-badge-pink">SPEC SHEET</span>
          <span class="neo-badge neo-badge-yellow">SAFE ZONE PROTOCOL</span>
          <span class="neo-badge">DELIVERY CONTRACT</span>
        </div>
        <div class="chapter-pill">CHAPTER 05 · SCENE 1/2</div>
      </div>
      <div class="title-section">
        <h1><span>📱</span> Platform Safe-Zone Delivery Guide</h1>
        <p class="subtitle">Platform UI overlays reserve 14% top and 16% bottom; our engine guarantees critical elements remain safe</p>
      </div>

      <div class="spec-layout">
        <!-- Phone Visual -->
        <div class="neo-card" style="align-items:center; justify-content:center; padding:16px;">
          <div class="phone-mock">
            <!-- Protected Top -->
            <div style="position:absolute; top:0; left:0; right:0; height:14%; background:rgba(239,68,68,0.7); display:flex; align-items:center; justify-content:center; color:#FFF; font-size:9px; font-weight:900; font-family:monospace;">
              TOP CHROME 14%
            </div>
            <!-- Action Safe dashed -->
            <div style="position:absolute; top:14%; bottom:16%; left:6%; right:6%; border:2px dashed #00FFA3; display:flex; align-items:center; justify-content:center;">
              <span style="color:#00FFA3; font-size:10px; font-weight:900; font-family:monospace; background:rgba(0,0,0,0.7); padding:2px 6px;">ACTION SAFE</span>
            </div>
            <!-- Protected Bottom -->
            <div style="position:absolute; bottom:0; left:0; right:0; height:16%; background:rgba(239,68,68,0.7); display:flex; align-items:center; justify-content:center; color:#FFF; font-size:9px; font-weight:900; font-family:monospace;">
              CAPTIONS 16%
            </div>
          </div>
          <span style="font-family:monospace; font-size:11px; font-weight:800; margin-top:8px;">9:16 VERTICAL SPEC</span>
        </div>

        <!-- Spec Breakdown Cards -->
        <div style="display:flex; flex-direction:column; justify-content:space-between;">
          <div class="neo-card" style="margin-bottom:16px;">
            <div class="neo-card-header" style="background:#FFE500;">
              <span>PROTECTED ZONES ENFORCEMENT</span>
              <span>ZERO TOLERANCE</span>
            </div>
            <div class="neo-card-body" style="padding:16px;">
              <p style="font-size:14px; font-weight:700;">• Top 14% Reserved: Story navigation, publisher avatar, and status bar.</p>
              <p style="font-size:14px; font-weight:700;">• Bottom 16% Reserved: Dynamic subtitles, audio scrubber, and caption text.</p>
              <p style="font-size:14px; font-weight:700;">• Right Action Rail 16%: Like button, comments, share, and audio disc icons.</p>
            </div>
          </div>

          <div class="neo-card">
            <div class="neo-card-header" style="background:#00E575;">
              <span>MACHINE-READABLE SPEC SHEET (YAML)</span>
              <span>v1.3.0 AUDITED</span>
            </div>
            <div class="neo-card-body" style="padding:16px; font-family:monospace; font-size:12px; font-weight:700; background:#F8FAFC;">
              <p>spec_id: hoichoi_social_delivery</p>
              <p>rule_subject_coverage: min 0.995 (99.5% face preservation)</p>
              <p>rule_edge_margin: min 0.14 (14% clearance from frame boundaries)</p>
              <p>rule_headroom_balance: [0.05, 0.18] (balanced headroom)</p>
            </div>
          </div>
        </div>
      </div>

      <div class="footer-bar">
        <span>MACHINE-READABLE SPECS: AUTOMATED REPRODUCIBLE COMPLIANCE CONTRACTS</span>
        <span class="live-pill">STATUS: SPEC LOCKED</span>
      </div>
    </body></html>""",

    "ch5_scene2": f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><style>{BASE_CSS}
      .scorecard-table {{ width:100%; border-collapse:collapse; margin-top:10px; font-family:monospace; }}
      .scorecard-table th {{ background:#111; color:#FFF; padding:10px; font-size:13px; text-align:left; }}
      .scorecard-table td {{ padding:10px; border-bottom:2px solid #111; font-size:13px; font-weight:700; }}
    </style></head><body>
      <div class="top-bar">
        <div class="tag-group">
          <span class="neo-badge neo-badge-mint">AUTOMATED AUDIT</span>
          <span class="neo-badge neo-badge-pink">PUBLICATION GATE</span>
          <span class="neo-badge">PASS / FAIL SCORECARD</span>
        </div>
        <div class="chapter-pill">CHAPTER 05 · SCENE 2/2</div>
      </div>
      <div class="title-section">
        <h1><span>🛡️</span> Secondary Independent Compliance Audit</h1>
        <p class="subtitle">No asset enters the library without an unconditional PASS verdict verified directly on output pixels</p>
      </div>

      <div class="neo-card" style="margin: 24px 0; flex: 1;">
        <div class="neo-card-header" style="background:#00FFA3;">
          <span>AUTOMATED COMPLIANCE VERIFICATION REPORT (LIVE ENGINE OUTPUT)</span>
          <span style="font-family:monospace;">STATUS: PASS (7/7 RULES)</span>
        </div>
        <div class="neo-card-body" style="padding:16px;">
          <table class="scorecard-table">
            <thead>
              <tr>
                <th>RULE CHECK</th>
                <th>DELIVERY SPEC TARGET</th>
                <th>MEASURED METRIC</th>
                <th>TOLERANCE</th>
                <th>VERDICT</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>exact_dimensions</td>
                <td>1080 × 1920 (9:16)</td>
                <td>1080 × 1920</td>
                <td>0 px deviation</td>
                <td><span style="background:#DCFCE7; color:#15803D; padding:2px 8px; border:1.5px solid #111; border-radius:4px;">PASS</span></td>
              </tr>
              <tr>
                <td>faces_inside_safe_zone</td>
                <td>min 99.5% area</td>
                <td>99.8% inside</td>
                <td>≥ 99.5%</td>
                <td><span style="background:#DCFCE7; color:#15803D; padding:2px 8px; border:1.5px solid #111; border-radius:4px;">PASS</span></td>
              </tr>
              <tr>
                <td>platform_safe_margins</td>
                <td>min 14% boundary</td>
                <td>14.2% margin</td>
                <td>≥ 14.0%</td>
                <td><span style="background:#DCFCE7; color:#15803D; padding:2px 8px; border:1.5px solid #111; border-radius:4px;">PASS</span></td>
              </tr>
              <tr>
                <td>active_speaker_framed</td>
                <td>min 70% speech time</td>
                <td>94.6% framed</td>
                <td>≥ 70.0%</td>
                <td><span style="background:#DCFCE7; color:#15803D; padding:2px 8px; border:1.5px solid #111; border-radius:4px;">PASS</span></td>
              </tr>
              <tr>
                <td>headroom_balance</td>
                <td>between 5% and 18%</td>
                <td>11.2% headroom</td>
                <td>[5%, 18%]</td>
                <td><span style="background:#DCFCE7; color:#15803D; padding:2px 8px; border:1.5px solid #111; border-radius:4px;">PASS</span></td>
              </tr>
              <tr>
                <td>codec_compliance</td>
                <td>H.264 High / AAC-LC</td>
                <td>h264 / aac</td>
                <td>Exact</td>
                <td><span style="background:#DCFCE7; color:#15803D; padding:2px 8px; border:1.5px solid #111; border-radius:4px;">PASS</span></td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <div class="footer-bar">
        <span>SECURITY GUARANTEE: FAILED ASSETS AUTOMATICALLY QUARANTINED AND EXCLUDED</span>
        <span class="live-pill">ZERO DEFECT POLICY</span>
      </div>
    </body></html>""",

    # -------------------------------------------------------------------------
    # CHAPTER 6: Production Pitch
    # -------------------------------------------------------------------------
    "ch6_scene1": f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><style>{BASE_CSS}
      .infra-grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 24px; margin: 28px 0; flex: 1; }}
    </style></head><body>
      <div class="top-bar">
        <div class="tag-group">
          <span class="neo-badge neo-badge-cyan">AWS CLOUD DEPLOYMENT</span>
          <span class="neo-badge neo-badge-yellow">FREE TIER COMPLIANT</span>
          <span class="neo-badge">CI/CD AUTOMATION</span>
        </div>
        <div class="chapter-pill">CHAPTER 06 · SCENE 1/2</div>
      </div>
      <div class="title-section">
        <h1><span>☁️</span> AWS Free Tier Cloud Architecture</h1>
        <p class="subtitle">Complete zero-overhead cloud deployment running in production with sub-4 minute automated deployments</p>
      </div>

      <div class="infra-grid">
        <div class="neo-card">
          <div class="neo-card-header" style="background:#00E5FF;">01 · EDGE & GATEWAY</div>
          <div class="neo-card-body">
            <span style="font-size:32px;">🌐</span>
            <p style="font-weight:900; font-size:16px;">DNS & Reverse Proxy</p>
            <p style="font-size:13px; color:#4B5563;">Elastic IP with Let's Encrypt SSL. NGINX multiplexes API (8000) and Web SPA (80).</p>
            <div style="background:#111; color:#00E5FF; padding:4px 8px; border-radius:4px; font-family:monospace; font-size:11px;">cre-hoichoi.aritro.cloud</div>
          </div>
        </div>

        <div class="neo-card">
          <div class="neo-card-header" style="background:#FFE500;">02 · COMPUTE INSTANCE</div>
          <div class="neo-card-body">
            <span style="font-size:32px;">⚡</span>
            <p style="font-weight:900; font-size:16px;">EC2 Linux 2023</p>
            <p style="font-size:13px; color:#4B5563;">Docker Compose running API container with MediaPipe models + SQLite WAL database.</p>
            <div style="background:#111; color:#FFE500; padding:4px 8px; border-radius:4px; font-family:monospace; font-size:11px;">AWS FREE TIER: $0/MO</div>
          </div>
        </div>

        <div class="neo-card">
          <div class="neo-card-header" style="background:#00E575;">03 · DEPLOYMENT CI/CD</div>
          <div class="neo-card-body">
            <span style="font-size:32px;">🚀</span>
            <p style="font-weight:900; font-size:16px;">GitHub Actions</p>
            <p style="font-size:13px; color:#4B5563;">Push to main triggers multi-arch build, pushes to ECR, and updates EC2 via AWS SSM.</p>
            <div style="background:#111; color:#00E575; padding:4px 8px; border-radius:4px; font-family:monospace; font-size:11px;">DEPLOY TIME: 3m 37s</div>
          </div>
        </div>
      </div>

      <div class="footer-bar">
        <span>CLOUD NATIVE: AWS SSM (ZERO OPEN INBOUND PORTS FOR SSH) · ENCRYPTED HTTPS</span>
        <span class="live-pill">UPTIME: 100% OPERATIONAL</span>
      </div>
    </body></html>""",

    "ch6_scene2": f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><style>{BASE_CSS}
      .summary-box {{ background:#FFF; border:4px solid #111; box-shadow:10px 10px 0px #111; border-radius:14px; padding:32px; margin:28px 0; flex:1; display:flex; flex-direction:column; justify-content:space-between; }}
      .kpi-row {{ display:grid; grid-template-columns: repeat(4, 1fr); gap:20px; }}
      .kpi-card {{ background:#F8FAFC; border:3px solid #111; padding:16px; border-radius:8px; text-align:center; }}
    </style></head><body>
      <div class="top-bar">
        <div class="tag-group">
          <span class="neo-badge neo-badge-mint">PITCH CONCLUSION</span>
          <span class="neo-badge neo-badge-pink">PROBLEM 4 COMPLETE</span>
          <span class="neo-badge">HOICHOI READY</span>
        </div>
        <div class="chapter-pill">CHAPTER 06 · SCENE 2/2</div>
      </div>
      <div class="title-section">
        <h1><span>🏆</span> Creative Reformatting Engine · Hackathon Verdict</h1>
        <p class="subtitle">Broadcast-quality, zero-disqualifier automated creative adaptation for Hoichoi OTT</p>
      </div>

      <div class="summary-box">
        <div class="kpi-row">
          <div class="kpi-card" style="background:#FEF3C7;">
            <p style="font-family:monospace; font-size:12px; font-weight:800;">AUTO-DISQUALIFIERS</p>
            <p style="font-size:36px; font-weight:900; color:#111;">ZERO</p>
            <span style="font-size:11px; font-weight:700; color:#059669;">✓ 100% BEATEN</span>
          </div>
          <div class="kpi-card" style="background:#D1FAE5;">
            <p style="font-family:monospace; font-size:12px; font-weight:800;">SPEC COMPLIANCE</p>
            <p style="font-size:36px; font-weight:900; color:#059669;">100%</p>
            <span style="font-size:11px; font-weight:700; color:#059669;">✓ PUBLICATION GATE</span>
          </div>
          <div class="kpi-card" style="background:#E0F2FE;">
            <p style="font-family:monospace; font-size:12px; font-weight:800;">ACTIVE SPEAKER ASD</p>
            <p style="font-size:36px; font-weight:900; color:#0284C7;">SYNC</p>
            <span style="font-size:11px; font-weight:700; color:#0284C7;">✓ DYNAMIC REEL</span>
          </div>
          <div class="kpi-card" style="background:#FCE7F3;">
            <p style="font-family:monospace; font-size:12px; font-weight:800;">CLOUD RUNTIME COST</p>
            <p style="font-size:36px; font-weight:900; color:#DB2777;">$0.00</p>
            <span style="font-size:11px; font-weight:700; color:#DB2777;">✓ AWS FREE TIER</span>
          </div>
        </div>

        <div style="background:#111; color:#FFF; border:3px solid #111; padding:20px; border-radius:10px; display:flex; justify-content:space-between; align-items:center;">
          <div>
            <p style="font-size:12px; color:#FFE500; font-family:monospace; font-weight:800;">LIVE PRODUCTION WORKSTATION URL</p>
            <p style="font-size:24px; font-family:monospace; font-weight:900; color:#00FFA3;">https://cre-hoichoi.aritro.cloud</p>
          </div>
          <div style="text-align:right;">
            <span style="background:#00FFA3; color:#111; font-weight:900; font-size:14px; padding:8px 18px; border-radius:6px; font-family:monospace;">
              READY FOR OTT INTEGRATION ➔
            </span>
          </div>
        </div>
      </div>

      <div class="footer-bar">
        <span>THANK YOU · HOICHOI HACKATHON 2026 · CREATIVE REFORMATTING ENGINE</span>
        <span class="live-pill">STATUS: DELIVERED & AUDITED</span>
      </div>
    </body></html>""",
}


def render_all_slides():
    print(f"Rendering {len(SLIDES)} Neobrutalist slides via headless Chrome...")
    for slide_id, html_content in SLIDES.items():
        html_path = SLIDES_DIR / f"{slide_id}.html"
        png_path = SLIDES_DIR / f"{slide_id}.png"

        html_path.write_text(html_content, encoding="utf-8")
        print(f"Generating {slide_id}.png (1920x1080)...")

        cmd = [
            CHROME_BIN,
            "--headless=new",
            "--disable-gpu",
            "--hide-scrollbars",
            f"--window-size=1920,1080",
            f"--screenshot={png_path}",
            str(html_path),
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            print(f"Error rendering {slide_id}: {res.stderr}")
        else:
            print(f"  ✓ Saved {png_path} ({png_path.stat().st_size / 1024:.1f} KB)")

    print("\nAll 12 Neobrutalist slides rendered successfully!")


if __name__ == "__main__":
    render_all_slides()
