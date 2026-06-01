# RIGOL DHO1204 语音控制系统

[English](./README.md) | [中文](./README_zh.md)

---


基于浏览器的 RIGOL DHO1204 示波器语音控制工具，通过 SCPI over TCP/IP 协议与示波器通信。用中文或英文说出指令，示波器实时响应。

## 功能特性

- **语音识别** — 基于 Chrome/Edge 的 Web Speech API，支持连续听写，实时显示识别结果
- **实时画面** — Scope Display 面板展示示波器当前画面，支持一键全屏放大
- **触发通知** — 示波器捕获波形时弹出桌面通知，远程也能及时知晓
- **截图保存** — 语音或按钮触发，自动保存为 PNG 并叮声确认
- **零依赖** — 服务端纯 Python 标准库，无需 pip install

## 快速开始

1. 双击 `run.bat` 启动服务
2. 用 **Chrome 或 Edge 浏览器** 打开 `http://localhost:8765`
3. 点击右上角 **Connect Scope** 连接示波器（绿色圆点表示已连接）
4. 点击麦克风按钮开始说话，或使用快捷按钮操作

> 不支持 Firefox，因为 Firefox 没有中文 Web Speech API。

## 架构

```
麦克风 → 浏览器 (Web Speech API, zh-CN)
           ↓ WebSocket
      server.py — 纯 asyncio HTTP + WebSocket 服务端
           ↓ SCPI over TCP :5555
      RIGOL DHO1204 示波器 (192.168.152.177)
```

| 文件 | 用途 |
|------|------|
| `scpi.py` | SCPI 通信层，通过 TCP socket 直连示波器 |
| `commands.py` | 中英文语音 → SCPI 命令映射引擎（27 条规则） |
| `server.py` | 异步 HTTP + WebSocket 服务端（零外部依赖） |
| `static/index.html` | 浏览器前端，集成语音识别、实时画面、触发通知 |

## 语音指令

| 类别 | 示例 |
|------|------|
| **系统** | 运行 / Run, 停止 / Stop, 自动设置 / Auto, 单次触发 / Single, 清除 / Clear |
| **通道** | 打开通道一, 关闭通道二, 通道一设置为 1 伏每格, 通道一耦合直流 |
| **时基** | 时基设置为 1 毫秒 |
| **触发** | 触发源通道一, 触发模式自动, 触发电平 1.5 伏, 上升沿 / 下降沿 |
| **测量** | 测量通道一峰峰值, 测量通道一频率, 测量通道一平均值 / 最大值 / 最小值 / 周期 |
| **截图** | 截图 / Screenshot / Shot / 拍照 |
| **光标** | 打开光标 / 关闭光标 |
| **采集** | 普通模式采集 / 平均模式采集 / 峰值检测采集 |
| **信息** | 识别设备 |

## 截图

截图保存在 `screenshots/` 目录，命名格式为 `scope_YYYYMMDD_HHMMSS.png`。每次截图成功右上角弹出 toast 提示并伴随一声叮提示音。

## 命令行参数

```
python server.py --host 0.0.0.0 --port 8765 --scope-host 192.168.152.177 --scope-port 5555
```

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--host` | `0.0.0.0` | 服务器绑定地址 |
| `--port` | `8765` | 服务器端口 |
| `--scope-host` | `192.168.152.177` | 示波器 IP 地址 |
| `--scope-port` | `5555` | 示波器 SCPI 端口 |

## 推送更新

```powershell
cd D:\Codex-work\rigol-voice
git add -A
git commit -m "update"
git push
```

## 版本历史

| 标签 | 内容 |
|------|------|
| **v0.3** | 截图存盘 + 叮声提示, 触发通知 + 桌面弹窗, 实时画面放大缩小, v0.2 版本标识 |
| **v0.1** | 语音控制, SCPI 通信, WebSocket 服务端, 实时画面, 截图功能 |

回退到稳定基线：`git checkout v0.1`

## 运行环境

- Python 3.10+
- RIGOL DHO1204 示波器（或兼容 SCPI 的设备）在同一局域网内
- Chrome 或 Edge 浏览器（需要 zh-CN 语音识别支持）
- Windows 防火墙需放行 Python 对端口 5555 的出站 TCP 连接

## 开源协议

MIT