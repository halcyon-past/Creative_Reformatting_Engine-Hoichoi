import math
import struct
import wave
from pathlib import Path

DEMO_DIR = Path(__file__).resolve().parent

SAMPLE_RATE = 44100
DURATION_S = 275  # 4m 35s to cover the entire demo with fadeout


def generate_music():
    print(f"Synthesizing {DURATION_S}s ambient background music...")
    n_samples = int(SAMPLE_RATE * DURATION_S)
    wav_path = DEMO_DIR / "background_music.wav"

    # Ambient chord root frequencies in Hz (Dm9 -> Bbmaj7 -> Fmaj9 -> Cadd9)
    chords = [
        # Dm9: D3, F3, A3, C4, E4
        [146.83, 174.61, 220.00, 261.63, 329.63],
        # Bbmaj7: Bb2, D3, F3, A3, D4
        [116.54, 146.83, 174.61, 220.00, 293.66],
        # Fmaj9: F2, C3, E3, A3, G3
        [87.31, 130.81, 164.81, 220.00, 196.00],
        # C9sus4: C3, G3, Bb3, D4, F4
        [130.81, 196.00, 233.08, 293.66, 349.23],
    ]

    chord_len_s = 6.0  # 6 seconds per chord
    loop_period = len(chords) * chord_len_s

    with wave.open(str(wav_path), "wb") as wf:
        wf.setnchannels(2)  # Stereo
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(SAMPLE_RATE)

        # Generate in chunks of 44100 samples (1s) to conserve memory
        chunk_size = 44100
        total_chunks = (n_samples + chunk_size - 1) // chunk_size

        for chunk_idx in range(total_chunks):
            start_i = chunk_idx * chunk_size
            end_i = min(start_i + chunk_size, n_samples)
            frames = bytearray()

            for i in range(start_i, end_i):
                t = i / SAMPLE_RATE

                # Overall master fade in (first 4s) and fade out (last 6s)
                fade_in = min(1.0, t / 4.0)
                fade_out = min(1.0, (DURATION_S - t) / 6.0) if t > DURATION_S - 6.0 else 1.0
                envelope = fade_in * max(0.0, fade_out)

                # Which chord in the loop
                loop_t = t % loop_period
                chord_idx = int(loop_t / chord_len_s)
                chord_frac = (loop_t % chord_len_s) / chord_len_s
                cur_chord = chords[chord_idx]

                # Soft bell/pad envelope within the chord
                pad_env = (1.0 - math.cos(2.0 * math.pi * chord_frac)) * 0.5

                # Synthesize chord notes with gentle chorus & subtle stereo width
                left = 0.0
                right = 0.0

                for n_idx, freq in enumerate(cur_chord):
                    # Slight detuning for analog warmth
                    phase_l = 2.0 * math.pi * freq * t + math.sin(t * 0.3 + n_idx) * 0.08
                    phase_r = 2.0 * math.pi * (freq * 1.002) * t + math.cos(t * 0.25 + n_idx) * 0.08

                    # Fundamental + soft 2nd harmonic
                    sig_l = math.sin(phase_l) * 0.6 + math.sin(phase_l * 2.0) * 0.25
                    sig_r = math.sin(phase_r) * 0.6 + math.sin(phase_r * 2.0) * 0.25

                    gain = 1.0 / (1.0 + n_idx * 0.35)
                    pan = (n_idx / (len(cur_chord) - 1)) * 0.6 + 0.2  # 0.2 to 0.8 stereo pan

                    left += sig_l * gain * (1.0 - pan)
                    right += sig_r * gain * pan

                # Subtle gentle pulse / rhythmic click (subtle kick/arpeggio tap every 1.5s)
                pulse_phase = (t % 1.5) / 1.5
                pulse_click = math.exp(-pulse_phase * 24.0) * math.sin(2.0 * math.pi * 65.0 * pulse_phase) * 0.15

                # Master mix scaling: quiet background level (-22dB) so speech sits clearly on top
                master_gain = 0.075 * envelope * pad_env
                sample_l = int(max(-32767, min(32767, (left * master_gain + pulse_click * 0.05 * envelope) * 32767)))
                sample_r = int(max(-32767, min(32767, (right * master_gain + pulse_click * 0.05 * envelope) * 32767)))

                frames += struct.pack("<hh", sample_l, sample_r)

            wf.writeframes(frames)

    print(f"Generated {wav_path} ({wav_path.stat().st_size / (1024*1024):.2f} MB)")


if __name__ == "__main__":
    generate_music()
