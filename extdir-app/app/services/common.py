from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import AuditLog, Department, Plant


def get_plant(db: Session, code: str) -> Plant:
    p = db.scalar(select(Plant).where(Plant.code == code))
    if not p:
        raise LookupError(f"plant {code} not found")
    return p


def dept_index(db: Session, plant_id: int) -> dict[int, Department]:
    return {d.id: d for d in db.scalars(select(Department).where(Department.plant_id == plant_id))}


def dept_path(depts: dict[int, Department], dept_id: int | None, sep: str = " › ") -> str:
    names = []
    seen = set()
    while dept_id and dept_id in depts and dept_id not in seen:
        seen.add(dept_id)
        names.append(depts[dept_id].name)
        dept_id = depts[dept_id].parent_id
    return sep.join(reversed(names))


def top_of(depts: dict[int, Department], dept_id: int | None) -> int | None:
    seen = set()
    while dept_id and dept_id in depts and dept_id not in seen:
        seen.add(dept_id)
        p = depts[dept_id].parent_id
        if not p:
            return dept_id
        dept_id = p
    return None


def audit(db: Session, actor: str, plant_id: int | None, action: str, target: str = "",
          before: dict | None = None, after: dict | None = None) -> None:
    db.add(AuditLog(actor=actor, plant_id=plant_id, action=action, target=target, before=before, after=after))


def ext_snapshot(e) -> dict:
    return {c: getattr(e, c) for c in (
        "type", "name", "print_name", "email", "department_id", "title", "ext", "personal_ext",
        "in_directory", "hide_in_print", "sort", "active", "note")}
