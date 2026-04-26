import os
import numpy as np
import soundfile as sf
from scipy.signal import firwin2, minimum_phase

# --- Physical String Parameters ---
L = 34.0 * 0.0254       # Scale length in meters 
f0 = 41.20              # E1 string open
                        # Pickup aperture nulls depend on the string's wave speed (v). Because a static IR 
                        # cannot dynamically adapt to the varying wave speeds of different strings, using 
                        # the A string provides a median baseline. This balances the simulated comb filtering 
                        # across the fretboard, preventing higher strings from being overly filtered while 
                        # maintaining an authentic high-end roll-off.
v = 2 * L * f0          # Wave speed (used for aperture width calculation)

# --- Pickup Parameters ---
PICKUPS = {
    # Fender Jazz Bass (Neck): Typically brighter, lower output, with a narrower magnetic field.
    "J_Bass_Neck": {
        "w": 0.75,      # Aperture Width (inches): The physical width of the magnetic sensing area. 
                        # Smaller 'w' captures more high-frequency detail (less "comb filtering").
        "gain": 1.0,    # Relative Output: Baseline volume for the J-pickup.
        "f_r": 3000.0,  # Resonant Frequency (Hz): The electrical peak caused by coil inductance 
                        # and cable capacitance. Higher f_r = "brighter" sound.
        "Q": 1.4        # Quality Factor (Resonance Sharpness): How pronounced the peak at f_r is. 
                        # Higher Q = more "honk" or "quack" at the resonant frequency.
    },
    
    # Fender Precision Bass: Beefier, higher output, with a wider magnetic sensing area.
    "P_Bass": {
        "w": 1.00,      # Aperture Width (inches): Wider coils (like a P-bass) naturally 
                        # filter out some ultra-highs, contributing to a "thumpier" tone.
        "gain": 1.4,    # Relative Output: P-pickups generally have more winds and higher output.
        "f_r": 2000.0,  # Resonant Frequency (Hz): P-bass resonance is typically much lower, 
                        # emphasizing the low-mids rather than the crisp highs.
        "Q": 1.6        # Quality Factor: A smoother, broader resonance for a more "rounded" feel.
    } 
}

# --- IR File Formats ---
SAMPLE_RATES = [44100, 48000, 88200, 96000]
# Mapping bit depths to Scipy/WAV subtypes
BIT_DEPTHS = {
    "16bit": {"type": np.int16, "subtype": 'PCM_16'},
    "24bit": {"type": np.int32, "subtype": 'PCM_24'}, # Scipy uses int32 for 24-bit containers
    "32float": {"type": np.float32, "subtype": 'FLOAT'}
}
NUM_TAPS = 2048

def calculate_pickup_response(freqs, w_inches, v_speed, f_r, Q):
    """Calculates the static frequency response (Aperture + Electronics)."""
    w_m = w_inches * 0.0254
    f = np.where(freqs == 0, 1e-9, freqs)

    # 1. Aperture effect (Width of the magnetic window acting as a slight low-pass)
    # Instead of pure sinc, add a floor so it doesn't hit zero (simulating fringe fields)
    H_width = np.abs(np.sinc(f * w_m / v_speed)) + 0.1 

    # 2. RLC Electronics (Electrical resonance under load)
    H_elec = 1.0 / np.sqrt((1.0 - (f / f_r)**2)**2 + (1.0 / Q)**2 * (f / f_r)**2)
    
    return H_width * H_elec

def generate_ir(fs):
    nyq = fs / 2.0
    freqs = np.linspace(0, nyq, NUM_TAPS)
    
    resp_J = calculate_pickup_response(freqs, PICKUPS["J_Bass_Neck"]["w"], v, 
                                     PICKUPS["J_Bass_Neck"]["f_r"], PICKUPS["J_Bass_Neck"]["Q"])
    resp_P = calculate_pickup_response(freqs, PICKUPS["P_Bass"]["w"], v, 
                                     PICKUPS["P_Bass"]["f_r"], PICKUPS["P_Bass"]["Q"])
    
    # --- THE FIX: Restore Safe Relative Transfer Function (Wiener Deconvolution) ---
    # This prevents division-by-zero spikes at the pickup width null frequencies.
    epsilon = 0.05 * np.max(resp_J)**2 
    resp_rel = (resp_P * resp_J) / (resp_J**2 + epsilon)
    resp_rel *= (PICKUPS["P_Bass"]["gain"] / PICKUPS["J_Bass_Neck"]["gain"])
    
    # Normalize for filter generation and force Nyquist to 0.0 (Type II FIR constraint)
    resp_rel_norm = resp_rel / np.max(resp_rel)
    resp_rel_norm[-1] = 0.0 

    # Generate the Minimum Phase Impulse Response
    taps_rel_lin = firwin2(NUM_TAPS, freqs / nyq, resp_rel_norm)
    taps_rel = minimum_phase(taps_rel_lin)
    
    # Peak normalization to -0.1 dB to avoid any clipping on import
    taps_rel = taps_rel / np.max(np.abs(taps_rel)) * 0.99
    return taps_rel

print(f"Exporting IRs to {os.getcwd()}...")

for fs in SAMPLE_RATES:
    ir_data = generate_ir(fs)
    
    for name, specs in BIT_DEPTHS.items():
        filename = f"JtoP_{int(fs/1000)}k_{name}.wav"
        path = filename 
        
        # Format conversion (soundfile handles float-to-integer mapping internally via subtype)
        sf.write(path, ir_data, fs, subtype=specs['subtype'])
            
        print(f"  Created: {filename}")

print("\nDone! All files generated in the working directory.")