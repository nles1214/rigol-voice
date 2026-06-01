# RIGOL DHO1204 Voice Control

Browser-based voice control for the RIGOL DHO1204 oscilloscope via SCPI over TCP/IP. Speak commands in Chinese or English — the oscilloscope responds in real time.

## Features

- **Voice Recognition** — Chrome/Edge Web Speech API, continuous listening with interim results display
- **Live Scope View** — Real-time display panel with fullscreen zoom
- **Trigger Alert** — Desktop notification when the oscilloscope captures a waveform
- **Screenshot Capture** — One-click or voice-triggered, saved as PNG with ding confirmation
- **Zero Dependencies** — Pure Python standard library (no pip install required for the server)

## Quick Start

1. Double-click `run.bat`
2. Open **Chrome or Edge** and navigate to `http://localhost:8765`
3. Click **Connect Scope** in the top-right corner (green dot = connected)
4. Click the microphone button and start speaking, or use the quick-action buttons

> Firefox is not supported — it lacks the Chinese Web Speech API.

## Architecture

```
Microphone → Browser (Web Speech API, zh-CN)
                ↓ WebSocket
           server.py — pure asyncio HTTP + WebSocket server
                ↓ SCPI over TCP :5555
           RIGOL DHO1204 Oscilloscope (192.168.152.177)
```

| File | Purpose |
|------|---------|
| `scpi.py` | SCPI communication layer over raw TCP socket |
| `commands.py` | Chinese & English voice → SCPI command mapping (27 patterns) |
| `server.py` | Async HTTP + WebSocket server (zero external deps) |
| `static/index.html` | Browser UI with voice recognition, live view, trigger alerts |

## Voice Commands

| Category | Examples |
|----------|----------|
| **System** | 运行 / Run, 停止 / Stop, 自动设置 / Auto, 单次触发 / Single, 清除 / Clear |
| **Channel** | 打开通道一, 关闭通道二, 通道一设置为 1 伏每格, 通道一耦合直流 |
| **Timebase** | 时基设置为 1 毫秒 |
| **Trigger** | 触发源通道一, 触发模式自动, 触发电平 1.5 伏, 上升沿 / 下降沿 |
| **Measure** | 测量通道一峰峰值, 测量通道一频率, 测量通道一平均值 / 最大值 / 最小值 / 周期 |
| **Screenshot** | 截图 / Screenshot / Shot |
| **Cursor** | 打开光标 / 关闭光标 |
| **Acquisition** | 普通模式采集 / 平均模式采集 / 峰值检测采集 |
| **Info** | 识别设备 |

## Screenshots

Saved to `screenshots/` with naming format `scope_YYYYMMDD_HHMMSS.png`. A toast notification and a short ding sound confirm each capture.

## CLI Options

```
python server.py --host 0.0.0.0 --port 8765 --scope-host 192.168.152.177 --scope-port 5555
```

| Flag | Default | Description |
|------|---------|-------------|
| `--host` | `0.0.0.0` | Server bind address |
| `--port` | `8765` | Server port |
| `--scope-host` | `192.168.152.177` | Oscilloscope IP address |
| `--scope-port` | `5555` | Oscilloscope SCPI port |

## Version History

| Tag | Highlights |
|-----|------------|
| **v0.3** | Screenshot save + ding notification, trigger alert with desktop notifications, live view zoom, v0.2 cache badge |
| **v0.1** | Voice control, SCPI communication, WebSocket server, live scope view, screenshot capture |

To roll back to a stable baseline: `git checkout v0.1`

## Requirements

- Python 3.10+
- RIGOL DHO1204 oscilloscope (or compatible SCPI device) on the local network
- Chrome or Edge browser (Web Speech API zh-CN support)
- Windows Firewall rule allowing Python outbound TCP to port 5555

## License

MIT