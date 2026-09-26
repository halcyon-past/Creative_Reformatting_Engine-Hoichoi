import json
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEMO_DIR = REPO_ROOT / "demo_video"
SLIDES_DIR = DEMO_DIR / "slides"
DOCKER_IMAGE = "031879841983.dkr.ecr.us-east-1.amazonaws.com/hoichoi-cre:v2"


def run_docker_ffmpeg(args: list[str]):
    cmd = [
        "docker", "run", "--rm",
        "-v", f"{REPO_ROOT}:/workspace",
        "-w", "/workspace",
        DOCKER_IMAGE,
        "ffmpeg", "-y",
    ] + args
    print(f"Running ffmpeg in docker: {' '.join(cmd[:10])}...")
    subprocess.run(cmd, check=True)


def main():
    manifest_path = DEMO_DIR / "chapters.json"
    with manifest_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    chapters = data["chapters"]
    segment_files = []

    print(f"Assembling {len(chapters)} chapter segments...")

    for i, ch in enumerate(chapters, 1):
        ch_id = ch["id"]
        slide_img = f"demo_video/slides/{ch_id}.png"
        voice_audio = f"demo_video/{ch_id}.aiff"
        segment_mp4 = f"demo_video/{ch_id}_segment.mp4"
        duration = ch["scene_duration_s"]

        print(f"[{i}/{len(chapters)}] Rendering segment {ch_id} (duration: {duration:.2f}s)...")

        # Encode slide image + voice audio into MP4 segment
        # Using subtle zoom/pan filter for high visual engagement
        ffmpeg_args = [
            "-loop", "1",
            "-t", f"{duration}",
            "-i", slide_img,
            "-i", voice_audio,
            "-vf", (
                f"zoompan=z='min(zoom+0.0003,1.04)':d={int(duration*30)}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1920x1080:fps=30,"
                f"fade=t=in:st=0:d=0.6,fade=t=out:st={duration-0.6}:d=0.6"
            ),
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-r", "30",
            "-c:a", "aac",
            "-b:a", "192k",
            "-ar", "44100",
            "-ac", "2",
            "-shortest",
            segment_mp4,
        ]
        run_docker_ffmpeg(ffmpeg_args)
        segment_files.append(segment_mp4)

    # Concat list file
    concat_list_path = DEMO_DIR / "concat_list.txt"
    with concat_list_path.open("w", encoding="utf-8") as f:
        for seg in segment_files:
            f.write(f"file '/workspace/{seg}'\n")

    print("\nConcatenating all segments together...")
    unmixed_mp4 = "demo_video/video_narration_only.mp4"
    run_docker_ffmpeg([
        "-f", "concat",
        "-safe", "0",
        "-i", "demo_video/concat_list.txt",
        "-c", "copy",
        unmixed_mp4,
    ])

    print("\nMixing ambient background music with narration...")
    final_output_mp4 = "demo_video/creative_reformatting_engine_pitch_demo.mp4"

    # Audio filter graph:
    # [0:a] voice narration (volume=1.0)
    # [1:a] ambient background music (volume=0.22, subtle low-key ambient bed)
    # amix combines them with voice priority
    run_docker_ffmpeg([
        "-i", unmixed_mp4,
        "-i", "demo_video/background_music.wav",
        "-filter_complex", (
            "[0:a]volume=1.1[voice]; "
            "[1:a]volume=0.20[music]; "
            "[voice][music]amix=inputs=2:duration=first:dropout_transition=2[aout]"
        ),
        "-map", "0:v:0",
        "-map", "[aout]",
        "-c:v", "copy",
        "-c:a", "aac",
        "-b:a", "256k",
        "-ar", "44100",
        "-movflags", "+faststart",
        final_output_mp4,
    ])

    print(f"\nSUCCESS! Demo pitch video created at: {DEMO_DIR / 'creative_reformatting_engine_pitch_demo.mp4'}")


if __name__ == "__main__":
    main()
