"""資料模型，對應需求文件 4.5。分機狀態（使用中／空號）不存，由使用紀錄計算。"""
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def now() -> datetime:
    return datetime.now()


class Plant(Base):
    __tablename__ = "plants"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(8), unique=True)  # "1"=一廠
    name: Mapped[str] = mapped_column(String(32))
    phone: Mapped[str] = mapped_column(String(32), default="")  # 市話
    short_code: Mapped[str] = mapped_column(String(8), default="")  # 簡碼
    footer_text: Mapped[str] = mapped_column(Text, default="")  # 貼牆版檔尾（撥號規則等）


class Department(Base):
    __tablename__ = "departments"
    id: Mapped[int] = mapped_column(primary_key=True)
    plant_id: Mapped[int] = mapped_column(ForeignKey("plants.id"), index=True)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("departments.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(64))
    sort: Mapped[int] = mapped_column(Integer, default=0)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    default_ext: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ext_from: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ext_to: Mapped[int | None] = mapped_column(Integer, nullable=True)
    print_column: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 只對最上層：1~3
    print_order: Mapped[int] = mapped_column(Integer, default=0)
    fill_color: Mapped[str | None] = mapped_column(String(8), nullable=True)  # y=黃 c=淺青
    show_title: Mapped[bool] = mapped_column(Boolean, default=True)  # 「印標題列」
    children = relationship("Department", backref="parent", remote_side=[id])


class DeptMap(Base):
    """Domino 部門名稱 -> 部門；對應一次後記住。"""
    __tablename__ = "dept_map"
    __table_args__ = (UniqueConstraint("plant_id", "domino_name"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    plant_id: Mapped[int] = mapped_column(ForeignKey("plants.id"))
    domino_name: Mapped[str] = mapped_column(String(128))
    department_id: Mapped[int] = mapped_column(ForeignKey("departments.id"))


class ExtNumber(Base):
    __tablename__ = "ext_numbers"
    __table_args__ = (UniqueConstraint("plant_id", "ext"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    plant_id: Mapped[int] = mapped_column(ForeignKey("plants.id"))
    ext: Mapped[int] = mapped_column(Integer)
    department_id: Mapped[int | None] = mapped_column(ForeignKey("departments.id"), nullable=True)
    grade: Mapped[str] = mapped_column(String(1), default="B")  # A=可撥外線 B=不可
    note: Mapped[str] = mapped_column(String(128), default="")


class Extension(Base):
    """人員（type=P）與單位（type=U）。"""
    __tablename__ = "extensions"
    id: Mapped[int] = mapped_column(primary_key=True)
    plant_id: Mapped[int] = mapped_column(ForeignKey("plants.id"), index=True)
    type: Mapped[str] = mapped_column(String(1))  # P / U
    name: Mapped[str] = mapped_column(String(128))
    print_name: Mapped[str | None] = mapped_column(String(128), nullable=True)  # 單位用
    email: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    department_id: Mapped[int | None] = mapped_column(ForeignKey("departments.id"), nullable=True)
    title: Mapped[str] = mapped_column(String(64), default="")
    ext: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    personal_ext: Mapped[bool] = mapped_column(Boolean, default=False)
    in_directory: Mapped[bool] = mapped_column(Boolean, default=True)  # 列入分機表
    hide_in_print: Mapped[bool] = mapped_column(Boolean, default=False)  # 不列
    sort: Mapped[int] = mapped_column(Integer, default=0)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    note: Mapped[str] = mapped_column(String(256), default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now)
    updated_by: Mapped[str] = mapped_column(String(128), default="")
    department = relationship("Department")


class DominoRoster(Base):
    __tablename__ = "domino_roster"
    email: Mapped[str] = mapped_column(String(128), primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    dep: Mapped[str] = mapped_column(String(128), default="")
    title: Mapped[str] = mapped_column(String(64), default="")
    supervisor: Mapped[str] = mapped_column(String(128), default="")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_seen: Mapped[datetime] = mapped_column(DateTime, default=now)


class DominoChange(Base):
    """異動收件匣。status: pending / auto / applied / skipped / undone"""
    __tablename__ = "domino_changes"
    id: Mapped[int] = mapped_column(primary_key=True)
    plant_id: Mapped[int] = mapped_column(ForeignKey("plants.id"), index=True)
    kind: Mapped[str] = mapped_column(String(24))  # new / new_dept / leave / move / title / promote / rename_candidate
    email: Mapped[str] = mapped_column(String(128), default="")
    name: Mapped[str] = mapped_column(String(128), default="")
    from_dep: Mapped[str] = mapped_column(String(128), default="")
    to_dep: Mapped[str] = mapped_column(String(128), default="")
    from_title: Mapped[str] = mapped_column(String(64), default="")
    to_title: Mapped[str] = mapped_column(String(64), default="")
    status: Mapped[str] = mapped_column(String(12), default="pending", index=True)
    reason: Mapped[str] = mapped_column(String(128), default="")  # 為何交給廠務
    before: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # 還原用快照
    after: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    run_id: Mapped[str] = mapped_column(String(32), default="", index=True)
    detected_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class AuditLog(Base):
    __tablename__ = "audit_log"
    id: Mapped[int] = mapped_column(primary_key=True)
    at: Mapped[datetime] = mapped_column(DateTime, default=now, index=True)
    actor: Mapped[str] = mapped_column(String(128))  # 使用者 email 或 "system"
    plant_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    action: Mapped[str] = mapped_column(String(32))
    target: Mapped[str] = mapped_column(String(128), default="")
    before: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    after: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class PrintExport(Base):
    __tablename__ = "print_exports"
    id: Mapped[int] = mapped_column(primary_key=True)
    plant_id: Mapped[int] = mapped_column(ForeignKey("plants.id"))
    kind: Mapped[str] = mapped_column(String(16))  # eip / wall
    at: Mapped[datetime] = mapped_column(DateTime, default=now)
    by: Mapped[str] = mapped_column(String(128), default="")
