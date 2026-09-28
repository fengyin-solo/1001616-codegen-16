"""资质培训接口：维护培训记录，覆盖开班登记、确认结班、取消培训与成绩分档台账。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

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


# 台账相关路由需排在 /{entry_id} 之前，否则「ledger」会被当成培训编号解析。
@router.get("/ledger")
def get_ledger() -> dict[str, Any]:
    """成绩分档台账：各档人数与按主题归拢的补训名单同源于一份分档结果。"""
    return service.ledger_view()


@router.get("/remedial-export")
def export_remedial() -> Response:
    """把待补训人员名单另存为 CSV 文件，按培训主题归拢。"""
    content = service.remedial_csv()
    filename = "remedial-list.csv"
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={filename}; filename*=utf-8''%E8%A1%A5%E8%AE%AD%E5%90%8D%E5%8D%95.csv"},
    )


@router.get("/export")
def export_entries() -> dict[str, Any]:
    """导出资质培训清单：返回当前过滤条件下的全量数据。"""
    items, total = service.list_entries(page=1, size=10000)
    return {"module": "training", "total": total, "items": items}


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
    """执行开班登记、确认结班、取消培训。

    确认结班需随动作提交「成绩明细」（每人姓名与考核成绩）：分数缺失或超出
    0 到 100 区间时整批驳回并指明人员与项；重复结班以最后一次成绩为准。
    """
    action = str(payload.values.get("action") or "").strip()
    entry, message = service.run_action(entry_id, action, payload.values)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)
