"""Data extraction utilities for resume parsing."""

import re
from datetime import datetime
from decimal import Decimal
from typing import Dict, Any, List, Optional
import structlog

try:
    from email_validator import validate_email, EmailNotValidError
except ImportError:
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
        self.email_pattern = re.compile(
            r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"
        )

        # More precise phone pattern: avoids matching pure date/year sequences
        self.phone_patterns = [
            re.compile(r"(?<!\d)(\+?\d[\d\-\s().]{8,14}\d)(?!\d)"),
        ]

        self.name_patterns = [
            re.compile(r'^([A-Z][a-z]+ [A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)', re.MULTILINE),
        ]

        self.education_header_pattern = re.compile(
            r'(?:education|academic|qualifications|scholastic)',
            re.IGNORECASE
        )

        self.degree_patterns = [
            re.compile(
                r'\b(?:B\.?Tech|M\.?Tech|B\.?E\.?|M\.?E\.?|B\.?S\.?|M\.?S\.?|'
                r'B\.?A\.?|M\.?A\.?|Ph\.?D\.?|Bachelor|Master|Diploma|'
                r'B\.?Sc\.?|M\.?Sc\.?|MBA|BBA|LLB|LLM)\b',
                re.IGNORECASE,
            ),
            re.compile(r'\b(?:HSC|SSC|High School|Secondary School|10th|12th)\b', re.IGNORECASE),
        ]

        # Matches a single year or a year range like "2018-2022" or "2018 – 2022"
        self.year_range_pattern = re.compile(
            r'\b((?:19|20)\d{2})\s*(?:[-–—]|to)\s*((?:19|20)\d{2}|present|current)\b',
            re.IGNORECASE,
        )
        self.year_pattern = re.compile(r'\b((?:19|20)\d{2})\b')
        self.grade_pattern = re.compile(r'\b(?:CGPA|GPA|%|Grade)[\s:-]*([\d.]+%?)', re.IGNORECASE)

        self.skill_categories = {
            'languages': [
                'python', 'java', 'javascript', 'typescript', 'c++', 'c#', 'php',
                'ruby', 'go', 'rust', 'swift', 'kotlin', 'scala', 'perl', 'r',
                'matlab', 'dart', 'shell', 'bash', 'sql', 'html', 'css',
            ],
            'frameworks': [
                'react', 'angular', 'vue', 'next.js', 'django', 'flask', 'fastapi',
                'spring', 'spring boot', 'laravel', 'rails', 'ruby on rails',
                'express', 'node.js', 'dotnet', '.net', 'tensorflow', 'pytorch',
                'pandas', 'numpy', 'scikit-learn', 'keras', 'flutter', 'react native',
            ],
            'databases': [
                'mysql', 'postgresql', 'postgres', 'mongodb', 'redis', 'cassandra',
                'elasticsearch', 'oracle', 'sql server', 'sqlite', 'dynamodb',
                'firebase', 'mariadb',
            ],
            'cloud': [
                'aws', 'azure', 'gcp', 'google cloud', 'docker', 'kubernetes',
                'jenkins', 'circleci', 'gitlab ci', 'github actions', 'terraform',
                'ansible', 'prometheus', 'grafana', 'elk stack',
            ],
            'tools': [
                'git', 'github', 'gitlab', 'bitbucket', 'jira', 'confluence',
                'slack', 'trello', 'asana', 'figma', 'postman', 'swagger',
                'vs code', 'pycharm', 'intellij', 'eclipse',
            ],
            'concepts': [
                'rest api', 'graphql', 'grpc', 'microservices', 'serverless',
                'agile', 'scrum', 'ci/cd', 'devops', 'machine learning',
                'artificial intelligence', 'data science', 'big data', 'blockchain',
            ],
            'soft_skills': [
                'leadership', 'communication', 'teamwork', 'problem solving',
                'critical thinking', 'time management', 'adaptability', 'mentoring',
            ],
        }
        self._skill_patterns = self._build_skill_patterns()

        self.dob_patterns = [
            re.compile(
                r"\b(?:dob|date of birth)\s*[:\-]?\s*(\d{1,2}[\/\-.]\d{1,2}[\/\-.]\d{2,4})\b",
                re.IGNORECASE,
            ),
            re.compile(
                r"\b(?:dob|date of birth)\s*[:\-]?\s*(\d{1,2}\s+[A-Za-z]+\s+\d{4})\b",
                re.IGNORECASE,
            ),
            re.compile(r"\b(\d{4}-\d{2}-\d{2})\b"),          # ISO format
            re.compile(r"\b(\d{1,2}[\/\-.]\d{1,2}[\/\-.]\d{4})\b"),
        ]

        self.ctc_patterns = {
            "current": re.compile(
                r"\b(?:current|present)\s+ctc\s*[:\-]?\s*"
                r"([0-9][0-9.,]*(?:\s*(?:lpa|lac|lakh|lakhs|cr|crore|crores))?)",
                re.IGNORECASE,
            ),
            "expected": re.compile(
                r"\b(?:expected)\s+ctc\s*[:\-]?\s*"
                r"([0-9][0-9.,]*(?:\s*(?:lpa|lac|lakh|lakhs|cr|crore|crores))?)",
                re.IGNORECASE,
            ),
        }

        self.employer_patterns = [
            re.compile(
                r"\b(?:worked at|employed at|company)\s*[:\-]?\s*"
                r"([A-Z][A-Za-z0-9&.,\-\s]{2,60})",
                re.IGNORECASE,
            ),
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
            r"(?P<start>"
            r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?\s+\d{4}"
            r"|\d{1,2}[/-]\d{4}|\d{4})"
            r"\s*(?:-|–|—|to)\s*"
            r"(?P<end>"
            r"present|current|now|till date|till now|ongoing"
            r"|(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?\s+\d{4}"
            r"|\d{1,2}[/-]\d{4}|\d{4})",
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

        # FIX: Use a set for O(1) lookups instead of a list
        self.mapped_section_aliases: set = {
            "experience", "work experience", "employment history",
            "professional experience", "work history",
            "education", "academic background", "qualifications",
            "skills", "technical skills",
            "contact", "personal details", "salary", "ctc", "date of birth",
        }

    # ------------------------------------------------------------------ #
    #  Public API                                                          #
    # ------------------------------------------------------------------ #

    def extract_data(self, text: str, extra_links: Optional[List[str]] = None) -> Dict[str, Any]:
        """Extract all structured data from resume text."""
        logger.info("Starting data extraction", text_length=len(text))

        cleaned_text = self._clean_text(text)

        contact_info = self._extract_contact_info(text)
        skills = self._extract_skills(cleaned_text)
        experience = self._extract_experience(text)
        salary_info = self._extract_salary_info(text)
        date_of_birth = self._extract_date_of_birth(text)
        previous_employment = self._extract_previous_employment(text)
        key_skill = ", ".join([skill.name for skill in skills[:8]]) if skills else None
        linkedin_url = self._extract_linkedin_url(text, extra_links=extra_links or [])
        total_experience_years = self._calculate_total_experience_years(experience)
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
            'confidence_score': self._calculate_confidence_score(
                contact_info, experience, skills, education
            ),
        }

        logger.info("Data extraction completed", confidence_score=result['confidence_score'])
        return result

    # ------------------------------------------------------------------ #
    #  Internal helpers                                                    #
    # ------------------------------------------------------------------ #

    def _clean_text(self, text: str) -> str:
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
        """Return a normalised phone string, or '' if invalid."""
        # Preserve leading '+' before stripping non-digit chars
        has_plus = phone_candidate.lstrip().startswith("+")
        digits = re.sub(r"\D", "", phone_candidate)
        if not digits:
            return ""

        # Re-attach the leading '+' if present
        normalised = f"+{digits}" if has_plus else digits

        # Accept 10–15 digit numbers only
        if 10 <= len(digits) <= 15:
            return normalised
        return ""

    def _extract_name(self, text: str) -> str:
        header_stop_words = {
            "resume", "curriculum", "vitae", "profile", "summary", "objective",
            "experience", "education", "skills", "projects", "certifications",
        }
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

        for line in lines[:15]:
            line_lower = line.lower()
            if any(token in line_lower for token in ("@", "http", "linkedin", "github")):
                continue
            if any(char.isdigit() for char in line):
                continue
            words = line.split()
            if len(words) < 2 or len(words) > 6:
                continue
            if len(line) > 70:
                continue
            # Reject lines that are clearly section headers
            if any(word in header_stop_words for word in line_lower.split()):
                continue
            # Reject lines with non-name characters (brackets, slashes, colons, etc.)
            if re.search(r"[^A-Za-z.\-'\s]", line):
                continue
            # Require at least two words that look like name parts (start with uppercase)
            capitalised_words = [w for w in words if w[0].isupper()]
            if len(capitalised_words) < 2:
                continue
            return " ".join(word.capitalize() for word in words)
        return ""

    # ------------------------------------------------------------------ #
    #  Contact                                                             #
    # ------------------------------------------------------------------ #

    def _extract_contact_info(self, text: str) -> ContactInfo:
        contact_info = ContactInfo()

        email_matches = list(dict.fromkeys(self.email_pattern.findall(text)))
        if email_matches:
            try:
                validated = validate_email(email_matches[0])
                contact_info.email = validated.email
            except EmailNotValidError:
                pass

        for pattern in self.phone_patterns:
            for candidate in pattern.findall(text):
                phone = self._normalize_phone(candidate)
                if phone:
                    contact_info.phone = phone
                    break
            if contact_info.phone:
                break

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

    # ------------------------------------------------------------------ #
    #  Education                                                           #
    # ------------------------------------------------------------------ #

    def _extract_education(self, text: str) -> List[Education]:
        """Extract education entries from the education section."""
        education_entries: List[Education] = []

        lines = text.split('\n')
        in_education_section = False
        current_entry: Dict[str, Any] = {}

        other_sections = [
            'experience', 'work', 'skills', 'projects', 'interests',
            'certifications', 'achievements', 'languages',
        ]

        def _flush(entry: Dict[str, Any]) -> None:
            """Append a completed entry if it has at least one meaningful field."""
            if entry.get('degree') or entry.get('institution') or entry.get('year'):
                education_entries.append(Education(**entry))

        for line in lines:
            line_clean = line.strip()
            if not line_clean:
                continue

            # Detect education section header
            if self.education_header_pattern.search(line_clean) and len(line_clean.split()) <= 5:
                in_education_section = True
                continue

            # Detect the start of another section — stop collecting
            if in_education_section:
                normalized = line_clean.lower()
                if any(normalized == s or normalized.startswith(s + ' ') for s in other_sections):
                    if len(line_clean.split()) <= 4:
                        in_education_section = False
                        _flush(current_entry)
                        current_entry = {}
                        continue

            if not in_education_section:
                continue

            # --- parse the current line ---
            degree_match: Optional[str] = None
            for pattern in self.degree_patterns:
                m = pattern.search(line_clean)
                if m:
                    degree_match = m.group(0)
                    break

            year_range_match = self.year_range_pattern.search(line_clean)
            year_match = self.year_pattern.search(line_clean) if not year_range_match else None
            grade_match = self.grade_pattern.search(line_clean)

            is_institution_line = any(
                kw in line_clean.lower()
                for kw in ("university", "college", "institute", "school", "iit", "nit", "bits")
            )

            # A new entry begins when we see a degree keyword or a year (range)
            starts_new_entry = bool(degree_match or year_range_match or year_match)

            if starts_new_entry:
                # FIX: flush *before* resetting so we don't lose the previous entry
                _flush(current_entry)
                current_entry = {}

                if degree_match:
                    current_entry['degree'] = degree_match

                if year_range_match:
                    current_entry['year'] = f"{year_range_match.group(1)} - {year_range_match.group(2)}"
                elif year_match:
                    current_entry['year'] = year_match.group(0)

                if grade_match:
                    current_entry['grade'] = grade_match.group(1)

                if is_institution_line and not current_entry.get('institution'):
                    current_entry['institution'] = line_clean

            else:
                # Continuation line for the current entry
                if is_institution_line and not current_entry.get('institution'):
                    current_entry['institution'] = line_clean
                elif grade_match and not current_entry.get('grade'):
                    current_entry['grade'] = grade_match.group(1)
                elif (
                    current_entry
                    and not current_entry.get('institution')
                    and not current_entry.get('degree')
                    and len(line_clean.split()) <= 8
                    and not any(char.isdigit() for char in line_clean)
                ):
                    # Likely a standalone institution name without keywords
                    current_entry['institution'] = line_clean

        # Flush final pending entry
        _flush(current_entry)

        return education_entries

    # ------------------------------------------------------------------ #
    #  Experience                                                          #
    # ------------------------------------------------------------------ #

    def _extract_experience(self, text: str) -> List[Experience]:
        entries: List[Experience] = []
        section_lines = self._extract_section_lines(
            text,
            {
                "experience", "work experience", "employment history",
                "professional experience", "work history",
            },
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
        company_tokens = {
            "pvt", "ltd", "llc", "inc", "corp", "company",
            "technologies", "solutions", "systems", "labs",
        }
        if any(token in lowered for token in company_tokens):
            return True
        words = [w for w in re.split(r"\s+", line) if w]
        return (
            1 <= len(words) <= 6
            and sum(1 for w in words if w[:1].isupper()) >= max(1, len(words) - 1)
        )

    def _parse_experience_line(self, line: str) -> Optional[Experience]:
        match = self.date_range_pattern.search(line)
        if not match:
            return None

        start_raw = match.group("start")
        end_raw = match.group("end")
        before = line[: match.start()].strip(" |,-:")
        after = line[match.end():].strip(" |,-:")

        company = before[:120].strip() if before else None
        position = after[:120].strip() if after else None

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
        date_indexes = [
            idx for idx, line in enumerate(lines)
            if self.date_range_pattern.search(line)
        ]

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
                ln for ln in lines[prev_date_index + 1: date_index] if ln.strip()
            ]

            # Collect lines immediately after the date line until a blank gap
            context_after: List[str] = []
            for ln in lines[date_index + 1: next_date_index]:
                if not ln.strip():
                    if context_after:  # first blank after content → stop
                        break
                    continue
                context_after.append(ln)

            company: Optional[str] = None
            position: Optional[str] = None
            description_lines: List[str] = []

            if context_before:
                if len(context_before) >= 2:
                    candidate_a = context_before[-2]
                    candidate_b = context_before[-1]
                    # FIX: corrected swap logic — assign based on which looks like what
                    if self._looks_like_job_title(candidate_a) and self._looks_like_company_name(candidate_b):
                        position, company = candidate_a, candidate_b
                    elif self._looks_like_company_name(candidate_a) and self._looks_like_job_title(candidate_b):
                        position, company = candidate_b, candidate_a
                    else:
                        # Fallback: treat last line as company, second-to-last as position
                        position, company = candidate_a, candidate_b
                    description_lines.extend(context_before[:-2])
                else:
                    single = context_before[-1]
                    if self._looks_like_job_title(single):
                        position = single
                    elif self._looks_like_company_name(single):
                        company = single
                    else:
                        description_lines.append(single)

            # Supplement from inline date-line text
            before_date = date_line[: match.start()].strip(" |,-:")
            after_date = date_line[match.end():].strip(" |,-:")
            if not company and before_date:
                company = before_date
            if not position and after_date:
                position = after_date

            for ln in context_after:
                if not position and self._looks_like_job_title(ln):
                    position = ln
                    continue
                if not company and self._looks_like_company_name(ln):
                    company = ln
                    continue
                description_lines.append(ln)

            parsed_entries.append(
                Experience(
                    company=company[:120].strip() if company else None,
                    position=position[:120].strip() if position else None,
                    duration=f"{start_raw} - {end_raw}",
                    start_date=start_raw,
                    end_date=end_raw,
                    is_current=end_raw.lower() in {
                        "present", "current", "now", "till date", "till now", "ongoing"
                    },
                    description="\n".join(
                        ln for ln in description_lines if ln.strip()
                    ) or date_line,
                )
            )

        return parsed_entries

    # ------------------------------------------------------------------ #
    #  Skills                                                              #
    # ------------------------------------------------------------------ #

    def _extract_skills(self, text: str) -> List[Skill]:
        seen_skills: set = set()
        unique_skills: List[Skill] = []

        for category, skill_list in self.skill_categories.items():
            for skill_name in skill_list:
                skill_pattern = self._skill_patterns.get(skill_name)
                if skill_pattern and skill_pattern.search(text):
                    key = skill_name.lower()
                    if key not in seen_skills:
                        seen_skills.add(key)
                        unique_skills.append(Skill(name=skill_name, category=category))

        return unique_skills

    # ------------------------------------------------------------------ #
    #  Date of birth                                                       #
    # ------------------------------------------------------------------ #

    def _extract_date_of_birth(self, text: str):
        # Extended list of formats including ISO and textual month
        date_formats = [
            "%d/%m/%Y", "%d/%m/%y",
            "%m/%d/%Y", "%m/%d/%y",
            "%Y-%m-%d",
            "%d-%m-%Y", "%d-%m-%y",
            "%d %B %Y", "%d %b %Y",   # e.g. "15 January 1995" / "15 Jan 1995"
        ]
        for pattern in self.dob_patterns:
            for match in pattern.findall(text):
                raw = match if isinstance(match, str) else match[0]
                # Normalise separators for numeric formats
                normalised = raw.replace(".", "/").replace("-", "/")
                for fmt in date_formats:
                    # Use original `raw` for formats with text months; normalised for numeric
                    candidate = raw if "%b" in fmt or "%B" in fmt else normalised
                    # Re-normalise to the format's separator if needed
                    if "/" not in fmt and "-" not in fmt and "%" not in fmt:
                        candidate = raw
                    try:
                        parsed = datetime.strptime(candidate, fmt).date()
                        if 1940 <= parsed.year <= datetime.utcnow().year - 14:
                            return parsed
                    except ValueError:
                        continue
        return None

    # ------------------------------------------------------------------ #
    #  Salary                                                              #
    # ------------------------------------------------------------------ #

    def _extract_salary_info(self, text: str):
        current_ctc = None
        expected_ctc = None
        raw_fragments: List[str] = []

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
            value *= Decimal(10_000_000)
        elif any(token in lower for token in ["lpa", "lac", "lakh"]):
            value *= Decimal(100_000)

        return value

    # ------------------------------------------------------------------ #
    #  Previous employment                                                 #
    # ------------------------------------------------------------------ #

    def _extract_previous_employment(self, text: str) -> List[Dict[str, Any]]:
        experience_entries = self._extract_experience(text)
        if experience_entries:
            structured_entries: List[Dict[str, Any]] = []
            seen_companies: set = set()
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
        seen: set = set()
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

    # ------------------------------------------------------------------ #
    #  URLs                                                                #
    # ------------------------------------------------------------------ #

    def _extract_urls(self, text: str, extra_links: Optional[List[str]] = None) -> List[str]:
        urls = [u.strip(".,);]}>") for u in self.url_pattern.findall(text)]
        urls.extend(extra_links or [])
        normalised: List[str] = []
        seen: set = set()
        for url in urls:
            if not url:
                continue
            if url.lower().startswith("www."):
                url = f"https://{url}"
            key = url.lower()
            if key in seen:
                continue
            seen.add(key)
            normalised.append(url)
        return normalised

    def _extract_linkedin_url(self, text: str, extra_links: Optional[List[str]] = None) -> Optional[str]:
        """
        FIX: initialise company_url to None so we never reference an undefined variable,
        and reset it per source to avoid leaking a match across iterations.
        """
        sources = [text]
        if extra_links:
            sources.append(" ".join(extra_links))

        company_url: Optional[str] = None

        for source in sources:
            matches = self.linkedin_pattern.findall(source)
            for matched in matches:
                url = matched.strip(".,);]}>")
                if not url.lower().startswith("http"):
                    url = f"https://{url}"
                lowered = url.lower()
                if "/in/" in lowered or "/pub/" in lowered:
                    return url          # personal profile — return immediately
                if "/company/" in lowered:
                    company_url = url   # keep as fallback

        return company_url  # returns None if nothing was found

    # ------------------------------------------------------------------ #
    #  Section utilities                                                   #
    # ------------------------------------------------------------------ #

    def _extract_section_lines(self, text: str, target_headers: set) -> List[str]:
        lines = text.splitlines()
        collected: List[str] = []
        in_target = False

        for raw_line in lines:
            line = raw_line.strip()
            if not line:
                if in_target and collected and collected[-1] != "":
                    collected.append("")
                continue

            normalised = re.sub(r"[^a-zA-Z ]", " ", line).strip().lower()
            normalised = re.sub(r"\s+", " ", normalised)

            if normalised in target_headers:
                in_target = True
                continue

            if in_target:
                # FIX: mapped_section_aliases is now a set — O(1) lookup
                if normalised in self.mapped_section_aliases:
                    break
                if any(normalised in aliases for aliases in self.unmapped_section_aliases.values()):
                    break
                collected.append(line)

        while collected and collected[0] == "":
            collected.pop(0)
        while collected and collected[-1] == "":
            collected.pop()
        return collected

    def _normalize_section_header(self, line: str) -> Optional[str]:
        cleaned = re.sub(r"[^a-zA-Z ]", " ", line).strip().lower()
        cleaned = re.sub(r"\s+", " ", cleaned)
        # FIX: allow up to 7 words to catch longer section headers
        if not cleaned or len(cleaned.split()) > 7:
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
                    if sections[current_section][-1] != "":
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

        normalised_sections: Dict[str, Any] = {}
        for key, values in sections.items():
            trimmed = values[:]
            while trimmed and trimmed[0] == "":
                trimmed.pop(0)
            while trimmed and trimmed[-1] == "":
                trimmed.pop()
            if not trimmed:
                continue
            normalised_sections[key] = {
                "text": "\n".join(trimmed),
                "items": [v for v in trimmed if v],
            }

        return normalised_sections

    # ------------------------------------------------------------------ #
    #  Other details                                                       #
    # ------------------------------------------------------------------ #

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

    # ------------------------------------------------------------------ #
    #  Date / experience duration helpers                                  #
    # ------------------------------------------------------------------ #

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

    def _calculate_total_experience_years(
        self, experience_entries: List[Experience]
    ) -> Optional[Decimal]:
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

    # ------------------------------------------------------------------ #
    #  Confidence score                                                    #
    # ------------------------------------------------------------------ #

    def _calculate_confidence_score(
        self,
        contact_info: ContactInfo,
        experience: List[Experience],
        skills: List[Skill],
        education: List[Education],
    ) -> float:
        """
        FIX: weights are now balanced so the maximum possible raw score is 1.0,
        removing the need for a clamp (though we keep it as a safety net).

        Weights:
          name      0.20
          email     0.20
          phone     0.10
          skills    0.15  (+0.10 bonus for 5+ skills)
          education 0.10
          experience 0.15
          ─────────────
          max       1.00
        """
        score = 0.0

        if contact_info.name:
            score += 0.20
        if contact_info.email:
            score += 0.20
        if contact_info.phone:
            score += 0.10
        if skills:
            score += 0.15
            if len(skills) >= 5:
                score += 0.10
        if education:
            score += 0.10
        if experience:
            score += 0.15

        return round(min(score, 1.0), 4)