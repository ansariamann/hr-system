#!/usr/bin/env python3
"""Management script for duplicate detection operations."""

import sys
import argparse
from pathlib import Path
from uuid import UUID
import structlog

# Add the src directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ats_backend.core.database import get_db
from ats_backend.services.duplicate_detection_service import DuplicateDetectionService
from ats_backend.services.candidate_service import CandidateService
from ats_backend.repositories.client import ClientRepository

logger = structlog.get_logger(__name__)


def setup_logging():
    """Set up structured logging."""
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer()
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


def update_hashes(client_id: str, force: bool = False):
    """Update candidate hashes for a client.
    
    Args:
        client_id: Client UUID string
        force: Force regeneration of existing hashes
    """
    try:
        db = next(get_db())
        duplicate_service = DuplicateDetectionService()
        
        print(f"Updating candidate hashes for client {client_id}...")
        
        stats = duplicate_service.batch_update_candidate_hashes(
            db=db,
            client_id=UUID(client_id),
            force_regenerate=force
        )
        
        print(f"Hash update completed:")
        print(f"  Total candidates: {stats['total_candidates']}")
        print(f"  Updated: {stats['updated']}")
        print(f"  Skipped: {stats['skipped']}")
        print(f"  Errors: {stats['errors']}")
        
        db.close()
        
    except Exception as e:
        print(f"Error updating hashes: {e}")
        sys.exit(1)


def detect_duplicates(client_id: str, candidate_name: str, candidate_email: str = None, candidate_phone: str = None):
    """Detect duplicates for a candidate.
    
    Args:
        client_id: Client UUID string
        candidate_name: Candidate name
        candidate_email: Candidate email (optional)
        candidate_phone: Candidate phone (optional)
    """
    try:
        db = next(get_db())
        duplicate_service = DuplicateDetectionService()
        
        candidate_data = {
            "name": candidate_name,
            "email": candidate_email,
            "phone": candidate_phone
        }
        
        print(f"Detecting duplicates for candidate: {candidate_name}")
        
        result = duplicate_service.detect_duplicates(
            db=db,
            client_id=UUID(client_id),
            candidate_data=candidate_data
        )
        
        print(f"Duplicate detection results:")
        print(f"  Has duplicates: {result.has_duplicates}")
        print(f"  Should flag: {result.should_flag}")
        print(f"  Candidate hash: {result.candidate_hash[:16]}...")
        
        if result.flag_reason:
            print(f"  Flag reason: {result.flag_reason}")
        
        if result.matches:
            print(f"  Found {len(result.matches)} potential matches:")
            for i, match in enumerate(result.matches, 1):
                print(f"    {i}. Candidate {match.candidate.id}")
                print(f"       Similarity: {match.similarity_score:.3f}")
                print(f"       Match type: {match.match_type}")
                print(f"       Matching fields: {', '.join(match.matching_fields)}")
                print(f"       Status: {match.candidate.status}")
        
        db.close()
        
    except Exception as e:
        print(f"Error detecting duplicates: {e}")
        sys.exit(1)


def get_statistics(client_id: str):
    """Get duplicate detection statistics for a client.
    
    Args:
        client_id: Client UUID string
    """
    try:
        db = next(get_db())
        duplicate_service = DuplicateDetectionService()
        
        print(f"Getting duplicate detection statistics for client {client_id}...")
        
        stats = duplicate_service.get_duplicate_statistics(
            db=db,
            client_id=UUID(client_id)
        )
        
        print(f"Duplicate detection statistics:")
        print(f"  Total candidates: {stats['total_candidates']}")
        print(f"  Candidates with hash: {stats['candidates_with_hash']}")
        print(f"  Candidates without hash: {stats['candidates_without_hash']}")
        print(f"  Hash coverage: {stats['hash_coverage_percentage']:.1f}%")
        print(f"  Flagged applications: {stats['flagged_applications']}")
        print(f"  LEFT status candidates: {stats['left_status_candidates']}")
        
        db.close()
        
    except Exception as e:
        print(f"Error getting statistics: {e}")
        sys.exit(1)


def list_clients():
    """List all clients in the system."""
    try:
        db = next(get_db())
        client_repo = ClientRepository()
        
        clients = client_repo.get_multi(db, skip=0, limit=100)
        
        print("Available clients:")
        for client in clients:
            print(f"  {client.id} - {client.name}")
        
        db.close()
        
    except Exception as e:
        print(f"Error listing clients: {e}")
        sys.exit(1)


def main():
    """Main entry point."""
    setup_logging()
    
    parser = argparse.ArgumentParser(description="Manage duplicate detection operations")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Update hashes command
    update_parser = subparsers.add_parser("update-hashes", help="Update candidate hashes")
    update_parser.add_argument("client_id", help="Client UUID")
    update_parser.add_argument("--force", action="store_true", help="Force regeneration of existing hashes")
    
    # Detect duplicates command
    detect_parser = subparsers.add_parser("detect", help="Detect duplicates for a candidate")
    detect_parser.add_argument("client_id", help="Client UUID")
    detect_parser.add_argument("name", help="Candidate name")
    detect_parser.add_argument("--email", help="Candidate email")
    detect_parser.add_argument("--phone", help="Candidate phone")
    
    # Statistics command
    stats_parser = subparsers.add_parser("stats", help="Get duplicate detection statistics")
    stats_parser.add_argument("client_id", help="Client UUID")
    
    # List clients command
    subparsers.add_parser("list-clients", help="List all clients")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    if args.command == "update-hashes":
        update_hashes(args.client_id, args.force)
    elif args.command == "detect":
        detect_duplicates(args.client_id, args.name, args.email, args.phone)
    elif args.command == "stats":
        get_statistics(args.client_id)
    elif args.command == "list-clients":
        list_clients()
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()