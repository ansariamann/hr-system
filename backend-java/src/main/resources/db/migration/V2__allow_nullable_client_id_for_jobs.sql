-- V2: Allow nullable client_id for jobs, resume_jobs, and users
ALTER TABLE jobs ALTER COLUMN client_id DROP NOT NULL;
ALTER TABLE resume_jobs ALTER COLUMN client_id DROP NOT NULL;
ALTER TABLE users ALTER COLUMN client_id DROP NOT NULL;

