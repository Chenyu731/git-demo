"""貼牆版排版（需求 7.2）與列印前檢查。輸出結構同時供 HTML 預覽與 Excel 使用。"""
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Department, Extension, ExtNumber, Plant
from .common import dept_index, top_of
from .maintain import ext_status_map, is_manager

MAX_ROWS = 52  # 任一欄超過約 52 列時警告
TITLE_RANK = ["廠長", "副廠長", "處長", "部長", "經理", "副理", "課長", "副課長", "組長"]


@dataclass
class Row:
    kind: str  # title / item
    text: str = ""
    ext: int | None = None
    grade: str = ""
    fill: str | None = None  # y 黃 / c 淺青 / l 淺灰（標題）
    level: int = 0
    merge_key: str | None = None  # 相鄰同分機合併成一格
    empty: bool = False


@dataclass
class Layout:
    plant: str
    title: str
    revised: str
    columns: list[list[Row]] = field(default_factory=lambda: [[], [], []])
    warnings: list[str] = field(default_factory=list)
    footer: list[str] = field(default_factory=list)


def spaced(name: str) -> str:
    return "　".join(name)  # 第一層標題字間加全形空格，例如「生　產　一　部」


def _rank(title: str) -> int:
    for i, w in enumerate(TITLE_RANK):
        if title.startswith(w):
            return i
    return len(TITLE_RANK)


def _items_for(depts, recs, empties, dept_id, grades):
    """某部門自己的人員與單位，依排序；空號依分機接在前一支之後。"""
    rows = []
    for e in sorted((x for x in recs if x.department_id == dept_id), key=lambda x: (x.sort, x.id)):
        if e.type == "U":
            rows.append((e.ext or 0, Row("item", e.print_name or e.name, e.ext, grades.get(e.ext, ""))))
        elif e.personal_ext:
            label = f"{e.name} {e.title}".strip()
            rows.append((e.ext or 0, Row("item", label, e.ext, grades.get(e.ext, ""))))
    for ext in sorted(x for x, d in empties.items() if d == dept_id):
        er = Row("item", "", ext, grades.get(ext, ""), empty=True)
        pos = 0
        for i, (rx, _) in enumerate(rows):
            if rx and rx < ext:
                pos = i + 1
        rows.insert(pos, (ext, er))
    return [r for _, r in rows]


def build_wall(db: Session, plant: Plant, today: date | None = None) -> Layout:
    depts = dept_index(db, plant.id)
    grades = {n.ext: n.grade for n in db.scalars(select(ExtNumber).where(ExtNumber.plant_id == plant.id))}
    status = ext_status_map(db, plant.id)
    nums = {n.ext: n for n in db.scalars(select(ExtNumber).where(ExtNumber.plant_id == plant.id))}
    empties = {e: nums[e].department_id for e, s in status.items() if s == "空號" and nums[e].department_id}
    # 規則 1：啟用中、列入分機表、未標「不列」
    recs = [e for e in db.scalars(select(Extension).where(Extension.plant_id == plant.id, Extension.active.is_(True),
                                                          Extension.in_directory.is_(True),
                                                          Extension.hide_in_print.is_(False)))]
    d = today or date.today()
    lay = Layout(plant.name, f"{plant.name}各單位分機號碼表", f"{d.year}年{d.month:02d}月{d.day:02d}日",
                 footer=[ln for ln in plant.footer_text.splitlines() if ln.strip()])
    children: dict[int | None, list[Department]] = {}
    for x in depts.values():
        if x.active:
            children.setdefault(x.parent_id, []).append(x)
    for v in children.values():
        v.sort(key=lambda x: (x.sort, x.id))

    def has_personal(dept_id):
        return any(e.department_id == dept_id and e.type == "P" and e.personal_ext for e in recs)

    def block(dept: Department, level: int) -> list[Row]:
        rows: list[Row] = []
        show = dept.show_title or bool(children.get(dept.id)) or has_personal(dept.id)  # 規則 8
        if show:
            fill = dept.fill_color if dept.fill_color in ("y", "c") else ("y" if level == 0 else "l")
            rows.append(Row("title", spaced(dept.name) if level == 0 else dept.name, fill=fill, level=level))
        rows += _items_for(depts, recs, empties, dept.id, grades)
        for ch in children.get(dept.id, []):
            rows += block(ch, level + 1)
        return rows

    # 規則 5、6：無部門者置頂；最上層部門整塊同一欄
    cols: list[list[Row]] = [[], [], []]
    cols[0] += _items_for(depts, recs, empties, None, grades)
    tops = sorted(children.get(None, []), key=lambda x: (x.print_column or 1, x.print_order, x.id))
    for t in tops:
        c = min(max((t.print_column or 1), 1), 3) - 1
        cols[c] += block(t, 0)
    # 規則 9：區塊內相鄰同分機合併（欄內相鄰，且中間不隔標題）
    for col in cols:
        for i in range(1, len(col)):
            a, b = col[i - 1], col[i]
            if a.kind == b.kind == "item" and a.ext and a.ext == b.ext and not a.empty:
                key = a.merge_key or f"m{id(a)}"
                a.merge_key = b.merge_key = key
    lay.columns = cols
    lay.warnings = precheck(db, plant, depts, recs, cols)
    return lay


def precheck(db, plant, depts, recs, cols) -> list[str]:
    w: list[str] = []
    for e in recs:
        if e.type == "P" and is_manager(e.title) and not e.personal_ext:
            w.append(f"{e.name}（{e.title}）職稱為課長以上卻沒有個人分機")
    unit_depts = {e.department_id for e in recs if e.type == "U"}
    for e in recs:
        if e.type == "P" and not e.personal_ext and e.department_id not in unit_depts:
            w.append(f"{e.name} 使用部門公用分機，但該部門沒有單位紀錄（印不出來）")
    seen: dict[int, set] = {}
    for e in recs:
        if e.ext:
            seen.setdefault(e.ext, set()).add(top_of(depts, e.department_id) or 0)
    # 同分機出現在不同部門且都沒標不列：同一最上層內（共用公用分機）不算
    for ext, tops in sorted(seen.items()):
        if len(tops) > 1:
            names = "、".join(depts[t].name if t in depts else "置頂" for t in sorted(tops))
            w.append(f"分機 {ext} 同時出現在不同部門（{names}），都沒標「不列」")
    for t in (x for x in depts.values() if x.active and x.parent_id is None):
        if t.print_column not in (1, 2, 3):
            w.append(f"最上層部門「{t.name}」沒有指定欄")
    for i, col in enumerate(cols, 1):
        if len(col) > MAX_ROWS:
            w.append(f"第 {i} 欄有 {len(col)} 列，超過約 {MAX_ROWS} 列，一頁可能放不下")
    return w


def auto_balance(db: Session, plant: Plant) -> None:
    """自動平衡欄高：以最上層部門為單位，依序填入最短的欄。"""
    lay = build_wall(db, plant)
    depts = dept_index(db, plant.id)
    sizes = {}
    # 以現有版面計算各最上層部門列數
    tops = sorted((x for x in depts.values() if x.active and x.parent_id is None),
                  key=lambda x: (x.print_column or 1, x.print_order, x.id))
    for t in tops:
        solo = build_single(db, plant, t)
        sizes[t.id] = solo
    heights = [len(lay.columns[0]) - sum(sizes.get(t.id, 0) for t in tops if (t.print_column or 1) == 1)] + [0, 0]
    heights[0] = max(heights[0], 0)
    order = {1: 0, 2: 0, 3: 0}
    for t in tops:
        c = heights.index(min(heights))
        t.print_column = c + 1
        order[c + 1] += 1
        t.print_order = order[c + 1]
        heights[c] += sizes[t.id]


def build_single(db: Session, plant: Plant, top: Department) -> int:
    """某個最上層部門整塊的列數。"""
    depts = dept_index(db, plant.id)
    ids = {top.id}
    changed = True
    while changed:
        changed = False
        for x in depts.values():
            if x.parent_id in ids and x.id not in ids:
                ids.add(x.id)
                changed = True
    recs = db.scalars(select(Extension).where(Extension.plant_id == plant.id, Extension.active.is_(True),
                                              Extension.in_directory.is_(True), Extension.hide_in_print.is_(False),
                                              Extension.department_id.in_(ids)))
    n = sum(1 for e in recs if e.type == "U" or e.personal_ext)
    n += sum(1 for x in depts.values() if x.id in ids and x.active)  # 標題列（上限估計）
    status = ext_status_map(db, plant.id)
    n += sum(1 for n_ in db.scalars(select(ExtNumber).where(ExtNumber.plant_id == plant.id,
                                                            ExtNumber.department_id.in_(ids)))
             if status.get(n_.ext) == "空號")
    return n
