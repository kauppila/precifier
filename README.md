# Precifier - J-Bass to P-Bass IR Generator

This Python script generates minimum-phase Impulse Responses (IRs) that transform the tone of a Fender Jazz Bass (Neck) pickup into a Fender Precision Bass pickup. (Yes, it is essentially a highly accurate, glorified EQ)

By modeling the physical sensing area and electrical characteristics of both pickups, the tool creates `.wav` files compatible with any standard IR loader (Helix, Quad Cortex, Kemper, or DAW plugins).

![alt text](jazz-to-precision-illustration.png)

### Download IRs

If you don't want to mess with Python or can't run the script yourself, you can just download the pre-generated IRs below. 

Select the format that matches your hardware or DAW session. If you are unsure, **48k / 24-bit** is the most common standard for modern modelers like the Helix and Quad Cortex.

| Sample Rate | 16-bit | 24-bit | 32-bit float |
| :--- | :--- | :--- | :--- |
| **44.1 kHz** | [Download](./JtoP_44k_16bit.wav?raw=true) | [Download](./JtoP_44k_24bit.wav?raw=true) | [Download](./JtoP_44k_32float.wav?raw=true) |
| **48 kHz** | [Download](./JtoP_48k_16bit.wav?raw=true) | [Download](./JtoP_48k_24bit.wav?raw=true) | [Download](./JtoP_48k_32float.wav?raw=true) |
| **88.2 kHz** | [Download](./JtoP_88k_16bit.wav?raw=true) | [Download](./JtoP_88k_24bit.wav?raw=true) | [Download](./JtoP_88k_32float.wav?raw=true) |
| **96 kHz** | [Download](./JtoP_96k_16bit.wav?raw=true) | [Download](./JtoP_96k_24bit.wav?raw=true) | [Download](./JtoP_96k_32float.wav?raw=true) |

## How It Works

The script calculates the transfer function between the two pickups by modeling two primary domains:

* **Aperture Width (Comb Filtering):** Models the physical width of the magnetic field. The wider P-Bass coil naturally filters higher frequencies compared to the narrower J-Bass coil. This is simulated using a sinc function with magnetic fringe field compensation.
* **RLC Electronics (Loaded Resonance):** Pickups act as second-order low-pass filters. The script models the **Resonant Frequency ($f_r$)** and **Quality Factor ($Q$)** of the pickups as they behave under a standard load (250k pots and a guitar cable).

The generator uses **Wiener Deconvolution** to calculate the spectral ratio between the target and the source, then converts the result into a **Minimum-Phase** response. This ensures the resulting IR has zero latency and introduces no pre-ringing artifacts.

### Frequency Response
The following plot shows the frequency response of the generated IR using default settings.

![Frequency Response Curve](ir_analysis.png)

### Audio Examples

**Source (Jazz Bass Neck Pickup):**
[`real_j_bass.wav`](real_j_bass.wav)

**Target (Converted P-Bass Tone):**
[`convolved_p_bass.wav`](convolved_p_bass.wav)

## Usage

Simply run the script from your terminal:

```bash
uv run generate_irs.py
```

The script will automatically generate impulse responses in the current working directory, peak-normalized to -0.1 dB to prevent clipping.

### Option 2: Using pip
If you do not have uv:

```bash
pip install numpy scipy soundfile matplotlib
```

```bash
python generate_irs.py
```

### Output Formats
To ensure maximum compatibility with both hardware pedals and software plugins, the script exports IRs across multiple industry-standard formats:
* Sample Rates: 44.1kHz, 48kHz, 88.2kHz, 96kHz
* Bit Depths: 16-bit integer, 24-bit, and 32-bit float.
* IR Length: 2048 taps

### Demo Script

To hear the transformation and visualize the math, run the included `demo_ir.py` script. Note: **You must run the main generator script first** to ensure the IR files are available.

* **Audio Output:** Convolves the dry J-Bass clip to generate a transformed `convolved_p_bass.wav`.
* **Visual Output:** Generates `ir_analysis.png` showing both the minimum-phase IR and the frequency response.

```bash
python demo_ir.py
```

## Customizing the Tone

You can easily tweak the source and target pickup characteristics by modifying the PICKUPS dictionary in the script. The default values are tuned for a standard loaded bass circuit:

| Parameter | Fender Jazz Bass (Neck) | Fender Precision Bass | Description |
| :--- | :--- | :--- | :--- |
| w | 0.75 | 1.00 | Aperture Width (inches). Larger values equal more high-end roll-off. |
| gain | 1.0 | 1.4 | Relative Output. P-pickups generally have higher output. |
| f_r | 3000.0 | 2000.0 | Resonant Frequency (Hz). The electrical peak. P-basses sit lower in the high-mids. |
| Q | 1.4 | 1.6 | Quality Factor. How sharp the resonant peak is. |

## License
MIT License. Feel free to use, modify, and distribute!