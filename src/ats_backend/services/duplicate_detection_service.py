"""Duplicate detection service for candidate matching and flagging."""

from typing import List, Optional, Dict, Any, Tuple
from uuid import UUID
from dataclasses import dataclass

from sqlalchemy.orm import Session
import structlog

from ats_backend.models.candidate import Candidate
from ats_backend.models.application import Application
from ats_backend.repositories.candidate import CandidateRepository
from ats_backend.repositories.application import ApplicationRepository
from ats_backend.resume.hash_generator import CandidateHashGenerator
from ats_backend.schemas.candidate import CandidateCreate

logger = structlog.get_logger(__name__)


@dataclass
class DuplicateMatch:
    """Represents a potential duplicate candidate match."""
    candidate: Candidate
    similarity_score: float
    match_type: str  # 'exact_hash', 'high_similarity', 'partial_match'
    matching_fields: List[str]  # Fields that matched (name, email, phone)


@dataclass
class DuplicateDetectionResult:
    """Result of duplicate detection analysis."""
    has_duplicates: bool
    matches: List[DuplicateMatch]
    should_flag: bool
    flag_reason: Optional[str]
    candidate_hash: str
    similarity_threshold_used: float


class DuplicateDetectionService:
    """Service for detecting duplicate candidates and managing flagging logic."""
    
    def __init__(self):
        """Initialize duplicate detection service."""
        self.candidate_repository = CandidateRepository()
        self.application_repository = ApplicationRepository()
        self.hash_generator = CandidateHashGenerator()
        
        # Configuration thresholds
        self.high_similarity_threshold = 0.8
        self.partial_similarity_threshold = 0.6
        self.left_status_flag_threshold = 0.8
        
        logger.info("Duplicate detection service initialized")
    
    def detect_duplicates(
        self,
        db: Session,
        client_id: UUID,
        candidate_data: Dict[str, Optional[str]],
        similarity_threshold: Optional[float] = None
    ) -> DuplicateDetectionResult:
        """Detect potential duplicate candidates for new candidate data.
        
        Args:
            db: Database session
            client_id: Client UUID
            candidate_data: Dictionary with candidate information (name, email, phone)
            similarity_threshold: Custom similarity threshold (optional)
            
        Returns:
            DuplicateDetectionResult with analysis results
        """
        threshold = similarity_threshold or self.high_similarity_threshold
        
        try:
            logger.info(
                "Starting duplicate detection",
                client_id=str(client_id),
                candidate_name=candidate_data.get("name", "Unknown"),
                threshold=threshold
            )
            
            # Generate candidate hash
            candidate_hash = self.hash_generator.generate_hash_from_dict(candidate_data)
            
            # Find potential duplicates using multiple strategies
            matches = self._find_all_potential_matches(db, client_id, candidate_data, threshold)
            
            # Determine if flagging is needed
            should_flag, flag_reason = self._should_flag_candidate(matches)
            
            result = DuplicateDetectionResult(
                has_duplicates=len(matches) > 0,
                matches=matches,
                should_flag=should_flag,
                flag_reason=flag_reason,
                candidate_hash=candidate_hash,
                similarity_threshold_used=threshold
            )
            
            logger.info(
                "Duplicate detection completed",
                client_id=str(client_id),
                matches_found=len(matches),
                should_flag=should_flag,
                candidate_hash=candidate_hash[:16] + "..."
            )
            
            return result
            
        except Exception as e:
            logger.error(
                "Duplicate detection failed",
                client_id=str(client_id),
                error=str(e)
            )
            
            # Return safe default result
            return DuplicateDetectionResult(
                has_duplicates=False,
                matches=[],
                should_flag=False,
                flag_reason=None,
                candidate_hash=self.hash_generator.generate_hash_from_dict(candidate_data),
                similarity_threshold_used=threshold
            )
    
    def _find_all_potential_matches(
        self,
        db: Session,
        client_id: UUID,
        candidate_data: Dict[str, Optional[str]],
        threshold: float
    ) -> List[DuplicateMatch]:
        """Find all potential duplicate matches using multiple strategies.
        
        Args:
            db: Database session
            client_id: Client UUID
            candidate_data: Candidate information
            threshold: Similarity threshold
            
        Returns:
            List of DuplicateMatch objects
        """
        matches = []
        processed_candidate_ids = set()
        
        # Strategy 1: Exact hash match
        candidate_hash = self.hash_generator.generate_hash_from_dict(candidate_data)
        hash_match = self.candidate_repository.get_by_hash(db, client_id, candidate_hash)
        
        if hash_match:
            matches.append(DuplicateMatch(
                candidate=hash_match,
                similarity_score=1.0,
                match_type='exact_hash',
                matching_fields=['name', 'email', 'phone']
            ))
            processed_candidate_ids.add(hash_match.id)
        
        # Strategy 2: Exact email match
        email = candidate_data.get("email")
        if email:
            email_match = self.candidate_repository.get_by_email(db, client_id, email)
            if email_match and email_match.id not in processed_candidate_ids:
                similarity = self.hash_generator.calculate_similarity_score(
                    candidate_data,
                    {
                        "name": email_match.name,
                        "email": email_match.email,
                        "phone": email_match.phone
                    }
                )
                
                if similarity >= threshold:
                    matches.append(DuplicateMatch(
                        candidate=email_match,
                        similarity_score=similarity,
                        match_type='email_match',
                        matching_fields=['email']
                    ))
                    processed_candidate_ids.add(email_match.id)
        
        # Strategy 3: Exact phone match
        phone = candidate_data.get("phone")
        if phone:
            phone_match = self.candidate_repository.get_by_phone(db, client_id, phone)
            if phone_match and phone_match.id not in processed_candidate_ids:
                similarity = self.hash_generator.calculate_similarity_score(
                    candidate_data,
                    {
                        "name": phone_match.name,
                        "email": phone_match.email,
                        "phone": phone_match.phone
                    }
                )
                
                if similarity >= threshold:
                    matches.append(DuplicateMatch(
                        candidate=phone_match,
                        similarity_score=similarity,
                        match_type='phone_match',
                        matching_fields=['phone']
                    ))
                    processed_candidate_ids.add(phone_match.id)
        
        # Strategy 4: Fuzzy name matching with repository search
        name = candidate_data.get("name")
        if name:
            potential_matches = self.candidate_repository.find_potential_duplicates(
                db, client_id, name, email, phone
            )
            
            for potential_match in potential_matches:
                if potential_match.id in processed_candidate_ids:
                    continue
                
                similarity = self.hash_generator.calculate_similarity_score(
                    candidate_data,
                    {
                        "name": potential_match.name,
                        "email": potential_match.email,
                        "phone": potential_match.phone
                    }
                )
                
                if similarity >= threshold:
                    # Determine matching fields
                    matching_fields = []
                    if self._fields_match("name", candidate_data.get("name"), potential_match.name):
                        matching_fields.append("name")
                    if self._fields_match("email", candidate_data.get("email"), potential_match.email):
                        matching_fields.append("email")
                    if self._fields_match("phone", candidate_data.get("phone"), potential_match.phone):
                        matching_fields.append("phone")
                    
                    match_type = 'high_similarity' if similarity >= self.high_similarity_threshold else 'partial_match'
                    
                    matches.append(DuplicateMatch(
                        candidate=potential_match,
                        similarity_score=similarity,
                        match_type=match_type,
                        matching_fields=matching_fields
                    ))
                    processed_candidate_ids.add(potential_match.id)
        
        # Sort matches by similarity score (highest first)
        matches.sort(key=lambda x: x.similarity_score, reverse=True)
        
        return matches
    
    def _fields_match(self, field_name: str, value1: Optional[str], value2: Optional[str]) -> bool:
        """Check if two field values match based on field type.
        
        Args:
            field_name: Name of the field being compared
            value1: First value
            value2: Second value
            
        Returns:
            True if fields match according to field-specific rules
        """
        if not value1 or not value2:
            return False
        
        if field_name == "email":
            return self.hash_generator._normalize_email(value1) == self.hash_generator._normalize_email(value2)
        elif field_name == "phone":
            return self.hash_generator._normalize_phone(value1) == self.hash_generator._normalize_phone(value2)
        elif field_name == "name":
            normalized1 = self.hash_generator._normalize_name(value1)
            normalized2 = self.hash_generator._normalize_name(value2)
            return self.hash_generator._calculate_string_similarity(normalized1, normalized2) >= 0.8
        
        return False
    
    def _should_flag_candidate(self, matches: List[DuplicateMatch]) -> Tuple[bool, Optional[str]]:
        """Determine if candidate should be flagged based on duplicate matches.
        
        Args:
            matches: List of duplicate matches
            
        Returns:
            Tuple of (should_flag, flag_reason)
        """
        if not matches:
            return False, None
        
        # Check for candidates with "LEFT" status
        left_status_matches = [
            match for match in matches 
            if match.candidate.status == "LEFT" and match.similarity_score >= self.left_status_flag_threshold
        ]
        
        if left_status_matches:
            best_match = left_status_matches[0]  # Already sorted by similarity
            return True, (
                f"Potential duplicate of candidate {best_match.candidate.id} with LEFT status "
                f"(similarity: {best_match.similarity_score:.2f}, matching fields: {', '.join(best_match.matching_fields)})"
            )
        
        # Check for very high similarity matches that might need review
        high_similarity_matches = [
            match for match in matches 
            if match.similarity_score >= 0.95 and match.match_type != 'exact_hash'
        ]
        
        if high_similarity_matches:
            best_match = high_similarity_matches[0]
            return True, (
                f"Very high similarity to existing candidate {best_match.candidate.id} "
                f"(similarity: {best_match.similarity_score:.2f}, status: {best_match.candidate.status})"
            )
        
        return False, None
    
    def check_workflow_progression_allowed(
        self,
        db: Session,
        application_id: UUID
    ) -> Tuple[bool, Optional[str]]:
        """Check if workflow progression is allowed for an application.
        
        Args:
            db: Database session
            application_id: Application UUID
            
        Returns:
            Tuple of (is_allowed, reason_if_blocked)
        """
        try:
            application = self.application_repository.get_by_id(db, application_id)
            if not application:
                return False, "Application not found"
            
            # Check if application is flagged for review
            if application.flagged_for_review:
                return False, f"Application flagged for review: {application.flag_reason}"
            
            # Check candidate status
            if application.candidate.status == "LEFT":
                return False, "Candidate has LEFT status - workflow progression blocked"
            
            return True, None
            
        except Exception as e:
            logger.error(
                "Workflow progression check failed",
                application_id=str(application_id),
                error=str(e)
            )
            return False, f"Error checking workflow progression: {str(e)}"
    
    def update_candidate_hash(
        self,
        db: Session,
        candidate_id: UUID,
        force_regenerate: bool = False
    ) -> bool:
        """Update or regenerate candidate hash for duplicate detection.
        
        Args:
            db: Database session
            candidate_id: Candidate UUID
            force_regenerate: Force regeneration even if hash exists
            
        Returns:
            True if hash was updated successfully
        """
        try:
            candidate = self.candidate_repository.get_by_id(db, candidate_id)
            if not candidate:
                return False
            
            # Skip if hash exists and not forcing regeneration
            if candidate.candidate_hash and not force_regenerate:
                return True
            
            # Generate new hash
            candidate_data = {
                "name": candidate.name,
                "email": candidate.email,
                "phone": candidate.phone
            }
            
            new_hash = self.hash_generator.generate_hash_from_dict(candidate_data)
            
            # Update hash
            return self.candidate_repository.update_candidate_hash(db, candidate_id, new_hash)
            
        except Exception as e:
            logger.error(
                "Candidate hash update failed",
                candidate_id=str(candidate_id),
                error=str(e)
            )
            return False
    
    def batch_update_candidate_hashes(
        self,
        db: Session,
        client_id: UUID,
        force_regenerate: bool = False
    ) -> Dict[str, int]:
        """Update candidate hashes for all candidates in a client.
        
        Args:
            db: Database session
            client_id: Client UUID
            force_regenerate: Force regeneration for all candidates
            
        Returns:
            Dictionary with update statistics
        """
        try:
            logger.info(
                "Starting batch candidate hash update",
                client_id=str(client_id),
                force_regenerate=force_regenerate
            )
            
            # Get all candidates for client
            candidates = self.candidate_repository.get_multi(
                db, skip=0, limit=10000, filters={"client_id": client_id}
            )
            
            updated_count = 0
            skipped_count = 0
            error_count = 0
            
            for candidate in candidates:
                try:
                    # Skip if hash exists and not forcing regeneration
                    if candidate.candidate_hash and not force_regenerate:
                        skipped_count += 1
                        continue
                    
                    # Generate and update hash
                    if self.update_candidate_hash(db, candidate.id, force_regenerate):
                        updated_count += 1
                    else:
                        error_count += 1
                        
                except Exception as e:
                    logger.error(
                        "Individual candidate hash update failed",
                        candidate_id=str(candidate.id),
                        error=str(e)
                    )
                    error_count += 1
            
            stats = {
                "total_candidates": len(candidates),
                "updated": updated_count,
                "skipped": skipped_count,
                "errors": error_count
            }
            
            logger.info(
                "Batch candidate hash update completed",
                client_id=str(client_id),
                stats=stats
            )
            
            return stats
            
        except Exception as e:
            logger.error(
                "Batch candidate hash update failed",
                client_id=str(client_id),
                error=str(e)
            )
            return {"total_candidates": 0, "updated": 0, "skipped": 0, "errors": 1}
    
    def get_duplicate_statistics(
        self,
        db: Session,
        client_id: UUID
    ) -> Dict[str, Any]:
        """Get duplicate detection statistics for a client.
        
        Args:
            db: Database session
            client_id: Client UUID
            
        Returns:
            Dictionary with duplicate detection statistics
        """
        try:
            # Get all candidates
            candidates = self.candidate_repository.get_multi(
                db, skip=0, limit=10000, filters={"client_id": client_id}
            )
            
            # Count candidates with hashes
            candidates_with_hash = sum(1 for c in candidates if c.candidate_hash)
            
            # Count flagged applications
            flagged_applications = self.application_repository.get_flagged_applications(
                db, client_id, skip=0, limit=10000
            )
            
            # Count LEFT status candidates
            left_candidates = self.candidate_repository.get_by_status(
                db, client_id, "LEFT", skip=0, limit=10000
            )
            
            stats = {
                "total_candidates": len(candidates),
                "candidates_with_hash": candidates_with_hash,
                "candidates_without_hash": len(candidates) - candidates_with_hash,
                "flagged_applications": len(flagged_applications),
                "left_status_candidates": len(left_candidates),
                "hash_coverage_percentage": (candidates_with_hash / len(candidates) * 100) if candidates else 0
            }
            
            logger.debug(
                "Duplicate detection statistics retrieved",
                client_id=str(client_id),
                stats=stats
            )
            
            return stats
            
        except Exception as e:
            logger.error(
                "Failed to get duplicate statistics",
                client_id=str(client_id),
                error=str(e)
            )
            return {
                "total_candidates": 0,
                "candidates_with_hash": 0,
                "candidates_without_hash": 0,
                "flagged_applications": 0,
                "left_status_candidates": 0,
                "hash_coverage_percentage": 0
            }