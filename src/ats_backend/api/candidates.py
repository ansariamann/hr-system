"""Candidate management API endpoints."""

from typing import List, Optional, Dict, Any
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
from sqlalchemy.orm import Session
import structlog

from ats_backend.core.database import get_db
from ats_backend.auth.dependencies import get_current_user, get_current_client
from ats_backend.auth.models import User
from ats_backend.models.client import Client
from ats_backend.services.candidate_service import CandidateService
from ats_backend.schemas.candidate import (
    CandidateCreate,
    CandidateUpdate,
    CandidateResponse
)
from ats_backend.core.logging import performance_logger

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/candidates", tags=["candidates"])


@router.post("/", response_model=CandidateResponse, status_code=status.HTTP_201_CREATED)
async def create_candidate(
    request: Request,
    candidate_data: CandidateCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_client: Client = Depends(get_current_client)
):
    """Create a new candidate.
    
    Creates a new candidate record with audit logging and automatic
    client association based on the authenticated user's client.
    """
    try:
        with performance_logger.log_operation_time(
            "create_candidate",
            user_id=str(current_user.id),
            client_id=str(current_client.id)
        ):
            # Get request metadata
            ip_address = request.client.host if request.client else None
            user_agent = request.headers.get("user-agent")
            
            candidate_service = CandidateService()
            candidate = candidate_service.create_candidate(
                db=db,
                client_id=current_client.id,
                candidate_data=candidate_data,
                user_id=current_user.id,
                ip_address=ip_address,
                user_agent=user_agent
            )
            
            logger.info(
                "Candidate created via API",
                candidate_id=str(candidate.id),
                client_id=str(current_client.id),
                user_id=str(current_user.id),
                name=candidate.name
            )
            
            return candidate
            
    except ValueError as e:
        logger.warning(
            "Candidate creation failed - validation error",
            client_id=str(current_client.id),
            user_id=str(current_user.id),
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(
            "Candidate creation failed - internal error",
            client_id=str(current_client.id),
            user_id=str(current_user.id),
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create candidate: {str(e)}"
        )


@router.get("/", response_model=List[CandidateResponse])
async def list_candidates(
    name_pattern: Optional[str] = Query(None, description="Search by name pattern"),
    skills: Optional[str] = Query(None, description="Search by skills (comma-separated)"),
    city: Optional[str] = Query(None, description="Search by location/city"),
    max_experience: Optional[int] = Query(None, description="Filter by maximum years of experience"),
    candidate_status: Optional[str] = Query(None, description="Filter by candidate status"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of records"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_client: Client = Depends(get_current_client)
):
    """List candidates with optional filtering.
    
    Supports filtering by name pattern, skills, status, city, and max experience.
    Results are automatically filtered to the current client.
    """
    try:
        with performance_logger.log_operation_time(
            "list_candidates",
            user_id=str(current_user.id),
            client_id=str(current_client.id)
        ):
            candidate_service = CandidateService()
            
            # Parse skills if provided
            skills_list = None
            if skills:
                skills_list = [skill.strip() for skill in skills.split(",")]
            
            candidates = candidate_service.search_candidates(
                db=db,
                client_id=current_client.id,
                name_pattern=name_pattern,
                skills=skills_list,
                location=city,
                max_experience=max_experience,
                status=candidate_status,
                skip=skip,
                limit=limit
            )
            
            logger.info(
                "Candidates listed via API",
                client_id=str(current_client.id),
                user_id=str(current_user.id),
                count=len(candidates),
                filters={
                    "name_pattern": name_pattern,
                    "skills": skills,
                    "city": city,
                    "max_experience": max_experience,
                    "status": candidate_status
                }
            )
            
            return candidates
            
    except Exception as e:
        logger.error(
            "Failed to list candidates",
            client_id=str(current_client.id),
            user_id=str(current_user.id),
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list candidates: {str(e)}"
        )


@router.get("/{candidate_id}", response_model=CandidateResponse)
async def get_candidate(
    candidate_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_client: Client = Depends(get_current_client)
):
    """Get a specific candidate by ID.
    
    Returns candidate details if the candidate belongs to the
    current client, otherwise returns 404.
    """
    try:
        with performance_logger.log_operation_time(
            "get_candidate",
            user_id=str(current_user.id),
            client_id=str(current_client.id),
            candidate_id=str(candidate_id)
        ):
            candidate_service = CandidateService()
            candidate = candidate_service.get_candidate_by_id(db, candidate_id)
            
            if not candidate:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Candidate not found"
                )
            
            # Verify candidate belongs to current client
            if candidate.client_id != current_client.id:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Candidate not found"
                )
            
            logger.info(
                "Candidate retrieved via API",
                candidate_id=str(candidate_id),
                client_id=str(current_client.id),
                user_id=str(current_user.id)
            )
            
            return candidate
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to get candidate",
            candidate_id=str(candidate_id),
            client_id=str(current_client.id),
            user_id=str(current_user.id),
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get candidate: {str(e)}"
        )


@router.put("/{candidate_id}", response_model=CandidateResponse)
async def update_candidate(
    candidate_id: UUID,
    request: Request,
    candidate_data: CandidateUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_client: Client = Depends(get_current_client)
):
    """Update a candidate's information.
    
    Updates candidate data with audit logging. Only provided fields
    are updated, others remain unchanged.
    """
    try:
        with performance_logger.log_operation_time(
            "update_candidate",
            user_id=str(current_user.id),
            client_id=str(current_client.id),
            candidate_id=str(candidate_id)
        ):
            # Get request metadata
            ip_address = request.client.host if request.client else None
            user_agent = request.headers.get("user-agent")
            
            candidate_service = CandidateService()
            candidate = candidate_service.update_candidate(
                db=db,
                candidate_id=candidate_id,
                client_id=current_client.id,
                candidate_data=candidate_data,
                user_id=current_user.id,
                ip_address=ip_address,
                user_agent=user_agent
            )
            
            if not candidate:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Candidate not found"
                )
            
            logger.info(
                "Candidate updated via API",
                candidate_id=str(candidate_id),
                client_id=str(current_client.id),
                user_id=str(current_user.id)
            )
            
            return candidate
            
    except ValueError as e:
        logger.warning(
            "Candidate update failed - validation error",
            candidate_id=str(candidate_id),
            client_id=str(current_client.id),
            user_id=str(current_user.id),
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to update candidate",
            candidate_id=str(candidate_id),
            client_id=str(current_client.id),
            user_id=str(current_user.id),
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update candidate: {str(e)}"
        )


@router.delete("/{candidate_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_candidate(
    candidate_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_client: Client = Depends(get_current_client)
):
    """Delete a candidate.
    
    Permanently deletes a candidate record with audit logging.
    This is a hard delete operation.
    """
    try:
        with performance_logger.log_operation_time(
            "delete_candidate",
            user_id=str(current_user.id),
            client_id=str(current_client.id),
            candidate_id=str(candidate_id)
        ):
            # Get request metadata
            ip_address = request.client.host if request.client else None
            user_agent = request.headers.get("user-agent")
            
            candidate_service = CandidateService()
            deleted = candidate_service.delete_candidate(
                db=db,
                candidate_id=candidate_id,
                client_id=current_client.id,
                user_id=current_user.id,
                ip_address=ip_address,
                user_agent=user_agent
            )
            
            if not deleted:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Candidate not found"
                )
            
            logger.info(
                "Candidate deleted via API",
                candidate_id=str(candidate_id),
                client_id=str(current_client.id),
                user_id=str(current_user.id)
            )
            
    except ValueError as e:
        logger.warning(
            "Candidate deletion failed - validation error",
            candidate_id=str(candidate_id),
            client_id=str(current_client.id),
            user_id=str(current_user.id),
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to delete candidate",
            candidate_id=str(candidate_id),
            client_id=str(current_client.id),
            user_id=str(current_user.id),
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete candidate: {str(e)}"
        )


@router.get("/{candidate_id}/duplicates", response_model=List[CandidateResponse])
async def find_candidate_duplicates(
    candidate_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_client: Client = Depends(get_current_client)
):
    """Find potential duplicate candidates.
    
    Returns a list of candidates that might be duplicates of the
    specified candidate based on name, email, and phone matching.
    """
    try:
        with performance_logger.log_operation_time(
            "find_candidate_duplicates",
            user_id=str(current_user.id),
            client_id=str(current_client.id),
            candidate_id=str(candidate_id)
        ):
            candidate_service = CandidateService()
            
            # First get the candidate to use for duplicate detection
            candidate = candidate_service.get_candidate_by_id(db, candidate_id)
            if not candidate:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Candidate not found"
                )
            
            # Verify candidate belongs to current client
            if candidate.client_id != current_client.id:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Candidate not found"
                )
            
            # Find potential duplicates
            duplicates = candidate_service.find_potential_duplicates(
                db=db,
                client_id=current_client.id,
                name=candidate.name,
                email=candidate.email,
                phone=candidate.phone
            )
            
            # Remove the original candidate from results
            duplicates = [dup for dup in duplicates if dup.id != candidate_id]
            
            logger.info(
                "Candidate duplicates found via API",
                candidate_id=str(candidate_id),
                client_id=str(current_client.id),
                user_id=str(current_user.id),
                duplicates_count=len(duplicates)
            )
            
            return duplicates
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to find candidate duplicates",
            candidate_id=str(candidate_id),
            client_id=str(current_client.id),
            user_id=str(current_user.id),
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to find candidate duplicates: {str(e)}"
        )


@router.get("/email/{email}", response_model=CandidateResponse)
async def get_candidate_by_email(
    email: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_client: Client = Depends(get_current_client)
):
    """Get candidate by email address.
    
    Returns candidate with the specified email address within
    the current client's context.
    """
    try:
        with performance_logger.log_operation_time(
            "get_candidate_by_email",
            user_id=str(current_user.id),
            client_id=str(current_client.id),
            email=email
        ):
            candidate_service = CandidateService()
            candidate = candidate_service.get_candidate_by_email(
                db, current_client.id, email
            )
            
            if not candidate:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Candidate not found"
                )
            
            logger.info(
                "Candidate retrieved by email via API",
                candidate_id=str(candidate.id),
                client_id=str(current_client.id),
                user_id=str(current_user.id),
                email=email
            )
            
            return candidate
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to get candidate by email",
            email=email,
            client_id=str(current_client.id),
            user_id=str(current_user.id),
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get candidate by email: {str(e)}"
        )


@router.get("/stats/summary")
async def get_candidate_statistics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_client: Client = Depends(get_current_client)
):
    """Get candidate statistics for the current client.
    
    Returns summary statistics including total candidates,
    status breakdown, and other metrics.
    """
    try:
        with performance_logger.log_operation_time(
            "get_candidate_statistics",
            user_id=str(current_user.id),
            client_id=str(current_client.id)
        ):
            candidate_service = CandidateService()
            stats = candidate_service.get_candidate_statistics(
                db, current_client.id
            )
            
            logger.info(
                "Candidate statistics retrieved via API",
                client_id=str(current_client.id),
                user_id=str(current_user.id),
                total_candidates=stats.get("total_candidates", 0)
            )
            
            return stats
            
    except Exception as e:
        logger.error(
            "Failed to get candidate statistics",
            client_id=str(current_client.id),
            user_id=str(current_user.id),
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get candidate statistics: {str(e)}"
        )