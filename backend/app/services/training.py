"""资质培训业务规则：状态流转、字段校验、结班成绩分档与台账口径都收在这里。

成绩分档阈值：80 分及以上为合格，60-79 分为待补训，60 分以下为不合格。
同一培训编号重复收尾时，以序号最大的一次成绩为准，旧成绩保留明细但不计入汇总。
"""
from __future__ import annotations

from typing import Any

from app.store import store

MODULE = "training"
REQUIRED_FIELDS = ["培训编号", "培训主题", "培训对象"]
STATUS_ORDER = ["待开班", "进行中", "已结班", "已取消"]
ACTION_RULES = {"开班登记": "进行中", "确认结班": "已结班", "取消培训": "已取消"}
NEGATIVE_ACTIONS = []

CLOSED_STATUS = "已结班"
CANCELLED_STATUS = "已取消"
SCORE_PASS = 80
SCORE_RETRAIN = 60
TIERS = ["合格", "待补训", "不合格"]
LEDGER_KEY = "成绩台账"


def tier_of(score: float) -> str:
    if score >= SCORE_PASS:
        return "合格"
    if score >= SCORE_RETRAIN:
        return "待补训"
    return "不合格"


class TrainingService:
    def __init__(self) -> None:
        # 每次结班分配一个递增序号，用来判定同一培训编号的最后一次收尾
        self._close_seq = 0

    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(MODULE)
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("培训编号", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        total = len(rows)
        start = max(page - 1, 0) * size
        # 列表只呈现台账摘要字段，完整人员明细走 grade_ledger 接口，避免两份口径
        views = [
            {key: value for key, value in row.items() if key != LEDGER_KEY}
            for row in rows[start:start + size]
        ]
        return views, total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        return store.find(MODULE, entry_id)

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing
        rows = store.rows(MODULE)
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry.update({field: values.get(field) for field in REQUIRED_FIELDS})
        entry["status"] = STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = False
        rows.append(entry)
        return entry, []

    def run_action(
        self,
        entry_id: int,
        action: str,
        people: list[dict[str, Any]] | None = None,
    ) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"培训记录 {entry_id} 不存在或已归档"
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于资质培训可执行范围"
        target = ACTION_RULES[action]
        if target not in STATUS_ORDER:
            return None, f"目标状态「{target}」不在允许的状态序列里"
        if action == "确认结班":
            return self._close_with_scores(entry, people or [])
        # 开班登记、取消培训沿用原有状态流转，不在本次改动范围内
        entry["status"] = target
        entry["pending"] = target != STATUS_ORDER[-1]
        entry["abnormal"] = action in NEGATIVE_ACTIONS
        return entry, f"培训记录已{action}"

    def _close_with_scores(
        self,
        entry: dict[str, Any],
        people: list[dict[str, Any]],
    ) -> tuple[dict[str, Any] | None, str]:
        """收尾校验：人员名单与成绩逐项核对，任何一项不合规都不允许结班。"""
        if not isinstance(people, list):
            return None, "本次结班没有收到人员成绩名单，请先逐人录入考核成绩"
        if not people:
            return None, "本次结班没有可分档的人员，请先录入考核成绩"

        roster: list[dict[str, Any]] = []
        seen_names: set[str] = set()
        problems: list[str] = []
        for index, item in enumerate(people, start=1):
            if not isinstance(item, dict):
                problems.append(f"第 {index} 位人员的成绩条目格式不正确")
                continue
            name = str(item.get("姓名") or "").strip()
            if not name:
                problems.append(f"第 {index} 位人员的姓名未填写，无法登记成绩")
                continue
            if name in seen_names:
                problems.append(f"人员「{name}」在名单里重复出现，请核对后再收尾")
                continue
            seen_names.add(name)

            raw_score = str(item.get("成绩") if item.get("成绩") is not None else "").strip()
            if not raw_score:
                problems.append(f"人员「{name}」的考核成绩未填写")
                continue
            try:
                score = float(raw_score)
            except (TypeError, ValueError):
                problems.append(f"人员「{name}」的考核成绩「{raw_score}」不是数字")
                continue
            if not 0 <= score <= 100:
                problems.append(f"人员「{name}」的考核成绩 {raw_score} 不在 0 到 100 之间")
                continue
            roster.append({"姓名": name, "成绩": score, "档位": tier_of(score)})

        if problems:
            # 状态与旧台账原样保留，本次收尾不予通过
            return None, "本次收尾不予通过：" + "；".join(problems)

        counts = {tier: 0 for tier in TIERS}
        for person in roster:
            counts[person["档位"]] += 1

        self._close_seq += 1
        entry[LEDGER_KEY] = {
            "seq": self._close_seq,
            "培训编号": str(entry.get("培训编号") or ""),
            "培训主题": str(entry.get("培训主题") or ""),
            "人员": roster,
            "汇总": counts,
        }
        entry["status"] = CLOSED_STATUS
        entry["pending"] = False
        entry["abnormal"] = False
        summary = self._summary_text(counts)
        return entry, f"培训记录已确认结班，{summary}"

    @staticmethod
    def _summary_text(counts: dict[str, int]) -> str:
        return f"合格 {counts['合格']} 人、待补训 {counts['待补训']} 人、不合格 {counts['不合格']} 人"

    def grade_ledger(self) -> dict[str, Any]:
        """成绩分档台账：同编号取最后一次收尾，已取消的不计入，汇总数字与明细同源。"""
        ledgers = [
            (row, row[LEDGER_KEY])
            for row in store.rows(MODULE)
            if isinstance(row.get(LEDGER_KEY), dict)
        ]
        latest_seq: dict[str, int] = {}
        for _, ledger in ledgers:
            code = str(ledger.get("培训编号") or "")
            latest_seq[code] = max(latest_seq.get(code, 0), int(ledger.get("seq", 0)))

        totals = {tier: 0 for tier in TIERS}
        items: list[dict[str, Any]] = []
        retrain_groups: dict[str, dict[str, Any]] = {}

        for row, ledger in sorted(ledgers, key=lambda pair: int(pair[1].get("seq", 0))):
            code = str(ledger.get("培训编号") or "")
            topic = str(ledger.get("培训主题") or "")
            counts = {tier: int(ledger.get("汇总", {}).get(tier, 0)) for tier in TIERS}
            cancelled = row.get("status") == CANCELLED_STATUS
            superseded = int(ledger.get("seq", 0)) < latest_seq.get(code, 0)
            effective = not cancelled and not superseded
            if effective:
                for tier in TIERS:
                    totals[tier] += counts[tier]
                for person in ledger.get("人员", []):
                    if person.get("档位") != "待补训":
                        continue
                    group = retrain_groups.setdefault(
                        topic,
                        {"培训主题": topic, "人数": 0, "人员": []},
                    )
                    group["人数"] += 1
                    group["人员"].append({
                        "培训编号": code,
                        "姓名": person.get("姓名", ""),
                        "成绩": person.get("成绩", 0),
                    })

            items.append({
                "id": row.get("id"),
                "seq": int(ledger.get("seq", 0)),
                "培训编号": code,
                "培训主题": topic,
                "培训日期": row.get("培训日期"),
                "状态": row.get("status"),
                "汇总": counts,
                "分档结果": self._summary_text(counts),
                "人员": list(ledger.get("人员", [])),
                "有效": effective,
                "已取消": cancelled,
                "已覆盖": superseded,
            })

        groups = sorted(retrain_groups.values(), key=lambda group: group["培训主题"])
        retrain_total = sum(int(group["人数"]) for group in groups)
        return {
            "thresholds": {"合格": f"{SCORE_PASS}-100", "待补训": f"{SCORE_RETRAIN}-{SCORE_PASS - 1}", "不合格": f"0-{SCORE_RETRAIN - 1}"},
            "totals": totals,
            "总人数": sum(totals.values()),
            "结班数": sum(1 for item in items if item["有效"]),
            "items": items,
            "retraining_groups": groups,
            "retraining_total": retrain_total,
        }
