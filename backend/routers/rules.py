"""积分规则配置接口：成果类别、级别基础分、作者贡献系数规则。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import Achievement, Category, ContributionRule, Level
from backend.schemas import (
    CategoryCreate,
    CategoryOut,
    ContributionRuleCreate,
    ContributionRuleOut,
    LevelCreate,
    LevelOut,
)
from backend.scoring import DEFAULT_RATIO_TABLE, default_ratios

router = APIRouter(prefix="/api", tags=["积分规则配置"])


# --------------------------- 类别与级别 --------------------------- #
@router.get("/categories", response_model=list[CategoryOut])
def list_categories(db: Session = Depends(get_db)):
    return db.scalars(select(Category).order_by(Category.sort_order, Category.id)).all()


@router.post("/categories", response_model=CategoryOut, status_code=201)
def create_category(payload: CategoryCreate, db: Session = Depends(get_db)):
    if db.scalar(select(Category).where(Category.code == payload.code)):
        raise HTTPException(status_code=400, detail="类别编码已存在")
    if db.scalar(select(Category).where(Category.name == payload.name)):
        raise HTTPException(status_code=400, detail="类别名称已存在")
    category = Category(**payload.model_dump())
    db.add(category)
    db.commit()
    db.refresh(category)
    return category


@router.put("/categories/{category_id}", response_model=CategoryOut)
def update_category(category_id: int, payload: CategoryCreate, db: Session = Depends(get_db)):
    category = db.get(Category, category_id)
    if category is None:
        raise HTTPException(status_code=404, detail="类别不存在")
    for field, value in (("code", payload.code), ("name", payload.name)):
        duplicate = db.scalar(
            select(Category).where(getattr(Category, field) == value, Category.id != category_id)
        )
        if duplicate:
            raise HTTPException(status_code=400, detail=f"类别{'编码' if field == 'code' else '名称'}已存在")
    for key, value in payload.model_dump().items():
        setattr(category, key, value)
    db.commit()
    db.refresh(category)
    return category


@router.delete("/categories/{category_id}", status_code=204)
def delete_category(category_id: int, db: Session = Depends(get_db)):
    category = db.get(Category, category_id)
    if category is None:
        raise HTTPException(status_code=404, detail="类别不存在")
    used = db.scalar(select(Achievement).where(Achievement.category_id == category_id).limit(1))
    if used is not None:
        raise HTTPException(status_code=400, detail="该类别已被成果引用，无法删除")
    db.delete(category)
    db.commit()


@router.post("/categories/{category_id}/levels", response_model=LevelOut, status_code=201)
def create_level(category_id: int, payload: LevelCreate, db: Session = Depends(get_db)):
    category = db.get(Category, category_id)
    if category is None:
        raise HTTPException(status_code=404, detail="类别不存在")
    duplicate = db.scalar(
        select(Level).where(Level.category_id == category_id, Level.name == payload.name)
    )
    if duplicate:
        raise HTTPException(status_code=400, detail="该类别下级别名称已存在")
    level = Level(category_id=category_id, **payload.model_dump())
    db.add(level)
    db.commit()
    db.refresh(level)
    return level


@router.put("/levels/{level_id}", response_model=LevelOut)
def update_level(level_id: int, payload: LevelCreate, db: Session = Depends(get_db)):
    level = db.get(Level, level_id)
    if level is None:
        raise HTTPException(status_code=404, detail="级别不存在")
    duplicate = db.scalar(
        select(Level).where(
            Level.category_id == level.category_id,
            Level.name == payload.name,
            Level.id != level_id,
        )
    )
    if duplicate:
        raise HTTPException(status_code=400, detail="该类别下级别名称已存在")
    for key, value in payload.model_dump().items():
        setattr(level, key, value)
    db.commit()
    db.refresh(level)
    return level


@router.delete("/levels/{level_id}", status_code=204)
def delete_level(level_id: int, db: Session = Depends(get_db)):
    level = db.get(Level, level_id)
    if level is None:
        raise HTTPException(status_code=404, detail="级别不存在")
    used = db.scalar(select(Achievement).where(Achievement.level_id == level_id).limit(1))
    if used is not None:
        raise HTTPException(status_code=400, detail="该级别已被成果引用，无法删除")
    db.delete(level)
    db.commit()


# --------------------------- 作者贡献系数 --------------------------- #
def _rule_out(rule: ContributionRule) -> dict:
    return {
        "id": rule.id,
        "category_id": rule.category_id,
        "category_name": rule.category.name if rule.category else None,
        "author_count": rule.author_count,
        "ratios": list(rule.ratios or []),
        "corresponding_ratio": rule.corresponding_ratio,
        "remark": rule.remark,
    }


@router.get("/rules", response_model=list[ContributionRuleOut])
def list_rules(db: Session = Depends(get_db)):
    rules = db.scalars(
        select(ContributionRule).order_by(ContributionRule.category_id, ContributionRule.author_count)
    ).all()
    return [_rule_out(r) for r in rules]


@router.get("/rules/defaults")
def rule_defaults():
    """返回系统内置的默认分成方案，供前端参考。"""
    return {
        "table": {str(k): v for k, v in DEFAULT_RATIO_TABLE.items()},
        "examples": {str(n): default_ratios(n) for n in (5, 6, 7, 8)},
    }


@router.post("/rules", response_model=ContributionRuleOut, status_code=201)
def create_rule(payload: ContributionRuleCreate, db: Session = Depends(get_db)):
    _validate_ratios(payload)
    existing = db.scalar(
        select(ContributionRule).where(
            ContributionRule.category_id == payload.category_id,
            ContributionRule.author_count == payload.author_count,
        )
    )
    if existing:
        raise HTTPException(status_code=400, detail="该类别与人数的规则已存在")
    rule = ContributionRule(**payload.model_dump())
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return _rule_out(rule)


@router.put("/rules/{rule_id}", response_model=ContributionRuleOut)
def update_rule(rule_id: int, payload: ContributionRuleCreate, db: Session = Depends(get_db)):
    rule = db.get(ContributionRule, rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail="规则不存在")
    _validate_ratios(payload)
    duplicate = db.scalar(
        select(ContributionRule).where(
            ContributionRule.category_id == payload.category_id,
            ContributionRule.author_count == payload.author_count,
            ContributionRule.id != rule_id,
        )
    )
    if duplicate:
        raise HTTPException(status_code=400, detail="该类别与人数的规则已存在")
    for key, value in payload.model_dump().items():
        setattr(rule, key, value)
    db.commit()
    db.refresh(rule)
    return _rule_out(rule)


@router.delete("/rules/{rule_id}", status_code=204)
def delete_rule(rule_id: int, db: Session = Depends(get_db)):
    rule = db.get(ContributionRule, rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail="规则不存在")
    db.delete(rule)
    db.commit()


def _validate_ratios(payload: ContributionRuleCreate) -> None:
    if len(payload.ratios) != payload.author_count:
        raise HTTPException(
            status_code=400,
            detail=f"分成系数个数（{len(payload.ratios)}）必须与作者人数（{payload.author_count}）一致",
        )
    total = sum(payload.ratios)
    if abs(total - 1.0) > 0.01:
        raise HTTPException(status_code=400, detail=f"分成系数之和应为 1.0，当前为 {round(total, 4)}")
