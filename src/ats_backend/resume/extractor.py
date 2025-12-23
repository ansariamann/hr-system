"""Data extraction utilities for resume parsing."""

import re
from decimal import Decimal, InvalidOperation
from typing import Dict, Any, List, Optional
import structlog

try:
    from email_validator import validate_email, EmailNotValidError
except ImportError:
    # Fallback if email_validator is not available
    def validate_email(email):
        class ValidatedEmail:
            def __init__(self, email):
                self.email = email
        return ValidatedEmail(email)
    
    class EmailNotValidError(Exception):
        pass

from ats_backend.resume.models import (
    ContactInfo, Experience, Education, Skill, SalaryInfo
)

logger = structlog.get_logger(__name__)


class DataExtractor:
    """Extract structured data from resume text."""
    
    def __init__(self):
        """Initialize data extractor with patterns and configurations."""
        # Email pattern
        self.email_pattern = re.compile(
            r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        )
        
        # Phone patterns
        self.phone_patterns = [
            re.compile(r'(\+91[-.\s]?)?[6-9]\d{9}'),  # Indian mobile
            re.compile(r'\b\d{10}\b'),  # 10-digit numbers
        ]
        
        # Name patterns
        self.name_patterns = [
            re.compile(r'^([A-Z][a-z]+ [A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)', re.MULTILINE),
        ]
        
        # Common skill categories
        self.skill_categories = {
            'programming': ['python', 'java', 'javascript', 'c++', 'c#', 'php', 'ruby'],
            'web': ['html', 'css', 'react', 'angular', 'vue', 'nodejs'],
            'database': ['mysql', 'postgresql', 'mongodb', 'redis'],
            'cloud': ['aws', 'azure', 'gcp', 'docker', 'kubernetes'],
        }
    
    def extract_data(self, text: str) -> Dict[str, Any]:
        """Extract all structured data from resume text."""
        logger.info("Starting data extraction", text_length=len(text))
        
        # Clean text
        cleaned_text = self._clean_text(text)
        
        # Extract components
        contact_info = self._extract_contact_info(cleaned_text)
        skills = self._extract_skills(cleaned_text)
        
        result = {
            'contact_info': contact_info,
            'experience': [],  # Simplified for now
            'education': [],   # Simplified for now
            'skills': skills,
            'salary_info': None,  # Simplified for now
            'parsing_method': 'text_extraction',
            'confidence_score': self._calculate_confidence_score(contact_info, [], skills),
        }
        
        logger.info("Data extraction completed", confidence_score=result['confidence_score'])
        return result
    
    def _clean_text(self, text: str) -> str:
        """Clean and normalize text for better parsing."""
        text = re.sub(r'\s+', ' ', text)
        return text.strip()
    
    def _extract_contact_info(self, text: str) -> ContactInfo:
        """Extract contact information from text."""
        contact_info = ContactInfo()
        
        # Extract email
        email_matches = self.email_pattern.findall(text)
        if email_matches:
            try:
                validated = validate_email(email_matches[0])
                contact_info.email = validated.email
            except EmailNotValidError:
                pass
        
        # Extract phone
        for pattern in self.phone_patterns:
            phone_matches = pattern.findall(text)
            if phone_matches:
                phone = re.sub(r'[^\d+]', '', phone_matches[0])
                if len(phone) >= 10:
                    contact_info.phone = phone
                    break
        
        # Extract name
        for pattern in self.name_patterns:
            name_matches = pattern.findall(text)
            if name_matches:
                name = name_matches[0].strip()
                if len(name.split()) >= 2:
                    contact_info.name = name
                    break
        
        return contact_info
    
    def _extract_skills(self, text: str) -> List[Skill]:
        """Extract skills from text."""
        skills = []
        text_lower = text.lower()
        
        # Extract skills by category
        for category, skill_list in self.skill_categories.items():
            for skill_name in skill_list:
                if skill_name.lower() in text_lower:
                    skills.append(Skill(name=skill_name, category=category))
        
        # Remove duplicates
        seen_skills = set()
        unique_skills = []
        for skill in skills:
            skill_key = skill.name.lower()
            if skill_key not in seen_skills:
                seen_skills.add(skill_key)
                unique_skills.append(skill)
        
        return unique_skills
    
    def _calculate_confidence_score(self, contact_info: ContactInfo, experience: List[Experience], skills: List[Skill]) -> float:
        """Calculate confidence score based on extracted data quality."""
        score = 0.0
        
        if contact_info.name:
            score += 0.3
        if contact_info.email:
            score += 0.2
        if contact_info.phone:
            score += 0.1
        if skills:
            score += 0.2
            if len(skills) >= 3:
                score += 0.2
        
        return min(score, 1.0)