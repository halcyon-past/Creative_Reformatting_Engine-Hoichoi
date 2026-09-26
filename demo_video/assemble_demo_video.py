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

    scenes = data["scenes"]
    segment_files = []

    print(f"Assembling {len(scenes)} Neobrutalist animated scene segments...")

    for i, sc in enumerate(scenes, 1):
        sc_id = sc["id"]
        slide_img = f"demo_video/slides/{sc_id}.png"
        voice_audio = f"demo_video/{sc_id}.aiff"
        segment_mp4 = f"demo_video/{sc_id}_segment.mp4"
        duration = sc["scene_duration_s"]
        frames = int(duration * 30)

        print(f"[{i:02d}/{len(scenes)}] Rendering {sc_id} ({duration:.2f}s, {frames} frames)...")

        # Alternate camera animation styles per scene:
        # Odd scenes: subtle slow zoom-in on the focal cards
        # Even scenes: subtle slow pan across the graphs/metrics
        if i % 2 == 1:
            vf = (
                f"zoompan=z='min(zoom+0.00035,1.05)':d={frames}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1920x1080:fps=30,"
                f"fade=t=in:st=0:d=0.4,fade=t=out:st={duration-0.4:.2f}:d=0.4"
            )
        else:
            vf = (
                f"zoompan=z='1.03':d={frames}:x='iw*0.015*on/{frames}':y='ih/2-(ih/zoom/2)':s=1920x1080:fps=30,"
                f"fade=t=in:st=0:d=0.4,fade=t=out:st={duration-0.4:.2f}:d=0.4"
            )

        ffmpeg_args = [
            "-loop", "1",
            "-t", f"{duration}",
            "-i", slide_img,
            "-i", voice_audio,
            "-vf", vf,
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-preset", "veryfast",
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

    print("\nConcatenating all 12 animated segments together...")
    unmixed_mp4 = "demo_video/video_narration_only.mp4"
    run_docker_ffmpeg([
        "-f", "concat",
        "-safe", "0",
        "-i", "demo_video/concat_list.txt",
        "-c", "copy",
        unmixed_mp4,
    ])

    print("\nMixing broadcast-mastered voice + upbeat background music...")
    final_output_mp4 = "demo_video/creative_reformatting_engine_pitch_demo.mp4"

    # Audio Filter Graph:
    # 1. Voice channel [0:a]:
    #    - highpass at 80Hz (removes mic rumble)
    #    - equalizer cuts 250Hz by 2dB (clears chest mud)
    #    - equalizer boosts 3200Hz by 3.5dB (vocal clarity & presence)
    #    - compand (broadcast leveling compression)
    #    - volume boost to 1.25
    # 2. Music channel [1:a]:
    #    - volume at 0.36 (clearly audible, energetic upbeat groove)
    #    - sidechain compression: smoothly ducks music by 4dB when voice is actively speaking!
    # 3. amix combines them with first duration priority
    audio_filters = (
        "[0:a]highpass=f=80,"
        "equalizer=f=250:t=q:w=1.2:g=-2.0,"
        "equalizer=f=3200:t=q:w=1.5:g=3.5,"
        "compand=attacks=0.03:decays=0.18:points=-60/-60|-24/-16|-12/-8|0/-3,"
        "volume=1.25[voice];"
        "[1:a]volume=0.36[music];"
        "[music][voice]sidechaincompress=threshold=0.18:ratio=2.5:attack=30:release=350[ducked_music];"
        "[voice][ducked_music]amix=inputs=2:duration=first:dropout_transition=2[aout]"
    )

    run_docker_ffmpeg([
        "-i", unmixed_mp4,
        "-i", "demo_video/background_music.wav",
        "-filter_complex", audio_filters,
        "-map", "0:v:0",
        "-map", "[aout]",
        "-c:v", "copy",
        "-c:a", "aac",
        "-b:a", "256k",
        "-ar", "44100",
        "-shortest",
        final_output_mp4,
    ])

    final_path = DEMO_DIR / "creative_reformatting_engine_pitch_demo.mp4"
    print(f"\nSUCCESS! Assembled demo pitch video: {final_path}")
    print(f"File size: {final_path.stat().st_size / (1024*1024):.2f} MB")


if __name__ == "__main__":
    main()
