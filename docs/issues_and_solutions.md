# ATS Backend Issues and Solutions

## Critical Issues Found and Fixed

### 1. Database Transaction Management (FATAL FLAW)

**Problem**: Records were not being saved to the database due to multiple `db.commit()` calls breaking transaction atomicity.

**Root Cause**:

- Repository layer called `db.commit()`
- Audit logger called `db.commit()` again
- FastAPI dependency called `db.commit()` a third time
- This created separate transactions, causing data inconsistency and potential data loss

**Solution**: Replaced all intermediate `db.commit()` with `db.flush()` to maintain single atomic transaction.

**Files Fixed**: 23 methods across 10 files

- `src/ats_backend/core/audit.py`
- `src/ats_backend/repositories/base.py`
- `src/ats_backend/repositories/application.py`
- `src/ats_backend/repositories/candidate.py`
- `src/ats_backend/repositories/resume_job.py`
- `src/ats_backend/services/client_service.py`
- `src/ats_backend/services/fsm_service.py`
- `src/ats_backend/auth/utils.py`
- `src/ats_backend/auth/security.py`

### 2. Middleware Stack Causing Connection Failures

**Problem**: HTTP requests were being closed without response, preventing frontend from communicating with backend.

**Root Causes**:

1. **InputSanitizationMiddleware**: Calling synchronous validation methods in async context
2. **AbuseProtectionMiddleware**: Rate limiter trying to access Redis with improper async handling
3. **AuthenticationMiddleware**: Complex token verification causing silent failures

**Temporary Solution**: Created `start_minimal.py` that bypasses all security middleware to get API functional.

**Permanent Solution Needed**:

- Refactor middleware to properly handle async/await
- Add better error handling and logging in middleware
- Implement graceful degradation when Redis is unavailable

### 3. Syntax and Import Errors

**Fixed**:

- `RateLimiter.__init__` missing method signature (IndentationError)
- `EmailServer` import should be `EmailSender`
- Signal handler naming conflict (`shutdown_event` used as both variable and function)
- Unicode encoding errors in Windows console output

## Current Status

### ✅ Working

- Health endpoint: `GET /health` returns 200
- Database connection established
- Redis connection established
- Basic API structure functional
- Frontend dashboard running on http://localhost:8081/

### ❌ Not Working

- **Fetching candidates/applications**: Requires authentication which is disabled in minimal mode
- **Resume upload/parsing**: Requires file upload endpoints and Celery workers
- **Authentication**: Disabled in minimal mode to bypass middleware issues

## Why Fetching Candidates/Applications Fails

### Issue 1: Authentication Required

The API endpoints for candidates and applications require authentication:

```python
@router.get("/candidates")
async def get_candidates(
    current_user: User = Depends(get_current_user),  # ← Requires auth
    current_client: Client = Depends(get_current_client),
    db: Session = Depends(get_db)
):
```

**Problem**: Authentication middleware is disabled in minimal mode, so `get_current_user` fails.

**Solution Options**:

1. Create a test user and login to get a token
2. Temporarily bypass authentication for development
3. Fix the middleware issues and re-enable authentication

### Issue 2: Database May Be Empty

Even with authentication working, the database might not have any records.

**Solution**: Run seed scripts to populate test data:

```bash
python scripts/seed_candidates.py
python scripts/seed_admin.py
```

## Why Resume Upload/Parsing Fails

### Issue 1: File Upload Endpoint

The resume upload endpoint requires:

1. Multipart form data handling
2. File storage configuration
3. Celery worker running for async processing

**Location**: `src/ats_backend/api/email.py` - resume upload endpoints

### Issue 2: Resume Parsing Pipeline

Resume parsing requires:

1. **OCR (Tesseract)**: Currently not installed (warning in logs)
2. **Celery Workers**: Must be running to process resumes asynchronously
3. **File Storage**: Configured storage directory for uploaded files

**Current State**:

- OCR unavailable: `[WinError 2] The system cannot find the file specified`
- Celery configured but workers not started
- Storage directory exists but upload handling disabled

### Issue 3: Resume Processing Flow

```
1. Upload Resume → 2. Store File → 3. Create Job → 4. Celery Task → 5. Parse → 6. Extract Data → 7. Create Candidate
```

**What's Missing**:

- Step 1: Upload endpoint needs authentication
- Step 4: Celery worker not running
- Step 5: OCR/parsing tools not configured

## How to Fix Resume Upload/Parsing

### Step 1: Start Celery Worker

```bash
# In a new terminal
celery -A src.ats_backend.workers.celery_app worker --loglevel=info
```

### Step 2: Install Tesseract OCR (Optional)

```bash
# Windows: Download from https://github.com/UB-Mannheim/tesseract/wiki
# Or use Chocolatey:
choco install tesseract

# Update .env.local with path:
TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe
```

### Step 3: Enable Authentication

Fix the middleware issues and re-enable:

- AuthenticationMiddleware
- AbuseProtectionMiddleware (with proper async handling)
- InputSanitizationMiddleware (with proper async handling)

### Step 4: Create Test User

```bash
python scripts/seed_admin.py
```

### Step 5: Test Upload

```bash
# Login to get token
curl -X POST http://localhost:8000/auth/login \
  -d "username=admin@example.com&password=admin123"

# Upload resume with token
curl -X POST http://localhost:8000/email/upload-resume \
  -H "Authorization: Bearer <token>" \
  -F "file=@resume.pdf"
```

## Recommended Next Steps

1. **Fix Middleware Issues** (High Priority)

   - Refactor to properly handle async/await
   - Add comprehensive error handling
   - Test each middleware independently

2. **Seed Database** (High Priority)

   - Run seed scripts to create test data
   - Verify candidates and applications are created

3. **Enable Authentication** (Medium Priority)

   - Create admin user
   - Test login flow
   - Verify token generation

4. **Start Celery Worker** (Medium Priority)

   - Start worker process
   - Test async task processing
   - Monitor task queue

5. **Configure Resume Parsing** (Low Priority)

   - Install Tesseract OCR
   - Test resume upload
   - Verify parsing and extraction

6. **Integration Testing** (Low Priority)
   - Test complete flow end-to-end
   - Verify data persistence
   - Check audit logging

## Files to Review

### For Fetching Issues:

- `src/ats_backend/api/candidates.py` - Candidate endpoints
- `src/ats_backend/api/applications.py` - Application endpoints
- `src/ats_backend/auth/dependencies.py` - Authentication dependencies
- `src/ats_backend/repositories/candidate.py` - Candidate data access
- `src/ats_backend/repositories/application.py` - Application data access

### For Resume Upload Issues:

- `src/ats_backend/api/email.py` - Resume upload endpoints
- `src/ats_backend/workers/email_tasks.py` - Celery tasks for processing
- `src/ats_backend/resume/parser.py` - Resume parsing logic
- `src/ats_backend/email/storage.py` - File storage handling
- `src/ats_backend/repositories/resume_job.py` - Resume job tracking

### For Middleware Issues:

- `src/ats_backend/main.py` - Middleware configuration
- `src/ats_backend/auth/middleware.py` - Authentication middleware
- `src/ats_backend/security/middleware.py` - Security middleware
- `src/ats_backend/security/abuse_protection.py` - Rate limiting

## Quick Start Guide

### To Get API Working with Authentication:

```bash
# 1. Seed database
python scripts/seed_admin.py
python scripts/seed_candidates.py

# 2. Start backend (minimal mode)
python start_minimal.py

# 3. Start frontend
cd frontend/hr-dashboard
npm run dev

# 4. Login with:
# Email: admin@example.com
# Password: admin123
```

### To Enable Resume Upload:

```bash
# 1. Start Celery worker
celery -A src.ats_backend.workers.celery_app worker --loglevel=info

# 2. (Optional) Install Tesseract
# Download from: https://github.com/UB-Mannheim/tesseract/wiki

# 3. Test upload via API or frontend
```
