"""复读检测：模型输出里是否有「同一段内容原样连续重复」的区域。

逐条对齐 Deva `apps/desktop/src/main/services/repetition.ts`。模型退化时会原地打转——
反复吐 `<|end|>` 之类的模板标记、同一句话或同一段落，具体是什么无从预料，共同点是逐字
重复，故这里只看结构、不看内容。只认逐字符完全相同的周期：带递增序号的列表、每行内容
不同的表格都不算，免得误伤正常输出。

两处用途：压缩摘要的把关（`find_repetition`）与回复流式输出中的实时拦截
（`watch_repetition`，只查结尾）。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

# 认得出的最长重复单元（字符）：段落级复读也在此之内。
MAX_PERIOD = 1000

# 判为复读的两档门槛（字符数；中文一字一字符），满足其一即可：
#  - 同一段话重复至少 4 遍、连续 250 字符以上；
#  - 同一短单元重复至少 10 遍、连续 200 字符以上。
RULES: tuple[tuple[int, int], ...] = ((250, 4), (200, 10))

# 流式检测的节流：文本每长出这么多字符才查一次结尾。
WATCH_STEP = 32
# 看守只留结尾这么多字符（够格的区域最长 = min_span_for(MAX_PERIOD)）。
WATCH_TAIL = 4096


@dataclass(frozen=True)
class RepetitionHit:
    """一段复读区域。"""

    start: int
    period: int
    span: int


def _qualifies(span: int, period: int) -> bool:
    return any(span >= min_span and span / period >= min_count for min_span, min_count in RULES)


def min_span_for(period: int) -> int:
    """周期为 period 的重复区域至少多长才算复读（各档门槛取最宽松的那档）。"""
    return min(max(min_span, min_count * period) for min_span, min_count in RULES)


def find_repetition(text: str) -> Optional[RepetitionHit]:
    """找出文本里最长的一段复读区域；没有则 None。"""
    n = len(text)
    max_period = min(MAX_PERIOD, n // 2)
    best: Optional[RepetitionHit] = None
    for period in range(1, max_period + 1):
        # run = 连续满足 text[i] == text[i - period] 的字符数；该区域总长 = run + period。
        run = 0
        for i in range(period, n + 1):
            if i < n and text[i] == text[i - period]:
                run += 1
                continue
            if run > 0:
                span = run + period
                if _qualifies(span, period) and (best is None or span > best.span):
                    best = RepetitionHit(start=i - span, period=period, span=span)
                run = 0
    return best


def trailing_repetition(text: str) -> Optional[RepetitionHit]:
    """文本**结尾**是否正在复读：只看收尾于结尾的那段重复区域。"""
    n = len(text)
    max_period = min(MAX_PERIOD, n // 2)
    for period in range(1, max_period + 1):
        need = min_span_for(period) - period  # 够格所需的 run（span = run + period）
        if need > n - period:
            continue
        run = 0
        while run < need and text[n - 1 - run] == text[n - 1 - run - period]:
            run += 1
        if run < need:
            continue
        while run < n - period and text[n - 1 - run] == text[n - 1 - run - period]:
            run += 1
        return RepetitionHit(start=n - run - period, period=period, span=run + period)
    return None


def watch_repetition() -> Callable[[str], Optional[RepetitionHit]]:
    """流式输出的复读看守：逐段传入增量，结尾正在复读时返回命中（start/span 相对看守的结尾）。"""
    state = {"tail": "", "pending": 0}

    def feed(delta: str) -> Optional[RepetitionHit]:
        state["tail"] += delta
        state["pending"] += len(delta)
        if len(state["tail"]) > WATCH_TAIL * 2:
            state["tail"] = state["tail"][-WATCH_TAIL:]
        if state["pending"] < WATCH_STEP:
            return None
        state["pending"] = 0
        return trailing_repetition(state["tail"])

    return feed


__all__ = [
    "MAX_PERIOD",
    "RULES",
    "RepetitionHit",
    "WATCH_STEP",
    "WATCH_TAIL",
    "find_repetition",
    "min_span_for",
    "trailing_repetition",
    "watch_repetition",
]
