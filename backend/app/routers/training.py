"""资质培训接口：维护培训记录，覆盖开班登记、确认结班、取消培训等动作。

确认结班时随动作提交人员考核成绩，服务端逐人校验分档；成绩分档台账与补训名单
都从同一份台账数据汇总，保证培训记录、分档结果、补训名单上的数字一致。
"""
from __future__ import annotations

import csv
import io
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from app.schemas import ActionResult, EntryPayload, PageResult
from app.services.training import TrainingService

router = APIRouter(prefix="/api/training", tags=["资质培训"])

service = TrainingService()

LIST_FIELDS = ["培训编号", "培训主题", "培训对象", "授课人员", "培训课时", "考核成绩", "培训日期", "培训状态"]
STATUSES = ["待开班", "进行中", "已结班", "已取消"]


@router.get("", response_model=PageResult[dict])
def list_entries(
    keyword: str | None = Query(default=None, description="按培训编号检索"),
    status: str | None = Query(default=None, description="待开班、进行中、已结班、已取消"),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """按培训编号与状态过滤资质培训列表；没有数据时返回空页，不报错。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    items, total = service.list_entries(keyword=keyword, status=status, page=page, size=size)
    return PageResult(items=items, total=total, page=page, size=size)


@router.get("/grade-ledger")
def grade_ledger() -> dict[str, Any]:
    """成绩分档台账：各档人数、分档明细与按培训主题归拢的补训名单在同一处返回。"""
    return service.grade_ledger()


@router.get("/retraining/export")
def export_retraining() -> StreamingResponse:
    """把补训名单另存成 CSV 文件：与台账同源，页面刷新后数字保持一致。"""
    ledger = service.grade_ledger()
    buffer = io.StringIO()
    buffer.write("﻿")  # 带 BOM，Excel 直接打开不乱码
    writer = csv.writer(buffer)
    writer.writerow(["培训主题", "培训编号", "姓名", "考核成绩", "档位"])

    def display_score(value: float) -> str:
        return str(int(value)) if float(value).is_integer() else str(value)

    for group in ledger["retraining_groups"]:
        for person in group["人员"]:
            writer.writerow([
                group["培训主题"],
                person["培训编号"],
                person["姓名"],
                display_score(float(person["成绩"])),
                "待补训",
            ])
    buffer.seek(0)
    headers = {"Content-Disposition": "attachment; filename=retraining-roster.csv"}
    return StreamingResponse(iter([buffer.getvalue()]), media_type="text/csv; charset=utf-8", headers=headers)


@router.get("/{entry_id}", response_model=dict)
def get_entry(entry_id: int) -> dict:
    """读取单条培训记录明细；不存在时给出可读的错误说明。"""
    entry = service.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"培训记录 {entry_id} 不存在或已归档")
    return entry


@router.post("", response_model=ActionResult)
def create_entry(payload: EntryPayload) -> ActionResult:
    """登记一条培训记录，缺字段时说明原因而不是静默丢弃。"""
    entry, missing = service.create_entry(payload.values)
    if missing:
        return ActionResult(ok=False, message=f"缺少必填字段：{'、'.join(missing)}")
    return ActionResult(ok=True, message="培训记录已登记", entry=entry)


@router.post("/{entry_id}/actions", response_model=ActionResult)
def run_action(entry_id: int, payload: EntryPayload) -> ActionResult:
    """对单条培训记录执行开班登记、确认结班、取消培训；不允许的动作会被拦下并说明原因。

    确认结班时需在 values.人员成绩 里提交逐人成绩（姓名、成绩），
    成绩缺失或不在 0 到 100 之间的，本次收尾不予通过并指出具体人员。
    """
    action = str(payload.values.get("action") or "").strip()
    people = payload.values.get("人员成绩") if action == "确认结班" else None
    entry, message = service.run_action(entry_id, action, people)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)


@router.get("/export")
def export_entries() -> dict[str, Any]:
    """导出资质培训清单：返回当前过滤条件下的全量数据。"""
    items, total = service.list_entries(page=1, size=10000)
    return {"module": "training", "total": total, "items": items}
