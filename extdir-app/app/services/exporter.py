"""匯出：EIP 上傳 Excel（7.1）與貼牆版 Excel（7.2）。"""
from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Extension, Plant, PrintExport
from .common import dept_index, dept_path
from .printlayout import Layout

FILLS = {"y": "FFFF00", "c": "CCFFFF", "l": "F2F2F2"}
THIN = Side(style="thin", color="000000")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)


def eip_rows(db: Session, plant: Plant) -> list[list]:
    """列出該廠所有啟用且「列入分機表」的人員與單位；「不列」只影響列印版。"""
    depts = dept_index(db, plant.id)
    out = []
    q = select(Extension).where(Extension.plant_id == plant.id, Extension.active.is_(True),
                                Extension.in_directory.is_(True)).order_by(Extension.sort, Extension.id)
    for e in db.scalars(q):
        name = (e.print_name or e.name) if e.type == "U" else e.name
        out.append([plant.name, dept_path(depts, e.department_id, "\\"), name, e.title or "", plant.phone,
                    e.ext if e.ext is not None else "", plant.short_code, e.note or ""])
    return out


def eip_xlsx(db: Session, plant: Plant, actor: str) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "EIP"
    ws.append(["廠區／分公司", "部門", "姓名", "職稱", "市話", "分機", "簡碼", "備註"])
    for r in eip_rows(db, plant):
        ws.append(r)
    for c in ws[1]:
        c.font = Font(bold=True)
    db.add(PrintExport(plant_id=plant.id, kind="eip", by=actor))
    bio = BytesIO()
    wb.save(bio)
    return bio.getvalue()


def wall_xlsx(lay: Layout, db: Session, plant: Plant, actor: str) -> bytes:
    """A4 直式、縮放 80%、三組並排（每組：單位名稱／分機號碼／等級）、一頁印完。"""
    wb = Workbook()
    ws = wb.active
    ws.title = lay.title
    font = Font(name="標楷體", size=12, bold=True)
    mid = Alignment(horizontal="center", vertical="center")
    ws.merge_cells("A1:I1")
    ws["A1"] = f"{lay.title}　修訂日期：{lay.revised}"
    ws["A1"].font = Font(name="標楷體", size=18, bold=True)
    ws["A1"].alignment = mid
    for g in range(3):
        for j, h in enumerate(("單位名稱", "分機號碼", "等級")):
            c = ws.cell(2, g * 3 + 1 + j, h)
            c.font, c.alignment, c.border = font, mid, BORDER
    height = max(len(c) for c in lay.columns)
    for g, col in enumerate(lay.columns):
        c0 = g * 3 + 1
        i = 0
        while i < len(col):
            r = 3 + i
            row = col[i]
            if row.kind == "title":
                ws.merge_cells(start_row=r, start_column=c0, end_row=r, end_column=c0 + 2)
                cell = ws.cell(r, c0, row.text)
                cell.font, cell.alignment = font, mid
                for j in range(3):
                    ws.cell(r, c0 + j).border = BORDER
                    ws.cell(r, c0 + j).fill = PatternFill("solid", fgColor=FILLS.get(row.fill or "l", "F2F2F2"))
                i += 1
                continue
            run = 1
            while row.merge_key and i + run < len(col) and col[i + run].merge_key == row.merge_key:
                run += 1
            for k in range(run):
                x = col[i + k]
                for j, v in enumerate((x.text, x.ext if x.ext is not None else "", x.grade)):
                    c = ws.cell(r + k, c0 + j, v)
                    c.font, c.alignment, c.border = font, mid, BORDER
            if run > 1:
                ws.merge_cells(start_row=r, start_column=c0 + 1, end_row=r + run - 1, end_column=c0 + 1)
            i += run
    for ln, row in enumerate(lay.footer):  # 檔尾：撥號規則、各廠 TEL/FAX、辦事處
        r = 3 + height + 1 + ln
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=9)
        ws.cell(r, 1, row).font = Font(name="標楷體", size=11)
        ws.cell(r, 1).alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)
    for letter, w in zip("ABCDEFGHI", (22, 9, 6) * 3, strict=True):
        ws.column_dimensions[letter].width = w
    last = 3 + height + len(lay.footer) + 1
    ws.print_area = f"A1:I{last}"
    ws.page_setup.paperSize = ws.PAPERSIZE_A4
    ws.page_setup.orientation = "portrait"
    ws.page_setup.scale = 80
    ws.sheet_properties.pageSetUpPr.fitToPage = False
    db.add(PrintExport(plant_id=plant.id, kind="wall", by=actor))
    bio = BytesIO()
    wb.save(bio)
    return bio.getvalue()
