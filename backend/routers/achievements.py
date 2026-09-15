"""科研成果录入与认定接口。"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from backend.database import get_db
from backend.models import (
    Achievement,
    AchievementAuthor,
    AchievementStatus,
    Category,
    ContributionRule,
    Level,
    Person,
)
from backend.schemas import (
    AchievementCreate,
    AchievementOut,
    AchievementReviewIn,
)
from backend.serializers import achievement_out

router = APIRouter(prefix="/api/achievements", tags=["成果录入与认定"])


def _all_rules(db: Session) -> list[ContributionRule]:
    return list(db.scalars(select(ContributionRule)).all())


def _base_query():
    return select(Achievement).options(
        selectinload(Achievement.authors).selectinload(AchievementAuthor.person).selectinload(Person.department),
        selectinload(Achievement.category),
        selectinload(Achievement.level),
        selectinload(Achievement.owner),
    )


@router.get("", response_model=list[AchievementOut])
def list_achievements(
    status: Optional[str] = None,
    category_id: Optional[int] = None,
    year: Optional[int] = None,
    person_id: Optional[int] = None,
    department_id: Optional[int] = None,
    keyword: Optional[str] = None,
    db: Session = Depends(get_db),
):
    stmt = _base_query()
    if status:
        stmt = stmt.where(Achievement.status == status)
    if category_id is not None:
        stmt = stmt.where(Achievement.category_id == category_id)
    if year is not None:
        stmt = stmt.where(Achievement.year == year)
    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.where(
            (Achievement.title.like(like)) | (Achievement.external_no.like(like))
        )
    if person_id is not None:
        stmt = stmt.where(
            Achievement.id.in_(
                select(AchievementAuthor.achievement_id).where(
                    AchievementAuthor.person_id == person_id
                )
            )
        )
    if department_id is not None:
        stmt = stmt.where(
            Achievement.id.in_(
                select(AchievementAuthor.achievement_id)
                .join(Person, Person.id == AchievementAuthor.person_id)
                .where(Person.department_id == department_id)
            )
        )
    stmt = stmt.order_by(Achievement.year.desc(), Achievement.id.desc())
    rules = _all_rules(db)
    return [achievement_out(a, rules) for a in db.scalars(stmt).all()]


@router.get("/{achievement_id}", response_model=AchievementOut)
def get_achievement(achievement_id: int, db: Session = Depends(get_db)):
    achievement = db.scalar(_base_query().where(Achievement.id == achievement_id))
    if achievement is None:
        raise HTTPException(status_code=404, detail="成果不存在")
    return achievement_out(achievement, _all_rules(db))


@router.post("", response_model=AchievementOut, status_code=201)
def create_achievement(payload: AchievementCreate, db: Session = Depends(get_db)):
    _validate(db, payload)
    achievement = Achievement(**_achievement_fields(payload))
    db.add(achievement)
    db.flush()
    _replace_authors(db, achievement, payload)
    db.commit()
    db.refresh(achievement)
    return achievement_out(achievement, _all_rules(db))


@router.put("/{achievement_id}", response_model=AchievementOut)
def update_achievement(
    achievement_id: int, payload: AchievementCreate, db: Session = Depends(get_db)
):
    achievement = db.scalar(_base_query().where(Achievement.id == achievement_id))
    if achievement is None:
        raise HTTPException(status_code=404, detail="成果不存在")
    _validate(db, payload)
    for key, value in _achievement_fields(payload).items():
        setattr(achievement, key, value)
    achievement.authors.clear()
    db.flush()
    _replace_authors(db, achievement, payload)
    db.commit()
    db.refresh(achievement)
    return achievement_out(achievement, _all_rules(db))


@router.post("/{achievement_id}/review", response_model=AchievementOut)
def review_achievement(
    achievement_id: int, payload: AchievementReviewIn, db: Session = Depends(get_db)
):
    achievement = db.scalar(_base_query().where(Achievement.id == achievement_id))
    if achievement is None:
        raise HTTPException(status_code=404, detail="成果不存在")
    if payload.status == AchievementStatus.REJECTED and not payload.reject_reason.strip():
        raise HTTPException(status_code=400, detail="不予认定时必须填写原因")
    achievement.status = payload.status
    achievement.reject_reason = (
        payload.reject_reason if payload.status == AchievementStatus.REJECTED else ""
    )
    db.commit()
    db.refresh(achievement)
    return achievement_out(achievement, _all_rules(db))


@router.delete("/{achievement_id}", status_code=204)
def delete_achievement(achievement_id: int, db: Session = Depends(get_db)):
    achievement = db.get(Achievement, achievement_id)
    if achievement is None:
        raise HTTPException(status_code=404, detail="成果不存在")
    db.delete(achievement)
    db.commit()


# --------------------------------------------------------------------------- #
# 辅助
# --------------------------------------------------------------------------- #
def _achievement_fields(payload: AchievementCreate) -> dict:
    data = payload.model_dump(exclude={"authors"})
    return data


def _replace_authors(db: Session, achievement: Achievement, payload: AchievementCreate) -> None:
    for item in payload.authors:
        db.add(
            AchievementAuthor(
                achievement_id=achievement.id,
                person_id=item.person_id,
                rank=item.rank,
                is_corresponding=item.is_corresponding,
                custom_ratio=item.custom_ratio,
            )
        )


def _validate(db: Session, payload: AchievementCreate) -> None:
    level = db.get(Level, payload.level_id)
    if level is None:
        raise HTTPException(status_code=400, detail="所选级别不存在")
    if level.category_id != payload.category_id:
        raise HTTPException(status_code=400, detail="所选级别不属于该成果类别")
    if db.get(Category, payload.category_id) is None:
        raise HTTPException(status_code=400, detail="所选类别不存在")
    if payload.owner_id is not None and db.get(Person, payload.owner_id) is None:
        raise HTTPException(status_code=400, detail="所选申报人不存在")
    for item in payload.authors:
        if db.get(Person, item.person_id) is None:
            raise HTTPException(status_code=400, detail=f"作者 #{item.person_id} 不存在")
