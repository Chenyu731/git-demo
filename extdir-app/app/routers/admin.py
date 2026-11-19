"""維護路由 /admin/*：一律要 OIDC 登入並屬於該廠廠務群組；所有 POST 都驗 CSRF。"""
from urllib.parse import quote

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..auth import csrf_token, require_admin, verify_csrf
from ..config import Settings, get_settings
from ..db import get_db
from ..models import AuditLog, Department, DeptMap, DominoChange, Extension, ExtNumber, PrintExport
from ..services import domino, exporter, maintain
from ..services.common import dept_index, dept_path, get_plant
from ..services.maintain import RuleError
from ..services.printlayout import auto_balance, build_wall

router = APIRouter(prefix="/admin", dependencies=[Depends(require_admin)])
PAGE = 50


def render(request: Request, name: str, **ctx):
    u = request.session.get("user", {})
    ctx.update(user=u, csrf=csrf_token(request), msg=request.query_params.get("msg", ""),
               err=request.query_params.get("err", ""))
    return request.app.state.templates.TemplateResponse(request, name, ctx)


def back(path: str, msg: str = "", err: str = "", warns: list[str] | None = None):
    q = []
    if err:
        q.append("err=" + quote(err))
    elif msg or warns:
        q.append("msg=" + quote("；".join([m for m in [msg, *(warns or [])] if m])))
    return RedirectResponse(path + ("?" + "&".join(q) if q else ""), status_code=303)


def actor(request: Request) -> str:
    return request.session["user"]["email"]


def plant_of(db: Session, s: Settings):
    return get_plant(db, s.default_plant)


# ---------- 異動收件匣（廠務首頁） ----------

@router.get("/")
def inbox(request: Request, db: Session = Depends(get_db), s: Settings = Depends(get_settings)):
    p = plant_of(db, s)
    def rows(status):
        return list(db.scalars(select(DominoChange).where(DominoChange.plant_id == p.id, DominoChange.status == status)
                               .order_by(DominoChange.id.desc()).limit(200)))
    depts = [d for d in dept_index(db, p.id).values() if d.active]
    return render(request, "inbox.html", pending=rows("pending"), auto=rows("auto"), depts=sorted(depts, key=lambda d: d.name))


@router.post("/inbox/{cid}/undo", dependencies=[Depends(verify_csrf)])
def inbox_undo(cid: int, request: Request, db: Session = Depends(get_db), s: Settings = Depends(get_settings)):
    try:
        domino.undo(db, actor(request), plant_of(db, s).id, cid)
        db.commit()
    except RuleError as e:
        return back("/admin/", err=str(e))
    return back("/admin/", "已還原")


@router.post("/inbox/{cid}/act", dependencies=[Depends(verify_csrf)])
def inbox_act(cid: int, request: Request, action: str = Form(...), department_id: str = Form(""), ext: str = Form(""),
              personal_ext: str = Form(""), db: Session = Depends(get_db), s: Settings = Depends(get_settings)):
    pid, who = plant_of(db, s).id, actor(request)
    warns: list[str] = []
    try:
        if action == "skip":
            domino.skip(db, who, pid, cid)
        elif action == "map_dept":
            domino.map_dept(db, who, pid, cid, int(department_id))
        elif action == "confirm_new":
            warns = domino.confirm_new(db, who, pid, cid, {"department_id": department_id, "ext": ext,
                                                           "personal_ext": bool(personal_ext)})
        elif action == "confirm_leave":
            domino.confirm_leave(db, who, pid, cid)
        elif action == "confirm_move":
            warns = domino.confirm_move(db, who, pid, cid, {"department_id": department_id, "ext": ext,
                                                            "personal_ext": bool(personal_ext)})
        elif action == "ack":
            domino.ack(db, who, pid, cid)
        elif action == "apply_rename":
            domino.apply_rename(db, who, pid, cid, int(department_id))
        else:
            raise RuleError("未知的動作")
        db.commit()
    except (RuleError, ValueError) as e:
        db.rollback()
        return back("/admin/", err=str(e))
    return back("/admin/", "已處理", warns=warns)


# ---------- 人員與單位 ----------

@router.get("/people")
def people(request: Request, q: str = "", dept: str = "", typ: str = "", inactive: str = "", page: int = 1,
           db: Session = Depends(get_db), s: Settings = Depends(get_settings)):
    p = plant_of(db, s)
    depts = dept_index(db, p.id)
    stmt = select(Extension).where(Extension.plant_id == p.id)
    if not inactive:
        stmt = stmt.where(Extension.active.is_(True))
    if typ in ("P", "U"):
        stmt = stmt.where(Extension.type == typ)
    if dept.isdigit():
        stmt = stmt.where(Extension.department_id == int(dept))
    if q.strip():
        like = f"%{q.strip()}%"
        cond = (Extension.name.like(like) | Extension.print_name.like(like) | Extension.email.like(like))
        if q.strip().isdigit():
            cond = cond | (Extension.ext == int(q.strip()))
        stmt = stmt.where(cond)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    all_total = db.scalar(select(func.count()).select_from(Extension).where(Extension.plant_id == p.id)) or 0
    rows = list(db.scalars(stmt.order_by(Extension.sort, Extension.id).offset((max(page, 1) - 1) * PAGE).limit(PAGE)))
    return render(request, "people.html", rows=rows, depts=depts, paths={i: dept_path(depts, i) for i in depts},
                  total=total, all_total=all_total, page=page, pages=(total + PAGE - 1) // PAGE,
                  f={"q": q, "dept": dept, "typ": typ, "inactive": inactive})


@router.get("/people/new")  # 必須排在 /people/{eid} 前面，否則 "new" 會被當成 eid 而回 422
def person_new(request: Request, db: Session = Depends(get_db), s: Settings = Depends(get_settings)):
    return person_form(request, None, db, s)


@router.get("/people/{eid}")
def person_form(request: Request, eid: int | None, db: Session = Depends(get_db), s: Settings = Depends(get_settings)):
    p = plant_of(db, s)
    obj = db.get(Extension, eid) if eid else None
    if eid and (not obj or obj.plant_id != p.id):
        return back("/admin/people", err="紀錄不存在")
    depts = dept_index(db, p.id)
    return render(request, "person_form.html", obj=obj, depts=depts, paths={i: dept_path(depts, i) for i in depts},
                  vac=maintain.vacancies(db, p.id, obj.department_id) if obj and obj.department_id else [])


@router.post("/people/save", dependencies=[Depends(verify_csrf)])
async def person_save(request: Request, db: Session = Depends(get_db), s: Settings = Depends(get_settings)):
    f = await request.form()
    data = {k: f.get(k) for k in ("type", "name", "print_name", "email", "department_id", "title", "ext", "note", "sort")}
    for flag in ("personal_ext", "in_directory", "hide_in_print"):
        data[flag] = bool(f.get(flag))
    eid = int(f["id"]) if f.get("id") else None
    p = plant_of(db, s)
    try:
        _, warns = maintain.save_extension(db, actor(request), p.id, eid, data)
        db.commit()
    except RuleError as e:
        db.rollback()
        return back(f"/admin/people/{eid}" if eid else "/admin/people/new", err=str(e))
    return back("/admin/people", "已儲存", warns=warns)


@router.post("/people/{eid}/active", dependencies=[Depends(verify_csrf)])
def person_active(eid: int, request: Request, active: str = Form("0"), db: Session = Depends(get_db),
                  s: Settings = Depends(get_settings)):
    try:
        maintain.set_active(db, actor(request), plant_of(db, s).id, eid, active == "1")
        db.commit()
    except RuleError as e:
        return back("/admin/people", err=str(e))
    return back("/admin/people", "已更新")


# ---------- 部門表 ----------

@router.get("/depts")
def depts_page(request: Request, db: Session = Depends(get_db), s: Settings = Depends(get_settings)):
    p = plant_of(db, s)
    depts = dept_index(db, p.id)
    kids: dict[int | None, list[Department]] = {}
    for d in depts.values():
        kids.setdefault(d.parent_id, []).append(d)
    flat: list[tuple[int, Department]] = []
    def walk(pid, lvl):
        for d in sorted(kids.get(pid, []), key=lambda x: (x.sort, x.id)):
            flat.append((lvl, d))
            walk(d.id, lvl + 1)
    walk(None, 0)
    maps = list(db.scalars(select(DeptMap).where(DeptMap.plant_id == p.id)))
    return render(request, "depts.html", flat=flat, depts=depts, maps=maps)


@router.post("/depts/create", dependencies=[Depends(verify_csrf)])
def dept_create(request: Request, name: str = Form(...), parent_id: str = Form(""), db: Session = Depends(get_db),
                s: Settings = Depends(get_settings)):
    try:
        maintain.create_dept(db, actor(request), plant_of(db, s).id, name, int(parent_id) if parent_id else None)
        db.commit()
    except RuleError as e:
        db.rollback()
        return back("/admin/depts", err=str(e))
    return back("/admin/depts", "已新增")


@router.post("/depts/{did}/op", dependencies=[Depends(verify_csrf)])
async def dept_op(did: int, request: Request, db: Session = Depends(get_db), s: Settings = Depends(get_settings)):
    f = await request.form()
    op, pid, who = f.get("op"), plant_of(db, s).id, actor(request)
    try:
        if op == "rename":
            maintain.rename_dept(db, who, pid, did, f.get("name", ""))
        elif op == "move":
            maintain.move_dept(db, who, pid, did, int(f["parent_id"]) if f.get("parent_id") else None)
        elif op in ("up", "down"):
            maintain.reorder_dept(db, who, pid, did, -1 if op == "up" else 1)
        elif op in ("disable", "enable"):
            maintain.set_dept_active(db, who, pid, did, op == "enable")
        elif op == "settings":
            maintain.save_dept_settings(db, who, pid, did, {**f, "show_title": bool(f.get("show_title"))})
        else:
            raise RuleError("未知的動作")
        db.commit()
    except (RuleError, ValueError) as e:
        db.rollback()
        return back("/admin/depts", err=str(e))
    return back("/admin/depts", "已更新")


# ---------- 分機號碼表 ----------

@router.get("/exts")
def exts_page(request: Request, dept: str = "", db: Session = Depends(get_db), s: Settings = Depends(get_settings)):
    p = plant_of(db, s)
    depts = dept_index(db, p.id)
    status = maintain.ext_status_map(db, p.id)
    stmt = select(ExtNumber).where(ExtNumber.plant_id == p.id).order_by(ExtNumber.ext)
    if dept.isdigit():
        stmt = stmt.where(ExtNumber.department_id == int(dept))
    return render(request, "exts.html", nums=list(db.scalars(stmt)), status=status, depts=depts,
                  paths={i: dept_path(depts, i) for i in depts}, dept=dept)


@router.post("/exts/save", dependencies=[Depends(verify_csrf)])
def ext_save(request: Request, ext: int = Form(...), department_id: str = Form(""), grade: str = Form("B"),
             note: str = Form(""), db: Session = Depends(get_db), s: Settings = Depends(get_settings)):
    try:
        maintain.save_ext_number(db, actor(request), plant_of(db, s).id, ext,
                                 {"department_id": department_id, "grade": grade, "note": note})
        db.commit()
    except RuleError as e:
        db.rollback()
        return back("/admin/exts", err=str(e))
    return back("/admin/exts", "已儲存")


# ---------- 列印版面與匯出 ----------

@router.get("/print")
def print_page(request: Request, db: Session = Depends(get_db), s: Settings = Depends(get_settings)):
    p = plant_of(db, s)
    lay = build_wall(db, p)
    last = {k: db.scalar(select(PrintExport.at).where(PrintExport.plant_id == p.id, PrintExport.kind == k)
                         .order_by(PrintExport.id.desc()).limit(1)) for k in ("eip", "wall")}
    return render(request, "print.html", lay=lay, last=last, rowspan=max(len(c) for c in lay.columns))


@router.post("/print/balance", dependencies=[Depends(verify_csrf)])
def print_balance(request: Request, db: Session = Depends(get_db), s: Settings = Depends(get_settings)):
    p = plant_of(db, s)
    auto_balance(db, p)
    maintain.audit(db, actor(request), p.id, "print.balance", "wall")
    db.commit()
    return back("/admin/print", "已自動平衡欄高")


XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@router.post("/export/eip", dependencies=[Depends(verify_csrf)])
def export_eip(request: Request, db: Session = Depends(get_db), s: Settings = Depends(get_settings)):
    p = plant_of(db, s)
    data = exporter.eip_xlsx(db, p, actor(request))
    maintain.audit(db, actor(request), p.id, "export.eip", p.name)
    db.commit()
    return Response(data, media_type=XLSX, headers={"Content-Disposition": f"attachment; filename=eip-plant{p.code}.xlsx"})


@router.post("/export/wall", dependencies=[Depends(verify_csrf)])
def export_wall(request: Request, db: Session = Depends(get_db), s: Settings = Depends(get_settings)):
    p = plant_of(db, s)
    data = exporter.wall_xlsx(build_wall(db, p), db, p, actor(request))
    maintain.audit(db, actor(request), p.id, "export.wall", p.name)
    db.commit()
    return Response(data, media_type=XLSX, headers={"Content-Disposition": f"attachment; filename=wall-plant{p.code}.xlsx"})


@router.get("/audit")
def audit_page(request: Request, page: int = 1, db: Session = Depends(get_db), s: Settings = Depends(get_settings)):
    p = plant_of(db, s)
    stmt = select(AuditLog).where((AuditLog.plant_id == p.id) | AuditLog.plant_id.is_(None)).order_by(AuditLog.id.desc())
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = list(db.scalars(stmt.offset((max(page, 1) - 1) * PAGE).limit(PAGE)))
    return render(request, "audit.html", rows=rows, page=page, pages=(total + PAGE - 1) // PAGE)

