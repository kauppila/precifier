import os
import numpy as np
import matplotlib.pyplot as plt
from scipy.io import wavfile
from scipy.signal import convolve, freqz

# --- Configuration ---
IR_FILE = "JtoP_44k_16bit.wav" 
INPUT_FILE = "real_j_bass.wav"
OUTPUT_FILE = "convolved_p_bass.wav"

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

if not os.path.exists(IR_FILE) or not os.path.exists(INPUT_FILE):
    print(f"Error: Ensure files exist.")
else:
    fs_ir, ir_taps = load_wav_as_float(IR_FILE)
    fs_sig, signal = load_wav_as_float(INPUT_FILE)

    # 1. Convolution
    processed = convolve(signal, ir_taps, mode='same')
    peak = np.max(np.abs(processed))
    if peak > 0:
        processed = (processed / peak) * 0.89 
    wavfile.write(OUTPUT_FILE, fs_sig, (processed * 2147483647).astype(np.int32))

    # 2. Plotting (Time and Frequency Domains)
    w, h = freqz(ir_taps, 1.0, worN=8192, fs=fs_ir)
    
    # Raw magnitude from the file
    mag_db_raw = 20 * np.log10(np.abs(h) + 1e-12)
    
    # --- SCALE RESTORATION ---
    mag_db_scaled = mag_db_raw - np.max(mag_db_raw)
    
    # Add back the intended P-Bass vs J-Bass gain difference (1.4 / 1.0)
    gain_diff_db = 20 * np.log10(1.4 / 1.0)
    mag_db_final = mag_db_scaled + gain_diff_db

    # --- TIME VECTOR CALCULATION ---
    # Convert samples to milliseconds for the IR plot
    time_ms = (np.arange(len(ir_taps)) / fs_ir) * 1000.0

    # Create figure with 2 subplots vertically stacked
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 10))

    # --- Plot 1: Impulse Response (Time Domain) ---
    ax1.plot(time_ms, ir_taps, color='steelblue', lw=1.5)
    ax1.set_title('Impulse Response (Minimum-Phase)')
    ax1.set_xlabel('Time (ms)')
    ax1.set_ylabel('Amplitude')
    ax1.grid(True, which="both", ls="-", alpha=0.3)
    ax1.axhline(0, color='black', lw=1)

    # --- Plot 2: Frequency Response ---
    ax2.semilogx(w, mag_db_final, color='firebrick', lw=2)
    ax2.set_ylim(-15, 15) 
    ax2.set_xlim(20, 15000)
    ax2.set_title('Frequency Response (Transformation Curve)')
    ax2.set_xlabel('Frequency (Hz)')
    ax2.set_ylabel('Relative Gain (dB)')
    ax2.grid(True, which="both", ls="-", alpha=0.3)
    ax2.axhline(0, color='black', lw=1)
    
    plt.tight_layout()
    plt.savefig("ir_analysis.png")
    print(f"Plot saved as ir_analysis.png. Peak gain centered at {gain_diff_db:.2f} dB.")