"""公開查詢專用查詢（需求第 3 節）。

刻意與維護頁分開寫：固定只回傳姓名、部門、職稱、分機、等級。
日後在 Extension 加欄位（email、工號…）也不會因此洩漏到公開頁。
"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Department, Extension, ExtNumber
from .common import dept_index, dept_path, top_of

PUBLIC_FIELDS = ("name", "dept", "title", "ext", "grade")


def public_search(db: Session, plant_id: int, q: str = "", top_dept_id: int | None = None, limit: int = 500) -> list[dict]:
    depts = dept_index(db, plant_id)
    grades = {n.ext: n.grade for n in db.scalars(select(ExtNumber).where(ExtNumber.plant_id == plant_id))}
    rows = db.scalars(
        select(Extension)
        .where(Extension.plant_id == plant_id, Extension.active.is_(True), Extension.in_directory.is_(True))
        .order_by(Extension.sort, Extension.id)
    )
    needle = q.strip().lower()
    out = []
    for e in rows:
        if top_dept_id and top_of(depts, e.department_id) != top_dept_id:
            continue
        name = (e.print_name or e.name) if e.type == "U" else e.name
        path = dept_path(depts, e.department_id)
        rec = {"name": name, "dept": path, "title": e.title or "", "ext": e.ext, "grade": grades.get(e.ext, "")}
        if needle and needle not in " ".join(str(rec[k]) for k in PUBLIC_FIELDS).lower():
            continue
        out.append(rec)
        if len(out) >= limit:
            break
    return out


def public_top_depts(db: Session, plant_id: int) -> list[dict]:
    ds = db.scalars(
        select(Department)
        .where(Department.plant_id == plant_id, Department.parent_id.is_(None), Department.active.is_(True))
        .order_by(Department.print_column, Department.print_order)
    )
    return [{"id": d.id, "name": d.name} for d in ds]
