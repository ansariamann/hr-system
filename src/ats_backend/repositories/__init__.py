"""Repository pattern implementations for data access."""

from .base import BaseRepository
from .client import ClientRepository
from .candidate import CandidateRepository
from .application import ApplicationRepository
from .resume_job import ResumeJobRepository

__all__ = [
    "BaseRepository",
    "ClientRepository", 
    "CandidateRepository",
    "ApplicationRepository",
    "ResumeJobRepository"
]