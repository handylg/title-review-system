"""Pydantic 请求 / 响应模型。"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.models import AchievementStatus


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --------------------------------------------------------------------------- #
# 部门
# --------------------------------------------------------------------------- #
class DepartmentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    code: str = ""
    remark: str = ""


class DepartmentOut(ORMModel):
    id: int
    name: str
    code: str
    remark: str


# --------------------------------------------------------------------------- #
# 人员
# --------------------------------------------------------------------------- #
class PersonCreate(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    employee_no: str = Field(min_length=1, max_length=50)
    department_id: Optional[int] = None
    current_title: str = ""
    apply_title: str = ""
    is_active: bool = True


class PersonOut(ORMModel):
    id: int
    name: str
    employee_no: str
    department_id: Optional[int] = None
    department_name: Optional[str] = None
    current_title: str
    apply_title: str
    is_active: bool


# --------------------------------------------------------------------------- #
# 类别 / 级别
# --------------------------------------------------------------------------- #
class LevelCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    base_score: float = Field(ge=0)
    sort_order: int = 0
    remark: str = ""


class LevelOut(ORMModel):
    id: int
    category_id: int
    name: str
    base_score: float
    sort_order: int
    remark: str


class CategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    code: str = Field(min_length=1, max_length=50)
    sort_order: int = 0
    description: str = ""


class CategoryOut(ORMModel):
    id: int
    name: str
    code: str
    sort_order: int
    description: str
    levels: list[LevelOut] = []


# --------------------------------------------------------------------------- #
# 作者贡献系数规则
# --------------------------------------------------------------------------- #
class ContributionRuleCreate(BaseModel):
    category_id: Optional[int] = None
    author_count: int = Field(ge=1, le=50)
    ratios: list[float] = Field(min_length=1)
    corresponding_ratio: Optional[float] = Field(default=None, ge=0, le=1)
    remark: str = ""

    @field_validator("ratios")
    @classmethod
    def _check_ratios(cls, v: list[float]) -> list[float]:
        for item in v:
            if item < 0 or item > 1:
                raise ValueError("分成系数必须在 0 到 1 之间")
        return v


class ContributionRuleOut(ORMModel):
    id: int
    category_id: Optional[int]
    category_name: Optional[str] = None
    author_count: int
    ratios: list[float]
    corresponding_ratio: Optional[float]
    remark: str


# --------------------------------------------------------------------------- #
# 成果
# --------------------------------------------------------------------------- #
class AchievementAuthorIn(BaseModel):
    person_id: int
    rank: int = Field(ge=1)
    is_corresponding: bool = False
    custom_ratio: Optional[float] = Field(default=None, ge=0, le=1)


class AchievementAuthorOut(BaseModel):
    person_id: int
    person_name: str
    employee_no: str
    department_name: Optional[str] = None
    rank: int
    is_corresponding: bool
    custom_ratio: Optional[float] = None
    ratio: float = 0.0
    score: float = 0.0


class AchievementCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    category_id: int
    level_id: int
    owner_id: Optional[int] = None
    year: int = Field(default=0, ge=0, le=3000)
    achievement_date: str = ""
    external_no: str = ""
    publisher: str = ""
    remark: str = ""
    evidence_url: str = ""
    status: str = AchievementStatus.PENDING
    authors: list[AchievementAuthorIn] = Field(min_length=1)

    @field_validator("status")
    @classmethod
    def _check_status(cls, v: str) -> str:
        if v not in AchievementStatus.ALL:
            raise ValueError("无效的认定状态")
        return v

    @field_validator("authors")
    @classmethod
    def _check_authors(cls, v: list[AchievementAuthorIn]) -> list[AchievementAuthorIn]:
        ids = [a.person_id for a in v]
        if len(set(ids)) != len(ids):
            raise ValueError("同一成果中作者不能重复")
        ranks = [a.rank for a in v]
        if len(set(ranks)) != len(ranks):
            raise ValueError("作者排名不能重复")
        if len([a for a in v if a.is_corresponding]) > 1:
            raise ValueError("只能指定一位通讯作者")
        return v


class AchievementReviewIn(BaseModel):
    status: str
    reject_reason: str = ""

    @field_validator("status")
    @classmethod
    def _check_status(cls, v: str) -> str:
        if v not in AchievementStatus.ALL:
            raise ValueError("无效的认定状态")
        return v


class AchievementOut(ORMModel):
    id: int
    title: str
    category_id: int
    category_name: str
    level_id: int
    level_name: str
    base_score: float
    owner_id: Optional[int]
    owner_name: Optional[str]
    year: int
    achievement_date: str
    external_no: str
    publisher: str
    remark: str
    evidence_url: str
    status: str
    status_label: str
    reject_reason: str
    total_score: float
    authors: list[AchievementAuthorOut] = []
