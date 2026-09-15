"""人员管理接口。"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import AchievementAuthor, Department, Person
from backend.schemas import PersonCreate, PersonOut
from backend.serializers import person_out

router = APIRouter(prefix="/api/persons", tags=["人员管理"])


@router.get("", response_model=list[PersonOut])
def list_persons(
    department_id: Optional[int] = None,
    keyword: Optional[str] = None,
    is_active: Optional[bool] = None,
    db: Session = Depends(get_db),
):
    stmt = select(Person)
    if department_id is not None:
        stmt = stmt.where(Person.department_id == department_id)
    if is_active is not None:
        stmt = stmt.where(Person.is_active == is_active)
    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.where((Person.name.like(like)) | (Person.employee_no.like(like)))
    persons = db.scalars(stmt.order_by(Person.department_id, Person.id)).all()
    return [person_out(p) for p in persons]


@router.post("", response_model=PersonOut, status_code=201)
def create_person(payload: PersonCreate, db: Session = Depends(get_db)):
    exists = db.scalar(select(Person).where(Person.employee_no == payload.employee_no))
    if exists:
        raise HTTPException(status_code=400, detail="工号已存在")
    _ensure_department(db, payload.department_id)
    person = Person(**payload.model_dump())
    db.add(person)
    db.commit()
    db.refresh(person)
    return person_out(person)


@router.put("/{person_id}", response_model=PersonOut)
def update_person(person_id: int, payload: PersonCreate, db: Session = Depends(get_db)):
    person = db.get(Person, person_id)
    if person is None:
        raise HTTPException(status_code=404, detail="人员不存在")
    duplicate = db.scalar(
        select(Person).where(Person.employee_no == payload.employee_no, Person.id != person_id)
    )
    if duplicate:
        raise HTTPException(status_code=400, detail="工号已存在")
    _ensure_department(db, payload.department_id)
    for key, value in payload.model_dump().items():
        setattr(person, key, value)
    db.commit()
    db.refresh(person)
    return person_out(person)


@router.delete("/{person_id}", status_code=204)
def delete_person(person_id: int, db: Session = Depends(get_db)):
    person = db.get(Person, person_id)
    if person is None:
        raise HTTPException(status_code=404, detail="人员不存在")
    referenced = db.scalar(
        select(AchievementAuthor).where(AchievementAuthor.person_id == person_id).limit(1)
    )
    if referenced is not None:
        raise HTTPException(status_code=400, detail="该人员已关联科研成果，请改为停用")
    db.delete(person)
    db.commit()


def _ensure_department(db: Session, department_id: Optional[int]) -> None:
    if department_id is None:
        return
    if db.get(Department, department_id) is None:
        raise HTTPException(status_code=400, detail="所选部门不存在")
