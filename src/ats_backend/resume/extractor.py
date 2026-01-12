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
        
        # Education patterns
        self.education_header_pattern = re.compile(
            r'(?:education|academic|qualifications|scholastic)', 
            re.IGNORECASE
        )
        
        self.degree_patterns = [
            re.compile(r'\b(?:B\.?Tech|M\.?Tech|B\.?E|M\.?E|B\.?S|M\.?S|B\.?A|M\.?A|Ph\.?D\.?|Bachelor|Master|Diploma)\b', re.IGNORECASE),
            re.compile(r'\b(?:HSC|SSC|High School|Secondary School)\b', re.IGNORECASE),
        ]
        
        self.year_pattern = re.compile(r'\b(19|20)\d{2}\b')
        self.grade_pattern = re.compile(r'\b(?:CGPA|GPA|%|Grade)[\s:-]*([\d.]+%?)', re.IGNORECASE)
        
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
        
        # Clean text for specific regexes, but keep structural text for section parsing
        cleaned_text = self._clean_text(text)
        
        # Extract components
        contact_info = self._extract_contact_info(cleaned_text)
        skills = self._extract_skills(cleaned_text)
        
        # Extract education using the original text (preserving newlines)
        education = self._extract_education(text)
        
        result = {
            'contact_info': contact_info,
            'experience': [],  # Simplified for now
            'education': education,
            'skills': skills,
            'salary_info': None,  # Simplified for now
            'parsing_method': 'text_extraction',
            'confidence_score': self._calculate_confidence_score(contact_info, [], skills, education),
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
    
    def _extract_education(self, text: str) -> List[Education]:
        """Extract education information from text."""
        education_entries = []
        
        # Simple section extraction logic
        lines = text.split('\n')
        in_education_section = False
        current_entry = {}
        
        # Common section headers to detect end of education section
        other_sections = ['experience', 'work', 'skills', 'projects', 'interests', 'certifications', 'achievements', 'languages']
        
        for line in lines:
            line_clean = line.strip()
            if not line_clean:
                continue
            
            # Check for headers
            is_header = False
            # Check if this line is the Education header
            if self.education_header_pattern.search(line_clean) and len(line_clean.split()) < 5:
                in_education_section = True
                continue
            
            # Check if we've hit another section
            for section in other_sections:
                if section in line_clean.lower() and len(line_clean.split()) < 4:
                    if in_education_section:
                        in_education_section = False
                    is_header = True
                    break
            
            if is_header:
                continue
                
            if in_education_section:
                # We are in the education section, try to parse lines as entries or parts of entries
                # This is a very basic parser: assuming each entry might contain a degree, dates, or institution
                
                # Check for Degree
                degree_match = None
                for pattern in self.degree_patterns:
                    match = pattern.search(line_clean)
                    if match:
                        degree_match = match.group(0)
                        break
                
                # Check for Year
                year_match = self.year_pattern.search(line_clean)
                
                # Check for Grade
                grade_match = self.grade_pattern.search(line_clean)
                
                # Identify if this line looks like a new entry (simplistic heuristic: has degree or year)
                if degree_match or year_match:
                    # Save previous entry if it exists and has at least some data
                    if current_entry and (current_entry.get('degree') or current_entry.get('institution')):
                        education_entries.append(Education(**current_entry))
                        current_entry = {}
                    
                    if degree_match:
                        current_entry['degree'] = degree_match
                    
                    if year_match:
                        current_entry['year'] = year_match.group(0)
                        
                    if grade_match:
                        current_entry['grade'] = grade_match.group(1)
                    
                    # Assume the rest of the line or adjacent text might be institution
                    # If line has degree, maybe other parts are institution?
                    # For now, simplistic approach: if line is not just the degree/date, keep it as text
                    # A better way might be to look for "University" or "College" in this line
                    if "university" in line_clean.lower() or "college" in line_clean.lower() or "institute" in line_clean.lower() or "school" in line_clean.lower():
                        current_entry['institution'] = line_clean
                    elif not current_entry.get('institution') and not degree_match and not year_match:
                         # Any other line in education section could be institution?
                         # This is risky. Let's only capture if it has keywords for now.
                         pass

                elif current_entry:
                     # Continuation of previous entry?
                     if "university" in line_clean.lower() or "college" in line_clean.lower() or "institute" in line_clean.lower() or "school" in line_clean.lower():
                        current_entry['institution'] = line_clean
                     elif grade_match:
                        current_entry['grade'] = grade_match.group(1)
        
        # Append the last entry
        if current_entry and (current_entry.get('degree') or current_entry.get('institution')):
            education_entries.append(Education(**current_entry))
            
        return education_entries

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
    
    def _calculate_confidence_score(self, contact_info: ContactInfo, experience: List[Experience], skills: List[Skill], education: List[Education]) -> float:
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
                score += 0.1
        if education:
            score += 0.1
        
        return min(score, 1.0)