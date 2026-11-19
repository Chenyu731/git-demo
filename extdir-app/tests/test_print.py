import re
from io import BytesIO
from pathlib import Path

from openpyxl import load_workbook
from sqlalchemy import select

from app.models import Department, Extension
from app.services import exporter, maintain
from app.services.printlayout import MAX_ROWS, auto_balance, build_wall


def texts(col):
    return [r.text for r in col]


FIXTURE = Path(__file__).parent / "fixtures" / "plant1-wall.xlsx"  # 廠務提供的貼牆表（修訂 2026-07-08），標準答案


def _wall_chart_tokens():
    """把貼牆表 Excel 讀成每欄的 [("T", 標題) | ("I", 名稱, 分機, 等級)]，空白一律忽略；合併的分機欄補回數值。"""
    ws = load_workbook(FIXTURE).active
    norm = lambda s: re.sub(r"[\s\u3000]+", "", str(s or ""))  # noqa: E731
    merged_ext = {}
    for m in ws.merged_cells.ranges:
        if m.max_col == m.min_col and m.max_row > m.min_row:
            for r in range(m.min_row, m.max_row + 1):
                merged_ext[(r, m.min_col)] = ws.cell(m.min_row, m.min_col).value
    title_anchor = {(m.min_row, m.min_col) for m in ws.merged_cells.ranges if m.max_col - m.min_col == 2}
    cols = []
    for a in (1, 4, 7):
        col = []
        for r in range(3, 55):
            name, ext, grade = ws.cell(r, a).value, ws.cell(r, a + 1).value, ws.cell(r, a + 2).value
            ext = merged_ext.get((r, a + 1), ext)
            if (r, a) in title_anchor:
                col.append(("T", norm(name)))
            elif name is not None or ext is not None:
                col.append(("I", norm(name), ext, grade))
        cols.append(col)
    return cols


def _ours_tokens(lay):
    return [[("T", re.sub(r"[\s\u3000]+", "", r.text)) if r.kind == "title"
             else ("I", re.sub(r"[\s\u3000]+", "", r.text), r.ext, r.grade or None) for r in c] for c in lay.columns]


def test_wall_layout_matches_the_real_wall_chart_row_for_row(db, plant):
    """整張貼牆表逐列比對：標題、名稱、分機、等級、空號、順序都要一致。"""
    want, got = _wall_chart_tokens(), _ours_tokens(build_wall(db, plant))
    for g in range(3):
        assert got[g] == want[g], f"第 {g + 1} 欄不一致"


def test_seed_record_counts(db, plant):
    ext_rows = [r for c in build_wall(db, plant).columns for r in c if r.kind == "item"]
    assert len([r for r in ext_rows if not r.empty]) == 103  # 46 單位 + 57 人員
    assert sorted(r.ext for r in ext_rows if r.empty) == [614, 815, 816, 817, 818, 819]  # 現有空號


def test_pinned_block_first_and_top_dept_blocks_not_split(db, plant):
    lay = build_wall(db, plant)
    assert texts(lay.columns[0])[:4] == ["緊急專線", "總機", "陳坤木 廠長", "陳勳振 副廠長"]
    for c in lay.columns:
        titles = [r.text for r in c if r.kind == "title" and r.level == 0]
        assert len(titles) == len(set(titles))
    all_titles = [r.text.replace("　", "") for c in lay.columns for r in c if r.kind == "title" and r.level == 0]
    assert len(all_titles) == 14 and "生產一部" in all_titles


def test_title_rows_spaced_yellow_and_hidden_for_single_unit_groups(db, plant):
    lay = build_wall(db, plant)
    flat = [r for c in lay.columns for r in c]
    t = next(r for r in flat if r.text == "生　產　一　部")
    assert t.kind == "title" and t.fill == "y"
    assert "製一組" in texts(flat)
    assert not any(r.kind == "title" and r.text == "製一組" for r in flat)  # 印標題列關閉


def test_adjacent_same_ext_merged_not_distant(db, plant):
    flat = [r for c in build_wall(db, plant).columns for r in c]
    z1, z2 = (next(r for r in flat if r.text == n) for n in ("製一組", "製二組"))
    assert z1.merge_key and z1.merge_key == z2.merge_key  # 211
    h, j = (next(r for r in flat if r.text == n) for n in ("成品課 (H棟)", "乾燥課 (H棟)"))
    assert h.ext == j.ext == 541 and not (h.merge_key and h.merge_key == j.merge_key)  # 不相鄰各印各的


def test_empty_numbers_placed_in_dept_by_ext_order(db, plant):
    col = next(c for c in build_wall(db, plant).columns if any(r.empty and r.ext == 815 for r in c))
    i = next(i for i, r in enumerate(col) if r.empty and r.ext == 815)
    assert col[i].text == "" and col[i].grade == "A"
    assert [r.ext for r in col[i:i + 5]] == [815, 816, 817, 818, 819]
    assert col[i - 1].ext == 814  # 接在前一支分機之後


def test_hidden_and_not_in_directory_excluded(db, plant):
    e = db.scalar(select(Extension).where(Extension.name == "守衛室"))
    e.hide_in_print = True
    db.flush()
    assert "守衛室" not in texts([r for c in build_wall(db, plant).columns for r in c])
    assert any(x for x in [r for r in exporter.eip_rows(db, plant) if r[2] == "守衛室"])  # 「不列」只影響列印版


def test_precheck_warnings(db, plant):
    d = db.scalar(select(Department).where(Department.name == "品一課"))
    maintain.save_extension(db, "u", plant.id, None, {"type": "P", "name": "無分機課長", "title": "課長",
                                                       "department_id": d.id, "ext": "311", "personal_ext": False})
    w = build_wall(db, plant).warnings
    assert any("無分機課長" in x and "課長以上" in x for x in w)
    assert any("分機 613" in x for x in w)  # 總機 613 與總務課 613 並存，貼牆表現況，提醒廠務


def test_column_overflow_warning_and_auto_balance(db, plant):
    top = db.scalar(select(Department).where(Department.name == "總經理室"))
    for i in range(30):
        db.add(Extension(plant_id=plant.id, type="U", name=f"填充{i}", department_id=top.id, ext=900 + i, sort=9000 + i))
    for t in db.scalars(select(Department).where(Department.parent_id.is_(None))):
        t.print_column = 1
    db.flush()
    lay = build_wall(db, plant)
    assert len(lay.columns[0]) > MAX_ROWS and any("超過約" in w for w in lay.warnings)
    auto_balance(db, plant)
    db.flush()
    sizes = [len(c) for c in build_wall(db, plant).columns]
    assert max(sizes) - min(sizes) < 20 and max(sizes) < len(lay.columns[0])


def test_wall_xlsx_format(db, plant):
    lay = build_wall(db, plant)
    ws = load_workbook(BytesIO(exporter.wall_xlsx(lay, db, plant, "u"))).active
    assert ws.page_setup.orientation == "portrait" and ws.page_setup.scale == 80
    assert ws["A1"].value.startswith("一廠各單位分機號碼表") and ws["A1"].font.name == "標楷體"
    assert [ws.cell(2, c).value for c in range(1, 4)] == ["單位名稱", "分機號碼", "等級"]
    assert len(ws.merged_cells.ranges) > 20  # 標題列三格合併、同分機合併
    assert any("專線: 公司#80" in str(c.value) for row in ws.iter_rows() for c in row if c.value)


def test_eip_xlsx_columns_and_rows(db, plant):
    ws = load_workbook(BytesIO(exporter.eip_xlsx(db, plant, "u"))).active
    assert [c.value for c in ws[1]] == ["廠區／分公司", "部門", "姓名", "職稱", "市話", "分機", "簡碼", "備註"]
    rows = list(ws.iter_rows(min_row=2, values_only=True))
    assert len(rows) == 103
    q = next(r for r in rows if r[2] == "陳文斌")
    assert q[0] == "一廠" and q[1] == "品保部\\品二課" and q[3] == "課長" and q[4] == "03-386-8081" and q[5] == 320 and q[6] == "81"
