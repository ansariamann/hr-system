"""Data extraction utilities for resume parsing."""

import re
from datetime import datetime
from decimal import Decimal
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
        self.ctc_patterns = {
            "current": re.compile(r"\b(?:current|present)\s+ctc\s*[:\-]?\s*([0-9][0-9.,]*(?:\s*(?:lpa|lac|lakh|lakhs|cr|crore|crores))?)", re.IGNORECASE),
            "expected": re.compile(r"\b(?:expected)\s+ctc\s*[:\-]?\s*([0-9][0-9.,]*(?:\s*(?:lpa|lac|lakh|lakhs|cr|crore|crores))?)", re.IGNORECASE),
        }
        self.employer_patterns = [
            re.compile(r"\b(?:worked at|employed at|company)\s*[:\-]?\s*([A-Z][A-Za-z0-9&.,\-\s]{2,60})", re.IGNORECASE),
            re.compile(r"\bat\s+([A-Z][A-Za-z0-9&.,\-\s]{2,60})", re.IGNORECASE),
        ]
        self.url_pattern = re.compile(r"\b(?:https?://|www\.)[^\s<>()]+", re.IGNORECASE)
        self.linkedin_pattern = re.compile(
            r"(?:(?:https?://)?(?:[a-z]{2,3}\.)?linkedin\.com/"
            r"(?:(?:in|pub|company)/[A-Za-z0-9%._\-]+(?:/[A-Za-z0-9%._\-]+)*)"
            r"/?)",
            re.IGNORECASE,
        )
        self.date_range_pattern = re.compile(
            r"(?P<start>(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?\s+\d{4}|\d{1,2}[/-]\d{4}|\d{4})\s*(?:-|–|—|to)\s*(?P<end>(?:present|current|now|till date|till now|ongoing|(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?\s+\d{4}|\d{1,2}[/-]\d{4}|\d{4}))",
            re.IGNORECASE,
        )
        self.unmapped_section_aliases: Dict[str, List[str]] = {
            "summary": ["summary", "professional summary", "profile", "career summary"],
            "objective": ["objective", "career objective"],
            "projects": ["projects", "project experience", "academic projects", "personal projects"],
            "certifications": ["certifications", "certificates", "licenses"],
            "achievements": ["achievements", "accomplishments", "awards", "honors"],
            "publications": ["publications", "research", "papers"],
            "languages_spoken": ["languages", "language proficiency"],
            "interests": ["interests", "hobbies", "extracurricular activities"],
            "volunteering": ["volunteering", "volunteer experience", "community work"],
        }
        self.mapped_section_aliases: List[str] = [
            "experience", "work experience", "employment history", "professional experience",
            "education", "academic background", "qualifications", "skills", "technical skills",
            "contact", "personal details", "salary", "ctc", "date of birth",
        ]
    
    def extract_data(self, text: str, extra_links: Optional[List[str]] = None) -> Dict[str, Any]:
        """Extract all structured data from resume text."""
        logger.info("Starting data extraction", text_length=len(text))
        
        # Clean text for specific regexes, but keep structural text for section parsing
        cleaned_text = self._clean_text(text)
        
        # Extract components
        contact_info = self._extract_contact_info(text)
        skills = self._extract_skills(cleaned_text)
        experience = self._extract_experience(text)
        salary_info = self._extract_salary_info(text)
        date_of_birth = self._extract_date_of_birth(text)
        previous_employment = self._extract_previous_employment(text)
        key_skill = ", ".join([skill.name for skill in skills[:8]]) if skills else None
        linkedin_url = self._extract_linkedin_url(text, extra_links=extra_links or [])
        total_experience_years = self._calculate_total_experience_years(experience)
        
        # Extract education using the original text (preserving newlines)
        education = self._extract_education(text)
        
        extracted_urls = self._extract_urls(text, extra_links=extra_links or [])
        other_details = self._build_other_details(
            text=text,
            urls=extracted_urls,
            linkedin_url=linkedin_url,
            education=education,
            experience=experience,
            skills=skills,
        )

        result = {
            'contact_info': contact_info,
            'experience': experience,
            'education': education,
            'skills': skills,
            'salary_info': salary_info,
            'date_of_birth': date_of_birth,
            'previous_employment': previous_employment,
            'key_skill': key_skill,
            'total_experience_years': total_experience_years,
            'linkedin_url': linkedin_url,
            'other_details': other_details,
            'parsing_method': 'text_extraction',
            'confidence_score': self._calculate_confidence_score(contact_info, experience, skills, education),
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

    def _extract_experience(self, text: str) -> List[Experience]:
        """Extract work experience, preferring the explicit Experience section."""
        entries: List[Experience] = []
        section_lines = self._extract_section_lines(
            text,
            {"experience", "work experience", "employment history", "professional experience", "work history"},
        )

        if section_lines:
            entries.extend(self._parse_experience_section(section_lines))

        if entries:
            return entries[:15]

        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        for line in lines:
            fallback_entry = self._parse_experience_line(line)
            if fallback_entry:
                entries.append(fallback_entry)
            if len(entries) >= 15:
                break

        return entries

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
        experience_entries = self._extract_experience(text)
        if experience_entries:
            structured_entries: List[Dict[str, Any]] = []
            seen_companies = set()
            for exp in experience_entries:
                company = (exp.company or "").strip()
                position = (exp.position or "").strip()
                if not company and not position:
                    continue
                dedupe_key = f"{company.lower()}::{position.lower()}"
                if dedupe_key in seen_companies:
                    continue
                seen_companies.add(dedupe_key)
                structured_entries.append(
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
            if structured_entries:
                return structured_entries[:10]

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

    def _extract_urls(self, text: str, extra_links: Optional[List[str]] = None) -> List[str]:
        urls = [u.strip(".,);]}>") for u in self.url_pattern.findall(text)]
        urls.extend(extra_links or [])
        normalized: List[str] = []
        seen = set()
        for url in urls:
            if not url:
                continue
            if url.lower().startswith("www."):
                url = f"https://{url}"
            key = url.lower()
            if key in seen:
                continue
            seen.add(key)
            normalized.append(url)
        return normalized

    def _extract_linkedin_url(self, text: str, extra_links: Optional[List[str]] = None) -> Optional[str]:
        sources = [text]
        if extra_links:
            sources.append(" ".join(extra_links))
        for source in sources:
            matches = self.linkedin_pattern.findall(source)
            for matched in matches:
                url = matched.strip(".,);]}>")
                if not url.lower().startswith("http"):
                    url = f"https://{url}"
                lowered = url.lower()
                if "/in/" in lowered or "/pub/" in lowered:
                    return url
                if "/company/" in lowered:
                    company_url = url
            if 'company_url' in locals():
                return company_url
        return None

    def _extract_section_lines(self, text: str, target_headers: set[str]) -> List[str]:
        lines = text.splitlines()
        collected: List[str] = []
        in_target = False

        for raw_line in lines:
            line = raw_line.strip()
            if not line:
                if in_target and collected and collected[-1] != "":
                    collected.append("")
                continue

            normalized = re.sub(r"[^a-zA-Z ]", " ", line).strip().lower()
            normalized = re.sub(r"\s+", " ", normalized)
            if normalized in target_headers:
                in_target = True
                continue

            if in_target and normalized in self.mapped_section_aliases:
                break
            if in_target and any(normalized in aliases for aliases in self.unmapped_section_aliases.values()):
                break

            if in_target:
                collected.append(line)

        while collected and collected[0] == "":
            collected.pop(0)
        while collected and collected[-1] == "":
            collected.pop()
        return collected

    def _looks_like_job_title(self, line: str) -> bool:
        lowered = line.lower()
        title_tokens = {
            "engineer", "developer", "manager", "analyst", "consultant", "lead",
            "architect", "specialist", "intern", "administrator", "designer",
            "director", "executive", "associate", "officer", "coordinator",
            "tester", "devops", "qa", "scientist", "recruiter",
        }
        return any(token in lowered for token in title_tokens)

    def _looks_like_company_name(self, line: str) -> bool:
        lowered = line.lower()
        company_tokens = {"pvt", "ltd", "llc", "inc", "corp", "company", "technologies", "solutions", "systems", "labs"}
        if any(token in lowered for token in company_tokens):
            return True
        words = [word for word in re.split(r"\s+", line) if word]
        return 1 <= len(words) <= 6 and sum(1 for word in words if word[:1].isupper()) >= max(1, len(words) - 1)

    def _parse_experience_line(self, line: str) -> Optional[Experience]:
        match = self.date_range_pattern.search(line)
        if not match:
            return None

        start_raw = match.group("start")
        end_raw = match.group("end")
        before = line[: match.start()].strip(" |,-:")
        after = line[match.end() :].strip(" |,-:")

        company = before or None
        position = after or None
        if company and len(company) > 120:
            company = company[:120].strip()
        if position and len(position) > 120:
            position = position[:120].strip()

        return Experience(
            company=company,
            position=position,
            duration=f"{start_raw} - {end_raw}",
            start_date=start_raw,
            end_date=end_raw,
            is_current=end_raw.lower() in {"present", "current", "now", "till date", "till now", "ongoing"},
            description=line,
        )

    def _parse_experience_section(self, lines: List[str]) -> List[Experience]:
        parsed_entries: List[Experience] = []
        date_indexes = [index for index, line in enumerate(lines) if self.date_range_pattern.search(line)]

        for seq, date_index in enumerate(date_indexes):
            date_line = lines[date_index]
            match = self.date_range_pattern.search(date_line)
            if not match:
                continue
            start_raw = match.group("start")
            end_raw = match.group("end")
            prev_date_index = date_indexes[seq - 1] if seq > 0 else -1
            next_date_index = date_indexes[seq + 1] if seq + 1 < len(date_indexes) else len(lines)

            context_before = [
                line for line in lines[prev_date_index + 1 : date_index] if line.strip()
            ]
            context_after: List[str] = []
            blank_seen = False
            for line in lines[date_index + 1 : next_date_index]:
                if not line.strip():
                    if context_after:
                        break
                    blank_seen = True
                    continue
                if blank_seen and context_after:
                    break
                context_after.append(line)
            company: Optional[str] = None
            position: Optional[str] = None
            description_lines: List[str] = []

            if context_before:
                if len(context_before) >= 2:
                    position = context_before[-2]
                    company = context_before[-1]
                    if self._looks_like_company_name(position) and self._looks_like_job_title(company):
                        position, company = company, position
                else:
                    single_line = context_before[-1]
                    if self._looks_like_job_title(single_line):
                        position = single_line
                    elif self._looks_like_company_name(single_line):
                        company = single_line
                description_lines.extend(context_before[:-2] if len(context_before) >= 2 else [])

            before = date_line[: match.start()].strip(" |,-:")
            after = date_line[match.end() :].strip(" |,-:")
            if not company and before:
                company = before
            if not position and after:
                position = after

            for line in context_after:
                if not position and self._looks_like_job_title(line):
                    position = line
                    continue
                if not company and self._looks_like_company_name(line):
                    company = line
                    continue
                description_lines.append(line)

            parsed_entries.append(
                Experience(
                    company=company[:120].strip() if company else None,
                    position=position[:120].strip() if position else None,
                    duration=f"{start_raw} - {end_raw}",
                    start_date=start_raw,
                    end_date=end_raw,
                    is_current=end_raw.lower() in {"present", "current", "now", "till date", "till now", "ongoing"},
                    description="\n".join([line for line in description_lines if line.strip()]) or date_line,
                )
            )

        return parsed_entries

    def _normalize_section_header(self, line: str) -> Optional[str]:
        cleaned = re.sub(r"[^a-zA-Z ]", " ", line).strip().lower()
        cleaned = re.sub(r"\s+", " ", cleaned)
        if not cleaned or len(cleaned.split()) > 5:
            return None

        for canonical, aliases in self.unmapped_section_aliases.items():
            if cleaned in aliases:
                return canonical

        if cleaned in self.mapped_section_aliases:
            return "__mapped__"

        return None

    def _extract_unmapped_sections(self, text: str) -> Dict[str, Any]:
        lines = [line.rstrip() for line in text.splitlines()]
        sections: Dict[str, List[str]] = {}
        current_section: Optional[str] = None

        for raw_line in lines:
            line = raw_line.strip()
            if not line:
                if current_section and sections.get(current_section):
                    last_value = sections[current_section][-1]
                    if last_value != "":
                        sections[current_section].append("")
                continue

            header_key = self._normalize_section_header(line)
            if header_key:
                current_section = None if header_key == "__mapped__" else header_key
                if current_section:
                    sections.setdefault(current_section, [])
                continue

            if current_section:
                sections.setdefault(current_section, []).append(line)

        normalized_sections: Dict[str, Any] = {}
        for key, values in sections.items():
            trimmed_lines = values[:]
            while trimmed_lines and trimmed_lines[0] == "":
                trimmed_lines.pop(0)
            while trimmed_lines and trimmed_lines[-1] == "":
                trimmed_lines.pop()
            if not trimmed_lines:
                continue

            normalized_sections[key] = {
                "text": "\n".join(trimmed_lines),
                "items": [value for value in trimmed_lines if value],
            }

        return normalized_sections

    def _build_other_details(
        self,
        text: str,
        urls: List[str],
        linkedin_url: Optional[str],
        education: List[Education],
        experience: List[Experience],
        skills: List[Skill],
    ) -> Dict[str, Any]:
        details: Dict[str, Any] = {}
        details["raw_text_excerpt"] = text[:2000]
        details["detected_urls"] = urls
        non_linkedin_urls = [u for u in urls if "linkedin.com" not in u.lower()]
        if non_linkedin_urls:
            details["profile_links"] = non_linkedin_urls
        if linkedin_url:
            details["linkedin_detected"] = True
        details["parsed_counts"] = {
            "education": len(education),
            "experience": len(experience),
            "skills": len(skills),
        }
        unmapped_sections = self._extract_unmapped_sections(text)
        if unmapped_sections:
            details["unmapped_resume_sections"] = unmapped_sections
        return details

    def _parse_month_year(self, value: str) -> Optional[datetime]:
        raw = (value or "").strip().lower()
        if not raw:
            return None
        raw = raw.replace(".", "")
        if raw in {"present", "current", "now", "till date", "till now", "ongoing"}:
            return datetime.utcnow()

        for fmt in ("%b %Y", "%B %Y", "%m/%Y", "%m-%Y", "%Y"):
            try:
                return datetime.strptime(raw, fmt)
            except ValueError:
                continue
        return None

    def _calculate_total_experience_years(self, experience_entries: List[Experience]) -> Optional[Decimal]:
        if not experience_entries:
            return None

        total_months = 0
        for item in experience_entries:
            start = self._parse_month_year(item.start_date or "")
            end = self._parse_month_year(item.end_date or "")
            if not start or not end:
                continue
            months = (end.year - start.year) * 12 + (end.month - start.month)
            if months < 0:
                continue
            total_months += max(1, months)

        if total_months <= 0:
            return None
        return (Decimal(total_months) / Decimal(12)).quantize(Decimal("0.01"))
    
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
