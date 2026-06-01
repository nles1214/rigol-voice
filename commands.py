"""
Voice command parser — maps Chinese natural language to SCPI commands
for RIGOL DHO1204 oscilloscope.
"""

import re
import logging
from typing import NamedTuple

logger = logging.getLogger(__name__)


class ParsedCommand(NamedTuple):
    scpi: str           # SCPI command string to send
    is_query: bool      # True if this expects a response
    description: str    # Human-readable description for feedback


# ── Pattern matching engine ──────────────────────────────────────────────

class CommandParser:
    """Match Chinese voice input to SCPI commands via regex patterns."""

    CHANNEL_NAMES = {
        "一": "1", "1": "1", "二": "2", "2": "2",
        "三": "3", "3": "3", "四": "4", "4": "4",
        "通道一": "1", "通道1": "1", "通道二": "2", "通道2": "2",
        "通道三": "3", "通道3": "3", "通道四": "4", "通道4": "4",
    }

    @classmethod
    def _parse_number(cls, text: str) -> float | None:
        """Extract a numeric value from text like '1.5', '5e-3', '-0.5'."""
        m = re.search(r"([\d.eE+\-]+)", text)
        if m:
            try:
                return float(m.group(1))
            except ValueError:
                pass
        return None

    @classmethod
    def _extract_channel(cls, text: str) -> str | None:
        for key, val in cls.CHANNEL_NAMES.items():
            if key in text:
                return val
        return None

    # ── Main parse entry ──────────────────────────────────────────────

    @classmethod
    def parse(cls, voice_text: str) -> ParsedCommand | None:
        """Parse a Chinese voice command into a SCPI ParsedCommand."""
        text = voice_text.strip().lower()
        if not text:
            return None

        for method_name in sorted(dir(cls)):
            if not method_name.startswith("_pat_"):
                continue
            method = getattr(cls, method_name)
            result = method(text)
            if result is not None:
                logger.info(f"Matched: {method_name} → {result.scpi}")
                return result

        return None

    # ── Pattern methods — each returns ParsedCommand or None ──────────

    @classmethod
    def _pat_01_identify(cls, text: str) -> ParsedCommand | None:
        if re.search(r"(识别|查询型号|型号|你是谁|什么型号|设备信息)", text):
            return ParsedCommand("*IDN?", True, "查询示波器型号")
        return None

    @classmethod
    def _pat_02_run(cls, text: str) -> ParsedCommand | None:
        if re.search(r"(开始运行|继续运行|开始采集|继续采集|run)", text) or text in ("运行", "开始", "继续", "run", "start"):
            return ParsedCommand(":RUN", False, "开始采集")
        return None

    @classmethod
    def _pat_03_stop(cls, text: str) -> ParsedCommand | None:
        if re.search(r"(停止|暂停|stop|halt)", text):
            return ParsedCommand(":STOP", False, "停止采集")
        return None

    @classmethod
    def _pat_04_autoscale(cls, text: str) -> ParsedCommand | None:
        if re.search(r"(自动设置|自动调节|auto|autoset)", text) and "触发" not in text:
            return ParsedCommand(":AUToscale", False, "自动设置")
        return None

    @classmethod
    def _pat_05_clear(cls, text: str) -> ParsedCommand | None:
        if re.search(r"(清除|清屏|清除显示|clear|cls)", text) and "测量" not in text:
            return ParsedCommand(":CLEar", False, "清除显示")
        return None

    @classmethod
    def _pat_06_single(cls, text: str) -> ParsedCommand | None:
        if re.search(r"(单次触发|单次采集|single|oneshot)", text):
            return ParsedCommand(":SINGle", False, "单次触发")
        return None

    # ── Channel control ──────────────────────────────────────────────

    @classmethod
    def _pat_10_channel_on(cls, text: str) -> ParsedCommand | None:
        m = re.search(r"(打开|开启|显示)(通道)?([一二三四1234])", text)
        if m:
            ch = cls._extract_channel(m.group(0))
            return ParsedCommand(f":CHANnel{ch}:DISPlay ON", False, f"打开通道{ch}")
        return None

    @classmethod
    def _pat_11_channel_off(cls, text: str) -> ParsedCommand | None:
        m = re.search(r"(关闭|关掉|隐藏)(通道)?([一二三四1234])", text)
        if m:
            ch = cls._extract_channel(m.group(0))
            return ParsedCommand(f":CHANnel{ch}:DISPlay OFF", False, f"关闭通道{ch}")
        return None

    @classmethod
    def _pat_12_channel_scale(cls, text: str) -> ParsedCommand | None:
        m = re.search(r"(通道)?([一二三四1234]).{0,6}(伏|毫伏).{0,4}(每格|每格|一格)", text)
        if not m:
            m = re.search(r"(通道)?([一二三四1234]).{0,2}(设置为|设为|改成).{0,4}([\d.]+)\s*(伏|毫伏)?", text)
        if m:
            ch = cls._extract_channel(m.group(0))
            val = cls._parse_number(m.group(0))
            if val and ch:
                # Convert mV to V if needed
                if "毫伏" in text or "mv" in text.lower():
                    val = val / 1000.0
                return ParsedCommand(
                    f":CHANnel{ch}:SCALe {val}",
                    False,
                    f"通道{ch} 垂直刻度 {val}V/div"
                )
        return None

    @classmethod
    def _pat_13_channel_coupling(cls, text: str) -> ParsedCommand | None:
        m = re.search(r"(通道)?([一二三四1234]).{0,4}(耦合|偶合).{0,3}(直流|交流|接地)", text)
        if m:
            ch = cls._extract_channel(m.group(0))
            coupling = {"直流": "DC", "交流": "AC", "接地": "GND"}
            for cn, en in coupling.items():
                if cn in text:
                    return ParsedCommand(
                        f":CHANnel{ch}:COUPling {en}",
                        False,
                        f"通道{ch} 耦合{cn}"
                    )
        return None

    # ── Timebase ──────────────────────────────────────────────────────

    @classmethod
    def _pat_20_timebase(cls, text: str) -> ParsedCommand | None:
        m = re.search(r"(时基|水平刻度|时间刻度).{0,4}([\d.]+)\s*(秒|毫秒|微秒|纳秒|s|ms|us|ns)", text)
        if m:
            val = cls._parse_number(m.group(0))
            if val:
                if any(x in text for x in ("毫秒", "ms")):
                    val = val / 1000.0
                elif any(x in text for x in ("微秒", "us")):
                    val = val / 1_000_000.0
                elif any(x in text for x in ("纳秒", "ns")):
                    val = val / 1_000_000_000.0
                return ParsedCommand(
                    f":TIMebase:SCALe {val}",
                    False,
                    f"时基 {val}s/div"
                )
        return None

    # ── Trigger ───────────────────────────────────────────────────────

    @classmethod
    def _pat_30_trigger_source(cls, text: str) -> ParsedCommand | None:
        m = re.search(r"触发源.{0,4}(通道)?([一二三四1234])", text)
        if m:
            ch = cls._extract_channel(m.group(0))
            return ParsedCommand(
                f":TRIGger:EDGE:SOURce CHANnel{ch}",
                False,
                f"触发源通道{ch}"
            )
        return None

    @classmethod
    def _pat_31_trigger_mode(cls, text: str) -> ParsedCommand | None:
        if re.search(r"触发模式.{0,3}(自动|auto)", text):
            return ParsedCommand(":TRIGger:SWEep AUTO", False, "触发模式: 自动")
        if re.search(r"触发模式.{0,3}(普通|正常|normal)", text):
            return ParsedCommand(":TRIGger:SWEep NORMal", False, "触发模式: 普通")
        if re.search(r"触发模式.{0,3}(单次|single)", text):
            return ParsedCommand(":TRIGger:SWEep SINGle", False, "触发模式: 单次")
        return None

    @classmethod
    def _pat_32_trigger_level(cls, text: str) -> ParsedCommand | None:
        m = re.search(r"(触发电平|触发电压|trigger.?level).{0,4}([\d.\-]+)\s*(伏|毫伏)?", text)
        if m:
            val = cls._parse_number(m.group(0))
            if val is not None:
                if "毫伏" in text:
                    val = val / 1000.0
                return ParsedCommand(
                    f":TRIGger:EDGE:LEVel {val}",
                    False,
                    f"触发电平 {val}V"
                )
        return None

    @classmethod
    def _pat_33_trigger_slope(cls, text: str) -> ParsedCommand | None:
        if re.search(r"(上升沿|上升|上沿|正沿)", text):
            return ParsedCommand(":TRIGger:EDGE:SLOPe POSitive", False, "触发边沿: 上升沿")
        if re.search(r"(下降沿|下降|下沿|负沿)", text):
            return ParsedCommand(":TRIGger:EDGE:SLOPe NEGative", False, "触发边沿: 下降沿")
        return None

    # ── Measurements ──────────────────────────────────────────────────

    @classmethod
    def _pat_40_measure_vpp(cls, text: str) -> ParsedCommand | None:
        if not re.search(r"(峰峰值|峰峰值电压|峰值|vpp)", text):
            return None
        ch = cls._extract_channel(text) or "1"
        return ParsedCommand(
            f":MEASure:VPP? CHANnel{ch}",
            True,
            f"测量通道{ch}峰峰值"
        )

    @classmethod
    def _pat_41_measure_freq(cls, text: str) -> ParsedCommand | None:
        if not re.search(r"(频率|频率|freq)", text):
            return None
        ch = cls._extract_channel(text) or "1"
        return ParsedCommand(
            f":MEASure:FREQuency? CHANnel{ch}",
            True,
            f"测量通道{ch}频率"
        )

    @classmethod
    def _pat_42_measure_vavg(cls, text: str) -> ParsedCommand | None:
        if not re.search(r"(平均值|平均电压|直流分量)", text):
            return None
        ch = cls._extract_channel(text) or "1"
        return ParsedCommand(
            f":MEASure:VAVerage? CHANnel{ch}",
            True,
            f"测量通道{ch}平均值"
        )

    @classmethod
    def _pat_43_measure_vmax(cls, text: str) -> ParsedCommand | None:
        if not re.search(r"(最大值|最大电压)", text):
            return None
        ch = cls._extract_channel(text) or "1"
        return ParsedCommand(
            f":MEASure:VMAX? CHANnel{ch}",
            True,
            f"测量通道{ch}最大值"
        )

    @classmethod
    def _pat_44_measure_vmin(cls, text: str) -> ParsedCommand | None:
        if not re.search(r"(最小值|最小电压)", text):
            return None
        ch = cls._extract_channel(text) or "1"
        return ParsedCommand(
            f":MEASure:VMIN? CHANnel{ch}",
            True,
            f"测量通道{ch}最小值"
        )

    @classmethod
    def _pat_45_measure_period(cls, text: str) -> ParsedCommand | None:
        if not re.search(r"(周期|period)", text):
            return None
        ch = cls._extract_channel(text) or "1"
        return ParsedCommand(
            f":MEASure:PERiod? CHANnel{ch}",
            True,
            f"测量通道{ch}周期"
        )

    @classmethod
    def _pat_46_measure_rise_time(cls, text: str) -> ParsedCommand | None:
        if not re.search(r"(上升时间|rise.?time)", text):
            return None
        ch = cls._extract_channel(text) or "1"
        return ParsedCommand(
            f":MEASure:RISetime? CHANnel{ch}",
            True,
            f"测量通道{ch}上升时间"
        )

    @classmethod
    def _pat_47_measure_clear(cls, text: str) -> ParsedCommand | None:
        if re.search(r"(清除测量|关闭测量|取消测量|去掉测量)", text):
            return ParsedCommand(":MEASure:CLEar ALL", False, "清除所有测量项")
        return None

    # ── Cursor ────────────────────────────────────────────────────────

    @classmethod
    def _pat_50_cursor_on(cls, text: str) -> ParsedCommand | None:
        if re.search(r"(打开|开启|显示).{0,3}(光标|cursor)", text):
            return ParsedCommand(":CURSor:MODE MANual", False, "打开光标")
        return None

    @classmethod
    def _pat_51_cursor_off(cls, text: str) -> ParsedCommand | None:
        if re.search(r"(关闭|关掉|隐藏).{0,3}(光标|cursor)", text):
            return ParsedCommand(":CURSor:MODE OFF", False, "关闭光标")
        return None

    # ── Screenshot ────────────────────────────────────────────────────

    @classmethod
    def _pat_60_screenshot(cls, text: str) -> ParsedCommand | None:
        if re.search(r"(截图|截屏|保存屏幕|保存画面|抓图|抓屏|screenshot|capture|shot|snap|拍照|截取)", text):
            return ParsedCommand(":DISPlay:DATA? BMP,SCR", True, "截取屏幕画面")
        return None

    # ── Acquisition ───────────────────────────────────────────────────

    @classmethod
    def _pat_70_acq_mode(cls, text: str) -> ParsedCommand | None:
        if re.search(r"(普通模式|正常模式).{0,3}(采集|采样)", text):
            return ParsedCommand(":ACQuire:TYPE NORMal", False, "采集模式: 普通")
        if re.search(r"(平均模式).{0,3}(采集|采样)", text):
            return ParsedCommand(":ACQuire:TYPE AVERages", False, "采集模式: 平均")
        if re.search(r"(峰值检测|峰值).{0,3}(采集|采样)", text):
            return ParsedCommand(":ACQuire:TYPE PEAK", False, "采集模式: 峰值检测")
        if re.search(r"(高分辨率|高分辨).{0,3}(采集|采样)", text):
            return ParsedCommand(":ACQuire:TYPE HRESolution", False, "采集模式: 高分辨率")
        return None


def get_supported_commands() -> list[str]:
    """Return example voice commands for the help UI."""
    return [
        "运行 / 停止",
        "自动设置",
        "打开通道一 / 关闭通道二",
        "通道一设置为 1 伏每格",
        "通道一耦合直流",
        "时基设置为 1 毫秒",
        "触发源通道一",
        "触发模式自动",
        "触发电平 1.5 伏",
        "测量通道一峰峰值",
        "测量通道一频率",
        "截图",
        "打开光标 / 关闭光标",
        "清除测量",
        "识别设备",
    ]

