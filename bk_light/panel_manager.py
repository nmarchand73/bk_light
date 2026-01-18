from __future__ import annotations
import asyncio
from dataclasses import dataclass
from io import BytesIO
from typing import List, Optional, Union
from PIL import Image
from .config import AppConfig, PanelDescriptor
from .display_session import BleDisplaySession, adjust_image, build_frame


@dataclass
class PanelSession:
    descriptor: Optional[PanelDescriptor]
    session: BleDisplaySession


class PanelManager:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.sessions: List[PanelSession] = []
        self.multi_panel = bool(config.panels.items)
        self.tile_width = config.panels.tile_width
        self.tile_height = config.panels.tile_height
        self.columns = config.panels.columns if self.multi_panel else 1
        self.rows = config.panels.rows if self.multi_panel else 1

    @property
    def canvas_size(self) -> tuple[int, int]:
        return (self.columns * self.tile_width, self.rows * self.tile_height)

    async def __aenter__(self) -> "PanelManager":
        if self.multi_panel:
            await self._connect_panels()
        else:
            await self._connect_single()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        while self.sessions:
            descriptor_session = self.sessions.pop()
            try:
                await descriptor_session.session.__aexit__(exc_type, exc, tb)
            except Exception:
                pass

    async def _connect_single(self) -> None:
        address = self.config.device.address
        if not address:
            raise ValueError("No panel configured. Set device.address or define panels list in config.yaml.")
        session = BleDisplaySession(
            address=address,
            auto_reconnect=self.config.device.auto_reconnect,
            reconnect_delay=self.config.device.reconnect_delay,
            rotation=self.config.device.rotate,
            brightness=self.config.device.brightness,
            mtu=self.config.device.mtu,
            log_notifications=self.config.display.log_notifications,
            max_retries=self.config.display.max_retries,
            scan_timeout=self.config.device.scan_timeout,
        )
        await session.__aenter__()
        self.sessions.append(PanelSession(None, session))

    async def _connect_panels(self) -> None:
        tasks = []
        for descriptor in self.config.panels.items:
            rotation = descriptor.rotation if descriptor.rotation is not None else self.config.device.rotate
            brightness = descriptor.brightness if descriptor.brightness is not None else self.config.device.brightness
            session = BleDisplaySession(
                address=descriptor.address,
                auto_reconnect=self.config.device.auto_reconnect,
                reconnect_delay=self.config.device.reconnect_delay,
                rotation=rotation,
                brightness=brightness,
                mtu=self.config.device.mtu,
                log_notifications=self.config.display.log_notifications,
                max_retries=self.config.display.max_retries,
                scan_timeout=self.config.device.scan_timeout,
            )
            tasks.append(self._connect_panel(descriptor, session))
        await asyncio.gather(*tasks)

    async def _connect_panel(self, descriptor: PanelDescriptor, session: BleDisplaySession) -> None:
        await session.__aenter__()
        self.sessions.append(PanelSession(descriptor, session))

    async def send_image(self, image: Image.Image, delay: float = 0.2) -> None:
        if self.multi_panel:
            await self._send_multi(image, delay)
        else:
            buffer = BytesIO()
            image.save(buffer, format="PNG", optimize=False)
            await self.sessions[0].session.send_png(buffer.getvalue(), delay)

    async def _send_multi(self, image: Image.Image, delay: float) -> None:
        expected_width, expected_height = self.canvas_size
        if image.size != (expected_width, expected_height):
            image = image.resize((expected_width, expected_height))
        tasks = []
        for panel_session in self.sessions:
            descriptor = panel_session.descriptor
            if descriptor is None:
                continue
            left = descriptor.grid_x * self.tile_width
            top = descriptor.grid_y * self.tile_height
            right = left + self.tile_width
            bottom = top + self.tile_height
            region = image.crop((left, top, right, bottom))
            buffer = BytesIO()
            region.save(buffer, format="PNG", optimize=False)
            tasks.append(panel_session.session.send_png(buffer.getvalue(), delay))
        await asyncio.gather(*tasks)

    def prebuffer_image(self, image: Image.Image) -> Union[bytes, List[bytes]]:
        """Pre-convert a PIL Image to ready-to-send frame bytes.

        Returns a single bytes object for single-panel mode, or a list of bytes
        for multi-panel mode (one per panel in session order).
        """
        if self.multi_panel:
            return self._prebuffer_multi(image)
        else:
            png_bytes = self._compress_png(image)
            session = self.sessions[0].session
            processed = adjust_image(png_bytes, session.rotation, session.brightness)
            return build_frame(processed)

    def _compress_png(self, image: Image.Image) -> bytes:
        """Compress image to PNG with optimal settings for BLE transfer."""
        # Convert to RGB if needed (remove alpha for smaller size)
        if image.mode != "RGB":
            image = image.convert("RGB")

        # Reduce colors for smaller PNG (quantize to 64 colors)
        image = image.quantize(colors=64, method=Image.Quantize.FASTOCTREE).convert("RGB")

        buffer = BytesIO()
        image.save(buffer, format="PNG", optimize=True, compress_level=9)
        return buffer.getvalue()

    def _prebuffer_multi(self, image: Image.Image) -> List[bytes]:
        expected_width, expected_height = self.canvas_size
        if image.size != (expected_width, expected_height):
            image = image.resize((expected_width, expected_height))
        frames = []
        for panel_session in self.sessions:
            descriptor = panel_session.descriptor
            if descriptor is None:
                continue
            left = descriptor.grid_x * self.tile_width
            top = descriptor.grid_y * self.tile_height
            right = left + self.tile_width
            bottom = top + self.tile_height
            region = image.crop((left, top, right, bottom))
            png_bytes = self._compress_png(region)
            session = panel_session.session
            processed = adjust_image(png_bytes, session.rotation, session.brightness)
            frames.append(build_frame(processed))
        return frames

    def prebuffer_images(self, images: List[Image.Image]) -> List[Union[bytes, List[bytes]]]:
        """Pre-convert a list of PIL Images to ready-to-send frame bytes."""
        return [self.prebuffer_image(img) for img in images]

    async def send_prebuffered(self, frame_data: Union[bytes, List[bytes]], delay: float = 0.2) -> None:
        """Send pre-buffered frame data without any conversion."""
        if self.multi_panel:
            tasks = []
            for i, panel_session in enumerate(self.sessions):
                if panel_session.descriptor is None:
                    continue
                tasks.append(panel_session.session.send_frame(frame_data[i], delay))
            await asyncio.gather(*tasks)
        else:
            await self.sessions[0].session.send_frame(frame_data, delay)

    async def send_prebuffered_streaming(self, frame_data: Union[bytes, List[bytes]]) -> None:
        """Send pre-buffered frame with minimum latency for streaming."""
        if self.multi_panel:
            tasks = []
            for i, panel_session in enumerate(self.sessions):
                if panel_session.descriptor is None:
                    continue
                tasks.append(panel_session.session.send_frame_streaming(frame_data[i]))
            await asyncio.gather(*tasks)
        else:
            await self.sessions[0].session.send_frame_streaming(frame_data)

