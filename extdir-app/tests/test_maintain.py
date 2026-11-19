import pytest
from sqlalchemy import select

from app.models import AuditLog, Department, Extension, ExtNumber
from app.services import maintain
from app.services.maintain import RuleError, is_manager


def dept(db, name):
    return db.scalar(select(Department).where(Department.name == name))


def test_is_manager_rules():
    for t in ("廠長", "副廠長", "處長", "副處長", "部長", "經理", "技術經理", "副理", "課長"):
        assert is_manager(t), t
    for t in ("", "組長", "副課長", "特助", "副主任"):
        assert not is_manager(t), t


def test_create_person_adds_audit_and_warns_manager_without_personal_ext(db, plant):
    d = dept(db, "品一課")
    obj, warns = maintain.save_extension(db, "u@x", plant.id, None, {
        "type": "P", "name": "新課長", "title": "課長", "department_id": d.id, "ext": "311", "personal_ext": False})
    assert any("課長以上" in w for w in warns)
    assert db.scalar(select(AuditLog).where(AuditLog.action == "ext.create", AuditLog.actor == "u@x"))


def test_duplicate_only_when_name_and_ext_both_same(db, plant):
    d = dept(db, "皮技課")  # 貼牆表上皮技課 170／171 同名各印一列：同名不同分機要允許
    assert [e.ext for e in db.scalars(select(Extension).where(Extension.name == "皮技課"))] == [170, 171]
    with pytest.raises(RuleError, match="名稱與分機都相同"):
        maintain.save_extension(db, "u", plant.id, None, {"type": "U", "name": "皮技課", "department_id": d.id, "ext": "170"})
    maintain.save_extension(db, "u", plant.id, None, {"type": "U", "name": "皮技課", "department_id": d.id, "ext": "172"})


def test_personal_ext_requires_number(db, plant):
    with pytest.raises(RuleError, match="個人分機"):
        maintain.save_extension(db, "u", plant.id, None, {"type": "P", "name": "甲", "personal_ext": True})


def test_new_ext_number_auto_created_with_grade_b_and_range_warning(db, plant):
    d = dept(db, "品一課")  # 號段 310-319
    _, warns = maintain.save_extension(db, "u", plant.id, None, {"type": "U", "name": "新室", "department_id": d.id, "ext": "999"})
    assert db.scalar(select(ExtNumber).where(ExtNumber.ext == 999)).grade == "B"
    assert any("已新增" in w for w in warns)
    _, warns = maintain.save_extension(db, "u", plant.id, None, {"type": "U", "name": "新室2", "department_id": d.id, "ext": "150"})
    assert any("號段" in w for w in warns)  # 只提醒、不擋


def test_deactivate_never_deletes_and_frees_ext(db, plant):
    e = db.scalar(select(Extension).where(Extension.name == "守衛室"))
    assert maintain.ext_status_map(db, plant.id)[111] == "使用中"
    maintain.set_active(db, "u", plant.id, e.id, False)
    assert db.get(Extension, e.id) is not None and not e.active
    assert maintain.ext_status_map(db, plant.id)[111] == "空號"  # 狀態由使用紀錄計算


def test_ext_grade_belongs_to_number(db, plant):
    maintain.save_ext_number(db, "u", plant.id, 511, {"grade": "A", "department_id": dept(db, "噴乾一課").id})
    assert db.scalar(select(ExtNumber).where(ExtNumber.ext == 511)).grade == "A"
    with pytest.raises(RuleError):
        maintain.save_ext_number(db, "u", plant.id, 511, {"grade": "C"})


def test_vacancies_per_dept(db, plant):
    assert maintain.vacancies(db, plant.id, dept(db, "環資管理處").id) == [815, 816, 817, 818, 819]
    assert maintain.vacancies(db, plant.id, dept(db, "總務課").id) == [614]


def test_rename_dept_people_follow(db, plant):
    d = dept(db, "品一課")
    maintain.rename_dept(db, "u", plant.id, d.id, "品一新課")
    from app.services.directory import public_search
    assert any("品一新課" in r["dept"] for r in public_search(db, plant.id, "品一新課"))
    assert not public_search(db, plant.id, "品一課 (2F) 品保部 › 品一課")


def test_move_dept_blocks_same_name_cycle_and_moves_with_children(db, plant):
    h1, p3 = dept(db, "合一課"), dept(db, "生產三部")
    maintain.move_dept(db, "u", plant.id, h1.id, p3.id)  # 連同子部門一起搬
    assert db.get(Department, h1.id).parent_id == p3.id
    z1 = dept(db, "製一組")
    assert z1.parent_id == h1.id
    with pytest.raises(RuleError, match="自己的子部門"):
        maintain.move_dept(db, "u", plant.id, p3.id, z1.id)
    maintain.create_dept(db, "u", plant.id, "合一課", None)
    with pytest.raises(RuleError, match="已有「合一課」"):
        maintain.move_dept(db, "u", plant.id, h1.id, None)


def test_disable_dept_blocked_when_in_use(db, plant):
    with pytest.raises(RuleError, match="不能停用"):
        maintain.set_dept_active(db, "u", plant.id, dept(db, "品保部").id, False)
    d = maintain.create_dept(db, "u", plant.id, "空部門")
    maintain.set_dept_active(db, "u", plant.id, d.id, False)


def test_reorder_dept(db, plant):
    h2 = dept(db, "合二課")
    before = h2.sort
    maintain.reorder_dept(db, "u", plant.id, h2.id, -1)
    assert db.get(Department, h2.id).sort == before - 1
