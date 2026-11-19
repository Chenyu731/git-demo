"""第一版資料建立（需求第 8 節）：只從貼牆表建立。

來源 seed/plant1.json 由 demo-source/build_data.py 從貼牆表 Excel 產生（欄位 D/R/GR/EMPTY）。
舊 EIP 的共用人員（SH）不是資料來源，不匯入；未列名人員之後由 Domino 比對帶入。
"""
import json
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Department, Extension, ExtNumber, Plant
from .common import audit

SEED = Path(__file__).resolve().parents[2] / "seed" / "plant1.json"

FOOTER = "\n".join([
    "專線: 公司#80   一廠#81   二廠#82   三廠#83   四廠#84  聽到忙線音後直撥分機號碼，由總機小姐接聽，代轉分機。",
    "台北公司:TEL(02)2706-6006   FAX(02)2708-1254",
    "永光一廠:TEL(03)386-8081　 FAX(03)386-8048",
    "永光二廠:TEL(03)483-8088　 FAX(03)483-8008 | 中部辦事處:TEL(04)2358-3378      FAX(04)2358-2378",
    "永光三廠:TEL(03)483-7682 　FAX(03)483-7683 | 南部辦事處:TEL(06)215-2589　     FAX(06)215-3639",
    "永光四廠:TEL(03)473-7366 　FAX(03)473-7909",
    "上海明德專線：工廠撥打上海明德，先按#80，再按888，等響鈴聲結束後，再按66，由總機小姐接聽，代轉分機。",
])


def ensure_plant1(db: Session) -> Plant:
    p = db.scalar(select(Plant).where(Plant.code == "1"))
    if not p:
        p = Plant(code="1", name="一廠", phone="03-386-8081", short_code="81", footer_text=FOOTER)
        db.add(p)
        db.flush()
    return p


def seed_plant1(db: Session, path: Path = SEED) -> dict:
    """匯入一廠。已有部門資料時拒絕（避免覆蓋廠務已修改的內容）。"""
    plant = ensure_plant1(db)
    if db.scalar(select(Department.id).where(Department.plant_id == plant.id).limit(1)):
        raise RuntimeError("一廠已有資料，拒絕重複匯入")
    data = json.loads(path.read_text(encoding="utf-8"))

    by_key: dict[str, Department] = {}
    col_order: dict[int, int] = {}
    sib_order: dict[str | None, int] = {}
    for key, name, parent, fill, col, dflt, rng in data["D"]:
        sib_order[parent] = sib_order.get(parent, 0) + 1
        lo, hi = (int(x) for x in rng.split("-")) if rng else (None, None)
        d = Department(plant_id=plant.id, name=name, sort=sib_order[parent], default_ext=dflt,
                       ext_from=lo, ext_to=hi, fill_color=fill)
        if not parent:
            d.print_column = col
            col_order[col] = col_order.get(col, 0) + 1
            d.print_order = col_order[col]
        by_key[key] = d
        db.add(d)
    db.flush()
    for key, _name, parent, *_ in data["D"]:
        if parent:
            by_key[key].parent_id = by_key[parent].id

    n_units = n_people = 0
    first_dept_for_ext: dict[int, int | None] = {}
    for r in data["R"]:
        dept = by_key[r["d"]] if r["d"] else None
        if r["t"] == "U":
            e = Extension(plant_id=plant.id, type="U", name=r["n"], print_name=r.get("pn") or r["n"],
                          department_id=dept.id if dept else None, ext=r["ext"], personal_ext=False,
                          sort=r["sort"], note=r.get("note", ""), updated_by="seed")
            n_units += 1
        else:
            e = Extension(plant_id=plant.id, type="P", name=r["n"], title=r.get("title", ""),
                          department_id=dept.id if dept else None, ext=r["ext"], personal_ext=True,
                          sort=r["sort"], updated_by="seed")
            n_people += 1
        db.add(e)
        first_dept_for_ext.setdefault(r["ext"], dept.id if dept else None)

    # 「印標題列」（需求 4.3）：掛在「課」底下、沒有子部門、沒有個人分機人員、只有一個同名單位的組
    # （製一組、S棟…）不印標題列。紙技課、環保課、環資課雖然也只有一個同名單位，但上層是部，貼牆表有印標題列。
    for key, _name, parent, *_ in data["D"]:
        d = by_key[key]
        has_child = any(x[2] == key for x in data["D"])
        recs = [r for r in data["R"] if r["d"] == key]
        parent_is_ke = bool(parent) and by_key[parent].name.endswith("課")
        if (parent_is_ke and not has_child and len(recs) == 1 and recs[0]["t"] == "U"
                and (recs[0].get("pn") or recs[0]["n"]) == d.name):
            d.show_title = False

    # 分機號碼表：貼牆表上所有號碼（含等級）；空號掛在所屬部門
    empty = {int(k): v for k, v in data["EMPTY"].items()}
    for ext_s, grade in data["GR"].items():
        ext = int(ext_s)
        dept_id = by_key[empty[ext]].id if ext in empty else first_dept_for_ext.get(ext)
        db.add(ExtNumber(plant_id=plant.id, ext=ext, department_id=dept_id, grade=grade))
    audit(db, "system", plant.id, "seed", "plant1", after={"depts": len(by_key), "units": n_units, "people": n_people})
    db.commit()
    return {"departments": len(by_key), "units": n_units, "people": n_people,
            "ext_numbers": len(data["GR"]), "empty": len(empty)}
