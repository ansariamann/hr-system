"""Pydantic models for resume parsing results."""

from datetime import datetime
from decimal import Decimal
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, EmailStr, validator
import re


class ContactInfo(BaseModel):
    """Contact information extracted from resume."""
    
    name: Optional[str] = Field(None, description="Full name of the candidate")
    email: Optional[EmailStr] = Field(None, description="Email address")
    phone: Optional[str] = Field(None, description="Phone number")
    location: Optional[str] = Field(None, description="Location/address")
    
    @validator('phone')
    def validate_phone(cls, v):
        """Validate and normalize phone number."""
        if v is not None:
            # Remove common separators and normalize
            cleaned = re.sub(r'[^\d+]', '', v)
            if len(cleaned) >= 10:  # Minimum valid phone length
                return cleaned
        return v


class Experience(BaseModel):
    """Work experience entry."""
    
    company: Optional[str] = Field(None, description="Company name")
    position: Optional[str] = Field(None, description="Job position/title")
    duration: Optional[str] = Field(None, description="Duration of employment")
    description: Optional[str] = Field(None, description="Job description")
    start_date: Optional[str] = Field(None, description="Start date")
    end_date: Optional[str] = Field(None, description="End date")
    is_current: bool = Field(default=False, description="Is this the current job")


class Education(BaseModel):
    """Education entry."""
    
    institution: Optional[str] = Field(None, description="Educational institution")
    degree: Optional[str] = Field(None, description="Degree/qualification")
    field: Optional[str] = Field(None, description="Field of study")
    year: Optional[str] = Field(None, description="Graduation year")
    grade: Optional[str] = Field(None, description="Grade/GPA")


class Skill(BaseModel):
    """Skill entry."""
    
    name: str = Field(..., description="Skill name")
    category: Optional[str] = Field(None, description="Skill category (technical, soft, etc.)")
    level: Optional[str] = Field(None, description="Proficiency level")


class SalaryInfo(BaseModel):
    """Salary/compensation information."""
    
    current_ctc: Optional[Decimal] = Field(None, description="Current CTC in decimal format")
    expected_ctc: Optional[Decimal] = Field(None, description="Expected CTC in decimal format")
    currency: str = Field(default="INR", description="Currency code")
    raw_text: Optional[str] = Field(None, description="Original salary text from resume")


class ParsedResume(BaseModel):
    """Complete parsed resume data."""
    
    contact_info: ContactInfo = Field(default_factory=ContactInfo)
    experience: List[Experience] = Field(default_factory=list)
    education: List[Education] = Field(default_factory=list)
    skills: List[Skill] = Field(default_factory=list)
    salary_info: Optional[SalaryInfo] = Field(None)
    
    # Raw extracted text
    raw_text: str = Field(default="", description="Complete extracted text")
    
    # Parsing metadata
    parsing_method: str = Field(default="unknown", description="Method used for text extraction")
    confidence_score: float = Field(default=0.0, ge=0.0, le=1.0, description="Parsing confidence")
    parsing_errors: List[str] = Field(default_factory=list)
    
    # Additional structured data
    additional_data: Dict[str, Any] = Field(default_factory=dict)
    
    def to_candidate_data(self) -> Dict[str, Any]:
        """Convert parsed resume to candidate creation data."""
        # Prepare skills in JSONB format
        skills_data = {
            "skills": [skill.name for skill in self.skills],
            "skill_categories": {},
            "parsing_metadata": {
                "method": self.parsing_method,
                "confidence": self.confidence_score,
                "parsed_at": datetime.utcnow().isoformat()
            }
        }
        
        # Group skills by category
        for skill in self.skills:
            if skill.category:
                if skill.category not in skills_data["skill_categories"]:
                    skills_data["skill_categories"][skill.category] = []
                skills_data["skill_categories"][skill.category].append({
                    "name": skill.name,
                    "level": skill.level
                })
        
        # Prepare experience in JSONB format
        experience_data = {
            "work_experience": [
                {
                    "company": exp.company,
                    "position": exp.position,
                    "duration": exp.duration,
                    "description": exp.description,
                    "start_date": exp.start_date,
                    "end_date": exp.end_date,
                    "is_current": exp.is_current
                }
                for exp in self.experience
            ],
            "education": [
                {
                    "institution": edu.institution,
                    "degree": edu.degree,
                    "field": edu.field,
                    "year": edu.year,
                    "grade": edu.grade
                }
                for edu in self.education
            ],
            "parsing_metadata": {
                "method": self.parsing_method,
                "confidence": self.confidence_score,
                "parsed_at": datetime.utcnow().isoformat()
            }
        }
        
        return {
            "name": self.contact_info.name,
            "email": self.contact_info.email,
            "phone": self.contact_info.phone,
            "skills": skills_data,
            "experience": experience_data,
            "ctc_current": self.salary_info.current_ctc if self.salary_info else None,
            "ctc_expected": self.salary_info.expected_ctc if self.salary_info else None,
            "status": "ACTIVE"
        }
    
    def get_candidate_hash_data(self) -> Dict[str, str]:
        """Get data for generating candidate hash for duplicate detection."""
        return {
            "name": self.contact_info.name or "",
            "email": self.contact_info.email or "",
            "phone": self.contact_info.phone or ""
        }


class ParsingResult(BaseModel):
    """Result of resume parsing operation."""
    
    success: bool = Field(..., description="Whether parsing was successful")
    parsed_resume: Optional[ParsedResume] = Field(None, description="Parsed resume data")
    error_message: Optional[str] = Field(None, description="Error message if parsing failed")
    processing_time: float = Field(default=0.0, description="Processing time in seconds")
    file_info: Dict[str, Any] = Field(default_factory=dict, description="File metadata")