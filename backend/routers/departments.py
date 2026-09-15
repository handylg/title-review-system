"""部门管理接口。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import Department, Person
from backend.schemas import DepartmentCreate, DepartmentOut

router = APIRouter(prefix="/api/departments", tags=["部门管理"])


@router.get("", response_model=list[DepartmentOut])
def list_departments(db: Session = Depends(get_db)):
    return db.scalars(select(Department).order_by(Department.id)).all()


@router.post("", response_model=DepartmentOut, status_code=201)
def create_department(payload: DepartmentCreate, db: Session = Depends(get_db)):
    exists = db.scalar(select(Department).where(Department.name == payload.name))
    if exists:
        raise HTTPException(status_code=400, detail="部门名称已存在")
    dept = Department(**payload.model_dump())
    db.add(dept)
    db.commit()
    db.refresh(dept)
    return dept


@router.put("/{dept_id}", response_model=DepartmentOut)
def update_department(dept_id: int, payload: DepartmentCreate, db: Session = Depends(get_db)):
    dept = db.get(Department, dept_id)
    if dept is None:
        raise HTTPException(status_code=404, detail="部门不存在")
    duplicate = db.scalar(
        select(Department).where(Department.name == payload.name, Department.id != dept_id)
    )
    if duplicate:
        raise HTTPException(status_code=400, detail="部门名称已存在")
    for key, value in payload.model_dump().items():
        setattr(dept, key, value)
    db.commit()
    db.refresh(dept)
    return dept


@router.delete("/{dept_id}", status_code=204)
def delete_department(dept_id: int, db: Session = Depends(get_db)):
    dept = db.get(Department, dept_id)
    if dept is None:
        raise HTTPException(status_code=404, detail="部门不存在")
    person_count = db.scalar(select(Person).where(Person.department_id == dept_id).limit(1))
    if person_count is not None:
        raise HTTPException(status_code=400, detail="该部门下仍有人员，无法删除")
    db.delete(dept)
    db.commit()
