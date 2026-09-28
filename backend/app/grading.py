"""成绩分档规则：合格 / 待补训 / 不合格三档的口径全部收在这里。

收尾确认、台账汇总、示例数据播种都走同一份规则，避免同一批成绩在不同页面
算出不同的数字。分档口径：

* 80 分及以上：合格
* 60 分（含）到 80 分：待补训
* 60 分以下：不合格
"""
from __future__ import annotations

import math
from typing import Any

SCORE_FIELD = "考核成绩"
PASS_LINE = 80
REMEDIAL_LINE = 60

TIER_PASS = "合格"
TIER_REMEDIAL = "待补训"
TIER_FAIL = "不合格"
TIER_ORDER = [TIER_PASS, TIER_REMEDIAL, TIER_FAIL]
TIER_COLORS = {
    TIER_PASS: "#16a34a",
    TIER_REMEDIAL: "#d97706",
    TIER_FAIL: "#dc2626",
}
RULE_TEXT = "分档口径：80 分及以上合格，60 至 79 分待补训，60 分以下不合格；同一培训编号重复收尾以最后一次成绩为准。"


def tier_for(score: float) -> str:
    """按分数落档。"""
    if score >= PASS_LINE:
        return TIER_PASS
    if score >= REMEDIAL_LINE:
        return TIER_REMEDIAL
    return TIER_FAIL


def _coerce_score(value: Any) -> tuple[str, float | None]:
    """把前端传来的成绩解析成有限数字。

    返回 (状态, 数字)：状态为 ok / missing / invalid / out_of_range。
    布尔值、NaN、无穷、无法解析的文本都不算有效成绩。
    """
    if isinstance(value, bool):
        return "invalid", None
    if isinstance(value, (int, float)):
        number = float(value)
    else:
        text = str(value if value is not None else "").strip()
        if text == "":
            return "missing", None
        try:
            number = float(text)
        except ValueError:
            return "invalid", None
    if not math.isfinite(number):
        return "invalid", None
    if number < 0 or number > 100:
        return "out_of_range", number
    return "ok", number


def _display_number(number: float) -> int | float:
    """92.0 这类分数按整数展示，其余保留原值。"""
    return int(number) if number.is_integer() else number


def normalize_members(raw_items: Any) -> tuple[list[dict[str, Any]], list[str]]:
    """校验并归一化收尾时提交的人员成绩。

    一次性收齐所有错误，指明是第几行 / 哪个人的「考核成绩」哪一项有问题；
    只要有一条不合法，调用方就应当整批驳回，不写入任何分档结果。
    """
    members: list[dict[str, Any]] = []
    errors: list[str] = []
    if not isinstance(raw_items, list):
        return members, ["收尾成绩明细格式不正确，应为人员成绩列表"]

    for index, item in enumerate(raw_items, start=1):
        if not isinstance(item, dict):
            errors.append(f"第 {index} 行不是有效的人员成绩记录")
            continue
        name = str(item.get("姓名") or "").strip()
        label = f"人员「{name}」" if name else f"第 {index} 行人员"
        if not name:
            errors.append(f"第 {index} 行人员姓名未填写")

        status, number = _coerce_score(item.get(SCORE_FIELD))
        if status == "missing":
            errors.append(f"{label}的{SCORE_FIELD}未填写")
            continue
        if status == "invalid":
            errors.append(f"{label}的{SCORE_FIELD}「{item.get(SCORE_FIELD)}」无法识别为 0 到 100 之间的分数")
            continue
        if status == "out_of_range":
            errors.append(f"{label}的{SCORE_FIELD} {_display_number(number or 0)} 不在 0 到 100 之间")
            continue
        members.append({"姓名": name, SCORE_FIELD: _display_number(number or 0)})

    return members, errors


def build_ledger(entry: dict[str, Any], members: list[dict[str, Any]], finished_at: str) -> dict[str, Any]:
    """根据一批已校验成绩生成台账记录，并给出三档人数。"""
    counts = {tier: 0 for tier in TIER_ORDER}
    details: list[dict[str, Any]] = []
    for member in members:
        score = float(member[SCORE_FIELD])
        tier = tier_for(score)
        counts[tier] += 1
        details.append({"姓名": member["姓名"], SCORE_FIELD: member[SCORE_FIELD], "分档": tier})
    details.sort(key=lambda item: (TIER_ORDER.index(item["分档"]), -float(item[SCORE_FIELD]), item["姓名"]))
    return {
        "id": int(entry["id"]),
        "培训编号": entry["培训编号"],
        "培训主题": entry["培训主题"],
        "结班时间": finished_at,
        "人员明细": details,
        "分档结果": counts,
    }


def tier_totals(ledgers: list[dict[str, Any]]) -> dict[str, int]:
    """跨培训汇总各档人数，台账图表与补训名单都从这里取数。"""
    totals = {tier: 0 for tier in TIER_ORDER}
    for ledger in ledgers:
        for tier in TIER_ORDER:
            totals[tier] += int(ledger.get("分档结果", {}).get(tier, 0))
    return totals


def remedial_groups(ledgers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """把待补训人员按培训主题归拢成一份补训名单。"""
    grouped: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for ledger in ledgers:
        theme = str(ledger.get("培训主题") or "未命名主题")
        if theme not in grouped:
            grouped[theme] = {"培训主题": theme, "人数": 0, "items": []}
            order.append(theme)
        for detail in ledger.get("人员明细", []):
            if detail.get("分档") != TIER_REMEDIAL:
                continue
            grouped[theme]["items"].append({
                "培训编号": ledger.get("培训编号", ""),
                "姓名": detail.get("姓名", ""),
                SCORE_FIELD: detail.get(SCORE_FIELD, ""),
                "结班时间": ledger.get("结班时间", ""),
            })
            grouped[theme]["人数"] += 1
    return [grouped[theme] for theme in order if grouped[theme]["items"]]
