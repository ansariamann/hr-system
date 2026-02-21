"""Client management service."""

from typing import List, Optional
from uuid import UUID
import secrets
import re

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
import structlog

from ats_backend.models.client import Client
from ats_backend.auth.models import User
from ats_backend.auth.utils import create_user, get_password_hash

logger = structlog.get_logger(__name__)


class ClientService:
    """Service for managing client operations."""
    
    @staticmethod
    def create_client(
        db: Session,
        name: str,
        email_domain: Optional[str] = None
    ) -> Client:
        """Create a new client.
        
        Args:
            db: Database session
            name: Client name
            email_domain: Optional email domain for the client
            
        Returns:
            Created client
            
        Raises:
            ValueError: If client creation fails
        """
        try:
            client = Client(
                name=name,
                email_domain=email_domain
            )
            
            db.add(client)
            db.flush()  # Flush without committing - let caller control transaction
            db.refresh(client)
            
            logger.info("Client created", client_id=str(client.id), name=name)
            return client
            
        except IntegrityError as e:
            db.rollback()
            logger.error("Client creation failed", name=name, error=str(e))
            raise ValueError(f"Failed to create client: {str(e)}")

    @staticmethod
    def _slugify(value: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", ".", value.lower()).strip(".")
        return slug or "client"

    @staticmethod
    def _generate_temp_password(length: int = 12) -> str:
        alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789!@#$%"
        return "".join(secrets.choice(alphabet) for _ in range(length))

    @staticmethod
    def _generate_unique_admin_email(
        db: Session,
        client_name: str,
        email_domain: Optional[str]
    ) -> str:
        base_local = "client.admin"
        domain = email_domain or f"{ClientService._slugify(client_name)}.local"
        candidate_email = f"{base_local}@{domain}"

        counter = 1
        while db.query(User).filter(User.email == candidate_email).first():
            candidate_email = f"{base_local}{counter}@{domain}"
            counter += 1

        return candidate_email

    @staticmethod
    def provision_client_with_admin(
        db: Session,
        name: str,
        email_domain: Optional[str] = None
    ) -> tuple[Client, User, str]:
        """Create client and provision a default client_admin user."""
        client = ClientService.create_client(db, name=name, email_domain=email_domain)
        admin_email = ClientService._generate_unique_admin_email(db, name, email_domain)
        admin_password = ClientService._generate_temp_password()

        user = ClientService.create_client_admin_user(
            db=db,
            client_id=client.id,
            email=admin_email,
            password=admin_password,
            full_name=f"{name} Admin"
        )

        return client, user, admin_password
    
    @staticmethod
    def get_client_by_id(db: Session, client_id: UUID) -> Optional[Client]:
        """Get client by ID.
        
        Args:
            db: Database session
            client_id: Client UUID
            
        Returns:
            Client if found, None otherwise
        """
        return db.query(Client).filter(Client.id == client_id).first()
    
    @staticmethod
    def get_client_by_name(db: Session, name: str) -> Optional[Client]:
        """Get client by name.
        
        Args:
            db: Database session
            name: Client name
            
        Returns:
            Client if found, None otherwise
        """
        return db.query(Client).filter(Client.name == name).first()
    
    @staticmethod
    def get_client_by_email_domain(db: Session, email_domain: str) -> Optional[Client]:
        """Get client by email domain.
        
        Args:
            db: Database session
            email_domain: Email domain
            
        Returns:
            Client if found, None otherwise
        """
        return db.query(Client).filter(Client.email_domain == email_domain).first()
    
    @staticmethod
    def list_clients(db: Session, skip: int = 0, limit: int = 100) -> List[Client]:
        """List all clients with pagination.
        
        Args:
            db: Database session
            skip: Number of records to skip
            limit: Maximum number of records to return
            
        Returns:
            List of clients
        """
        return db.query(Client).offset(skip).limit(limit).all()
    
    @staticmethod
    def update_client(
        db: Session,
        client_id: UUID,
        name: Optional[str] = None,
        email_domain: Optional[str] = None
    ) -> Optional[Client]:
        """Update client information.
        
        Args:
            db: Database session
            client_id: Client UUID
            name: New client name (optional)
            email_domain: New email domain (optional)
            
        Returns:
            Updated client if found, None otherwise
        """
        client = db.query(Client).filter(Client.id == client_id).first()
        
        if not client:
            logger.warning("Client not found for update", client_id=str(client_id))
            return None
        
        try:
            if name is not None:
                client.name = name
            if email_domain is not None:
                client.email_domain = email_domain
            
            db.flush()  # Flush without committing - let caller control transaction
            db.refresh(client)
            
            logger.info("Client updated", client_id=str(client_id))
            return client
            
        except IntegrityError as e:
            db.rollback()
            logger.error("Client update failed", client_id=str(client_id), error=str(e))
            raise ValueError(f"Failed to update client: {str(e)}")
    
    @staticmethod
    def delete_client(db: Session, client_id: UUID) -> bool:
        """Delete a client and all associated data.
        
        Args:
            db: Database session
            client_id: Client UUID
            
        Returns:
            True if deleted, False if not found
            
        Note:
            This will cascade delete all associated candidates, applications, etc.
        """
        client = db.query(Client).filter(Client.id == client_id).first()
        
        if not client:
            logger.warning("Client not found for deletion", client_id=str(client_id))
            return False
        
        try:
            db.delete(client)
            db.flush()  # Flush without committing - let caller control transaction
            
            logger.info("Client deleted", client_id=str(client_id))
            return True
            
        except Exception as e:
            db.rollback()
            logger.error("Client deletion failed", client_id=str(client_id), error=str(e))
            raise ValueError(f"Failed to delete client: {str(e)}")
    
    @staticmethod
    def create_client_admin_user(
        db: Session,
        client_id: UUID,
        email: str,
        password: str,
        full_name: Optional[str] = None
    ) -> User:
        """Create an admin user for a client.
        
        Args:
            db: Database session
            client_id: Client UUID
            email: User email
            password: User password
            full_name: User full name (optional)
            
        Returns:
            Created user
            
        Raises:
            ValueError: If user creation fails
        """
        # Verify client exists
        client = ClientService.get_client_by_id(db, client_id)
        if not client:
            raise ValueError(f"Client {client_id} not found")
        
        try:
            user_data = {
                "email": email,
                "password": password,
                "full_name": full_name,
                "client_id": client_id,
                "is_active": True
            }
            
            user = create_user(db, user_data)
            user.role = "client_admin"
            db.flush()
            logger.info("Admin user created for client", 
                       client_id=str(client_id), 
                       user_id=str(user.id),
                       email=email)
            return user
            
        except Exception as e:
            logger.error("Admin user creation failed", 
                        client_id=str(client_id), 
                        email=email, 
                        error=str(e))
            raise ValueError(f"Failed to create admin user: {str(e)}")
    
    @staticmethod
    def get_client_users(db: Session, client_id: UUID) -> List[User]:
        """Get all users for a client.
        
        Args:
            db: Database session
            client_id: Client UUID
            
        Returns:
            List of users for the client
        """
        return db.query(User).filter(User.client_id == client_id).all()
    
    @staticmethod
    def get_client_stats(db: Session, client_id: UUID) -> dict:
        """Get statistics for a client.
        
        Args:
            db: Database session
            client_id: Client UUID
            
        Returns:
            Dictionary with client statistics
        """
        from ats_backend.models.candidate import Candidate
        from ats_backend.models.application import Application
        from ats_backend.models.resume_job import ResumeJob
        
        stats = {
            "total_users": db.query(User).filter(User.client_id == client_id).count(),
            "total_candidates": db.query(Candidate).filter(Candidate.client_id == client_id).count(),
            "total_applications": db.query(Application).filter(Application.client_id == client_id).count(),
            "total_resume_jobs": db.query(ResumeJob).filter(ResumeJob.client_id == client_id).count(),
        }
        
        logger.debug("Client stats retrieved", client_id=str(client_id), stats=stats)
        return stats
