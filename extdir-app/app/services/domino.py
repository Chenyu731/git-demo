"""Domino 每日比對（需求第 5 節）。

n8n 每天取 Domino 完整名冊，POST 給 /api/internal/domino-sync；本模組依 5.3 規則：
能判斷的自動處理（可還原），判斷不了的進異動收件匣交廠務確認。
"""
import re
import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import Settings
from ..models import Department, DeptMap, DominoChange, DominoRoster, Extension
from .common import audit, ext_snapshot
from .maintain import RuleError, is_manager, save_extension

EXTERNAL_RE = re.compile(r"^f\d+@", re.I)  # Email 為 f＋數字：預設不列入（未經證實的預設規則，廠務可改）
PLANT_PREFIX = {"1": "一廠"}


def resolve_dept(db: Session, plant_id: int, plant_code: str, dep_name: str) -> Department | None:
    """名稱相同自動對應；貼牆表名稱接近 Domino（「噴乾一課」對「一廠噴乾一課」）。"""
    dep_name = (dep_name or "").strip()
    if not dep_name:
        return None
    m = db.scalar(select(DeptMap).where(DeptMap.plant_id == plant_id, DeptMap.domino_name == dep_name))
    if m:
        return db.get(Department, m.department_id)
    cands = [dep_name]
    pre = PLANT_PREFIX.get(plant_code, "")
    if pre and dep_name.startswith(pre):
        cands.append(dep_name[len(pre):])
    for c in cands:
        d = db.scalar(select(Department).where(Department.plant_id == plant_id, Department.name == c,
                                               Department.active.is_(True)))
        if d:
            return d
    return None


def _person_by_email(db: Session, plant_id: int, email: str) -> Extension | None:
    return db.scalar(select(Extension).where(Extension.plant_id == plant_id, Extension.type == "P",
                                             Extension.email == email, Extension.active.is_(True)))


def _add_change(db, plant_id, run_id, kind, status, p=None, **kw) -> DominoChange | None:
    email = (p or {}).get("email", "")
    if status == "pending":  # 同一件事不重複排隊
        dup = db.scalar(select(DominoChange.id).where(
            DominoChange.plant_id == plant_id, DominoChange.kind == kind, DominoChange.status == "pending",
            DominoChange.email == email, DominoChange.to_dep == kw.get("to_dep", "")))
        if dup:
            return None
    c = DominoChange(plant_id=plant_id, run_id=run_id, kind=kind, status=status, email=email,
                     name=(p or {}).get("name", ""), **kw)
    db.add(c)
    db.flush()
    return c


def link_emails_by_name(db: Session, plant_id: int, roster: list[dict]) -> dict:
    """第一版建置：以姓名比對 Domino 名冊補上 Email；同名或比對不到的交廠務確認。"""
    by_name: dict[str, list[dict]] = {}
    for r in roster:
        by_name.setdefault(r["name"], []).append(r)
    linked, ambiguous, missing = 0, [], []
    for e in db.scalars(select(Extension).where(Extension.plant_id == plant_id, Extension.type == "P",
                                                Extension.email.is_(None), Extension.active.is_(True))):
        hits = by_name.get(e.name, [])
        if len(hits) == 1 and not db.scalar(select(Extension.id).where(Extension.email == hits[0]["email"])):
            e.email = hits[0]["email"]
            linked += 1
        elif len(hits) > 1:
            ambiguous.append(e.name)
        else:
            missing.append(e.name)
    return {"linked": linked, "ambiguous": ambiguous, "not_found": missing}


def _upsert_roster(db: Session, p: dict) -> None:
    r = db.get(DominoRoster, p["email"])
    if not r:
        r = DominoRoster(email=p["email"], name=p["name"])
        db.add(r)
    r.name, r.dep, r.title, r.supervisor = p["name"], p.get("dep", ""), p.get("title", ""), p.get("supervisor", "")
    r.active, r.last_seen = True, datetime.now()


def _handle_new(db, plant, run_id, p) -> None:
    pid = plant.id
    dept = resolve_dept(db, pid, plant.code, p.get("dep", ""))
    title = p.get("title", "")
    if EXTERNAL_RE.match(p["email"]):
        e = Extension(plant_id=pid, type="P", name=p["name"], email=p["email"], title=title,
                      department_id=dept.id if dept else None, personal_ext=False, in_directory=False,
                      updated_by="system")
        db.add(e)
        db.flush()
        _add_change(db, pid, run_id, "new", "auto", p, to_dep=p.get("dep", ""), to_title=title,
                    reason="Email 為 f＋數字，設為不列入，不通知", after={"ext_id": e.id, "silent": True})
        return
    if not dept:
        _add_change(db, pid, run_id, "new_dept", "pending", p, to_dep=p.get("dep", ""),
                    reason="Domino 部門在部門表沒有對應（先指定部門）")
        _add_change(db, pid, run_id, "new", "pending", p, to_dep=p.get("dep", ""), to_title=title,
                    reason="部門對不上（部門處理完才能補分機）")
    elif is_manager(title):
        _add_change(db, pid, run_id, "new", "pending", p, to_dep=p.get("dep", ""), to_title=title,
                    reason="主管不會自動套用公用分機")
    elif not dept.default_ext:
        _add_change(db, pid, run_id, "new", "pending", p, to_dep=p.get("dep", ""), to_title=title,
                    reason="部門沒有預設分機")
    else:
        e = Extension(plant_id=pid, type="P", name=p["name"], email=p["email"], title=title,
                      department_id=dept.id, ext=dept.default_ext, personal_ext=False, updated_by="system")
        db.add(e)
        db.flush()
        _add_change(db, pid, run_id, "new", "auto", p, to_dep=p.get("dep", ""), to_title=title,
                    reason=f"部門對得上、非主管 → 使用公用分機 {dept.default_ext}", after={"ext_id": e.id})


def _handle_leave(db, plant, run_id, r: DominoRoster, hold: bool, reason_hold: str) -> None:
    pid = plant.id
    p = {"email": r.email, "name": r.name}
    e = _person_by_email(db, pid, r.email)
    if not e:
        return
    if e.personal_ext or hold:
        _add_change(db, pid, run_id, "leave", "pending", p, from_dep=r.dep, from_title=r.title,
                    reason=reason_hold if hold else "有個人分機，確認後號碼回到空號",
                    after={"ext_id": e.id})
    else:
        before = ext_snapshot(e)
        e.active = False
        e.updated_by = "system"
        _add_change(db, pid, run_id, "leave", "auto", p, from_dep=r.dep, from_title=r.title,
                    reason="使用公用分機 → 已停用（不刪除）", before={"ext_id": e.id, **before}, after={"ext_id": e.id})


def _handle_move(db, plant, run_id, old: DominoRoster, p: dict) -> None:
    pid = plant.id
    e = _person_by_email(db, pid, p["email"])
    if not e:
        return
    new_dept = resolve_dept(db, pid, plant.code, p.get("dep", ""))
    title = p.get("title", "")
    common = dict(from_dep=old.dep, to_dep=p.get("dep", ""), from_title=old.title, to_title=title)
    if e.personal_ext:
        _add_change(db, pid, run_id, "move", "pending", p, reason="有個人分機", after={"ext_id": e.id}, **common)
    elif not new_dept:
        _add_change(db, pid, run_id, "move", "pending", p, reason="新部門對不上", after={"ext_id": e.id}, **common)
    elif is_manager(title):
        _add_change(db, pid, run_id, "move", "pending", p, reason="調動後成為主管、沒有個人分機",
                    after={"ext_id": e.id}, **common)
    elif not new_dept.default_ext:
        _add_change(db, pid, run_id, "move", "pending", p, reason="新部門沒有預設分機",
                    after={"ext_id": e.id}, **common)
    else:
        before = ext_snapshot(e)
        e.department_id, e.ext, e.title, e.updated_by = new_dept.id, new_dept.default_ext, title, "system"
        _add_change(db, pid, run_id, "move", "auto", p, reason=f"新部門對得上 → 分機改為 {new_dept.default_ext}",
                    before={"ext_id": e.id, **before}, after={"ext_id": e.id}, **common)


def _handle_title(db, plant, run_id, old: DominoRoster, p: dict) -> None:
    pid = plant.id
    e = _person_by_email(db, pid, p["email"])
    if not e:
        return
    title = p.get("title", "")
    before = ext_snapshot(e)
    e.title, e.updated_by = title, "system"  # 系統的職稱以 Domino 為準
    common = dict(from_title=old.title, to_title=title)
    _add_change(db, pid, run_id, "title", "auto", p, reason="職稱以 Domino 為準",
                before={"ext_id": e.id, **before}, after={"ext_id": e.id}, **common)
    if is_manager(title) and not e.personal_ext:
        _add_change(db, pid, run_id, "promote", "pending", p, reason="職稱變為主管，且沒有個人分機", **common)


def sync(db: Session, plant, roster_in: list[dict], s: Settings, baseline: bool = False,
         bring_in_unlisted: bool = False) -> dict:
    run_id = uuid.uuid4().hex[:12]
    incoming: dict[str, dict] = {}
    for r in roster_in:
        email = (r.get("email") or "").strip().lower()
        if email:
            incoming[email] = {**r, "email": email, "name": (r.get("name") or "").strip()}
    if not incoming:
        raise RuleError("名冊是空的，拒絕處理（防止 API 回傳不完整）")
    old_rows = {r.email: r for r in db.scalars(select(DominoRoster))}

    if baseline:
        report = link_emails_by_name(db, plant.id, list(incoming.values()))
        for p in incoming.values():
            _upsert_roster(db, p)
        db.flush()
        if bring_in_unlisted:
            for p in incoming.values():
                if not _person_by_email(db, plant.id, p["email"]) and not db.scalar(
                        select(Extension.id).where(Extension.plant_id == plant.id, Extension.email == p["email"])):
                    _handle_new(db, plant, run_id, p)
        audit(db, "system", plant.id, "domino.baseline", run_id, after=report)
        db.commit()
        return {"run_id": run_id, "baseline": True, **report}

    active_old = {e: r for e, r in old_rows.items() if r.active}
    new_emails = [e for e in incoming if e not in active_old]
    left = [active_old[e] for e in active_old if e not in incoming]
    abnormal = bool(active_old) and (len(left) > s.domino_leave_abs_limit
                                     or len(left) / len(active_old) > s.domino_leave_ratio_limit)
    hold_reason = f"異常暫停：本次離職 {len(left)} 人，超過 {s.domino_leave_abs_limit} 人或 " \
                  f"{s.domino_leave_ratio_limit:.0%}，整批改為待確認"

    for e in new_emails:
        if abnormal:
            p = incoming[e]
            _add_change(db, plant.id, run_id, "new", "pending", p, to_dep=p.get("dep", ""), to_title=p.get("title", ""),
                        reason=hold_reason)
        else:
            _handle_new(db, plant, run_id, incoming[e])
    for r in left:
        _handle_leave(db, plant, run_id, r, abnormal, hold_reason)
    moved = []
    for e, p in incoming.items():
        old = active_old.get(e)
        if not old:
            continue
        if (old.dep or "") != (p.get("dep") or ""):
            moved.append((old, p))
        elif (old.title or "") != (p.get("title") or ""):
            if abnormal:
                _add_change(db, plant.id, run_id, "title", "pending", p, from_title=old.title,
                            to_title=p.get("title", ""), reason=hold_reason)
            else:
                _handle_title(db, plant, run_id, old, p)
    # 部門改名：同一批人同時從同一部門換到同一個對不上的新部門
    groups: dict[tuple[str, str], list] = {}
    for old, p in moved:
        groups.setdefault((old.dep, p.get("dep", "")), []).append((old, p))
    for (frm, to), items in groups.items():
        rename = len(items) >= 2 and resolve_dept(db, plant.id, plant.code, to) is None
        if rename:
            _add_change(db, plant.id, run_id, "rename_candidate", "pending", {"email": "", "name": f"{len(items)} 人"},
                        from_dep=frm, to_dep=to,
                        reason="同一批人同時換到同一個新部門，可能是部門改名：到部門表改名後整批套用")
        for old, p in items:
            if abnormal or rename:
                _add_change(db, plant.id, run_id, "move", "pending", p, from_dep=old.dep, to_dep=p.get("dep", ""),
                            from_title=old.title, to_title=p.get("title", ""),
                            reason=hold_reason if abnormal else "可能是部門改名（見上方）")
            else:
                _handle_move(db, plant, run_id, old, p)

    # 更新名冊。異常暫停時離職者維持 active，等廠務確認，避免下次被當成「新進」重複
    for p in incoming.values():
        _upsert_roster(db, p)
    if not abnormal:
        for r in left:
            r.active = False
    db.flush()
    counts = {k: db.scalar(select(func.count()).select_from(DominoChange)
                           .where(DominoChange.run_id == run_id, DominoChange.status == k)) for k in ("auto", "pending")}
    audit(db, "system", plant.id, "domino.sync", run_id, after={"abnormal": abnormal, "leave": len(left), **counts})
    db.commit()
    return {"run_id": run_id, "baseline": False, "abnormal": abnormal, "auto": counts["auto"],
            "pending": counts["pending"], "leave": len(left)}


def digest(db: Session, plant_id: int, run_id: str | None = None) -> dict:
    """每日彙整信內容：已自動處理（不含靜默）與待確認。n8n 取走後寄給廠務。"""
    q = select(DominoChange).where(DominoChange.plant_id == plant_id)
    if run_id:
        q = q.where(DominoChange.run_id == run_id)
    rows = list(db.scalars(q.order_by(DominoChange.id)))
    fmt = lambda c: {"id": c.id, "kind": c.kind, "name": c.name, "from": c.from_dep, "to": c.to_dep, "reason": c.reason}  # noqa: E731
    return {
        "auto": [fmt(c) for c in rows if c.status == "auto" and not (c.after or {}).get("silent")],
        "pending": [fmt(c) for c in rows if c.status == "pending"],
    }


# ---------- 收件匣動作 ----------

def _change(db: Session, plant_id: int, cid: int, want: tuple[str, ...]) -> DominoChange:
    c = db.get(DominoChange, cid)
    if not c or c.plant_id != plant_id or c.status not in want:
        raise RuleError("這筆異動不存在或狀態不對")
    return c


def undo(db: Session, actor: str, plant_id: int, cid: int) -> None:
    """自動處理的每一筆可一鍵還原。"""
    c = _change(db, plant_id, cid, ("auto",))
    ext_id = (c.after or {}).get("ext_id")
    e = db.get(Extension, ext_id) if ext_id else None
    if not e:
        raise RuleError("找不到要還原的紀錄")
    if c.kind == "new":
        e.active = False  # 新進建立的紀錄：停用（不刪除）
    elif c.before:
        for k, v in c.before.items():
            if k != "ext_id":
                setattr(e, k, v)
    r = db.get(DominoRoster, c.email) if c.email else None
    if r and c.kind == "leave":
        r.active = True
    e.updated_by = actor
    c.status = "undone"
    audit(db, actor, plant_id, "domino.undo", f"{c.kind}:{c.name}", c.before, c.after)


def skip(db: Session, actor: str, plant_id: int, cid: int) -> None:
    c = _change(db, plant_id, cid, ("pending",))
    c.status = "skipped"
    audit(db, actor, plant_id, "domino.skip", f"{c.kind}:{c.name}")


def map_dept(db: Session, actor: str, plant_id: int, cid: int, department_id: int) -> None:
    """部門對不上：指定放到哪個既有部門，對應一次後記住。"""
    c = _change(db, plant_id, cid, ("pending",))
    if c.kind != "new_dept":
        raise RuleError("這筆不是部門對應")
    d = db.get(Department, department_id)
    if not d or d.plant_id != plant_id:
        raise RuleError("部門不存在")
    if not db.scalar(select(DeptMap.id).where(DeptMap.plant_id == plant_id, DeptMap.domino_name == c.to_dep)):
        db.add(DeptMap(plant_id=plant_id, domino_name=c.to_dep, department_id=d.id))
    c.status = "applied"
    audit(db, actor, plant_id, "domino.map_dept", c.to_dep, None, {"department_id": d.id})


def confirm_new(db: Session, actor: str, plant_id: int, cid: int, data: dict) -> list[str]:
    """新進補分機：部門有預設就帶入，沒有就由廠務選；存檔後才加進「人員與單位」。"""
    c = _change(db, plant_id, cid, ("pending",))
    if c.kind != "new":
        raise RuleError("這筆不是新進")
    payload = {"type": "P", "name": c.name, "email": c.email, "title": c.to_title, **data}
    obj, warns = save_extension(db, actor, plant_id, None, payload)
    c.status, c.after = "applied", {"ext_id": obj.id}
    return warns


def confirm_leave(db: Session, actor: str, plant_id: int, cid: int) -> None:
    c = _change(db, plant_id, cid, ("pending",))
    if c.kind != "leave":
        raise RuleError("這筆不是離職")
    e = _person_by_email(db, plant_id, c.email)
    if e:
        e.active, e.updated_by = False, actor  # 分機自動回到空號（狀態由使用紀錄計算）
    r = db.get(DominoRoster, c.email)
    if r:
        r.active = False
    c.status = "applied"
    audit(db, actor, plant_id, "domino.confirm_leave", c.name)


def confirm_move(db: Session, actor: str, plant_id: int, cid: int, data: dict) -> list[str]:
    c = _change(db, plant_id, cid, ("pending",))
    if c.kind != "move":
        raise RuleError("這筆不是調部門")
    e = _person_by_email(db, plant_id, c.email)
    if not e:
        raise RuleError("找不到人員")
    payload = {"type": "P", "name": e.name, "email": e.email, "title": c.to_title or e.title,
               "department_id": data.get("department_id"), "ext": data.get("ext"),
               "personal_ext": data.get("personal_ext"), "in_directory": e.in_directory,
               "hide_in_print": e.hide_in_print, "note": e.note}
    _, warns = save_extension(db, actor, plant_id, e.id, payload)
    c.status = "applied"
    return warns


def ack(db: Session, actor: str, plant_id: int, cid: int) -> None:
    """promote / rename_candidate：廠務處理完（改人員或改部門名）後標為已處理。"""
    c = _change(db, plant_id, cid, ("pending",))
    c.status = "applied"
    audit(db, actor, plant_id, "domino.ack", f"{c.kind}:{c.name}")


def apply_rename(db: Session, actor: str, plant_id: int, cid: int, department_id: int) -> int:
    """部門改名整批套用：新 Domino 名稱對應到已改名的部門，該批待確認的調動標為已處理。"""
    c = _change(db, plant_id, cid, ("pending",))
    if c.kind != "rename_candidate":
        raise RuleError("這筆不是部門改名")
    d = db.get(Department, department_id)
    if not d or d.plant_id != plant_id:
        raise RuleError("部門不存在")
    if not db.scalar(select(DeptMap.id).where(DeptMap.plant_id == plant_id, DeptMap.domino_name == c.to_dep)):
        db.add(DeptMap(plant_id=plant_id, domino_name=c.to_dep, department_id=d.id))
    n = 0
    for m in db.scalars(select(DominoChange).where(
            DominoChange.plant_id == plant_id, DominoChange.kind == "move", DominoChange.status == "pending",
            DominoChange.from_dep == c.from_dep, DominoChange.to_dep == c.to_dep)):
        m.status = "applied"
        n += 1
    c.status = "applied"
    audit(db, actor, plant_id, "domino.apply_rename", f"{c.from_dep}→{c.to_dep}", None, {"people": n})
    return n
