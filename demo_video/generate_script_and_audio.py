import json
import subprocess
from pathlib import Path

DEMO_DIR = Path(__file__).resolve().parent

CHAPTERS = [
    {
        "id": "ch1_problem_overview",
        "chapter_num": 1,
        "title": "Problem 4: Creative Reformatting Engine",
        "subtitle": "Automated OTT & Social Delivery Pipeline for Hoichoi",
        "badge": "EXECUTIVE SUMMARY",
        "text": (
            "Welcome to the Creative Reformatting Engine demo, engineered for Problem 4 of the Hoichoi Hackathon. "
            "In OTT streaming, hero titles must be distributed across fragmented platform ratios: 16 by 9 widescreen, "
            "1 by 1 square feeds, 9 by 16 vertical stories and reels, and 4 by 5 mobile portrait. "
            "Naive center crops slice off off-center actors, violate platform safe zones, and freeze on wide dialogue. "
            "We engineered an automated pipeline with subject-aware smart crop, active-speaker vertical reframing, and clean "
            "key still extraction—with every asset verified against a machine-readable spec before entering the library."
        ),
    },
    {
        "id": "ch2_architecture_vision",
        "chapter_num": 2,
        "title": "Computer Vision & Audio Architecture",
        "subtitle": "BlazeFace, SSD Person Tracking & Active Speaker Audio Sync",
        "badge": "CORE CV STACK",
        "text": (
            "The hackathon brief specified three auto-disqualifiers: center-crop with a disconnected face detector, "
            "vertical video reframed once at frame zero and held static, and validators that merely check dimensions. "
            "To decisively beat these failure modes, we built an end-to-end computer vision stack. "
            "We deploy MediaPipe BlazeFace for sub-millisecond facial landmarking, paired with SSD MobileNet person tracking "
            "and Laplacian gradient saliency. "
            "Our rule-of-thirds composition solver frames subjects with headroom preservation. "
            "For video, our Active Speaker Detector pairs audio Voice Activity Detection with visual lip dynamics, "
            "smoothly tracking whoever is talking."
        ),
    },
    {
        "id": "ch3_stills_pipeline",
        "chapter_num": 3,
        "title": "Stills Pipeline: Subject-Aware Smart Crop",
        "subtitle": "16:9, 1:1, 9:16 & 4:5 Variants Composed Around Detected Subjects",
        "badge": "STILLS REFORMATTING",
        "text": (
            "Let us examine the stills reformatting pipeline on our toughest benchmark assets. "
            "Consider an image with an actor positioned deliberately off-center to the far left. "
            "A naive center crop cuts directly through the actor's face, ruining the asset. "
            "The Creative Reformatting Engine analyzes the master, detects all primary faces, calculates subject coverage, "
            "and composes around the true focal center. "
            "It generates all four mandated platform ratios: 16 by 9 Hero Landscape, 1 by 1 Social Square, 9 by 16 Story, "
            "and 4 by 5 Feed Portrait. "
            "Each variant maintains calibrated safe-zone margins, and our platform supports single-variant regeneration "
            "to re-render individual ratios in isolation."
        ),
    },
    {
        "id": "ch4_video_pipeline",
        "chapter_num": 4,
        "title": "Video Pipeline: Speaker-Aware Reel Cutdown",
        "subtitle": "Dynamic Active-Speaker Camera Tracking & Sharp Key Still Extraction",
        "badge": "VIDEO & REEL REFRAME",
        "text": (
            "Next is the video reframing engine—the centerpiece of our pipeline. "
            "The brief's toughest test is a two-person alternating-speaker clip. Naive approaches hold a static wide shot "
            "or stick to one person while the other speaks. "
            "Our Active Speaker Detector continuously correlates speech audio energy with facial lip motion across multiple tracks. "
            "When person A speaks, the crop follows them. When dialogue shifts to person B, the camera smoothly pans "
            "to frame the new speaker in sync with audio. "
            "The system plots the complete Reframe Path over time, color-coded by speaker track ID. "
            "Simultaneously, the pipeline extracts a pristine key still scanning candidate frames for peak Laplacian sharpness."
        ),
    },
    {
        "id": "ch5_spec_validation",
        "chapter_num": 5,
        "title": "Machine-Readable Spec & Publication Gate",
        "subtitle": "Independent Compliance Auditing Before Entering the Library",
        "badge": "COMPLIANCE ENGINE",
        "text": (
            "Automated validation is the core requirement of the brief: no asset enters the library unvalidated. "
            "In our architecture, the Publication Gate enforces this structurally: every variant is rendered, validated, "
            "and published only upon an unconditional PASS verdict. "
            "Our delivery contracts are encoded in a machine-readable platform YAML specification with exact safe-zone tolerances. "
            "Crucially, our validator does not rely on pipeline hints. It runs an independent secondary detection pass "
            "directly on rendered outputs. "
            "It verifies that faces remain 99.5% inside the frame, maintain safe margins from edges, and clear Instagram "
            "and TikTok reserved UI overlays. Quarantined assets never enter the library."
        ),
    },
    {
        "id": "ch6_production_pitch",
        "chapter_num": 6,
        "title": "Production Deployment & Conclusion",
        "subtitle": "Live on AWS Free Tier · GitHub Actions CI/CD · https://cre-hoichoi.aritro.cloud",
        "badge": "LIVE PRODUCTION",
        "text": (
            "The entire system is deployed live in production on AWS Free Tier architecture. "
            "It runs on Amazon Linux 2023 with an Elastic IP, backed by an S3 media bucket with lifecycle rules, "
            "asynchronous SQS queues, and CloudWatch logging. "
            "We engineered an automated GitHub Actions CI/CD pipeline deploying container updates via AWS Systems Manager "
            "in under three and a half minutes. "
            "The user interface is a darkroom production workstation, live at cre-hoichoi dot aritro dot cloud with "
            "Let's Encrypt HTTPS encryption. "
            "The Creative Reformatting Engine solves Problem 4 with broadcast quality and zero operational overhead. "
            "Thank you for your time."
        ),
    },
]


def get_audio_duration(aiff_path: Path) -> float:
    cmd = ["afinfo", str(aiff_path)]
    res = subprocess.run(cmd, capture_output=True, text=True, check=True)
    for line in res.stdout.splitlines():
        if "estimated duration" in line.lower():
            parts = line.split(":")
            if len(parts) >= 2:
                dur_str = parts[1].strip().split()[0]
                return float(dur_str)
    return 35.0


def main():
    print("Synthesizing narration calibrated for ~4 minutes (240s)...")
    total_duration = 0.0

    for i, ch in enumerate(CHAPTERS, 1):
        aiff_path = DEMO_DIR / f"{ch['id']}.aiff"
        print(f"[{i}/{len(CHAPTERS)}] Synthesizing {ch['id']}...")
        # Daniel voice at 186 words per minute (crisp and natural)
        cmd = ["/usr/bin/say", "-v", "Daniel", "-r", "186", "-o", str(aiff_path), ch["text"]]
        subprocess.run(cmd, check=True)
        dur = get_audio_duration(aiff_path)
        # Pad duration slightly by 1.5s for breath and visual transition
        ch["audio_duration_s"] = dur
        ch["scene_duration_s"] = round(dur + 1.5, 2)
        total_duration += ch["scene_duration_s"]
        print(f"  -> Audio: {dur:.2f}s, Scene: {ch['scene_duration_s']:.2f}s")

    print(f"\nTotal Video Duration: {total_duration:.2f}s ({total_duration/60:.2f} minutes / ~4m:00s)")

    manifest_path = DEMO_DIR / "chapters.json"
    with manifest_path.open("w", encoding="utf-8") as f:
        json.dump({"total_duration_s": total_duration, "chapters": CHAPTERS}, f, indent=2)

    print(f"Saved calibrated manifest to {manifest_path}")


if __name__ == "__main__":
    main()
