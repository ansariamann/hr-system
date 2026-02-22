"""Data extraction utilities for resume parsing."""

import re
from datetime import datetime
from decimal import Decimal
from typing import Dict, Any, List
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
            r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"
        )
        
        # Phone patterns
        self.phone_patterns = [
            # International-like phone candidates; final validation is done in _normalize_phone.
            re.compile(r"(?:\+?\d[\d\-\s().]{8,}\d)"),
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
            'languages': ['python', 'java', 'javascript', 'typescript', 'c++', 'c#', 'php', 'ruby', 'go', 'rust', 'swift', 'kotlin', 'scala', 'perl', 'r', 'matlab', 'dart', 'shell', 'bash', 'sql', 'html', 'css'],
            'frameworks': ['react', 'angular', 'vue', 'next.js', 'django', 'flask', 'fastapi', 'spring', 'spring boot', 'laravel', 'rails', 'ruby on rails', 'express', 'node.js', 'dotnet', '.net', 'tensorflow', 'pytorch', 'pandas', 'numpy', 'scikit-learn', 'keras', 'flutter', 'react native'],
            'databases': ['mysql', 'postgresql', 'postgres', 'mongodb', 'redis', 'cassandra', 'elasticsearch', 'oracle', 'sql server', 'sqlite', 'dynamodb', 'firebase', 'mariadb'],
            'cloud': ['aws', 'azure', 'gcp', 'google cloud', 'docker', 'kubernetes', 'jenkins', 'circleci', 'gitlab ci', 'github actions', 'terraform', 'ansible', 'prometheus', 'grafana', 'elk stack'],
            'tools': ['git', 'github', 'gitlab', 'bitbucket', 'jira', 'confluence', 'slack', 'trello', 'asana', 'figma', 'postman', 'swagger', 'vs code', 'pycharm', 'intellij', 'eclipse'],
            'concepts': ['rest api', 'graphql', 'grpc', 'microservices', 'serverless', 'agile', 'scrum', 'ci/cd', 'devops', 'machine learning', 'artificial intelligence', 'data science', 'big data', 'blockchain'],
            'soft_skills': ['leadership', 'communication', 'teamwork', 'problem solving', 'critical thinking', 'time management', 'adaptability', 'mentoring']
        }
        self._skill_patterns = self._build_skill_patterns()
        self.dob_patterns = [
            re.compile(r"\b(?:dob|date of birth)\s*[:\-]?\s*(\d{1,2}[\/\-.]\d{1,2}[\/\-.]\d{2,4})\b", re.IGNORECASE),
            re.compile(r"\b(\d{1,2}[\/\-.]\d{1,2}[\/\-.]\d{4})\b"),
        ]
        self.present_address_pattern = re.compile(r"\b(?:present|current)\s+address\s*[:\-]?\s*(.+)", re.IGNORECASE)
        self.permanent_address_pattern = re.compile(r"\bpermanent\s+address\s*[:\-]?\s*(.+)", re.IGNORECASE)
        self.ctc_patterns = {
            "current": re.compile(r"\b(?:current|present)\s+ctc\s*[:\-]?\s*([0-9][0-9.,]*(?:\s*(?:lpa|lac|lakh|lakhs|cr|crore|crores))?)", re.IGNORECASE),
            "expected": re.compile(r"\b(?:expected)\s+ctc\s*[:\-]?\s*([0-9][0-9.,]*(?:\s*(?:lpa|lac|lakh|lakhs|cr|crore|crores))?)", re.IGNORECASE),
        }
        self.employer_patterns = [
            re.compile(r"\b(?:worked at|employed at|company)\s*[:\-]?\s*([A-Z][A-Za-z0-9&.,\-\s]{2,60})", re.IGNORECASE),
            re.compile(r"\bat\s+([A-Z][A-Za-z0-9&.,\-\s]{2,60})", re.IGNORECASE),
        ]
    
    def extract_data(self, text: str) -> Dict[str, Any]:
        """Extract all structured data from resume text."""
        logger.info("Starting data extraction", text_length=len(text))
        
        # Clean text for specific regexes, but keep structural text for section parsing
        cleaned_text = self._clean_text(text)
        
        # Extract components
        contact_info = self._extract_contact_info(text)
        skills = self._extract_skills(cleaned_text)
        salary_info = self._extract_salary_info(text)
        date_of_birth = self._extract_date_of_birth(text)
        present_address, permanent_address = self._extract_addresses(text)
        previous_employment = self._extract_previous_employment(text)
        key_skill = ", ".join([skill.name for skill in skills[:8]]) if skills else None
        if present_address and not contact_info.location:
            contact_info.location = present_address.split(",")[0].strip()
        
        # Extract education using the original text (preserving newlines)
        education = self._extract_education(text)
        
        result = {
            'contact_info': contact_info,
            'experience': [],  # Simplified for now
            'education': education,
            'skills': skills,
            'salary_info': salary_info,
            'date_of_birth': date_of_birth,
            'present_address': present_address,
            'permanent_address': permanent_address,
            'previous_employment': previous_employment,
            'key_skill': key_skill,
            'parsing_method': 'text_extraction',
            'confidence_score': self._calculate_confidence_score(contact_info, [], skills, education),
        }
        
        logger.info("Data extraction completed", confidence_score=result['confidence_score'])
        return result
    
    def _clean_text(self, text: str) -> str:
        """Clean and normalize text for better parsing."""
        text = re.sub(r"\r\n?", "\n", text)
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    def _build_skill_patterns(self) -> Dict[str, re.Pattern]:
        patterns: Dict[str, re.Pattern] = {}
        for skill_list in self.skill_categories.values():
            for skill_name in skill_list:
                escaped = re.escape(skill_name)
                patterns[skill_name] = re.compile(
                    rf"(?<![A-Za-z0-9]){escaped}(?![A-Za-z0-9])",
                    re.IGNORECASE,
                )
        return patterns

    def _normalize_phone(self, phone_candidate: str) -> str:
        digits = re.sub(r"[^\d+]", "", phone_candidate)
        if digits.startswith("00"):
            digits = f"+{digits[2:]}"
        if digits.count("+") > 1:
            digits = digits.replace("+", "")
        if "+" in digits and not digits.startswith("+"):
            digits = digits.replace("+", "")
        digit_count = len(re.sub(r"\D", "", digits))
        if 10 <= digit_count <= 15:
            return digits
        return ""

    def _extract_name(self, text: str) -> str:
        header_stop_words = {
            "resume", "curriculum", "vitae", "profile", "summary", "objective",
            "experience", "education", "skills", "projects", "certifications",
        }
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

        # Prefer first non-header lines, where names typically appear.
        for line in lines[:12]:
            line_lower = line.lower()
            if any(token in line_lower for token in ("@", "http", "linkedin", "github")):
                continue
            if any(char.isdigit() for char in line):
                continue
            if any(word in header_stop_words for word in line_lower.split()):
                continue
            if len(line.split()) < 2 or len(line.split()) > 5:
                continue
            if len(line) > 60:
                continue
            if re.search(r"[^A-Za-z.\-'\s]", line):
                continue
            normalized = " ".join(word.capitalize() for word in line.split())
            return normalized
        return ""
    
    def _extract_contact_info(self, text: str) -> ContactInfo:
        """Extract contact information from text."""
        contact_info = ContactInfo()
        
        # Extract email
        email_matches = list(dict.fromkeys(self.email_pattern.findall(text)))
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
                phone = self._normalize_phone(phone_matches[0])
                if phone:
                    contact_info.phone = phone
                    break
        
        # Extract name using line-based heuristic first, regex fallback second.
        extracted_name = self._extract_name(text)
        if extracted_name:
            contact_info.name = extracted_name
        else:
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
        
        # Extract skills by category
        for category, skill_list in self.skill_categories.items():
            for skill_name in skill_list:
                skill_pattern = self._skill_patterns.get(skill_name)
                if skill_pattern and skill_pattern.search(text):
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

    def _extract_date_of_birth(self, text: str):
        for pattern in self.dob_patterns:
            for match in pattern.findall(text):
                raw = match if isinstance(match, str) else match[0]
                normalized = raw.replace(".", "/").replace("-", "/")
                for fmt in ("%d/%m/%Y", "%d/%m/%y", "%m/%d/%Y", "%m/%d/%y"):
                    try:
                        parsed = datetime.strptime(normalized, fmt).date()
                        if 1950 <= parsed.year <= datetime.utcnow().year - 14:
                            return parsed
                    except ValueError:
                        continue
        return None

    def _extract_addresses(self, text: str):
        present_address = None
        permanent_address = None
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

        for line in lines:
            if not present_address:
                match = self.present_address_pattern.search(line)
                if match:
                    present_address = match.group(1).strip(" ,.-")
            if not permanent_address:
                match = self.permanent_address_pattern.search(line)
                if match:
                    permanent_address = match.group(1).strip(" ,.-")
            if present_address and permanent_address:
                break

        if not present_address:
            generic = next((ln for ln in lines if "address" in ln.lower() and "email" not in ln.lower()), None)
            if generic:
                parts = re.split(r"address\s*[:\-]?", generic, flags=re.IGNORECASE)
                if len(parts) > 1 and parts[1].strip():
                    present_address = parts[1].strip(" ,.-")

        return present_address, permanent_address

    def _extract_salary_info(self, text: str):
        current_ctc = None
        expected_ctc = None
        raw_fragments = []

        current_match = self.ctc_patterns["current"].search(text)
        expected_match = self.ctc_patterns["expected"].search(text)

        if current_match:
            raw = current_match.group(1).strip()
            raw_fragments.append(f"current={raw}")
            current_ctc = self._normalize_ctc_value(raw)

        if expected_match:
            raw = expected_match.group(1).strip()
            raw_fragments.append(f"expected={raw}")
            expected_ctc = self._normalize_ctc_value(raw)

        if current_ctc is None and expected_ctc is None:
            return None

        return SalaryInfo(
            current_ctc=current_ctc,
            expected_ctc=expected_ctc,
            raw_text="; ".join(raw_fragments) if raw_fragments else None,
        )

    def _normalize_ctc_value(self, raw: str):
        lower = raw.lower()
        numeric_part = re.sub(r"[^0-9.]", "", raw)
        if not numeric_part:
            return None
        try:
            value = Decimal(numeric_part)
        except Exception:
            return None

        if any(token in lower for token in ["cr", "crore"]):
            value *= Decimal(10000000)
        elif any(token in lower for token in ["lpa", "lac", "lakh"]):
            value *= Decimal(100000)

        return value

    def _extract_previous_employment(self, text: str) -> List[Dict[str, Any]]:
        entries: List[Dict[str, Any]] = []
        seen = set()

        for pattern in self.employer_patterns:
            for match in pattern.findall(text):
                company = match.strip(" ,.-")
                if len(company) < 3:
                    continue
                lower = company.lower()
                if lower in seen:
                    continue
                seen.add(lower)
                entries.append({"company": company})
                if len(entries) >= 10:
                    return entries

        return entries
    
    def _calculate_confidence_score(self, contact_info: ContactInfo, experience: List[Experience], skills: List[Skill], education: List[Education]) -> float:
        """Calculate confidence score based on extracted data quality."""
        score = 0.0
        
        if contact_info.name:
            score += 0.25
        if contact_info.email:
            score += 0.25
        if contact_info.phone:
            score += 0.15
        if skills:
            score += 0.2
            if len(skills) >= 5:
                score += 0.1
        if education:
            score += 0.05
        if experience:
            score += 0.1
        
        return min(score, 1.0)
