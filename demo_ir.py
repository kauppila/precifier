import os
import argparse
import shutil
import numpy as np
import matplotlib.pyplot as plt
from scipy.io import wavfile
from scipy.signal import convolve, freqz

# --- Configuration ---
INPUT_COPY = "original_input.wav"
OUTPUT_FILE = "convolved_output.wav"
PLOT_FILE = "ir_analysis.png"
HTML_FILE = "preview.html"

def load_wav_as_float(path):
    fs, data = wavfile.read(path)
    if len(data.shape) > 1:
        data = data[:, 0]
    if data.dtype == np.int16:
        data = data.astype(np.float64) / 32768.0
    elif data.dtype == np.int32:
        data = data.astype(np.float64) / 2147483648.0
    else:
        data = data.astype(np.float64)
    return fs, data

def generate_html(ir_name):
    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>Pickup Conversion Preview</title>
    <style>
        body {{ font-family: sans-serif; margin: 40px; background: #f4f4f9; color: #333; }}
        .container {{ max-width: 900px; margin: auto; background: white; padding: 20px; border-radius: 8px; shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        h1 {{ color: #2c3e50; border-bottom: 2px solid #eee; padding-bottom: 10px; }}
        .section {{ margin-bottom: 30px; }}
        audio {{ width: 100%; margin-top: 10px; }}
        img {{ max-width: 100%; height: auto; border: 1px solid #ddd; margin-top: 10px; }}
        .label {{ font-weight: bold; display: block; margin-top: 20px; color: #555; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>IR Preview: {ir_name}</h1>
        
        <div class="section">
            <h2>1. Audio Comparison</h2>
            <span class="label">Original Input Pickup:</span>
            <audio controls src="{INPUT_COPY}"></audio>
            
            <span class="label">Convolved Target Pickup:</span>
            <audio controls src="{OUTPUT_FILE}"></audio>
        </div>

        <div class="section">
            <h2>2. Frequency & Time Analysis</h2>
            <img src="{PLOT_FILE}" alt="IR Analysis Plot">
        </div>
    </div>
</body>
</html>
"""
    with open(HTML_FILE, "w") as f:
        f.write(html_content)

def main():
    parser = argparse.ArgumentParser(description="Apply an Impulse Response to an audio file and analyze it.")
    parser.add_argument("ir_file", type=str, help="Path to the IR .wav file.")
    parser.add_argument("input_file", type=str, help="Path to the dry/input audio .wav file.")
    args = parser.parse_args()

    if not os.path.exists(args.ir_file) or not os.path.exists(args.input_file):
        print("Error: Ensure both IR and input files exist.")
        return

    # Copy original input to generic name
    shutil.copy2(args.input_file, INPUT_COPY)

    fs_ir, ir_taps = load_wav_as_float(args.ir_file)
    fs_sig, signal = load_wav_as_float(args.input_file)

    if fs_ir != fs_sig:
        print(f"Warning: Sample rate mismatch! IR ({{fs_ir}}Hz) vs Signal ({{fs_sig}}Hz).")

    print(f"Processing conversion...")

    # 1. Convolution
    processed = convolve(signal, ir_taps, mode='same')
    peak = np.max(np.abs(processed))
    if peak > 0:
        processed = (processed / peak) * 0.89 
    wavfile.write(OUTPUT_FILE, fs_sig, (processed * 2147483647).astype(np.int32))

    # 2. Plotting
    w, h = freqz(ir_taps, 1.0, worN=8192, fs=fs_ir)
    mag_db_final = 20 * np.log10(np.abs(h) + 1e-12)
    mag_db_final -= np.max(mag_db_final)

    time_ms = (np.arange(len(ir_taps)) / fs_ir) * 1000.0

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 10))

    ax1.plot(time_ms, ir_taps, color='steelblue', lw=1.5)
    ax1.set_title('Impulse Response (Time Domain)')
    ax1.set_xlabel('Time (ms)')
    ax1.set_ylabel('Amplitude')
    ax1.grid(True, which="both", ls="-", alpha=0.3)

    ax2.semilogx(w, mag_db_final, color='firebrick', lw=2)
    ax2.set_ylim(-25, 5)
    ax2.set_xlim(20, 20000)
    ax2.set_title('Frequency Response (Normalized Transformation)')
    ax2.set_xlabel('Frequency (Hz)')
    ax2.set_ylabel('Relative Gain (dB)')
    ax2.grid(True, which="both", ls="-", alpha=0.3)
    ax2.axhline(0, color='black', lw=1)
    
    plt.tight_layout()
    plt.savefig(PLOT_FILE)

    # 3. HTML Generation
    generate_html(os.path.basename(args.ir_file))
    
    print("-" * 30)
    print(f"Done!")
    print(f"Audio Output: {OUTPUT_FILE}")
    print(f"Analysis Plot: {PLOT_FILE}")
    print(f"Web Dashboard: {HTML_FILE} (Open this in your browser)")
    print("-" * 30)

if __name__ == "__main__":
    main()