"""維運指令：python -m app.cli seed-plant1 | check

資料表由 Alembic 建立（alembic upgrade head）；這裡只負責匯入第一版資料。
"""
import argparse

from .db import SessionLocal
from .services.seed import seed_plant1


def main() -> None:
    ap = argparse.ArgumentParser(prog="app.cli")
    ap.add_argument("cmd", choices=["seed-plant1"])
    args = ap.parse_args()
    with SessionLocal() as db:
        if args.cmd == "seed-plant1":
            print(seed_plant1(db))


if __name__ == "__main__":
    main()
