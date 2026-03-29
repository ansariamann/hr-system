"""Service layer for CompanyEmployee CRUD operations."""

from datetime import date
from typing import Any, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
import structlog

from ats_backend.models.company_employee import CompanyEmployee

logger = structlog.get_logger(__name__)


class CompanyEmployeeService:
    """Service for managing company employee records."""

    _MISSING = object()

    @staticmethod
    def list_by_client(db: Session, client_id: UUID) -> List[CompanyEmployee]:
        """List all employees for a given client."""
        return (
            db.query(CompanyEmployee)
            .filter(CompanyEmployee.client_id == client_id)
            .order_by(CompanyEmployee.created_at.desc())
            .all()
        )

    @staticmethod
    def get_by_id(db: Session, employee_id: UUID) -> Optional[CompanyEmployee]:
        """Get a single employee by ID."""
        return db.query(CompanyEmployee).filter(CompanyEmployee.id == employee_id).first()

    @staticmethod
    def create(
        db: Session,
        client_id: UUID,
        *,
        name: str,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        role: Optional[str] = None,
        department: Optional[str] = None,
        date_of_joining: Optional[date] = None,
        status: str = "ACTIVE",
        is_active: bool = True,
        notes: Optional[str] = None,
        candidate_id: Optional[UUID] = None,
        application_id: Optional[UUID] = None,
    ) -> CompanyEmployee:
        """Create a new company employee record."""
        try:
            employee = CompanyEmployee(
                client_id=client_id,
                candidate_id=candidate_id,
                application_id=application_id,
                name=name,
                email=email,
                phone=phone,
                role=role,
                department=department,
                date_of_joining=date_of_joining,
                status=status,
                is_active=is_active,
                notes=notes,
            )
            db.add(employee)
            db.flush()
            db.refresh(employee)
            logger.info(
                "Company employee created",
                employee_id=str(employee.id),
                client_id=str(client_id),
                name=name,
            )
            return employee
        except IntegrityError as e:
            db.rollback()
            logger.error("Company employee creation failed", error=str(e))
            raise ValueError(f"Failed to create company employee: {e}")

    @staticmethod
    def create_from_candidate(
        db: Session,
        client_id: UUID,
        candidate_id: UUID,
        application_id: Optional[UUID] = None,
        role: Optional[str] = None,
    ) -> Optional[CompanyEmployee]:
        """Auto-create a company employee from a selected candidate.

        Returns None if an employee record already exists for this
        candidate + client combination.
        """
        existing = (
            db.query(CompanyEmployee)
            .filter(
                CompanyEmployee.client_id == client_id,
                CompanyEmployee.candidate_id == candidate_id,
            )
            .first()
        )
        if existing:
            logger.info(
                "Company employee already exists for candidate",
                candidate_id=str(candidate_id),
                client_id=str(client_id),
            )
            return existing

        # Fetch candidate details to populate the employee record
        from ats_backend.models.candidate import Candidate

        candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
        if not candidate:
            logger.warning("Candidate not found for auto-creation", candidate_id=str(candidate_id))
            return None

        return CompanyEmployeeService.create(
            db,
            client_id,
            name=candidate.name,
            email=candidate.email,
            phone=candidate.phone,
            role=role,
            candidate_id=candidate_id,
            application_id=application_id,
        )

    @staticmethod
    def update(
        db: Session,
        employee_id: UUID,
        **kwargs: Any,
    ) -> Optional[CompanyEmployee]:
        """Update a company employee record.

        Fields passed in ``kwargs`` are applied verbatim so optional values can
        also be cleared by explicitly sending ``null`` from the API layer.
        """
        employee = db.query(CompanyEmployee).filter(CompanyEmployee.id == employee_id).first()
        if not employee:
            return None

        for field, value in kwargs.items():
            if value is not CompanyEmployeeService._MISSING and hasattr(employee, field):
                setattr(employee, field, value)

        try:
            db.flush()
            db.refresh(employee)
            logger.info("Company employee updated", employee_id=str(employee_id))
            return employee
        except IntegrityError as e:
            db.rollback()
            logger.error("Company employee update failed", error=str(e))
            raise ValueError(f"Failed to update company employee: {e}")

    @staticmethod
    def delete(db: Session, employee_id: UUID) -> bool:
        """Delete a company employee record. Returns True if deleted."""
        employee = db.query(CompanyEmployee).filter(CompanyEmployee.id == employee_id).first()
        if not employee:
            return False

        db.delete(employee)
        db.flush()
        logger.info("Company employee deleted", employee_id=str(employee_id))
        return True
