import pytest
from sqlalchemy import select

from app.config import Settings
from app.models import Department, DeptMap, DominoChange, DominoRoster, Extension
from app.services import domino
from app.services.maintain import RuleError

S = Settings()


def person(n, dep, title="", email=None):
    return {"email": email or f"u{n}@x.com", "name": f"人{n}", "dep": dep, "title": title}


def base_roster(db, plant, extra=()):
    """基準名冊：60 位一般人員（分母夠大，單一離職 1.7% 不觸發異常暫停）＋指定的人。"""
    people = [person(i, "一廠製一組") for i in range(60)] + list(extra)
    domino.sync(db, plant, people, S, baseline=True, bring_in_unlisted=True)
    return people


def changes(db, kind=None, status=None):
    q = select(DominoChange)
    if kind:
        q = q.where(DominoChange.kind == kind)
    if status:
        q = q.where(DominoChange.status == status)
    return list(db.scalars(q.order_by(DominoChange.id)))


def ext_of(db, email):
    return db.scalar(select(Extension).where(Extension.email == email))


def run(db, plant, people):
    return domino.sync(db, plant, people, S)


def test_empty_roster_refused(db, plant):
    with pytest.raises(RuleError, match="名冊是空的"):
        domino.sync(db, plant, [], S)


def test_baseline_links_emails_by_name_and_reports_unmatched(db, plant):
    roster = [{"email": "kun@x.com", "name": "陳坤木", "dep": "", "title": "廠長"},
              {"email": "w1@x.com", "name": "王同名", "dep": ""}, {"email": "w2@x.com", "name": "王同名", "dep": ""}]
    r = domino.sync(db, plant, roster, S, baseline=True)
    assert r["linked"] == 1 and "陳坤木" not in r["not_found"]
    assert db.scalar(select(Extension).where(Extension.name == "陳坤木")).email == "kun@x.com"
    assert len(r["not_found"]) == 56


def test_new_person_auto_added_with_dept_default_ext(db, plant):
    """新進：部門對得上、非主管、部門有預設分機 → 加入並用預設分機。「一廠製三組」靠去掉廠名前綴對上。"""
    people = base_roster(db, plant)
    run(db, plant, people + [person(100, "一廠製三組")])
    e = ext_of(db, "u100@x.com")
    assert e and e.ext == 221 and not e.personal_ext and e.active
    c = changes(db, "new", "auto")[-1]
    assert c.name == "人100" and "221" in c.reason


def test_new_person_external_f_number_not_listed_and_silent(db, plant):
    people = base_roster(db, plant)
    run(db, plant, people + [{"email": "f12345@x.com", "name": "外籍", "dep": "一廠製三組", "title": ""}])
    e = ext_of(db, "f12345@x.com")
    assert e and e.in_directory is False
    assert all(x["name"] != "外籍" for x in domino.digest(db, plant.id)["auto"])  # 不通知


def test_new_person_manager_goes_pending_no_auto_ext(db, plant):
    people = base_roster(db, plant)
    run(db, plant, people + [person(101, "一廠製三組", "課長")])
    assert ext_of(db, "u101@x.com") is None
    assert "主管" in changes(db, "new", "pending")[-1].reason


def test_new_person_dept_without_default_ext_pending(db, plant):
    people = base_roster(db, plant)
    run(db, plant, people + [person(102, "一廠生產二部")])  # 生產二部沒有預設分機
    assert ext_of(db, "u102@x.com") is None and "預設分機" in changes(db, "new", "pending")[-1].reason


def test_new_person_unmapped_dept_makes_two_pending_in_order_then_resolves(db, plant):
    people = base_roster(db, plant)
    run(db, plant, people + [person(103, "一廠新創部")])
    kinds = [c.kind for c in changes(db, status="pending")]
    assert kinds == ["new_dept", "new"]  # 先部門、再補分機
    d = db.scalar(select(Department).where(Department.name == "環保課"))
    domino.map_dept(db, "w", plant.id, changes(db, "new_dept")[0].id, d.id)
    assert db.scalar(select(DeptMap).where(DeptMap.domino_name == "一廠新創部")).department_id == d.id  # 記住對應
    warns = domino.confirm_new(db, "w", plant.id, changes(db, "new", "pending")[0].id, {"department_id": d.id, "ext": "710"})
    assert ext_of(db, "u103@x.com").ext == 710 and isinstance(warns, list)
    # 對應記住後，同部門下一位新進自動對上
    run(db, plant, people + [person(103, "一廠新創部"), person(104, "一廠新創部")])
    assert ext_of(db, "u104@x.com").department_id == d.id


def test_leave_shared_ext_auto_deactivated_and_undoable(db, plant):
    people = base_roster(db, plant)
    run(db, plant, people[1:])
    e = ext_of(db, "u0@x.com")
    assert e.active is False  # 停用、不刪除
    c = changes(db, "leave", "auto")[0]
    domino.undo(db, "w", plant.id, c.id)
    assert ext_of(db, "u0@x.com").active is True and db.get(DominoChange, c.id).status == "undone"
    assert db.get(DominoRoster, "u0@x.com").active is True


def test_leave_personal_ext_pending_then_number_returns_to_vacant(db, plant):
    kun = {"email": "kun@x.com", "name": "陳坤木", "dep": "", "title": "廠長"}
    people = base_roster(db, plant, [kun])
    run(db, plant, [p for p in people if p["email"] != "kun@x.com"])
    c = changes(db, "leave", "pending")[0]
    assert ext_of(db, "kun@x.com").active  # 還沒確認，不動
    domino.confirm_leave(db, "w", plant.id, c.id)
    from app.services.maintain import ext_status_map
    assert not ext_of(db, "kun@x.com").active and ext_status_map(db, plant.id)[101] == "空號"


def test_move_shared_ext_auto_changes_dept_and_ext(db, plant):
    people = base_roster(db, plant)
    moved = [dict(people[0], dep="一廠製三組")] + people[1:]
    run(db, plant, moved)
    e = ext_of(db, "u0@x.com")
    assert e.ext == 221 and e.department_id == db.scalar(select(Department.id).where(Department.name == "製三組"))
    c = changes(db, "move", "auto")[0]
    domino.undo(db, "w", plant.id, c.id)
    assert ext_of(db, "u0@x.com").ext == 211


def test_move_personal_or_becoming_manager_or_unknown_dept_pending(db, plant):
    kun = {"email": "kun@x.com", "name": "陳坤木", "dep": "一廠廠長室", "title": "廠長"}
    people = base_roster(db, plant, [kun])
    run(db, plant, [dict(kun, dep="一廠總經理室"),  # 有個人分機
                    dict(people[0], dep="一廠製三組", title="課長"),  # 調動後成為主管
                    dict(people[1], dep="一廠火星部")]  # 新部門對不上
        + people[2:-1])  # 最後一位是陳坤木本人，已在最前面改過部門
    reasons = {c.name: c.reason for c in changes(db, "move", "pending")}
    assert "個人分機" in reasons["陳坤木"] and "主管" in reasons["人0"] and "對不上" in reasons["人1"]


def test_title_change_updates_and_promotion_without_personal_ext_pending(db, plant):
    people = base_roster(db, plant)
    run(db, plant, [dict(people[0], title="課長")] + people[1:])
    assert ext_of(db, "u0@x.com").title == "課長"  # 職稱以 Domino 為準
    assert changes(db, "promote", "pending")[0].name == "人0"


def test_rename_candidate_when_group_moves_to_same_unknown_dept_then_apply(db, plant):
    people = base_roster(db, plant)
    run(db, plant, [dict(p, dep="一廠製一新組") for p in people[:5]] + people[5:])
    rc = changes(db, "rename_candidate", "pending")
    assert len(rc) == 1 and "改名" in rc[0].reason
    assert len(changes(db, "move", "pending")) == 5 and not changes(db, "move", "auto")
    d = db.scalar(select(Department).where(Department.name == "製一組"))
    assert domino.apply_rename(db, "w", plant.id, rc[0].id, d.id) == 5
    assert not changes(db, status="pending")


def test_abnormal_pause_when_too_many_leave_everything_pending_roster_kept(db, plant):
    people = base_roster(db, plant)
    r = run(db, plant, people[10:])  # 10 人離職 > 5
    assert r["abnormal"] and r["auto"] == 0 and r["pending"] == 10
    assert all(e.active for e in db.scalars(select(Extension).where(Extension.email.like("u%@x.com"))))
    assert db.get(DominoRoster, "u0@x.com").active  # 名冊維持，避免下次被當新進
    run(db, plant, people[10:])  # 再跑一次不重複排隊
    assert len(changes(db, "leave", "pending")) == 10


def test_abnormal_pause_by_ratio_even_below_absolute_limit(db, plant):
    people = base_roster(db, plant)  # 60 人，離職 3 人 = 5% > 3%（但沒超過 5 人）
    assert run(db, plant, people[3:])["abnormal"] is True


def test_unchanged_roster_makes_no_changes(db, plant):
    people = base_roster(db, plant)
    n = len(changes(db))
    assert run(db, plant, people)["auto"] == 0 and len(changes(db)) == n


def test_digest_splits_auto_and_pending(db, plant):
    people = base_roster(db, plant)
    r = run(db, plant, people + [person(200, "一廠製三組"), person(201, "一廠製三組", "課長")])
    d = domino.digest(db, plant.id, r["run_id"])
    assert [x["name"] for x in d["auto"]] == ["人200"] and [x["name"] for x in d["pending"]] == ["人201"]


def test_skip_and_state_guards(db, plant):
    people = base_roster(db, plant)
    run(db, plant, people + [person(300, "一廠製三組", "課長")])
    c = changes(db, "new", "pending")[0]
    domino.skip(db, "w", plant.id, c.id)
    with pytest.raises(RuleError):
        domino.skip(db, "w", plant.id, c.id)  # 已處理過
    with pytest.raises(RuleError):
        domino.undo(db, "w", plant.id, c.id)  # 非自動處理不能還原
