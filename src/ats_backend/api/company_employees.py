"""API router for company employee CRUD (client portal)."""

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ats_backend.core.database import get_db
from ats_backend.core.error_handling import with_error_handling
from ats_backend.auth.dependencies import get_current_user, get_current_client
from ats_backend.auth.models import User
from ats_backend.models.client import Client
from ats_backend.models.activity_log import ActivityLog
from ats_backend.schemas.company_employee import (
    CompanyEmployeeCreate,
    CompanyEmployeeUpdate,
    CompanyEmployeeResponse,
)
from ats_backend.services.company_employee_service import CompanyEmployeeService

router = APIRouter(
    prefix="/company-employees",
    tags=["company-employees"],
    responses={404: {"description": "Not found"}},
)


@router.get("/", response_model=List[CompanyEmployeeResponse])
@with_error_handling(component="company_employee_api")
def list_company_employees(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_client: Client = Depends(get_current_client),
):
    """List all company employees for the authenticated client."""
    return CompanyEmployeeService.list_by_client(db, current_client.id)


@router.get("/{employee_id}", response_model=CompanyEmployeeResponse)
@with_error_handling(component="company_employee_api")
def get_company_employee(
    employee_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_client: Client = Depends(get_current_client),
):
    """Get a single company employee by ID."""
    employee = CompanyEmployeeService.get_by_id(db, employee_id)
    if not employee or employee.client_id != current_client.id:
        raise HTTPException(status_code=404, detail="Employee not found")
    return employee


@router.post("/", response_model=CompanyEmployeeResponse, status_code=status.HTTP_201_CREATED)
@with_error_handling(component="company_employee_api")
def create_company_employee(
    payload: CompanyEmployeeCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_client: Client = Depends(get_current_client),
):
    """Create a new company employee (manual entry)."""
    employee = CompanyEmployeeService.create(
        db,
        current_client.id,
        name=payload.name,
        email=payload.email,
        phone=payload.phone,
        role=payload.role,
        department=payload.department,
        date_of_joining=payload.date_of_joining,
        status=payload.status,
        is_active=payload.is_active,
        notes=payload.notes,
    )

    activity_log = ActivityLog(
        client_id=current_client.id,
        user_id=current_user.id,
        action_type="COMPANY_EMPLOYEE_CREATED",
        entity_id=employee.id,
        details={"name": employee.name, "role": employee.role},
    )
    db.add(activity_log)
    db.commit()
    db.refresh(employee)
    return employee


@router.patch("/{employee_id}", response_model=CompanyEmployeeResponse)
@with_error_handling(component="company_employee_api")
def update_company_employee(
    employee_id: UUID,
    payload: CompanyEmployeeUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_client: Client = Depends(get_current_client),
):
    """Update a company employee."""
    existing = CompanyEmployeeService.get_by_id(db, employee_id)
    if not existing or existing.client_id != current_client.id:
        raise HTTPException(status_code=404, detail="Employee not found")

    update_data = payload.model_dump(exclude_unset=True)
    employee = CompanyEmployeeService.update(db, employee_id, **update_data)

    activity_log = ActivityLog(
        client_id=current_client.id,
        user_id=current_user.id,
        action_type="COMPANY_EMPLOYEE_UPDATED",
        entity_id=employee_id,
        details={"updated_fields": list(update_data.keys())},
    )
    db.add(activity_log)
    db.commit()
    db.refresh(employee)
    return employee


@router.delete("/{employee_id}", status_code=status.HTTP_204_NO_CONTENT)
@with_error_handling(component="company_employee_api")
def delete_company_employee(
    employee_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_client: Client = Depends(get_current_client),
):
    """Delete a company employee."""
    existing = CompanyEmployeeService.get_by_id(db, employee_id)
    if not existing or existing.client_id != current_client.id:
        raise HTTPException(status_code=404, detail="Employee not found")

    CompanyEmployeeService.delete(db, employee_id)

    activity_log = ActivityLog(
        client_id=current_client.id,
        user_id=current_user.id,
        action_type="COMPANY_EMPLOYEE_DELETED",
        entity_id=employee_id,
        details={"name": existing.name},
    )
    db.add(activity_log)
    db.commit()
