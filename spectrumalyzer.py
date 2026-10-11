#!/usr/bin/env python3
import os, sys, json, math, struct, subprocess
from datetime import datetime
import argparse

def parse_args():
    parser = argparse.ArgumentParser(prog='spectrumalyzer',
        description='Audio beat analysis tool for motion graphics')
    parser.add_argument('audio_file', help='Path to audio file')
    parser.add_argument('--output', '-o', default='beats.json',
                        help='Output JSON file path')
    parser.add_argument('--format', '-f', choices=['json', 'remotion'],
                        default='json', help='Output format')
    parser.add_argument('--threshold', '-t', type=float, default=0.15,
                        help='Beat detection threshold (0.0-1.0, default: 0.15)')
    parser.add_argument('--fft-size', type=int, default=1024,
                        help='FFT size for spectrum (256-4096)')
    return parser.parse_args()

def get_audio_duration(filepath):
    try:
        result = subprocess.run(
            ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
             '-of', 'default=noprint_wrappers=1:nokey=1', filepath],
            capture_output=True, text=True)
        return float(result.stdout.strip())
    except Exception as e:
        print(f'Error getting duration: {e}', file=sys.stderr)
        return 0

def extract_pcm(filepath, duration):
    try:
        result = subprocess.run(
            ['ffmpeg', '-i', filepath, '-vn', '-acodec', 'pcm_s16le',
             '-ar', '44100', '-ac', '1', '-f', 's16le',
             '-ss', '0', '-t', str(duration or 999999), 'pipe:1'],
            capture_output=True)
        if len(result.stdout) == 0:
            print('Warning: No audio data extracted', file=sys.stderr)
            return []
        samples = struct.unpack(f'<{len(result.stdout)//2}h', result.stdout)
        return [s / 32768.0 for s in samples]
    except Exception as e:
        print(f'Error extracting PCM: {e}', file=sys.stderr)
        return []

def fft_transform(signal, inverse=False):
    n = len(signal)
    if n <= 1:
        return signal[:]
    output = [0] * n
    bits = n.bit_length() - 1
    for i in range(n):
        j = 0
        for k in range(bits):
            if i & (1 << k):
                j |= (1 << (bits - 1 - k))
        output[j] = signal[i]
    size = 2
    while size < n:
        step = size * 2
        angle = 2 * math.pi / step * (-1 if inverse else 1)
        w_real = math.cos(angle)
        w_imag = math.sin(angle)
        for i in range(0, n, step):
            for j in range(size):
                k = i + j
                m = k + size
                t_real = output[m] * w_real - output[m + 1] * w_imag
                t_imag = output[m] * w_imag + output[m + 1] * w_real
                output[k] = output[k] - t_real
                output[k + 1] = output[k + 1] - t_imag
                output[m] = output[k] + t_real
                output[m + 1] = output[k + 1] + t_imag
        size = step
    if inverse:
        for i in range(n):
            output[i] /= n
    return output

def detect_beats(audio, sample_rate=44100, threshold=0.3, min_interval=0.5):
    hop_size = 512
    num_frames = len(audio) // hop_size
    energies = [0] * num_frames
    for i in range(num_frames):
        start = i * hop_size
        end = min(start + hop_size, len(audio))
        energy = 0
        for j in range(start, end):
            energy += audio[j] * audio[j]
        energies[i] = math.sqrt(energy / max(1, end - start))
    onsets = [0] * (num_frames - 1)
    for i in range(1, num_frames):
        diff = energies[i] - energies[i - 1]
        onsets[i - 1] = max(0, diff)
    beat_times = []
    last_beat_idx = -float('inf')
    min_frames = int(min_interval * sample_rate / hop_size)
    for i in range(len(onsets)):
        if onsets[i] > threshold and (i - last_beat_idx) > min_frames:
            beat_times.append(i * hop_size / sample_rate)
            last_beat_idx = i
    bpm = 0
    if len(beat_times) >= 2:
        intervals = []
        for i in range(1, len(beat_times)):
            interval = beat_times[i] - beat_times[i - 1]
            if 0 < interval < 10.0:
                intervals.append(interval)
        if intervals:
            sorted_intervals = sorted(intervals)
            n = len(sorted_intervals)
            mid = n // 2
            median_interval = sorted_intervals[mid] if n % 2 == 1 else (sorted_intervals[mid - 1] + sorted_intervals[mid]) / 2
            if median_interval > 0:
                bpm = round(60 / median_interval)
                bpm = max(20, min(220, bpm))
    return beat_times, bpm

def generate_spectrum(audio, sample_rate=44100, fft_size=1024):
    num_bins = fft_size // 2
    spectrum = []
    for i in range(num_bins):
        start = int((i / num_bins) * len(audio))
        end = int(((i + 1) / num_bins) * len(audio))
        energy = 0
        for j in range(start, min(end, len(audio))):
            energy += audio[j] * audio[j]
        energy = math.sqrt(energy / max(1, end - start)) * 100
        spectrum.append(energy)
    freq_data = []
    for i, e in enumerate(spectrum):
        freq = (i * sample_rate) / fft_size
        freq_data.append({'frequency': freq, 'energy': e})
    return freq_data

def main():
    args = parse_args()
    if not os.path.exists(args.audio_file):
        print(f'Error: File not found: {args.audio_file}', file=sys.stderr)
        sys.exit(1)
    print('=== spectrumalyzer ===')
    print(f'Input: {args.audio_file}')
    duration = get_audio_duration(args.audio_file)
    print(f'Duration: {duration:.2f}s')
    audio = extract_pcm(args.audio_file, duration)
    print(f'Samples: {len(audio)}')
    if len(audio) == 0:
        print('Error: No audio data could be extracted', file=sys.stderr)
        sys.exit(1)
    threshold = max(0.0, min(1.0, args.threshold))
    min_interval = max(0.1, 2.0)
    beat_times, bpm = detect_beats(audio, 44100, threshold, min_interval)
    print(f'Beats: {len(beat_times)}')
    print(f'BPM: {bpm}')
    fft_size = max(256, min(4096, args.fft_size))
    spectrum = generate_spectrum(audio, 44100, fft_size)
    beat_times_rounded = [round(t, 4) for t in beat_times]
    spectrum_128 = spectrum[:128]
    output = {
        'bpm': bpm,
        'duration': duration,
        'sampleRate': 44100,
        'beatCount': len(beat_times),
        'beats': beat_times_rounded,
        'beatTimes': beat_times_rounded,
        'spectrum': [{'frequency': round(s['frequency'], 1), 'energy': round(s['energy'], 2)} for s in spectrum_128],
        'metadata': {'version': '1.0.0', 'created': datetime.now().isoformat(), 'analyzer': 'spectrumalyzer'}
    }
    out_path = os.path.abspath(args.output)
    with open(out_path, 'w') as f:
        json.dump(output, f, indent=2)
    remotion_output = {'bpm': bpm, 'beatTimes': beat_times_rounded,
        'duration': duration, 'beatCount': len(beat_times),
        'measures': [], 'beatData': [{'time': t, 'index': i + 1} for i, t in enumerate(beat_times_rounded)]}
    rem_path = out_path.replace('.json', '.remotion.json')
    with open(rem_path, 'w') as f:
        json.dump(remotion_output, f, indent=2)
    print()
    print('=== Output Summary ===')
    print(f'Beats: {len(beat_times)}')
    print(f'BPM: {bpm}')
    print(f'Output: {out_path}')
    print()
    print('First 8 beats:')
    for i, t in enumerate(beat_times_rounded[:8]):
        print(f'  {i + 1}. {t:.2f}s')
    print()
    print(f'Remotion format: {rem_path}')
    print()
    print('=== spectrumalyzer complete ===')

if __name__ == '__main__':
    main()
