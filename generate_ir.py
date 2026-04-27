import os
import argparse
import numpy as np
import soundfile as sf
from scipy.signal import firwin2, minimum_phase

# --- Preamp Parameters ---
PREAMPS = {
    # True StingRay Preamp Model (LM4250 Circuit Match)
    # Accurately mapping the SPICE response of the 2-band EQ's interactive flaw
    "StingRay_2Band": lambda freqs: (
        calculate_shelf_filter(freqs, fc=80.0, gain_db=12.0, is_lowshelf=True) * # Bass Boost
        calculate_shelf_filter(freqs, fc=4000.0, gain_db=8.0, is_lowshelf=False) * # Treble Boost
        calculate_peak_filter(freqs, fc=500.0, gain_db=-6.0, Q=0.5)                # Interactive Mid-Scoop
    )
}

# --- Pickup Parameters ---
PICKUPS = {
    # Fender Jazz Bass (Neck): Typically brighter, lower output, with a narrower magnetic field.
    "J_Bass_Neck": {
        "w": 0.75,      # Aperture Width (inches): The physical width of the magnetic sensing area. 
                        # Smaller 'w' captures more high-frequency detail (less low-pass filtering).
        "d": 0.0,       # Coil Distance (inches): 0.0 for single coil (no spatial comb filtering).
        "gain": 1.0,    # Relative Output: Baseline volume for the instrument.
        "f_r": 3000.0,  # Resonant Frequency (Hz): The electrical peak caused by coil inductance 
                        # and cable capacitance. Higher f_r = "brighter" sound.
        "Q": 1.4,       # Quality Factor (Resonance Sharpness): How pronounced the peak at f_r is. 
        "pos": 5.5      # Position (inches): Approximate distance from the bridge saddles.
    },
    
    # Fender Precision Bass: Beefier, higher output, with a wider magnetic sensing area.
    "P_Bass": {
        "w": 1.00,      # Aperture Width: Wider coils naturally filter out some ultra-highs, 
                        # contributing to a "thumpier" tone.
        "d": 0.0,       # Coil Distance: 0.0 because an individual string only crosses one coil half.
        "gain": 1.4,    # Relative Output: P-pickups generally have more winds and hit amps harder.
        "f_r": 2000.0,  # Resonant Frequency: P-bass resonance is typically much lower, 
                        # emphasizing the low-mids rather than the crisp highs.
        "Q": 1.6,       # Quality Factor: A smoother, broader resonance for a more "rounded" feel.
        "pos": 4.5      # Position: Sits in the classic mid-body sweet spot.
    },
    
    # Fender Jazz Bass (Bridge): Tighter, punchier, and brighter than the neck version.
    "J_Bass_Bridge": {
        "w": 0.75,      # Aperture Width: Matches the neck pickup for that focused J-Bass bite.
        "d": 0.0,       # Coil Distance: Single coil.
        "gain": 1.05,   # Relative Output: Slightly overwound to compensate for string energy loss near the bridge.
        "f_r": 3200.0,  # Resonant Frequency: Very high, placing the peak right in the "growl" frequencies.
        "Q": 1.5,       # Quality Factor: Noticeable but musical midrange spike.
        "pos": 1.6      # Position: Very close to the bridge, creating a tight fundamental.
    },
    
    # Music Man StingRay (Sweet Spot): Massive, active, parallel-wired humbucker.
    "MusicMan": {
        "w": 1.50,      # Aperture Width: Massive magnetic window captures more string length.
        "d": 0.75,      # Coil Distance: Distance between coils creates a spatial comb-filter notch.
        "gain": 2.2,    # Relative Output: Highly responsive output hitting the active preamp.
        "f_r": 3800.0,  # Resonant Frequency: Parallel wiring keeps this surprisingly high ("sizzle").
        "Q": 1.2,       # Quality Factor: Smoother, broader peak typical of humbuckers.
        "pos": 2.6,     # Position: The legendary "sweet spot", slightly further from the bridge than a J-Bass.
        "preamp": "StingRay_2Band" # Points directly to the PREAMPS dictionary
    }
}

# --- IR File Formats ---
SAMPLE_RATES = [44100, 48000, 88200, 96000]
# Mapping bit depths to Scipy/WAV subtypes
BIT_DEPTHS = {
    "16bit": {"subtype": 'PCM_16'},
    "24bit": {"subtype": 'PCM_24'}, 
    "32float": {"subtype": 'FLOAT'}
}
NUM_TAPS = 2048

def calculate_shelf_filter(freqs, fc, gain_db, is_lowshelf=True):
    """Calculates the magnitude response of a 1st-order analog shelving filter."""
    G = 10.0 ** (gain_db / 20.0)
    f = np.where(freqs == 0, 1e-9, freqs) # Prevent division by zero
    
    if is_lowshelf:
        return np.sqrt((G**2 + (f / fc)**2) / (1.0 + (f / fc)**2))
    else:
        return np.sqrt((1.0 + G**2 * (f / fc)**2) / (1.0 + (f / fc)**2))

def calculate_peak_filter(freqs, fc, gain_db, Q):
    """Calculates the magnitude response of an analog parametric peaking/notch filter."""
    A = 10.0 ** (gain_db / 40.0)
    f = np.where(freqs == 0, 1e-9, freqs)
    x = f / fc
    
    num = (1.0 - x**2)**2 + (A * x / Q)**2
    den = (1.0 - x**2)**2 + (x / (A * Q))**2
    return np.sqrt(num / den)

def calculate_position_tilt(freqs, source_pos, target_pos):
    """
    Applies a broad spectral tilt to simulate moving the pickup closer to or further from the bridge.
    Moving away from the bridge (positive delta) boosts fundamentals and cuts harsh highs.
    """
    delta_inches = target_pos - source_pos
    tilt_db = delta_inches * 1.5  # 1.5 dB shift per inch of movement
    
    low_tilt = calculate_shelf_filter(freqs, fc=300.0, gain_db=tilt_db, is_lowshelf=True)
    high_tilt = calculate_shelf_filter(freqs, fc=2000.0, gain_db=-tilt_db, is_lowshelf=False)
    
    return low_tilt * high_tilt

def calculate_pickup_response(freqs, w_inches, d_inches, v_speed, f_r, Q):
    """Calculates the static frequency response (Aperture + Dual Coil + Electronics)."""
    w_m = w_inches * 0.0254
    d_m = d_inches * 0.0254
    f = np.where(freqs == 0, 1e-9, freqs)

    # 1. Aperture effect (Width of the magnetic window acting as a slight low-pass)
    H_width = np.abs(np.sinc(f * w_m / v_speed)) + 0.1 
    
    # 2. Dual-coil Comb Filtering (Phase cancellation due to spatial separation)
    H_comb = np.abs(np.cos(np.pi * f * d_m / v_speed)) + 0.05
    
    # 3. RLC Electronics (Electrical resonance under load)
    H_elec = 1.0 / np.sqrt((1.0 - (f / f_r)**2)**2 + (1.0 / Q)**2 * (f / f_r)**2)
    
    return H_width * H_comb * H_elec

def generate_ir(fs, source_key, target_key, v):
    nyq = fs / 2.0
    freqs = np.linspace(0, nyq, NUM_TAPS)
    source_p, target_p = PICKUPS[source_key], PICKUPS[target_key]
    
    resp_s = calculate_pickup_response(freqs, source_p["w"], source_p["d"], v, source_p["f_r"], source_p["Q"])
    resp_t = calculate_pickup_response(freqs, target_p["w"], target_p["d"], v, target_p["f_r"], target_p["Q"])
    
    # --- Regularized Transfer Function (Wiener Deconvolution) ---
    # Prevents instability/ringing at magnetic aperture nulls by adding 
    # a noise floor (epsilon) to the source spectrum during inversion.
    epsilon = 0.001 * np.max(resp_s)**2 
    resp_rel = (resp_t * resp_s) / (resp_s**2 + epsilon)
    
    # --- POSITION COMPENSATION (Spectral Tilt) ---
    pos_tilt = calculate_position_tilt(freqs, source_p["pos"], target_p["pos"])
    resp_rel *= pos_tilt
    
    # --- GENERIC PREAMP / EQ MODELING ---
    # Dynamically apply active EQ stages if the target pickup points to a valid preamp
    if "preamp" in target_p and target_p["preamp"] in PREAMPS:
        preamp_func = PREAMPS[target_p["preamp"]]
        resp_rel *= preamp_func(freqs)

    # Normalize for filter generation and force Nyquist to 0.0 (Type II FIR constraint)
    resp_rel_norm = resp_rel / np.max(resp_rel)
    resp_rel_norm[-1] = 0.0 

    # Generate the Minimum Phase Impulse Response
    taps = minimum_phase(firwin2(NUM_TAPS, freqs / nyq, resp_rel_norm))
    
    # Peak normalization to -0.1 dB to avoid any clipping on import
    return taps / np.max(np.abs(taps)) * 0.99

def process_conversion(source, target, scale_override=None, freq_override=None):
    # --- Physical String Parameters ---
    scale_inches = scale_override if scale_override else 34.0
    L = scale_inches * 0.0254     # Scale length in meters 
    
    f0 = freq_override if freq_override else 41.20 # E1 string open
                                  # Pickup aperture nulls depend on the string's wave speed (v). Because a static IR 
                                  # cannot dynamically adapt to the varying wave speeds of different strings, using 
                                  # the E string provides a median baseline. This balances the simulated comb filtering 
                                  # across the fretboard.
    v = 2 * L * f0                # Wave speed (used for aperture and comb filter calculations)

    # Calculate decibel offset for the user's reference since IRs are peak-normalized
    gain_db = 20 * np.log10(PICKUPS[target]["gain"] / PICKUPS[source]["gain"])

    print(f"  [{source} -> {target}] | Offset: {gain_db:+.1f} dB")

    for fs in SAMPLE_RATES:
        ir_data = generate_ir(fs, source, target, v)
        for name, specs in BIT_DEPTHS.items():
            filename = f"{source}_to_{target}_{int(fs/1000)}k_{name}.wav"
            # Write directly to the current working directory
            sf.write(filename, ir_data, fs, subtype=specs['subtype'])

def main():
    parser = argparse.ArgumentParser(description="Generate Pickup Match IRs.")
    parser.add_argument("--source", type=str, choices=PICKUPS.keys())
    parser.add_argument("--target", type=str, choices=PICKUPS.keys())
    args = parser.parse_args()

    # If no arguments are passed, fall back to the default curated list
    if not args.source or not args.target:
        print(f"Generating Default Conversions in {os.getcwd()}...\n")
        
        default_conversions = [
            ("J_Bass_Neck", "P_Bass"),
            ("J_Bass_Bridge", "MusicMan")
        ]

        for src, tgt in default_conversions:
            process_conversion(src, tgt)
    else:
        process_conversion(args.source, args.target)
        
    print("\nDone! All files generated in the working directory.")

if __name__ == "__main__":
    main()