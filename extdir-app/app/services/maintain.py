"""維護規則（需求第 4、6 節）。路由只做驗證與轉送，規則集中在這裡以便測試。"""
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import Department, Extension, ExtNumber
from .common import audit, dept_index, ext_snapshot

MANAGER_WORDS = ("廠長", "處長", "部長", "經理", "副理", "課長")  # 課長以上；「副課長」「組長」不算


class RuleError(ValueError):
    """違反業務規則；路由回 400 並顯示訊息。"""


def is_manager(title: str) -> bool:
    t = (title or "").strip()
    if not t or t.startswith("副課長"):
        return False
    return any(w in t for w in MANAGER_WORDS)


def _int_or_none(v):
    if v in (None, ""):
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        raise RuleError(f"分機必須是數字：{v}") from None


# ---------- 人員與單位 ----------

def ensure_ext_number(db: Session, plant_id: int, ext: int | None, dept_id: int | None) -> list[str]:
    """分機不在號碼表就建立（等級預設 B）；回傳提醒訊息（不擋）。"""
    warnings = []
    if ext is None:
        return warnings
    num = db.scalar(select(ExtNumber).where(ExtNumber.plant_id == plant_id, ExtNumber.ext == ext))
    if not num:
        db.add(ExtNumber(plant_id=plant_id, ext=ext, department_id=dept_id, grade="B"))
        warnings.append(f"分機 {ext} 原本不在號碼表，已新增（等級 B），請確認等級")
        return warnings
    dept = db.get(Department, dept_id) if dept_id else None
    if dept and dept.ext_from and dept.ext_to and not (dept.ext_from <= ext <= dept.ext_to):
        warnings.append(f"分機 {ext} 不在「{dept.name}」的號段 {dept.ext_from}-{dept.ext_to}（只提醒）")
    return warnings


def save_extension(db: Session, actor: str, plant_id: int, ext_id: int | None, data: dict) -> tuple[Extension, list[str]]:
    typ = data.get("type", "P")
    if typ not in ("P", "U"):
        raise RuleError("類型必須是人員或單位")
    name = (data.get("name") or "").strip()
    if not name:
        raise RuleError("名稱不可空白")
    ext = _int_or_none(data.get("ext"))
    dept_id = _int_or_none(data.get("department_id"))
    if dept_id:
        d = db.get(Department, dept_id)
        if not d or d.plant_id != plant_id:
            raise RuleError("部門不存在")
    personal = bool(data.get("personal_ext")) if typ == "P" else False
    if typ == "P" and personal and ext is None:
        raise RuleError("有個人分機必須填分機")

    # 重複：只有「名稱與分機都相同」才視為重複（同部門內列印名稱可重複，靠分機區分）
    q = select(Extension.id).where(Extension.plant_id == plant_id, Extension.active.is_(True), Extension.type == typ,
                                   Extension.name == name, Extension.ext == ext,
                                   Extension.department_id == dept_id)
    if ext_id:
        q = q.where(Extension.id != ext_id)
    if db.scalar(q.limit(1)):
        raise RuleError("已有名稱與分機都相同的紀錄")

    obj = db.get(Extension, ext_id) if ext_id else Extension(plant_id=plant_id, type=typ)
    if ext_id and (not obj or obj.plant_id != plant_id):
        raise RuleError("紀錄不存在")
    before = ext_snapshot(obj) if ext_id else None
    obj.type = typ
    obj.name = name
    obj.print_name = (data.get("print_name") or name).strip() if typ == "U" else None
    obj.email = (data.get("email") or "").strip().lower() or None if typ == "P" else None
    obj.department_id = dept_id
    obj.title = (data.get("title") or "").strip() if typ == "P" else ""
    obj.ext = ext
    obj.personal_ext = personal
    obj.in_directory = bool(data.get("in_directory", True))
    obj.hide_in_print = bool(data.get("hide_in_print", False))
    obj.note = (data.get("note") or "").strip()
    if data.get("sort") not in (None, ""):
        obj.sort = _int_or_none(data["sort"])
    elif not ext_id:
        obj.sort = (db.scalar(select(func.max(Extension.sort)).where(Extension.plant_id == plant_id)) or 0) + 1
    obj.updated_by = actor
    if not ext_id:
        db.add(obj)
    db.flush()
    warnings = ensure_ext_number(db, plant_id, ext, dept_id)
    if typ == "P" and is_manager(obj.title) and not personal:
        warnings.append("職稱為課長以上卻沒有個人分機（只提醒）")
    audit(db, actor, plant_id, "ext.update" if ext_id else "ext.create", f"{typ}:{name}", before, ext_snapshot(obj))
    return obj, warnings


def set_active(db: Session, actor: str, plant_id: int, ext_id: int, active: bool) -> Extension:
    """人員與單位只停用、不刪除。"""
    obj = db.get(Extension, ext_id)
    if not obj or obj.plant_id != plant_id:
        raise RuleError("紀錄不存在")
    before = ext_snapshot(obj)
    obj.active = active
    obj.updated_by = actor
    audit(db, actor, plant_id, "ext.enable" if active else "ext.disable", f"{obj.type}:{obj.name}", before, ext_snapshot(obj))
    return obj


# ---------- 分機號碼表 ----------

def ext_status_map(db: Session, plant_id: int) -> dict[int, str]:
    used = set(db.scalars(select(Extension.ext).where(Extension.plant_id == plant_id, Extension.active.is_(True),
                                                      Extension.ext.is_not(None))))
    return {n.ext: ("使用中" if n.ext in used else "空號")
            for n in db.scalars(select(ExtNumber).where(ExtNumber.plant_id == plant_id))}


def vacancies(db: Session, plant_id: int, dept_id: int) -> list[int]:
    st = ext_status_map(db, plant_id)
    return sorted(n.ext for n in db.scalars(select(ExtNumber).where(
        ExtNumber.plant_id == plant_id, ExtNumber.department_id == dept_id)) if st.get(n.ext) == "空號")


def save_ext_number(db: Session, actor: str, plant_id: int, ext: int, data: dict) -> ExtNumber:
    grade = (data.get("grade") or "B").upper()
    if grade not in ("A", "B"):
        raise RuleError("等級只能是 A 或 B")
    num = db.scalar(select(ExtNumber).where(ExtNumber.plant_id == plant_id, ExtNumber.ext == ext))
    before = None
    if num:
        before = {"department_id": num.department_id, "grade": num.grade, "note": num.note}
    else:
        num = ExtNumber(plant_id=plant_id, ext=ext)
        db.add(num)
    num.department_id = _int_or_none(data.get("department_id"))
    num.grade = grade  # 等級屬於分機號碼：改一次，所有使用者跟著變
    num.note = (data.get("note") or "").strip()
    audit(db, actor, plant_id, "extnum.update", str(ext), before,
          {"department_id": num.department_id, "grade": num.grade, "note": num.note})
    return num


# ---------- 部門表 ----------

def _check_unique_name(db: Session, plant_id: int, parent_id: int | None, name: str, self_id: int | None = None):
    q = select(Department.id).where(Department.plant_id == plant_id, Department.name == name,
                                    Department.active.is_(True),
                                    Department.parent_id.is_(None) if parent_id is None else Department.parent_id == parent_id)
    if self_id:
        q = q.where(Department.id != self_id)
    if db.scalar(q.limit(1)):
        raise RuleError(f"同一層已有「{name}」")


def create_dept(db: Session, actor: str, plant_id: int, name: str, parent_id: int | None = None) -> Department:
    name = name.strip()
    if not name:
        raise RuleError("部門名稱不可空白")
    _check_unique_name(db, plant_id, parent_id, name)
    sib = db.scalar(select(func.max(Department.sort)).where(
        Department.plant_id == plant_id,
        Department.parent_id.is_(None) if parent_id is None else Department.parent_id == parent_id)) or 0
    d = Department(plant_id=plant_id, parent_id=parent_id, name=name, sort=sib + 1)
    if parent_id is None:
        d.print_column = 1
        d.print_order = (db.scalar(select(func.max(Department.print_order)).where(
            Department.plant_id == plant_id, Department.parent_id.is_(None), Department.print_column == 1)) or 0) + 1
    db.add(d)
    db.flush()
    audit(db, actor, plant_id, "dept.create", name, None, {"parent_id": parent_id})
    return d


def rename_dept(db: Session, actor: str, plant_id: int, dept_id: int, name: str) -> Department:
    d = db.get(Department, dept_id)
    name = name.strip()
    if not d or d.plant_id != plant_id or not name:
        raise RuleError("部門不存在或名稱空白")
    _check_unique_name(db, plant_id, d.parent_id, name, d.id)
    old, d.name = d.name, name  # 底下人員以 department_id 關聯，自動跟著變
    audit(db, actor, plant_id, "dept.rename", old, {"name": old}, {"name": name})
    return d


def move_dept(db: Session, actor: str, plant_id: int, dept_id: int, new_parent_id: int | None) -> Department:
    depts = dept_index(db, plant_id)
    d = depts.get(dept_id)
    if not d:
        raise RuleError("部門不存在")
    if new_parent_id is not None:
        if new_parent_id not in depts:
            raise RuleError("目的地不存在")
        cur = new_parent_id
        while cur:  # 不能搬到自己底下
            if cur == dept_id:
                raise RuleError("不能搬到自己的子部門底下")
            cur = depts[cur].parent_id
    _check_unique_name(db, plant_id, new_parent_id, d.name, d.id)  # 目的地有同名就擋下
    before = {"parent_id": d.parent_id}
    d.parent_id = new_parent_id
    d.sort = (db.scalar(select(func.max(Department.sort)).where(
        Department.plant_id == plant_id,
        Department.parent_id.is_(None) if new_parent_id is None else Department.parent_id == new_parent_id)) or 0) + 1
    if new_parent_id is None:
        d.print_column = d.print_column or 1
    else:
        d.print_column = None
    audit(db, actor, plant_id, "dept.move", d.name, before, {"parent_id": new_parent_id})
    return d


def reorder_dept(db: Session, actor: str, plant_id: int, dept_id: int, direction: int) -> None:
    d = db.get(Department, dept_id)
    if not d or d.plant_id != plant_id:
        raise RuleError("部門不存在")
    sibs = list(db.scalars(select(Department).where(
        Department.plant_id == plant_id, Department.active.is_(True),
        Department.parent_id.is_(None) if d.parent_id is None else Department.parent_id == d.parent_id
    ).order_by(Department.sort, Department.id)))
    i = sibs.index(d)
    j = i + (1 if direction > 0 else -1)
    if 0 <= j < len(sibs):
        sibs.insert(j, sibs.pop(i))
        for n, x in enumerate(sibs, 1):
            x.sort = n
        audit(db, actor, plant_id, "dept.reorder", d.name)


def set_dept_active(db: Session, actor: str, plant_id: int, dept_id: int, active: bool) -> Department:
    d = db.get(Department, dept_id)
    if not d or d.plant_id != plant_id:
        raise RuleError("部門不存在")
    if not active:
        has_child = db.scalar(select(Department.id).where(Department.parent_id == d.id, Department.active.is_(True)).limit(1))
        has_rec = db.scalar(select(Extension.id).where(Extension.department_id == d.id, Extension.active.is_(True)).limit(1))
        if has_child or has_rec:
            raise RuleError("底下還有部門、人員或單位，不能停用")
    d.active = active
    audit(db, actor, plant_id, "dept.enable" if active else "dept.disable", d.name)
    return d


def save_dept_settings(db: Session, actor: str, plant_id: int, dept_id: int, data: dict) -> Department:
    d = db.get(Department, dept_id)
    if not d or d.plant_id != plant_id:
        raise RuleError("部門不存在")
    before = {k: getattr(d, k) for k in ("default_ext", "ext_from", "ext_to", "print_column", "print_order",
                                         "fill_color", "show_title")}
    d.default_ext = _int_or_none(data.get("default_ext"))
    d.ext_from = _int_or_none(data.get("ext_from"))
    d.ext_to = _int_or_none(data.get("ext_to"))
    d.show_title = bool(data.get("show_title"))
    fill = (data.get("fill_color") or "").strip() or None
    if fill not in (None, "y", "c"):
        raise RuleError("底色只能是 y（黃）或 c（淺青）")
    d.fill_color = fill
    if d.parent_id is None:
        col = _int_or_none(data.get("print_column")) or 1
        if col not in (1, 2, 3):
            raise RuleError("欄只能是 1～3")
        d.print_column = col
        d.print_order = _int_or_none(data.get("print_order")) or d.print_order
    audit(db, actor, plant_id, "dept.settings", d.name, before,
          {k: getattr(d, k) for k in before})
    return d
