"""Pydantic models for resume parsing results."""

from datetime import datetime, date
from decimal import Decimal
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, EmailStr, validator
import re


class ContactInfo(BaseModel):
    """Contact information extracted from resume."""
    
    name: Optional[str] = Field(None, description="Full name of the candidate")
    email: Optional[EmailStr] = Field(None, description="Email address")
    phone: Optional[str] = Field(None, description="Phone number")
    location: Optional[str] = Field(None, description="Candidate's primary location (City, State, Country)")
    
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
    date_of_birth: Optional[date] = Field(None, description="Candidate date of birth")
    previous_employment: List[Dict[str, Any]] = Field(default_factory=list, description="Previous employment entries")
    key_skill: Optional[str] = Field(None, description="Key skill summary")
    total_experience_years: Optional[Decimal] = Field(None, description="Computed total years of experience")
    linkedin_url: Optional[str] = Field(None, description="Detected LinkedIn profile URL")
    other_details: Dict[str, Any] = Field(default_factory=dict, description="Other details parsed from resume")
    
    # Raw extracted text
    summary: Optional[str] = Field(None, description="Resume summary")
    raw_text: str = Field(default="", description="Complete extracted text")
    
    # Parsing metadata
    parsing_method: str = Field(default="unknown", description="Method used for text extraction")
    confidence_score: float = Field(default=0.0, ge=0.0, le=1.0, description="Parsing confidence")
    parsing_errors: List[str] = Field(default_factory=list)
    
    # Additional structured data
    additional_data: Dict[str, Any] = Field(default_factory=dict)

    def _build_previous_employment_entries(self) -> List[Dict[str, Any]]:
        if self.previous_employment:
            return self.previous_employment

        entries: List[Dict[str, Any]] = []
        for exp in self.experience:
            if not any([exp.company, exp.position, exp.start_date, exp.end_date, exp.duration]):
                continue
            entries.append(
                {
                    "company": exp.company,
                    "position": exp.position,
                    "start_date": exp.start_date,
                    "end_date": exp.end_date,
                    "duration": exp.duration,
                    "is_current": exp.is_current,
                    "description": exp.description,
                }
            )
        return entries

    def _infer_company(self, previous_employment: List[Dict[str, Any]]) -> Optional[str]:
        for exp in self.experience:
            if exp.is_current and exp.company:
                return exp.company

        for exp in self.experience:
            if exp.company:
                return exp.company

        for item in previous_employment:
            company = item.get("company")
            if isinstance(company, str) and company.strip():
                return company.strip()

        return None
    
    def to_candidate_data(self) -> Dict[str, Any]:
        """Convert parsed resume to candidate creation data."""
        previous_employment = self._build_previous_employment_entries()
        inferred_company = self._infer_company(previous_employment)

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
            "company": inferred_company,
            "location": self.contact_info.location,
            "date_of_birth": self.date_of_birth,
            "previous_employment": previous_employment,
            "key_skill": self.key_skill,
            "total_experience_years": self.total_experience_years,
            "linkedin_url": self.linkedin_url,
            "skills": skills_data,
            "experience": experience_data,
            "ctc_current": self.salary_info.current_ctc if self.salary_info else None,
            "ctc_expected": self.salary_info.expected_ctc if self.salary_info else None,
            "status": "ACTIVE",
            "other_details": self.other_details
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
