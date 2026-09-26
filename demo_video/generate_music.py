import math
import struct
import wave
from pathlib import Path

DEMO_DIR = Path(__file__).resolve().parent
SAMPLE_RATE = 44100
DURATION_S = 275  # 4m 35s to comfortably cover the full narration + outro

# Musical parameters: 116 BPM upbeat electronic lo-fi tech groove
BPM = 116.0
BEAT_S = 60.0 / BPM  # ~0.5172s
SIXTEENTH_S = BEAT_S / 4.0
BAR_S = BEAT_S * 4.0  # ~2.069s
LOOP_BARS = 4
LOOP_S = BAR_S * LOOP_BARS  # ~8.276s

# Chord progressions (Hz): Dm9 -> Bbmaj7 -> Fmaj9 -> C9sus4
CHORD_DATA = [
    # Bar 0: Dm (root 73.42 Hz D2, chord: D3, F3, A3, C4, E4)
    {"root": 73.42, "notes": [146.83, 174.61, 220.00, 261.63, 329.63]},
    # Bar 1: Bb (root 58.27 Hz Bb1, chord: Bb2, D3, F3, A3, D4)
    {"root": 58.27, "notes": [116.54, 146.83, 174.61, 220.00, 293.66]},
    # Bar 2: F (root 87.31 Hz F2, chord: F2, C3, E3, A3, G3)
    {"root": 87.31, "notes": [87.31, 130.81, 164.81, 220.00, 196.00]},
    # Bar 3: C (root 65.41 Hz C2, chord: C3, G3, Bb3, D4, F4)
    {"root": 65.41, "notes": [130.81, 196.00, 233.08, 293.66, 349.23]},
]

# Pentatonic scale frequencies for high-energy arpeggiator
PENTATONIC = [
    293.66, 329.63, 349.23, 440.00, 523.25,
    587.33, 659.25, 698.46, 880.00, 1046.50
]


def generate_music():
    print(f"Synthesizing {DURATION_S}s high-energy Neobrutalist tech-pop demo groove...")
    n_samples = int(SAMPLE_RATE * DURATION_S)
    wav_path = DEMO_DIR / "background_music.wav"

    with wave.open(str(wav_path), "wb") as wf:
        wf.setnchannels(2)  # Stereo
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(SAMPLE_RATE)

        chunk_size = 44100
        total_chunks = (n_samples + chunk_size - 1) // chunk_size

        # Simple pseudo-random generator for noise (hi-hats/snare)
        rng_state = 123456789

        for chunk_idx in range(total_chunks):
            start_i = chunk_idx * chunk_size
            end_i = min(start_i + chunk_size, n_samples)
            frames = bytearray()

            for i in range(start_i, end_i):
                t = i / SAMPLE_RATE

                # Master fade in (first 3s) and fade out (last 5s)
                fade_in = min(1.0, t / 3.0)
                fade_out = min(1.0, (DURATION_S - t) / 5.0) if t > DURATION_S - 5.0 else 1.0
                envelope = fade_in * max(0.0, fade_out)

                # Loop position
                loop_t = t % LOOP_S
                bar_idx = int(loop_t / BAR_S) % LOOP_BARS
                bar_t = loop_t % BAR_S
                beat_idx = int(bar_t / BEAT_S) % 4
                beat_t = bar_t % BEAT_S
                sixteenth_idx = int(bar_t / SIXTEENTH_S) % 16
                sixteenth_t = bar_t % SIXTEENTH_S

                cur_chord = CHORD_DATA[bar_idx]
                root_freq = cur_chord["root"]

                # -------------------------------------------------------------
                # 1. DRUMS: Kick, Snare/Clap, Hi-Hats
                # -------------------------------------------------------------
                # Kick on beat 0 and beat 2 (and syncopated kick at 14/16 = 3.5 beat)
                is_kick = (beat_idx == 0 and beat_t < 0.28) or \
                          (beat_idx == 2 and beat_t < 0.28) or \
                          (sixteenth_idx == 10 and sixteenth_t < 0.22)
                kick_sig = 0.0
                if is_kick:
                    k_t = beat_t if beat_idx in (0, 2) else sixteenth_t
                    k_freq = 45.0 + 95.0 * math.exp(-k_t * 32.0)
                    k_env = math.exp(-k_t * 16.0)
                    kick_sig = math.sin(2.0 * math.pi * k_freq * k_t) * k_env * 0.85

                # Snare / Clap on beat 1 and beat 3 (0-indexed)
                is_snare = (beat_idx in (1, 3)) and (beat_t < 0.22)
                snare_sig = 0.0
                if is_snare:
                    # White noise + body tone
                    rng_state = (rng_state * 1103515245 + 12345) & 0x7FFFFFFF
                    noise = (rng_state / 0x40000000) - 1.0
                    s_env = math.exp(-beat_t * 22.0)
                    body = math.sin(2.0 * math.pi * 185.0 * beat_t) * 0.4
                    snare_sig = (noise * 0.7 + body) * s_env * 0.65

                # Hi-Hats on every 16th note with groovy accent
                hat_env = math.exp(-sixteenth_t * 55.0)
                rng_state = (rng_state * 1103515245 + 12345) & 0x7FFFFFFF
                hat_noise = (rng_state / 0x40000000) - 1.0
                # Accent off-beats (sixteenth 2, 6, 10, 14)
                hat_accent = 0.45 if (sixteenth_idx % 4 == 2) else 0.22
                hat_sig = hat_noise * hat_env * hat_accent

                # -------------------------------------------------------------
                # 2. BASSLINE: Plucky, driving sub-synth
                # -------------------------------------------------------------
                # 8th note rhythmic bass
                eighth_idx = int(bar_t / (BEAT_S / 2.0)) % 8
                eighth_t = bar_t % (BEAT_S / 2.0)
                # Octave pattern: Root, Root, Octave, Root, Octave, 5th, Root, Octave
                octave_mult = [1.0, 1.0, 2.0, 1.0, 2.0, 1.5, 1.0, 2.0][eighth_idx]
                bass_freq = root_freq * octave_mult
                b_env = math.exp(-eighth_t * 12.0)
                # Saturation / warm harmonics
                b_phase = 2.0 * math.pi * bass_freq * t
                bass_sig = (math.sin(b_phase) * 0.7 + math.sin(b_phase * 2.0) * 0.3) * b_env * 0.55

                # -------------------------------------------------------------
                # 3. SYNTH CHORDS: Upbeat neo-disco / tech chords on offbeats
                # -------------------------------------------------------------
                # Play chord stabs on offbeat of each beat (syncopated 8th notes)
                is_chord_stab = (sixteenth_idx % 4 in (2, 3))
                chord_env = math.exp(-(sixteenth_t if sixteenth_idx % 4 == 2 else sixteenth_t + SIXTEENTH_S) * 7.0)
                chord_l = 0.0
                chord_r = 0.0

                for n_i, freq in enumerate(cur_chord["notes"]):
                    p_l = 2.0 * math.pi * freq * t + n_i * 0.5
                    p_r = 2.0 * math.pi * (freq * 1.003) * t + n_i * 0.5
                    s_l = math.sin(p_l) * 0.5 + (1.0 if (p_l % (2.0 * math.pi)) < math.pi else -1.0) * 0.15
                    s_r = math.sin(p_r) * 0.5 + (1.0 if (p_r % (2.0 * math.pi)) < math.pi else -1.0) * 0.15
                    chord_l += s_l * 0.22
                    chord_r += s_r * 0.22

                chord_sig_l = chord_l * chord_env * 0.40
                chord_sig_r = chord_r * chord_env * 0.40

                # -------------------------------------------------------------
                # 4. ARPEGGIATOR: Bright, playful 16th-note tech pluck
                # -------------------------------------------------------------
                # Cycle through pentatonic notes based on bar and 16th index
                arp_note_idx = (bar_idx * 3 + sixteenth_idx) % len(PENTATONIC)
                arp_freq = PENTATONIC[arp_note_idx]
                arp_env = math.exp(-sixteenth_t * 22.0)
                arp_phase = 2.0 * math.pi * arp_freq * t
                arp_base = math.sin(arp_phase) * math.exp(-sixteenth_t * 14.0) * 0.20
                arp_l = arp_base * (0.3 + 0.4 * math.sin(t * 1.2))
                arp_r = arp_base * (0.3 + 0.4 * math.cos(t * 1.2))

                # -------------------------------------------------------------
                # MASTER MIX (Balanced at punchy demo level)
                # -------------------------------------------------------------
                # Mono drum & bass core + wide stereo synths
                mono_core = (kick_sig + snare_sig + bass_sig) * 0.70
                out_l = (mono_core + hat_sig * 0.6 + chord_sig_l + arp_l) * envelope
                out_r = (mono_core + hat_sig * 0.6 + chord_sig_r + arp_r) * envelope

                # Soft limiter / clip guard
                out_l = math.tanh(out_l * 1.3) * 0.85
                out_r = math.tanh(out_r * 1.3) * 0.85

                sample_l = int(max(-32767, min(32767, out_l * 32767)))
                sample_r = int(max(-32767, min(32767, out_r * 32767)))

                frames += struct.pack("<hh", sample_l, sample_r)

            wf.writeframes(frames)

    size_mb = wav_path.stat().st_size / (1024 * 1024)
    print(f"Generated {wav_path} successfully ({size_mb:.2f} MB, {DURATION_S}s @ 116 BPM)")


if __name__ == "__main__":
    generate_music()
