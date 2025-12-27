"""Smart test data generators for property-based testing using Hypothesis."""

import string
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Any
from uuid import UUID, uuid4

from hypothesis import strategies as st
from hypothesis.strategies import composite


# Basic data generators
@composite
def uuids(draw) -> UUID:
    """Generate valid UUIDs."""
    return draw(st.uuids())


@composite
def email_addresses(draw) -> str:
    """Generate valid email addresses."""
    username = draw(st.text(
        alphabet=string.ascii_lowercase + string.digits + "._-",
        min_size=1,
        max_size=20
    ).filter(lambda x: x[0].isalnum() and x[-1].isalnum()))
    
    domain = draw(st.text(
        alphabet=string.ascii_lowercase + string.digits + "-",
        min_size=1,
        max_size=15
    ).filter(lambda x: x[0].isalnum() and x[-1].isalnum()))
    
    tld = draw(st.sampled_from(["com", "org", "net", "edu", "gov", "co.uk", "io"]))
    
    return f"{username}@{domain}.{tld}"


@composite
def phone_numbers(draw) -> str:
    """Generate realistic phone numbers."""
    formats = [
        "+1-{}-{}-{}",
        "({}) {}-{}",
        "{}.{}.{}",
        "{}-{}-{}"
    ]
    format_str = draw(st.sampled_from(formats))
    
    if format_str.startswith("+1"):
        area = draw(st.integers(min_value=200, max_value=999))
        exchange = draw(st.integers(min_value=200, max_value=999))
        number = draw(st.integers(min_value=1000, max_value=9999))
        return format_str.format(area, exchange, number)
    else:
        area = draw(st.integers(min_value=200, max_value=999))
        exchange = draw(st.integers(min_value=200, max_value=999))
        number = draw(st.integers(min_value=1000, max_value=9999))
        return format_str.format(area, exchange, number)


@composite
def names(draw) -> str:
    """Generate realistic human names."""
    first_names = [
        "John", "Jane", "Michael", "Sarah", "David", "Emily", "Robert", "Lisa",
        "James", "Maria", "William", "Jennifer", "Richard", "Linda", "Joseph",
        "Elizabeth", "Thomas", "Barbara", "Christopher", "Susan", "Daniel",
        "Jessica", "Paul", "Karen", "Mark", "Nancy", "Donald", "Betty"
    ]
    
    last_names = [
        "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller",
        "Davis", "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez",
        "Wilson", "Anderson", "Thomas", "Taylor", "Moore", "Jackson", "Martin",
        "Lee", "Perez", "Thompson", "White", "Harris", "Sanchez", "Clark"
    ]
    
    first = draw(st.sampled_from(first_names))
    last = draw(st.sampled_from(last_names))
    
    return f"{first} {last}"


@composite
def skills_list(draw) -> List[str]:
    """Generate realistic skills lists."""
    tech_skills = [
        "Python", "JavaScript", "Java", "C++", "React", "Node.js", "SQL",
        "PostgreSQL", "MongoDB", "Docker", "Kubernetes", "AWS", "Azure",
        "Git", "Linux", "Machine Learning", "Data Analysis", "REST APIs",
        "GraphQL", "TypeScript", "Vue.js", "Angular", "Django", "Flask",
        "Spring Boot", "Microservices", "DevOps", "CI/CD", "Terraform"
    ]
    
    soft_skills = [
        "Communication", "Leadership", "Problem Solving", "Team Work",
        "Project Management", "Critical Thinking", "Adaptability",
        "Time Management", "Creativity", "Analytical Skills"
    ]
    
    all_skills = tech_skills + soft_skills
    num_skills = draw(st.integers(min_value=0, max_value=15))
    
    if num_skills == 0:
        return []
    
    return draw(st.lists(
        st.sampled_from(all_skills),
        min_size=num_skills,
        max_size=num_skills,
        unique=True
    ))


@composite
def experience_records(draw) -> List[Dict[str, Any]]:
    """Generate realistic experience records."""
    companies = [
        "Google", "Microsoft", "Amazon", "Apple", "Meta", "Netflix", "Tesla",
        "Uber", "Airbnb", "Spotify", "Adobe", "Salesforce", "Oracle", "IBM",
        "Intel", "NVIDIA", "Cisco", "VMware", "Dropbox", "Slack", "Zoom",
        "Acme Corp", "Tech Solutions Inc", "Digital Innovations LLC",
        "Global Systems Ltd", "Future Tech Co", "Smart Solutions Group"
    ]
    
    job_titles = [
        "Software Engineer", "Senior Software Engineer", "Lead Developer",
        "Full Stack Developer", "Backend Developer", "Frontend Developer",
        "DevOps Engineer", "Data Scientist", "Product Manager", "Tech Lead",
        "Principal Engineer", "Staff Engineer", "Engineering Manager",
        "Solutions Architect", "System Administrator", "Database Administrator"
    ]
    
    num_experiences = draw(st.integers(min_value=0, max_value=8))
    
    if num_experiences == 0:
        return []
    
    experiences = []
    current_date = datetime.now()
    
    for i in range(num_experiences):
        # Generate dates in reverse chronological order
        end_date = current_date - timedelta(days=draw(st.integers(min_value=30, max_value=365 * i + 365)))
        start_date = end_date - timedelta(days=draw(st.integers(min_value=90, max_value=365 * 3)))
        
        experience = {
            "company": draw(st.sampled_from(companies)),
            "title": draw(st.sampled_from(job_titles)),
            "start_date": start_date.strftime("%Y-%m-%d"),
            "end_date": end_date.strftime("%Y-%m-%d"),
            "description": draw(st.text(min_size=10, max_size=200))
        }
        experiences.append(experience)
        current_date = start_date - timedelta(days=30)  # Gap between jobs
    
    return experiences


@composite
def ctc_amounts(draw) -> Optional[Decimal]:
    """Generate realistic CTC amounts."""
    # 30% chance of None
    if draw(st.booleans().filter(lambda x: draw(st.integers(1, 10)) <= 3)):
        return None
    
    # Generate amounts between 300,000 and 50,000,000 (3 LPA to 5 Cr)
    amount = draw(st.integers(min_value=300000, max_value=50000000))
    return Decimal(str(amount))


# Domain-specific generators
@composite
def client_data(draw) -> Dict[str, Any]:
    """Generate realistic client/tenant data."""
    company_suffixes = ["Inc", "Corp", "LLC", "Ltd", "Co", "Group", "Solutions", "Systems", "Technologies"]
    company_prefixes = [
        "Tech", "Global", "Digital", "Smart", "Future", "Advanced", "Premier",
        "Elite", "Dynamic", "Innovative", "Strategic", "Professional", "Enterprise"
    ]
    
    base_name = draw(st.text(
        alphabet=string.ascii_letters + " ",
        min_size=3,
        max_size=20
    ).filter(lambda x: x.strip() and not x.isspace()))
    
    # 50% chance to add prefix/suffix
    if draw(st.booleans()):
        if draw(st.booleans()):
            prefix = draw(st.sampled_from(company_prefixes))
            company_name = f"{prefix} {base_name.strip()}"
        else:
            suffix = draw(st.sampled_from(company_suffixes))
            company_name = f"{base_name.strip()} {suffix}"
    else:
        company_name = base_name.strip()
    
    # Generate email domain from company name
    domain_base = "".join(c.lower() for c in company_name if c.isalnum())[:15]
    if not domain_base:
        domain_base = "company"
    
    domain_suffix = draw(st.sampled_from(["com", "org", "net", "co", "io"]))
    email_domain = f"{domain_base}.{domain_suffix}"
    
    return {
        "id": draw(uuids()),
        "name": company_name,
        "email_domain": email_domain
    }


@composite
def candidate_data(draw, client_id: Optional[UUID] = None) -> Dict[str, Any]:
    """Generate realistic candidate data."""
    candidate_statuses = ["ACTIVE", "INACTIVE", "JOINED", "LEFT_COMPANY"]
    
    return {
        "id": draw(uuids()),
        "client_id": client_id or draw(uuids()),
        "name": draw(names()),
        "email": draw(st.one_of(st.none(), email_addresses())),
        "phone": draw(st.one_of(st.none(), phone_numbers())),
        "skills": draw(skills_list()),
        "experience": draw(experience_records()),
        "ctc_current": draw(ctc_amounts()),
        "ctc_expected": draw(ctc_amounts()),
        "status": draw(st.sampled_from(candidate_statuses)),
        "candidate_hash": draw(st.one_of(
            st.none(),
            st.text(alphabet=string.hexdigits.lower(), min_size=64, max_size=64)
        ))
    }


@composite
def application_data(draw, client_id: Optional[UUID] = None, candidate_id: Optional[UUID] = None) -> Dict[str, Any]:
    """Generate realistic application data."""
    application_statuses = [
        "RECEIVED", "SCREENING", "INTERVIEW_SCHEDULED", "INTERVIEWED",
        "OFFER_EXTENDED", "OFFER_ACCEPTED", "OFFER_REJECTED", "REJECTED"
    ]
    
    job_titles = [
        "Software Engineer", "Senior Software Engineer", "Lead Developer",
        "Full Stack Developer", "Backend Developer", "Frontend Developer",
        "DevOps Engineer", "Data Scientist", "Product Manager", "Tech Lead",
        "Principal Engineer", "Staff Engineer", "Engineering Manager",
        "Solutions Architect", "System Administrator", "Database Administrator",
        "QA Engineer", "Security Engineer", "Mobile Developer", "UI/UX Designer"
    ]
    
    flag_reasons = [
        "Duplicate application", "Incomplete information", "Salary mismatch",
        "Location preference", "Experience gap", "Skills mismatch",
        "Background verification pending", "Reference check required"
    ]
    
    flagged = draw(st.booleans().filter(lambda x: draw(st.integers(1, 10)) <= 2))  # 20% chance
    
    return {
        "id": draw(uuids()),
        "client_id": client_id or draw(uuids()),
        "candidate_id": candidate_id or draw(uuids()),
        "job_title": draw(st.one_of(st.none(), st.sampled_from(job_titles))),
        "status": draw(st.sampled_from(application_statuses)),
        "flagged_for_review": flagged,
        "flag_reason": draw(st.sampled_from(flag_reasons)) if flagged else None,
        "deleted_at": draw(st.one_of(st.none(), st.datetimes(
            min_value=datetime(2020, 1, 1),
            max_value=datetime.now()
        )))
    }


@composite
def resume_job_data(draw, client_id: Optional[UUID] = None) -> Dict[str, Any]:
    """Generate realistic resume job data."""
    job_statuses = ["PENDING", "PROCESSING", "COMPLETED", "FAILED"]
    
    file_extensions = [".pdf", ".doc", ".docx", ".txt"]
    file_names = [
        "resume", "cv", "john_doe_resume", "jane_smith_cv", "software_engineer_resume",
        "senior_developer_cv", "my_resume", "updated_resume", "latest_cv"
    ]
    
    error_messages = [
        "File format not supported", "File corrupted", "OCR processing failed",
        "File too large", "Network timeout", "Processing queue full",
        "Invalid file structure", "Extraction failed"
    ]
    
    status = draw(st.sampled_from(job_statuses))
    
    base_filename = draw(st.sampled_from(file_names))
    extension = draw(st.sampled_from(file_extensions))
    filename = f"{base_filename}{extension}"
    
    return {
        "id": draw(uuids()),
        "client_id": client_id or draw(uuids()),
        "email_message_id": draw(st.one_of(
            st.none(),
            st.text(alphabet=string.ascii_letters + string.digits + "@.-_", min_size=10, max_size=50)
        )),
        "file_name": filename,
        "file_path": f"/storage/resumes/{client_id or draw(uuids())}/{filename}",
        "status": status,
        "error_message": draw(st.sampled_from(error_messages)) if status == "FAILED" else None,
        "processed_at": draw(st.one_of(st.none(), st.datetimes(
            min_value=datetime(2020, 1, 1),
            max_value=datetime.now()
        ))) if status in ["COMPLETED", "FAILED"] else None
    }


@composite
def user_data(draw, client_id: Optional[UUID] = None) -> Dict[str, Any]:
    """Generate realistic user data."""
    return {
        "id": draw(uuids()),
        "email": draw(email_addresses()),
        "full_name": draw(st.one_of(st.none(), names())),
        "is_active": draw(st.booleans().filter(lambda x: draw(st.integers(1, 10)) <= 9)),  # 90% active
        "client_id": client_id or draw(uuids()),
        "hashed_password": draw(st.text(min_size=60, max_size=60))  # bcrypt hash length
    }


# Multi-tenant data generators
@composite
def tenant_with_data(draw) -> Dict[str, Any]:
    """Generate a complete tenant with associated data."""
    client = draw(client_data())
    client_id = client["id"]
    
    # Generate candidates for this tenant
    num_candidates = draw(st.integers(min_value=0, max_value=20))
    candidates = [draw(candidate_data(client_id=client_id)) for _ in range(num_candidates)]
    
    # Generate applications for some candidates
    applications = []
    for candidate in candidates:
        if draw(st.booleans().filter(lambda x: draw(st.integers(1, 10)) <= 7)):  # 70% chance
            num_apps = draw(st.integers(min_value=1, max_value=3))
            for _ in range(num_apps):
                applications.append(draw(application_data(
                    client_id=client_id,
                    candidate_id=candidate["id"]
                )))
    
    # Generate resume jobs
    num_resume_jobs = draw(st.integers(min_value=0, max_value=10))
    resume_jobs = [draw(resume_job_data(client_id=client_id)) for _ in range(num_resume_jobs)]
    
    # Generate users
    num_users = draw(st.integers(min_value=1, max_value=5))
    users = [draw(user_data(client_id=client_id)) for _ in range(num_users)]
    
    return {
        "client": client,
        "candidates": candidates,
        "applications": applications,
        "resume_jobs": resume_jobs,
        "users": users
    }


# Email content generators for ingestion testing
@composite
def email_content(draw) -> Dict[str, Any]:
    """Generate realistic email content for ingestion testing."""
    subjects = [
        "Resume for Software Engineer Position",
        "Application for Senior Developer Role",
        "Job Application - Full Stack Developer",
        "CV for Data Scientist Position",
        "Application Materials",
        "Resume Submission",
        "Job Interest - Backend Developer",
        "Application for Tech Lead Role"
    ]
    
    senders = [
        "john.doe@gmail.com", "jane.smith@yahoo.com", "mike.johnson@outlook.com",
        "sarah.wilson@hotmail.com", "david.brown@gmail.com", "lisa.davis@yahoo.com"
    ]
    
    return {
        "subject": draw(st.sampled_from(subjects)),
        "sender": draw(st.sampled_from(senders)),
        "body": draw(st.text(min_size=50, max_size=500)),
        "attachments": draw(st.lists(
            st.text(alphabet=string.ascii_letters + string.digits + "._-", min_size=5, max_size=30),
            min_size=0,
            max_size=5
        ))
    }

# Observability-specific generators
@composite
def performance_metrics_strategy(draw):
    """Generate realistic performance metrics."""
    from src.ats_backend.core.observability import PerformanceMetrics
    
    operation = draw(st.text(min_size=1, max_size=50))
    
    # Generate realistic timing values with proper ordering
    min_ms = draw(st.floats(min_value=1.0, max_value=100.0))
    p50_ms = draw(st.floats(min_value=min_ms, max_value=min_ms * 5))
    p95_ms = draw(st.floats(min_value=p50_ms, max_value=p50_ms * 3))
    p99_ms = draw(st.floats(min_value=p95_ms, max_value=p95_ms * 2))
    max_ms = draw(st.floats(min_value=p99_ms, max_value=p99_ms * 2))
    avg_ms = draw(st.floats(min_value=min_ms, max_value=p95_ms))
    
    return PerformanceMetrics(
        operation=operation,
        p50_ms=p50_ms,
        p95_ms=p95_ms,
        p99_ms=p99_ms,
        avg_ms=avg_ms,
        min_ms=min_ms,
        max_ms=max_ms,
        count=draw(st.integers(min_value=1, max_value=10000)),
        error_rate=draw(st.floats(min_value=0.0, max_value=1.0)),
        throughput_per_second=draw(st.floats(min_value=0.1, max_value=1000.0))
    )


@composite
def cost_metrics_strategy(draw):
    """Generate realistic cost metrics."""
    from src.ats_backend.core.observability import CostMetrics
    
    cpu_cost = draw(st.floats(min_value=0.0, max_value=10.0))
    memory_cost = draw(st.floats(min_value=0.0, max_value=5.0))
    storage_cost = draw(st.floats(min_value=0.0, max_value=2.0))
    network_cost = draw(st.floats(min_value=0.0, max_value=1.0))
    
    return CostMetrics(
        cpu_cost_per_hour=cpu_cost,
        memory_cost_per_hour=memory_cost,
        storage_cost_per_gb=storage_cost,
        network_cost_per_gb=network_cost,
        total_estimated_cost_per_hour=cpu_cost + memory_cost + storage_cost + network_cost,
        resource_efficiency=draw(st.floats(min_value=0.0, max_value=1.0))
    )


@composite
def alert_strategy(draw):
    """Generate realistic alerts."""
    from src.ats_backend.core.observability import Alert, AlertSeverity
    
    return Alert(
        name=draw(st.text(min_size=1, max_size=50)),
        condition=draw(st.text(min_size=5, max_size=100)),
        severity=draw(st.sampled_from(list(AlertSeverity))),
        threshold=draw(st.floats(min_value=0.1, max_value=1000.0)),
        current_value=draw(st.floats(min_value=0.0, max_value=2000.0)),
        triggered_at=draw(st.datetimes(
            min_value=datetime.now() - timedelta(days=7),
            max_value=datetime.now()
        )),
        message=draw(st.text(min_size=1, max_size=200)),
        details=draw(st.dictionaries(
            st.text(min_size=1, max_size=20),
            st.one_of(st.text(), st.integers(), st.floats()),
            min_size=0,
            max_size=5
        ))
    )


@composite
def system_metrics_strategy(draw):
    """Generate realistic system metrics."""
    return {
        "cpu_percent": draw(st.floats(min_value=0.0, max_value=100.0)),
        "memory_percent": draw(st.floats(min_value=0.0, max_value=100.0)),
        "disk_percent": draw(st.floats(min_value=0.0, max_value=100.0)),
        "load_average": draw(st.lists(
            st.floats(min_value=0.0, max_value=10.0),
            min_size=3,
            max_size=3
        )),
        "network_io": {
            "bytes_sent": draw(st.integers(min_value=0, max_value=10**12)),
            "bytes_recv": draw(st.integers(min_value=0, max_value=10**12))
        }
    }


@composite
def alert_rule_strategy(draw):
    """Generate realistic alert rules."""
    from src.ats_backend.core.alerts import AlertRule, AlertSeverity, NotificationChannel
    
    return AlertRule(
        name=draw(st.text(min_size=1, max_size=50)),
        condition=draw(st.text(min_size=5, max_size=100)),
        threshold=draw(st.floats(min_value=0.1, max_value=1000.0)),
        severity=draw(st.sampled_from(list(AlertSeverity))),
        enabled=draw(st.booleans()),
        cooldown_minutes=draw(st.integers(min_value=1, max_value=60)),
        notification_channels=draw(st.lists(
            st.sampled_from(list(NotificationChannel)),
            min_size=1,
            max_size=3,
            unique=True
        ))
    )


@composite
def queue_metrics_strategy(draw):
    """Generate realistic queue metrics."""
    queue_names = ["resume_processing", "email_processing", "celery", "default"]
    
    return {
        "queues": {
            queue: draw(st.integers(min_value=0, max_value=1000))
            for queue in draw(st.lists(
                st.sampled_from(queue_names),
                min_size=1,
                max_size=len(queue_names),
                unique=True
            ))
        },
        "total_queued": draw(st.integers(min_value=0, max_value=5000)),
        "timestamp": datetime.utcnow().isoformat()
    }


@composite
def worker_metrics_strategy(draw):
    """Generate realistic worker metrics."""
    worker_count = draw(st.integers(min_value=0, max_value=10))
    
    return {
        "total_workers": worker_count,
        "active_tasks": draw(st.integers(min_value=0, max_value=worker_count * 10)),
        "workers": {
            f"worker_{i}": {
                "status": draw(st.sampled_from(["online", "offline", "busy"])),
                "active_tasks": draw(st.integers(min_value=0, max_value=10)),
                "processed_tasks": draw(st.integers(min_value=0, max_value=1000))
            }
            for i in range(worker_count)
        },
        "timestamp": datetime.utcnow().isoformat()
    }


@composite
def diagnostic_data_strategy(draw):
    """Generate realistic diagnostic data."""
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "collection_time_seconds": draw(st.floats(min_value=0.1, max_value=60.0)),
        "overall_status": draw(st.sampled_from(["healthy", "degraded", "unhealthy", "critical"])),
        "system_health": draw(system_metrics_strategy()),
        "performance_summary": draw(st.dictionaries(
            st.text(min_size=1, max_size=20),
            performance_metrics_strategy(),
            min_size=0,
            max_size=5
        )),
        "queue_status": draw(queue_metrics_strategy()),
        "worker_status": draw(worker_metrics_strategy()),
        "cost_summary": draw(cost_metrics_strategy()),
        "active_alerts": draw(st.lists(
            alert_strategy(),
            min_size=0,
            max_size=10
        )),
        "alert_count": draw(st.integers(min_value=0, max_value=10))
    }