"""数据模型定义。"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Department(Base):
    """部门 / 学院。"""

    __tablename__ = "departments"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    code: Mapped[str] = mapped_column(String(50), default="")
    remark: Mapped[str] = mapped_column(String(255), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    persons: Mapped[list["Person"]] = relationship(
        back_populates="department", cascade="all, delete-orphan"
    )


class Person(Base):
    """申报人员。"""

    __tablename__ = "persons"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50), index=True)
    employee_no: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    department_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("departments.id", ondelete="SET NULL"), nullable=True
    )
    current_title: Mapped[str] = mapped_column(String(50), default="")
    apply_title: Mapped[str] = mapped_column(String(50), default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    department: Mapped[Optional[Department]] = relationship(back_populates="persons")
    author_records: Mapped[list["AchievementAuthor"]] = relationship(
        back_populates="person", cascade="all, delete-orphan"
    )


class Category(Base):
    """科研成果类别，如 论文 / 专利 / 课题 / 著作 / 获奖。"""

    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True)
    code: Mapped[str] = mapped_column(String(50), unique=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    description: Mapped[str] = mapped_column(String(255), default="")

    levels: Mapped[list["Level"]] = relationship(
        back_populates="category",
        cascade="all, delete-orphan",
        order_by="Level.sort_order, Level.id",
    )


class Level(Base):
    """成果级别，如 论文-SCI一区、专利-发明专利，并携带基础分值。"""

    __tablename__ = "levels"
    __table_args__ = (UniqueConstraint("category_id", "name", name="uq_level_category_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(100))
    base_score: Mapped[float] = mapped_column(Float, default=0.0)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    remark: Mapped[str] = mapped_column(String(255), default="")

    category: Mapped[Category] = relationship(back_populates="levels")


class ContributionRule(Base):
    """作者贡献系数规则。

    针对「类别 + 作者人数」配置各排名作者的分成系数；category_id 为空表示
    适用所有类别的默认规则。corresponding_ratio 用于指定通讯作者的分成系数。
    """

    __tablename__ = "contribution_rules"
    __table_args__ = (
        UniqueConstraint("category_id", "author_count", name="uq_rule_category_count"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    category_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("categories.id", ondelete="CASCADE"), nullable=True
    )
    author_count: Mapped[int] = mapped_column(Integer)
    ratios: Mapped[list] = mapped_column(JSON, default=list)
    corresponding_ratio: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    remark: Mapped[str] = mapped_column(String(255), default="")

    category: Mapped[Optional[Category]] = relationship()


class AchievementStatus:
    """成果认定状态。"""

    PENDING = "pending"      # 待认定
    APPROVED = "approved"    # 已认定
    REJECTED = "rejected"    # 不予认定

    ALL = (PENDING, APPROVED, REJECTED)
    LABELS = {
        PENDING: "待认定",
        APPROVED: "已认定",
        REJECTED: "不予认定",
    }


class Achievement(Base):
    """科研成果记录。"""

    __tablename__ = "achievements"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(255), index=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id", ondelete="RESTRICT"))
    level_id: Mapped[int] = mapped_column(ForeignKey("levels.id", ondelete="RESTRICT"))
    owner_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("persons.id", ondelete="SET NULL"), nullable=True
    )
    year: Mapped[int] = mapped_column(Integer, default=0, index=True)
    achievement_date: Mapped[str] = mapped_column(String(20), default="")
    external_no: Mapped[str] = mapped_column(String(120), default="")
    publisher: Mapped[str] = mapped_column(String(255), default="")
    remark: Mapped[str] = mapped_column(Text, default="")
    evidence_url: Mapped[str] = mapped_column(String(500), default="")
    status: Mapped[str] = mapped_column(String(20), default=AchievementStatus.PENDING, index=True)
    reject_reason: Mapped[str] = mapped_column(String(255), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)

    category: Mapped[Category] = relationship()
    level: Mapped[Level] = relationship()
    owner: Mapped[Optional[Person]] = relationship()
    authors: Mapped[list["AchievementAuthor"]] = relationship(
        back_populates="achievement",
        cascade="all, delete-orphan",
        order_by="AchievementAuthor.rank",
    )


class AchievementAuthor(Base):
    """成果作者（完成人）及排名。"""

    __tablename__ = "achievement_authors"
    __table_args__ = (
        UniqueConstraint("achievement_id", "person_id", name="uq_author_achievement_person"),
        UniqueConstraint("achievement_id", "rank", name="uq_author_achievement_rank"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    achievement_id: Mapped[int] = mapped_column(
        ForeignKey("achievements.id", ondelete="CASCADE")
    )
    person_id: Mapped[int] = mapped_column(ForeignKey("persons.id", ondelete="CASCADE"))
    rank: Mapped[int] = mapped_column(Integer, default=1)
    is_corresponding: Mapped[bool] = mapped_column(Boolean, default=False)
    custom_ratio: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    achievement: Mapped[Achievement] = relationship(back_populates="authors")
    person: Mapped[Person] = relationship(back_populates="author_records")
