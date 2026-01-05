#!/usr/bin/env python3

import argparse
import asyncio
import sys
from pathlib import Path

try:
    import websockets
except ImportError:
    print("Error: websockets library required")
    print("Install with: pip install websockets")
    sys.exit(1)

project_root = Path(__file__).resolve().parents[1]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from bk_light.display_session import BleDisplaySession, build_frame

MIN_FRAME_INTERVAL = 0.08

panel_address = None
panel = None
last_frame_time = 0


def is_valid_png(data: bytes) -> bool:
    return len(data) >= 8 and data[:8] == b"\x89PNG\r\n\x1a\n"


async def handle_websocket(websocket):
    global panel, last_frame_time
    print(f"Client connected: {websocket.remote_address}")
    
    if not panel:
        panel = BleDisplaySession(
            address=panel_address,
            auto_reconnect=True,
            log_notifications=False,
        )
        try:
            await panel._connect()
            print("Connected to panel")
        except Exception as e:
            print(f"Failed to connect to panel: {e}")
            await websocket.close()
            return
    
    try:
        async for message in websocket:
            if not isinstance(message, bytes) or not panel:
                continue
            if not is_valid_png(message):
                continue
            now = asyncio.get_event_loop().time()
            if now - last_frame_time >= MIN_FRAME_INTERVAL:
                last_frame_time = now
                try:
                    frame = build_frame(message)
                    await panel.send_frame(frame, delay=0.1)
                except Exception as e:
                    print(f"Error sending frame: {e}")
                    if "not connected" in str(e).lower() or "disconnected" in str(e).lower():
                        try:
                            await panel._connect()
                        except:
                            pass
    except websockets.exceptions.ConnectionClosed:
        pass
    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        if panel:
            await panel._safe_disconnect()
            panel = None
        print(f"Client disconnected: {websocket.remote_address}")


async def handle_http(reader, writer):
    try:
        data = await reader.read(4096)
        request = data.decode("utf-8", errors="ignore")

        path = None
        for line in request.split("\n"):
            if line.startswith("GET "):
                parts = line.split()
                if len(parts) >= 2:
                    path = parts[1]
                break

        if path == "/":
            content = b"<!DOCTYPE html><html><head><title>BLE Panel Server</title></head><body><h1>BLE Panel Server</h1><p>Server is running. Connect via WebSocket to send frames.</p></body></html>"
            response = (
                b"HTTP/1.1 200 OK\r\n"
                b"Content-Type: text/html; charset=utf-8\r\n"
                b"Content-Length: " + str(len(content)).encode() + b"\r\n"
                b"Connection: close\r\n\r\n" + content
            )
        else:
            response = b"HTTP/1.1 404 Not Found\r\nConnection: close\r\n\r\nNot found"

        writer.write(response)
        await writer.drain()
    except Exception as e:
        print(f"HTTP error: {e}")
    finally:
        writer.close()
        await writer.wait_closed()


async def main():
    global panel_address

    parser = argparse.ArgumentParser()
    parser.add_argument("address")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--ws-port", type=int, default=8765)
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    panel_address = args.address

    try:
        http_server = await asyncio.start_server(handle_http, "0.0.0.0", args.port)
        print(f"HTTP: http://localhost:{args.port}/")

        ws_server = await websockets.serve(handle_websocket, "0.0.0.0", args.ws_port)
        print(f"WebSocket: ws://localhost:{args.ws_port}/")
        print("Waiting for WebSocket client... (panel will connect on first client)")

        await asyncio.gather(
            http_server.serve_forever(),
            ws_server.wait_closed(),
        )
    except KeyboardInterrupt:
        pass
    finally:
        if panel:
            await panel._safe_disconnect()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nStopped")
