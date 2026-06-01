
"""
RIGOL DHO1204 Voice Control Server - Pure stdlib HTTP + WebSocket.
Usage: python server.py [--host HOST] [--port PORT] [--scope-host SCOPE_HOST]
"""

import asyncio, base64, hashlib, json, logging, re, struct, time
from datetime import datetime
from http import HTTPStatus
from pathlib import Path

from scpi import ScpiClient
from commands import CommandParser, get_supported_commands

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("rigol-voice")

SCOPE_HOST = "192.168.152.177"
SCOPE_PORT = 5555
SERVER_HOST = "0.0.0.0"
SERVER_PORT = 8765

BASE_DIR = Path(__file__).parent
STATIC_DIR = BASE_DIR / "static"
SCREENSHOT_DIR = BASE_DIR / "screenshots"
SCREENSHOT_DIR.mkdir(exist_ok=True)

scpi = ScpiClient(host=SCOPE_HOST, port=SCOPE_PORT)
ws_clients = []
_state = {"live_view": False}

async def ws_broadcast(message):
    payload = json.dumps(message, ensure_ascii=False)
    dead = []
    for writer in ws_clients:
        try:
            await ws_send_text(writer, payload)
        except Exception:
            dead.append(writer)
    for w in dead:
        if w in ws_clients:
            ws_clients.remove(w)

def _extract_binary(raw):
    if not raw or raw[0] != "#":
        return None
    try:
        digits = int(raw[1])
        data_len = int(raw[2:2 + digits])
        start = 2 + digits
        return raw[start:start + data_len].encode("latin-1")
    except (ValueError, IndexError):
        return None

def execute_command(text):
    parsed = CommandParser.parse(text)
    if parsed is None:
        return {"type": "error", "message": f"Cannot parse: {text}", "voice_text": text}
    if not scpi.is_connected:
        return {"type": "error", "message": "Scope not connected", "voice_text": text, "command": parsed.scpi}
    result = scpi.send(parsed.scpi)
    resp = {"type": "command", "voice_text": text, "command": parsed.scpi,
            "description": parsed.description, "success": True}
    if parsed.is_query and result is not None:
        if ":DISPlay:DATA?" in parsed.scpi:
            img_bytes = _extract_binary(result)
            if img_bytes:
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                fname = f"scope_{ts}.png"
                fpath = SCREENSHOT_DIR / fname
                fpath.write_bytes(img_bytes)
                b64 = base64.b64encode(img_bytes).decode()
                resp.update({"result_type": "image", "result": b64,
                             "file_path": str(fpath), "file_name": fname})
                logger.info(f"Screenshot saved: {fpath}")
            else:
                resp["result"] = result[:200]
        else:
            resp["result"] = result
            resp["result_type"] = "text"
    elif not parsed.is_query:
        resp["result"] = "ok"
    return resp

async def ws_send_frame(writer, opcode, data):
    frame = bytearray([0x80 | opcode])
    n = len(data)
    if n < 126:
        frame.append(n)
    elif n < 65536:
        frame.append(126)
        frame.extend(struct.pack(">H", n))
    else:
        frame.append(127)
        frame.extend(struct.pack(">Q", n))
    frame.extend(data)
    writer.write(bytes(frame))
    await writer.drain()

async def ws_send_text(writer, text):
    await ws_send_frame(writer, 0x01, text.encode("utf-8"))

async def ws_send_pong(writer, data=b""):
    await ws_send_frame(writer, 0x0A, data)

async def ws_send_close(writer):
    await ws_send_frame(writer, 0x08, b"")

async def ws_read_frame(reader):
    try:
        hdr = await reader.readexactly(2)
    except (asyncio.IncompleteReadError, ConnectionResetError):
        return None, None
    opcode = hdr[0] & 0x0F
    masked = bool(hdr[1] & 0x80)
    length = hdr[1] & 0x7F
    if length == 126:
        length = struct.unpack(">H", await reader.readexactly(2))[0]
    elif length == 127:
        length = struct.unpack(">Q", await reader.readexactly(8))[0]
    mask = await reader.readexactly(4) if masked else None
    payload = await reader.readexactly(length)
    if mask:
        payload = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
    return opcode, payload

CT = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".json": "application/json",
    ".png": "image/png",
    ".bmp": "image/bmp",
    ".svg": "image/svg+xml",
}

def read_static(path):
    full = (STATIC_DIR / path).resolve()
    if not str(full).startswith(str(STATIC_DIR.resolve())):
        return 403, "text/plain", b"Forbidden"
    if not full.is_file():
        return 404, "text/plain", b"Not Found"
    return 200, CT.get(full.suffix, "application/octet-stream"), full.read_bytes()

async def send_http(writer, status, ct, body):
    reason = HTTPStatus(status).phrase
    resp = (f"HTTP/1.1 {status} {reason}\r\nContent-Type: {ct}\r\n"
            f"Content-Length: {len(body)}\r\nConnection: close\r\n"
            "Access-Control-Allow-Origin: *\r\n\r\n").encode() + body
    writer.write(resp)
    await writer.drain()

async def handle_connection(reader, writer):
    try:
        first_line = await reader.readline()
        if not first_line:
            return writer.close()
        header_lines = [first_line]
        while True:
            line = await reader.readline()
            header_lines.append(line)
            if line in (b"\r\n", b"\n", b""):
                break
        req_str = b"".join(header_lines).decode("utf-8", errors="ignore")
        parts = header_lines[0].decode("utf-8", errors="ignore").split(" ")
        if len(parts) < 2:
            return writer.close()
        method, path = parts[0], parts[1]

        km = re.search(r"Sec-WebSocket-Key:\s*(.+)", req_str)
        if km and "Upgrade: websocket" in req_str:
            key = km.group(1).strip()
            acc = base64.b64encode(hashlib.sha1(
                (key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest()).decode()
            hs = (f"HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\n"
                  f"Connection: Upgrade\r\nSec-WebSocket-Accept: {acc}\r\n\r\n")
            writer.write(hs.encode())
            await writer.drain()
            return await handle_ws(reader, writer)

        cl = 0
        for hl in header_lines:
            h = hl.decode("utf-8", errors="ignore").lower()
            if h.startswith("content-length:"):
                try:
                    cl = int(h.split(":")[1].strip())
                except ValueError:
                    pass
        body_bytes = await reader.readexactly(cl) if cl > 0 else b""

        if method == "GET":
            if path in ("/", "/index.html"):
                await send_http(writer, *read_static("index.html"))
            elif path.startswith("/static/"):
                await send_http(writer, *read_static(path[8:]))
            elif path.startswith("/screenshots/"):
                fp = SCREENSHOT_DIR / path.split("/")[-1]
                if fp.is_file():
                    await send_http(writer, 200, "image/png", fp.read_bytes())
                else:
                    await send_http(writer, 404, "text/plain", b"Not Found")
            elif path == "/api/status":
                j = json.dumps({
                    "connected": scpi.is_connected,
                    "scope_host": f"{SCOPE_HOST}:{SCOPE_PORT}",
                    "commands": get_supported_commands(),
                    "live_view": _state["live_view"],
                }, ensure_ascii=False)
                await send_http(writer, 200, "application/json", j.encode("utf-8"))
            else:
                await send_http(writer, 404, "text/plain", b"Not Found")
        elif method == "POST":
            if path == "/api/connect":
                ok, err = scpi.connect()
                j = json.dumps({"connected": ok, "scope_host": f"{SCOPE_HOST}:{SCOPE_PORT}",
                                "error": err or ""}, ensure_ascii=False)
                await send_http(writer, 200, "application/json", j.encode("utf-8"))
            elif path == "/api/disconnect":
                scpi.disconnect()
                j = json.dumps({"connected": False, "message": "\u5df2\u65ad\u5f00\u793a\u6ce2\u5668\u8fde\u63a5"}, ensure_ascii=False)
                await send_http(writer, 200, "application/json", j.encode("utf-8"))
            elif path == "/api/command":
                try:
                    p = json.loads(body_bytes.decode("utf-8"))
                    text = p.get("text", "")
                except Exception:
                    text = ""
                result = execute_command(text)
                await ws_broadcast(result)
                await send_http(writer, 200, "application/json",
                                json.dumps(result, ensure_ascii=False).encode("utf-8"))
            elif path == "/api/live_toggle":
                _state["live_view"] = not _state["live_view"]
                j = json.dumps({"live_view": _state["live_view"]}, ensure_ascii=False)
                await send_http(writer, 200, "application/json", j.encode("utf-8"))
            else:
                await send_http(writer, 404, "text/plain", b"Not Found")
        else:
            await send_http(writer, 405, "text/plain", b"Method Not Allowed")
    except Exception as e:
        logger.error(f"HTTP error: {e}")
    finally:
        writer.close()

async def handle_ws(reader, writer):
    ws_clients.append(writer)
    logger.info(f"WS + ({len(ws_clients)})")
    await ws_send_text(writer, json.dumps({
        "type": "status",
        "connected": scpi.is_connected,
        "commands": get_supported_commands(),
        "live_view": _state["live_view"],
    }, ensure_ascii=False))
    try:
        while True:
            opcode, payload = await ws_read_frame(reader)
            if opcode is None:
                break
            if opcode == 0x08:
                await ws_send_close(writer)
                break
            elif opcode == 0x09:
                await ws_send_pong(writer, payload)
                continue
            elif opcode == 0x0A:
                continue
            elif opcode == 0x01:
                try:
                    msg = json.loads(payload.decode("utf-8"))
                    a = msg.get("action", "")
                    if a == "connect":
                        ok, err = scpi.connect()
                        r = {"type": "status", "connected": ok}
                        if err:
                            r["error"] = err
                        await ws_send_text(writer, json.dumps(r, ensure_ascii=False))
                    elif a == "disconnect":
                        scpi.disconnect()
                        await ws_send_text(writer, json.dumps(
                            {"type": "status", "connected": False,
                             "message": "\u5df2\u65ad\u5f00\u793a\u6ce2\u5668\u8fde\u63a5"},
                            ensure_ascii=False))
                    elif a == "command":
                        result = execute_command(msg.get("text", ""))
                        await ws_send_text(writer, json.dumps(result, ensure_ascii=False))
                    elif a == "live_toggle":
                        _state["live_view"] = not _state["live_view"]
                        await ws_send_text(writer, json.dumps(
                            {"type": "status", "connected": scpi.is_connected,
                             "live_view": _state["live_view"]}, ensure_ascii=False))
                    elif a == "ping":
                        await ws_send_text(writer, '{"type":"pong"}')
                except Exception as e:
                    logger.error(f"WS msg: {e}")
    except (ConnectionResetError, asyncio.IncompleteReadError):
        pass
    except Exception as e:
        logger.debug(f"WS err: {e}")
    finally:
        if writer in ws_clients:
            ws_clients.remove(writer)
        try:
            writer.close()
        except Exception:
            pass
        logger.info(f"WS - ({len(ws_clients)})")

async def live_view_loop():
    while True:
        await asyncio.sleep(2.0)
        if not _state["live_view"] or not ws_clients or not scpi.is_connected:
            continue
        raw = scpi.send(":DISPlay:DATA?")
        if raw is None:
            continue
        img_bytes = _extract_binary(raw)
        if img_bytes:
            b64 = base64.b64encode(img_bytes).decode()
            await ws_broadcast({"type": "live_frame", "result": b64, "result_type": "image"})

async def main_async(host, port):
    server = await asyncio.start_server(handle_connection, host, port)
    logger.info(f"Server: http://{host}:{port}  |  Scope: {SCOPE_HOST}:{SCOPE_PORT}")
    asyncio.create_task(live_view_loop())
    async with server:
        await server.serve_forever()

def main():
    import argparse
    p = argparse.ArgumentParser(description="RIGOL DHO1204 Voice Control Server")
    p.add_argument("--host", default=SERVER_HOST)
    p.add_argument("--port", type=int, default=SERVER_PORT)
    p.add_argument("--scope-host", default=SCOPE_HOST)
    p.add_argument("--scope-port", type=int, default=SCOPE_PORT)
    args = p.parse_args()
    scpi.host = args.scope_host
    scpi.port = args.scope_port
    asyncio.run(main_async(args.host, args.port))

if __name__ == "__main__":
    main()
