"""统计报表与导出接口。"""

from __future__ import annotations

import csv
import io
from collections import defaultdict
from typing import Optional
from urllib.parse import quote

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from backend import scoring
from backend.database import get_db
from backend.models import (
    Achievement,
    AchievementAuthor,
    AchievementStatus,
    ContributionRule,
    Department,
    Person,
)

router = APIRouter(prefix="/api/reports", tags=["统计报表"])


def _load_achievements(
    db: Session,
    year: Optional[int],
    status: Optional[str],
) -> list[Achievement]:
    stmt = select(Achievement).options(
        selectinload(Achievement.authors)
        .selectinload(AchievementAuthor.person)
        .selectinload(Person.department),
        selectinload(Achievement.level),
        selectinload(Achievement.category),
        selectinload(Achievement.owner),
    )
    if status:
        stmt = stmt.where(Achievement.status == status)
    if year is not None:
        stmt = stmt.where(Achievement.year == year)
    return list(db.scalars(stmt.order_by(Achievement.year.desc(), Achievement.id.desc())).all())


def _collect_rows(
    db: Session,
    year: Optional[int],
    status: Optional[str],
    department_id: Optional[int],
) -> list[dict]:
    """展开为「成果 x 作者」的明细计分行。"""
    rules = list(db.scalars(select(ContributionRule)).all())
    achievements = _load_achievements(db, year, status)
    rows: list[dict] = []
    for achievement in achievements:
        for item in scoring.calculate_achievement(achievement, rules):
            author = item["author"]
            person = author.person
            if person is None:
                continue
            if department_id is not None and person.department_id != department_id:
                continue
            rows.append(
                {
                    "person_id": person.id,
                    "person_name": person.name,
                    "employee_no": person.employee_no,
                    "department_id": person.department_id,
                    "department_name": person.department.name if person.department else "未分配",
                    "current_title": person.current_title,
                    "apply_title": person.apply_title,
                    "achievement_id": achievement.id,
                    "achievement_title": achievement.title,
                    "category_id": achievement.category_id,
                    "category_name": achievement.category.name if achievement.category else "",
                    "level_name": achievement.level.name if achievement.level else "",
                    "base_score": achievement.level.base_score if achievement.level else 0.0,
                    "year": achievement.year,
                    "rank": author.rank,
                    "is_corresponding": author.is_corresponding,
                    "ratio": item["ratio"],
                    "score": item["score"],
                    "status": achievement.status,
                }
            )
    return rows


def _person_summaries(rows: list[dict]) -> list[dict]:
    grouped: dict[int, dict] = {}
    achievement_sets: dict[int, set] = defaultdict(set)
    for row in rows:
        pid = row["person_id"]
        entry = grouped.setdefault(
            pid,
            {
                "person_id": pid,
                "person_name": row["person_name"],
                "employee_no": row["employee_no"],
                "department_id": row["department_id"],
                "department_name": row["department_name"],
                "current_title": row["current_title"],
                "apply_title": row["apply_title"],
                "total_score": 0.0,
                "by_category": defaultdict(float),
            },
        )
        entry["total_score"] += row["score"]
        entry["by_category"][row["category_name"]] += row["score"]
        achievement_sets[pid].add(row["achievement_id"])

    result = []
    for pid, entry in grouped.items():
        entry["total_score"] = round(entry["total_score"], 2)
        entry["by_category"] = {k: round(v, 2) for k, v in entry["by_category"].items()}
        entry["achievement_count"] = len(achievement_sets[pid])
        result.append(entry)
    result.sort(key=lambda x: x["total_score"], reverse=True)
    return result


@router.get("/overview")
def overview(year: Optional[int] = None, db: Session = Depends(get_db)):
    rows = _collect_rows(db, year, None, None)
    approved_rows = [r for r in rows if r["status"] == AchievementStatus.APPROVED]

    status_counts = {key: 0 for key in AchievementStatus.ALL}
    seen_status: dict[int, str] = {}
    for row in rows:
        seen_status.setdefault(row["achievement_id"], row["status"])
    for status in seen_status.values():
        status_counts[status] += 1

    by_category: dict[str, float] = defaultdict(float)
    for row in approved_rows:
        by_category[row["category_name"]] += row["score"]

    return {
        "department_count": len(db.scalars(select(Department)).all()),
        "person_count": len(db.scalars(select(Person)).all()),
        "achievement_count": len({r["achievement_id"] for r in rows}),
        "status_counts": status_counts,
        "approved_total_score": round(sum(r["score"] for r in approved_rows), 2),
        "scored_person_count": len({r["person_id"] for r in approved_rows}),
        "by_category": {k: round(v, 2) for k, v in by_category.items()},
    }


@router.get("/person-scores")
def person_scores(
    year: Optional[int] = None,
    department_id: Optional[int] = None,
    status: str = AchievementStatus.APPROVED,
    db: Session = Depends(get_db),
):
    rows = _collect_rows(db, year, status, department_id)
    return _person_summaries(rows)


@router.get("/department-scores")
def department_scores(
    year: Optional[int] = None,
    status: str = AchievementStatus.APPROVED,
    db: Session = Depends(get_db),
):
    rows = _collect_rows(db, year, status, None)
    grouped: dict[str, dict] = {}
    for row in rows:
        key = row["department_name"]
        entry = grouped.setdefault(
            key,
            {
                "department_id": row["department_id"],
                "department_name": key,
                "total_score": 0.0,
                "person_ids": set(),
                "achievement_ids": set(),
                "by_category": defaultdict(float),
            },
        )
        entry["total_score"] += row["score"]
        entry["person_ids"].add(row["person_id"])
        entry["achievement_ids"].add(row["achievement_id"])
        entry["by_category"][row["category_name"]] += row["score"]

    result = []
    for entry in grouped.values():
        result.append(
            {
                "department_id": entry["department_id"],
                "department_name": entry["department_name"],
                "total_score": round(entry["total_score"], 2),
                "person_count": len(entry["person_ids"]),
                "achievement_count": len(entry["achievement_ids"]),
                "by_category": {k: round(v, 2) for k, v in entry["by_category"].items()},
            }
        )
    result.sort(key=lambda x: x["total_score"], reverse=True)
    return result


@router.get("/person/{person_id}/detail")
def person_detail(
    person_id: int,
    year: Optional[int] = None,
    status: str = AchievementStatus.APPROVED,
    db: Session = Depends(get_db),
):
    rows = [r for r in _collect_rows(db, year, status, None) if r["person_id"] == person_id]
    return {
        "person_id": person_id,
        "total_score": round(sum(r["score"] for r in rows), 2),
        "count": len({r["achievement_id"] for r in rows}),
        "items": rows,
    }


def _csv_response(filename: str, header: list[str], rows: list[list]) -> Response:
    buffer = io.StringIO()
    buffer.write("\ufeff")  # BOM，保证 Excel 正确识别 UTF-8
    writer = csv.writer(buffer)
    writer.writerow(header)
    writer.writerows(rows)
    encoded = quote(filename)
    headers = {"Content-Disposition": f"attachment; filename*=UTF-8''{encoded}"}
    return Response(
        content=buffer.getvalue().encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers=headers,
    )


@router.get("/export/person-scores.csv")
def export_person_scores(
    year: Optional[int] = None,
    department_id: Optional[int] = None,
    status: str = AchievementStatus.APPROVED,
    db: Session = Depends(get_db),
):
    summaries = person_scores(year=year, department_id=department_id, status=status, db=db)
    category_names: list[str] = []
    for item in summaries:
        for name in item["by_category"]:
            if name not in category_names:
                category_names.append(name)

    header = [
        "排名", "姓名", "工号", "部门", "现职称", "申报职称", "成果数", "总积分",
        *[f"{name}积分" for name in category_names],
    ]
    rows = []
    for index, item in enumerate(summaries, start=1):
        rows.append(
            [
                index,
                item["person_name"],
                item["employee_no"],
                item["department_name"] or "",
                item["current_title"],
                item["apply_title"],
                item["achievement_count"],
                item["total_score"],
                *[item["by_category"].get(name, 0) for name in category_names],
            ]
        )
    return _csv_response("个人积分汇总.csv", header, rows)


@router.get("/export/achievements.csv")
def export_achievements(
    year: Optional[int] = None,
    department_id: Optional[int] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
):
    rows = _collect_rows(db, year, status, department_id)
    header = [
        "成果名称", "类别", "级别", "基础分", "年份", "作者", "排名", "是否通讯",
        "分成系数", "个人得分", "认定状态",
    ]
    data = []
    for row in rows:
        data.append(
            [
                row["achievement_title"],
                row["category_name"],
                row["level_name"],
                row["base_score"],
                row["year"],
                row["person_name"],
                row["rank"],
                "是" if row["is_corresponding"] else "否",
                row["ratio"],
                row["score"],
                AchievementStatus.LABELS.get(row["status"], row["status"]),
            ]
        )
    return _csv_response("成果积分明细.csv", header, data)
