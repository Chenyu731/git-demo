import logging

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from ..config import Settings, get_settings
from ..db import get_db
from ..ratelimit import client_ip, public_rate_limit
from ..services.common import get_plant
from ..services.directory import public_search, public_top_depts

log = logging.getLogger("extdir.public")
router = APIRouter()


@router.get("/api/public/search", dependencies=[Depends(public_rate_limit)])
def api_search(request: Request, q: str = "", dept: int | None = None, db: Session = Depends(get_db),
               s: Settings = Depends(get_settings)):
    plant = get_plant(db, s.default_plant)
    log.info("public search ip=%s", client_ip(request))  # 只記 IP 與時間（日誌），不進異動紀錄
    return {"plant": plant.name, "rows": public_search(db, plant.id, q[:50], dept),
            "depts": public_top_depts(db, plant.id)}


@router.get("/", response_class=HTMLResponse)
def home(request: Request):
    return request.app.state.templates.TemplateResponse(request, "public.html", {})
