"""n8n 呼叫的內部 API：用密鑰驗證（標頭 X-Internal-Secret），與使用者登入分開。"""
import hmac

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..config import Settings, get_settings
from ..db import get_db
from ..services import domino
from ..services.common import get_plant
from ..services.maintain import RuleError

router = APIRouter(prefix="/api/internal", tags=["internal"])


def require_secret(x_internal_secret: str = Header(default=""), s: Settings = Depends(get_settings)):
    if not s.internal_api_secret or not hmac.compare_digest(x_internal_secret, s.internal_api_secret):
        raise HTTPException(status_code=403, detail="bad secret")


class Person(BaseModel):
    email: str
    name: str
    dep: str = ""
    title: str = ""
    supervisor: str = ""


class SyncBody(BaseModel):
    people: list[Person]
    baseline: bool = False
    bring_in_unlisted: bool = False


@router.post("/domino-sync", dependencies=[Depends(require_secret)])
def domino_sync(body: SyncBody, db: Session = Depends(get_db), s: Settings = Depends(get_settings)):
    plant = get_plant(db, s.default_plant)
    try:
        return domino.sync(db, plant, [p.model_dump() for p in body.people], s, body.baseline, body.bring_in_unlisted)
    except RuleError as e:
        raise HTTPException(400, str(e)) from None


@router.get("/domino-digest", dependencies=[Depends(require_secret)])
def domino_digest(run_id: str | None = None, db: Session = Depends(get_db), s: Settings = Depends(get_settings)):
    return domino.digest(db, get_plant(db, s.default_plant).id, run_id)
