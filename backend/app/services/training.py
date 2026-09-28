"""资质培训业务规则：状态流转、字段校验与成绩分档台账都收在这里。"""
from __future__ import annotations

import csv
import io
from datetime import datetime
from typing import Any

from app import grading
from app.store import store

MODULE = "training"
LEDGER_MODULE = "training_ledger"
REQUIRED_FIELDS = ["培训编号", "培训主题", "培训对象"]
STATUS_ORDER = ["待开班", "进行中", "已结班", "已取消"]
ACTION_RULES = {"开班登记": "进行中", "确认结班": "已结班", "取消培训": "已取消"}
NEGATIVE_ACTIONS = []
CLOSE_ACTION = "确认结班"


class TrainingService:
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
        return rows[start:start + size], total

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
        values: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"培训记录 {entry_id} 不存在或已归档"
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于资质培训可执行范围"
        target = ACTION_RULES[action]
        if target not in STATUS_ORDER:
            return None, f"目标状态「{target}」不在允许的状态序列里"

        # 结班要带人员成绩做分档：成绩不合法则整批驳回，状态、台账都不变。
        if action == CLOSE_ACTION:
            return self._close_with_scores(entry, values or {})

        entry["status"] = target
        entry["pending"] = target != STATUS_ORDER[-1]
        entry["abnormal"] = action in NEGATIVE_ACTIONS
        return entry, f"培训记录已{action}"

    def _close_with_scores(
        self,
        entry: dict[str, Any],
        values: dict[str, Any],
    ) -> tuple[dict[str, Any] | None, str]:
        members, errors = grading.normalize_members(values.get("成绩明细"))
        if errors:
            # 把所有人的问题一次讲清楚，便于用户逐行修改后重新提交。
            return None, "本次收尾不予通过：" + "；".join(errors)
        if not members:
            return None, "本次收尾不予通过：至少需要一名人员的考核成绩才能结班"

        finished_at = datetime.now().strftime("%Y-%m-%d %H:%M")
        ledger = grading.build_ledger(entry, members, finished_at)
        # 同一培训编号重复收尾：以最后一次成绩覆盖旧分档结果。
        bucket = store.ledger_rows(LEDGER_MODULE)
        for index, item in enumerate(bucket):
            if item.get("培训编号") == entry["培训编号"]:
                bucket[index] = ledger
                break
        else:
            bucket.append(ledger)

        counts = ledger["分档结果"]
        entry["status"] = "已结班"
        entry["pending"] = False
        entry["abnormal"] = False
        entry["成绩明细"] = members
        entry["成绩分档"] = dict(counts)
        entry["结班时间"] = finished_at
        summary = "、".join(f"{tier}{counts[tier]}人" for tier in grading.TIER_ORDER)
        return entry, f"培训记录已{CLOSE_ACTION}，{summary}"

    def ledger_view(self) -> dict[str, Any]:
        """成绩分档台账：分档结果、图表人数、补训名单全部由同一份台账推导。"""
        ledgers = list(store.ledger_rows(LEDGER_MODULE))
        ledgers.sort(key=lambda item: str(item.get("结班时间") or ""))
        totals = grading.tier_totals(ledgers)
        groups = grading.remedial_groups(ledgers)
        remedial_total = sum(int(group["人数"]) for group in groups)
        return {
            "rule": grading.RULE_TEXT,
            "ledgers": ledgers,
            "totals": totals,
            "total_people": sum(totals.values()),
            "remedial_groups": groups,
            "remedial_total": remedial_total,
            "tier_order": grading.TIER_ORDER,
            "tier_colors": grading.TIER_COLORS,
        }

    def remedial_csv(self) -> str:
        """补训名单按培训主题归拢导出为 CSV（带 BOM，Excel 直接打开不乱码）。"""
        view = self.ledger_view()
        buffer = io.StringIO()
        buffer.write("﻿")  # UTF-8 BOM
        writer = csv.writer(buffer)
        writer.writerow(["培训主题", "培训编号", "姓名", grading.SCORE_FIELD, "分档", "结班时间"])
        for group in view["remedial_groups"]:
            theme = group["培训主题"]
            for item in group["items"]:
                writer.writerow([
                    theme,
                    item["培训编号"],
                    item["姓名"],
                    item[grading.SCORE_FIELD],
                    grading.TIER_REMEDIAL,
                    item["结班时间"],
                ])
        return buffer.getvalue()
