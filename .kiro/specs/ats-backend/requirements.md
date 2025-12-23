# Requirements Document

## Introduction

The ATS Backend System is a multi-tenant applicant tracking system that automates resume processing through email ingestion, intelligent parsing, and secure data management. The system enables HR teams to efficiently manage candidate applications while maintaining strict data isolation between different client organizations.

## Glossary

- **ATS_System**: The complete Applicant Tracking System backend including API, worker processes, and data storage
- **Client**: A tenant organization using the ATS system (e.g., a company's HR department)
- **Candidate**: An individual job applicant whose resume and information are stored in the system
- **Application**: A record linking a candidate to a specific job or client, representing one application instance
- **Resume_Parser**: The automated system component that extracts structured data from resume documents
- **Email_Ingestion**: The process of receiving and processing resumes sent via email
- **RLS_Policy**: Row-Level Security policy that enforces data isolation at the database level
- **Worker_Process**: Background Celery worker that handles CPU-intensive resume parsing tasks
- **Multi_Tenant**: Architecture supporting multiple isolated client organizations in a single system

## Requirements

### Requirement 1

**User Story:** As an HR administrator, I want to receive and automatically process resumes sent via email, so that I can efficiently capture candidate information without manual data entry.

#### Acceptance Criteria

1. WHEN an email with resume attachments is sent to the system THEN the ATS_System SHALL receive the email and extract all attached resume files
2. WHEN a resume file is received via email THEN the ATS_System SHALL queue the file for background processing within 30 seconds
3. WHEN processing a resume attachment THEN the ATS_System SHALL support PDF and common image formats (PNG, JPG, TIFF)
4. WHEN an email contains multiple resume attachments THEN the ATS_System SHALL process each attachment as a separate candidate application
5. WHEN duplicate emails are received THEN the ATS_System SHALL prevent reprocessing using message ID deduplication

### Requirement 2

**User Story:** As an HR administrator, I want resumes to be automatically parsed into structured candidate profiles, so that I can quickly review and search candidate information.

#### Acceptance Criteria

1. WHEN a PDF resume is processed THEN the Resume_Parser SHALL extract text using layout-aware parsing methods
2. WHEN a PDF contains scanned or image-based content THEN the Resume_Parser SHALL apply OCR to extract readable text
3. WHEN parsing resume text THEN the Resume_Parser SHALL extract candidate name, email, phone number, and work experience
4. WHEN parsing resume content THEN the Resume_Parser SHALL identify and store skills as a structured list in JSONB format
5. WHEN salary or compensation information is present THEN the Resume_Parser SHALL extract and normalize CTC values using pattern matching

### Requirement 3

**User Story:** As a system administrator, I want strict data isolation between different client organizations, so that each client can only access their own candidate data.

#### Acceptance Criteria

1. WHEN a client user authenticates THEN the ATS_System SHALL set the database session context to that client's identifier
2. WHEN any database query is executed THEN the RLS_Policy SHALL automatically filter results to only include the current client's data
3. WHEN a client attempts to access another client's data THEN the RLS_Policy SHALL prevent access and return no results
4. WHEN creating new candidate or application records THEN the ATS_System SHALL automatically associate them with the authenticated client
5. WHERE multi-tenant isolation is required THEN the ATS_System SHALL enforce separation at the database level using PostgreSQL RLS

### Requirement 4

**User Story:** As an HR administrator, I want to perform CRUD operations on candidate and application data through a REST API, so that I can integrate the system with other HR tools and workflows.

#### Acceptance Criteria

1. WHEN creating a new candidate record THEN the ATS_System SHALL validate all required fields and store the data in PostgreSQL
2. WHEN retrieving candidate information THEN the ATS_System SHALL return structured data including skills, experience, and contact details
3. WHEN updating candidate records THEN the ATS_System SHALL preserve data integrity and maintain audit trails
4. WHEN deleting applications THEN the ATS_System SHALL perform soft deletes to maintain historical records
5. WHEN API requests are made THEN the ATS_System SHALL authenticate users and enforce client-specific access controls

### Requirement 5

**User Story:** As a system administrator, I want all services to run in containerized environments, so that the system is portable, scalable, and easy to deploy.

#### Acceptance Criteria

1. WHEN the system is deployed THEN the ATS_System SHALL run all components (API, worker, database, cache) in Docker containers
2. WHEN services start up THEN the ATS_System SHALL establish proper network connectivity between all containers
3. WHEN the database container starts THEN the ATS_System SHALL apply all migrations and enable RLS policies automatically
4. WHEN data persistence is required THEN the ATS_System SHALL use mounted volumes for PostgreSQL data storage
5. WHERE environment configuration is needed THEN the ATS_System SHALL use environment variables and .env files for secrets management

### Requirement 6

**User Story:** As an HR administrator, I want the system to prevent hiring candidates who have previously left the organization, so that we can maintain our "do not rehire" policies.

#### Acceptance Criteria

1. WHEN processing a new resume THEN the ATS_System SHALL check for existing candidates using fuzzy matching algorithms
2. WHEN a candidate match is found with "LEFT" status THEN the ATS_System SHALL flag the application for manual review
3. WHEN computing candidate similarity THEN the ATS_System SHALL use name, email, and phone number for matching
4. WHEN flagged candidates are identified THEN the ATS_System SHALL prevent automatic hiring workflow progression
5. WHERE duplicate detection is performed THEN the ATS_System SHALL maintain candidate hash values for efficient matching

### Requirement 7

**User Story:** As a system administrator, I want comprehensive logging and monitoring of the resume processing pipeline, so that I can troubleshoot issues and ensure system reliability.

#### Acceptance Criteria

1. WHEN emails are received THEN the ATS_System SHALL log all ingestion events with timestamps and message identifiers
2. WHEN resume parsing fails THEN the Worker_Process SHALL log detailed error information for debugging
3. WHEN database operations occur THEN the ATS_System SHALL maintain audit logs of all data modifications
4. WHEN system health checks are performed THEN the ATS_System SHALL report status of all critical services
5. WHERE performance monitoring is required THEN the ATS_System SHALL track processing times and queue depths
