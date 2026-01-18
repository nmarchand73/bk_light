"""2D FFT VU Meter - Audio-reactive frequency visualization for BK-Light LED panels."""

import argparse
import asyncio
import sys
import threading
import time
from dataclasses import replace
from pathlib import Path

from PIL import Image

project_root = Path(__file__).resolve().parents[1]
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

# Note: numpy and sounddevice are imported lazily to avoid COM conflicts with bleak on Windows

from bk_light.config import load_config
from bk_light.panel_manager import PanelManager


class AudioAnalyzer:
    """Real-time audio capture and FFT analysis.

    Imports sounddevice lazily in a separate thread to avoid COM threading
    conflicts with bleak on Windows.
    """

    def __init__(
        self,
        sample_rate: int = 44100,
        chunk_size: int = 1024,
        num_bands: int = 32,
        device: int | None = None,
    ):
        import numpy as np

        self.np = np
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size
        self.num_bands = num_bands
        self.device = device

        # Audio buffer (thread-safe access via lock)
        self.buffer = np.zeros(chunk_size, dtype=np.float32)
        self.lock = threading.Lock()

        # Frequency band edges (logarithmic scale for musical perception)
        self.band_edges = self._compute_band_edges()

        # Smoothing state
        self.smoothed = np.zeros(num_bands, dtype=np.float32)
        self.peaks = np.zeros(num_bands, dtype=np.float32)
        self.peak_decay = np.zeros(num_bands, dtype=np.float32)

        # Audio thread
        self._running = False
        self._thread = None
        self._ready = threading.Event()

    def _compute_band_edges(self) -> list[tuple[int, int]]:
        """Compute logarithmic frequency band edges."""
        np = self.np
        min_freq = 60
        max_freq = min(16000, self.sample_rate // 2)

        # Logarithmic spacing
        log_min = np.log10(min_freq)
        log_max = np.log10(max_freq)
        freqs = np.logspace(log_min, log_max, self.num_bands + 1)

        # Convert to FFT bin indices
        bin_width = self.sample_rate / self.chunk_size
        edges = []
        for i in range(self.num_bands):
            low_bin = max(1, int(freqs[i] / bin_width))
            high_bin = max(low_bin + 1, int(freqs[i + 1] / bin_width))
            edges.append((low_bin, high_bin))
        return edges

    def _audio_thread(self):
        """Audio capture thread - imports sounddevice here to avoid COM conflicts."""
        # Import sounddevice only in this thread
        import sounddevice as sd
        np = self.np

        def callback(indata, frames, time_info, status):
            # Take mono mix
            if indata.shape[1] > 1:
                mono = np.mean(indata, axis=1)
            else:
                mono = indata[:, 0]
            with self.lock:
                self.buffer = mono.astype(np.float32)

        try:
            with sd.InputStream(
                samplerate=self.sample_rate,
                channels=1,
                dtype=np.float32,
                blocksize=self.chunk_size,
                callback=callback,
                device=self.device,
            ):
                self._ready.set()
                while self._running:
                    sd.sleep(100)
        except Exception as e:
            print(f"Audio error: {e}")
            self._ready.set()

    def start(self):
        """Start audio capture in background thread."""
        self._running = True
        self._thread = threading.Thread(target=self._audio_thread, daemon=True)
        self._thread.start()
        # Wait for audio stream to be ready
        self._ready.wait(timeout=2.0)

    def stop(self):
        """Stop audio capture."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=1.0)
            self._thread = None

    def get_spectrum(self, smoothing: float = 0.7, peak_decay_rate: float = 0.05):
        """Get current frequency spectrum with smoothing and peak hold."""
        np = self.np

        # Get buffer with thread safety
        with self.lock:
            buffer = self.buffer.copy()

        # Apply window function
        window = np.hanning(len(buffer))
        windowed = buffer * window

        # FFT
        fft = np.abs(np.fft.rfft(windowed))

        # Compute band magnitudes
        magnitudes = np.zeros(self.num_bands, dtype=np.float32)
        for i, (low, high) in enumerate(self.band_edges):
            if high <= len(fft):
                magnitudes[i] = np.mean(fft[low:high])

        # Normalize and convert to dB-like scale
        magnitudes = np.clip(magnitudes / 50, 0, 1)
        magnitudes = np.power(magnitudes, 0.6)  # Compress dynamic range

        # Apply smoothing (fast attack, slow decay)
        for i in range(self.num_bands):
            if magnitudes[i] > self.smoothed[i]:
                self.smoothed[i] = magnitudes[i]
            else:
                self.smoothed[i] = smoothing * self.smoothed[i] + (1 - smoothing) * magnitudes[i]

        # Peak hold with decay
        for i in range(self.num_bands):
            if self.smoothed[i] >= self.peaks[i]:
                self.peaks[i] = self.smoothed[i]
                self.peak_decay[i] = 0
            else:
                self.peak_decay[i] += peak_decay_rate
                self.peaks[i] = max(0, self.peaks[i] - self.peak_decay[i])

        return self.smoothed.copy(), self.peaks.copy()


def get_bar_color(height: int, max_height: int) -> tuple[int, int, int]:
    """Get gradient color based on bar height (green -> yellow -> red)."""
    ratio = height / max_height if max_height > 0 else 0
    if ratio < 0.5:
        r = int(255 * (ratio * 2))
        g = 255
    else:
        r = 255
        g = int(255 * (1 - (ratio - 0.5) * 2))
    return (r, g, 0)


def render_vu_frame(width: int, height: int, spectrum, peaks) -> Image.Image:
    """Render VU meter frame."""
    image = Image.new("RGB", (width, height), (0, 0, 0))
    pixels = image.load()

    num_bands = len(spectrum)
    bar_width = max(1, width // num_bands)

    for i, (level, peak) in enumerate(zip(spectrum, peaks)):
        x_start = i * bar_width
        bar_height = int(level * height)
        peak_y = int(peak * height)

        for x in range(x_start, min(x_start + bar_width, width)):
            for y in range(height - bar_height, height):
                color = get_bar_color(height - y, height)
                pixels[x, y] = color

        if peak_y > 0:
            peak_row = height - peak_y
            if 0 <= peak_row < height:
                for x in range(x_start, min(x_start + bar_width, width)):
                    pixels[x, peak_row] = (255, 255, 255)

    return image


def render_mirror_frame(width: int, height: int, spectrum, peaks) -> Image.Image:
    """Render mirrored VU meter (bars from center)."""
    image = Image.new("RGB", (width, height), (0, 0, 0))
    pixels = image.load()

    num_bands = len(spectrum)
    bar_width = max(1, width // num_bands)
    center_y = height // 2

    for i, (level, peak) in enumerate(zip(spectrum, peaks)):
        x_start = i * bar_width
        bar_height = int(level * center_y)
        peak_offset = int(peak * center_y)

        for x in range(x_start, min(x_start + bar_width, width)):
            for dy in range(bar_height):
                color = get_bar_color(dy, center_y)
                if center_y - dy - 1 >= 0:
                    pixels[x, center_y - dy - 1] = color
                if center_y + dy < height:
                    pixels[x, center_y + dy] = color

        if peak_offset > 0:
            for x in range(x_start, min(x_start + bar_width, width)):
                if center_y - peak_offset >= 0:
                    pixels[x, center_y - peak_offset] = (255, 255, 255)
                if center_y + peak_offset - 1 < height:
                    pixels[x, center_y + peak_offset - 1] = (255, 255, 255)

    return image


def render_circular_frame(width: int, height: int, spectrum, peaks) -> Image.Image:
    """Render circular VU meter."""
    import math

    image = Image.new("RGB", (width, height), (0, 0, 0))
    pixels = image.load()

    cx, cy = width / 2, height / 2
    inner_radius = min(width, height) * 0.15
    max_radius = min(width, height) * 0.45

    num_bands = len(spectrum)

    for i, (level, peak) in enumerate(zip(spectrum, peaks)):
        angle_start = (i / num_bands) * 2 * math.pi - math.pi / 2
        angle_end = ((i + 1) / num_bands) * 2 * math.pi - math.pi / 2
        bar_length = level * (max_radius - inner_radius)

        for r in range(int(inner_radius), int(inner_radius + bar_length)):
            color = get_bar_color(r - int(inner_radius), int(max_radius - inner_radius))
            for a in range(10):
                angle = angle_start + (angle_end - angle_start) * a / 10
                x = int(cx + r * math.cos(angle))
                y = int(cy + r * math.sin(angle))
                if 0 <= x < width and 0 <= y < height:
                    pixels[x, y] = color

        peak_r = int(inner_radius + peak * (max_radius - inner_radius))
        for a in range(10):
            angle = angle_start + (angle_end - angle_start) * a / 10
            x = int(cx + peak_r * math.cos(angle))
            y = int(cy + peak_r * math.sin(angle))
            if 0 <= x < width and 0 <= y < height:
                pixels[x, y] = (255, 255, 255)

    return image


def list_audio_devices():
    """List available audio input devices."""
    import sounddevice as sd
    print("\nAvailable audio input devices:")
    devices = sd.query_devices()
    for i, dev in enumerate(devices):
        if dev["max_input_channels"] > 0:
            marker = "*" if i == sd.default.device[0] else " "
            print(f"  {marker}[{i}] {dev['name']}")
    print("\n  * = default device")


async def run_vu_meter(
    config,
    style: str = "bars",
    interval: float = 0.03,
    smoothing: float = 0.7,
    device: int | None = None,
) -> None:
    """Run the VU meter animation loop."""
    # Connect to BLE first, before starting audio
    async with PanelManager(config) as manager:
        width, height = manager.canvas_size
        num_bands = width

        print(f"FFT VU Meter on {width}x{height} canvas ({style} style)")
        print("Starting audio capture...")

        # Now start audio (after BLE is connected)
        analyzer = AudioAnalyzer(num_bands=num_bands, device=device)
        analyzer.start()

        print("Press Ctrl+C to stop")

        render_fn = {
            "bars": render_vu_frame,
            "mirror": render_mirror_frame,
            "circular": render_circular_frame,
        }.get(style, render_vu_frame)

        try:
            while True:
                spectrum, peaks = analyzer.get_spectrum(smoothing=smoothing)
                frame = render_fn(width, height, spectrum, peaks)
                await manager.send_image(frame, delay=0.05)
                await asyncio.sleep(interval)

        except asyncio.CancelledError:
            raise
        finally:
            analyzer.stop()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="FFT VU Meter for BK-Light LED panels")
    parser.add_argument("--config", type=Path, help="Path to config file")
    parser.add_argument("--address", help="Override device address")
    parser.add_argument(
        "--style",
        choices=["bars", "mirror", "circular"],
        default="bars",
        help="Visualization style (default: bars)",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=0.03,
        help="Frame interval in seconds (default: 0.03)",
    )
    parser.add_argument(
        "--smoothing",
        type=float,
        default=0.7,
        help="Smoothing factor 0-1 (default: 0.7)",
    )
    parser.add_argument(
        "--device",
        type=int,
        help="Audio input device index",
    )
    parser.add_argument(
        "--list-devices",
        action="store_true",
        help="List available audio devices and exit",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    if args.list_devices:
        list_audio_devices()
        sys.exit(0)

    # Check numpy is available
    try:
        import numpy
    except ImportError:
        print("Error: numpy is required. Install with: pip install numpy")
        sys.exit(1)

    config = load_config(args.config)
    if args.address:
        config = replace(config, device=replace(config.device, address=args.address))

    try:
        asyncio.run(run_vu_meter(
            config,
            style=args.style,
            interval=args.interval,
            smoothing=args.smoothing,
            device=args.device,
        ))
    except KeyboardInterrupt:
        print("\nStopped.")
