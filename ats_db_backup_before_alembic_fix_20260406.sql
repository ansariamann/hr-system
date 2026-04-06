--
-- PostgreSQL database dump
--

-- Dumped from database version 15.16
-- Dumped by pg_dump version 17.5

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: pg_trgm; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS pg_trgm WITH SCHEMA public;


--
-- Name: EXTENSION pg_trgm; Type: COMMENT; Schema: -; Owner: 
--

COMMENT ON EXTENSION pg_trgm IS 'text similarity measurement and index searching based on trigrams';


--
-- Name: pgcrypto; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS pgcrypto WITH SCHEMA public;


--
-- Name: EXTENSION pgcrypto; Type: COMMENT; Schema: -; Owner: 
--

COMMENT ON EXTENSION pgcrypto IS 'cryptographic functions';


--
-- Name: uuid-ossp; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS "uuid-ossp" WITH SCHEMA public;


--
-- Name: EXTENSION "uuid-ossp"; Type: COMMENT; Schema: -; Owner: 
--

COMMENT ON EXTENSION "uuid-ossp" IS 'generate universally unique identifiers (UUIDs)';


--
-- Name: securityeventseverity; Type: TYPE; Schema: public; Owner: ats_user
--

CREATE TYPE public.securityeventseverity AS ENUM (
    'LOW',
    'MEDIUM',
    'HIGH',
    'CRITICAL'
);


ALTER TYPE public.securityeventseverity OWNER TO ats_user;

--
-- Name: securityeventtype; Type: TYPE; Schema: public; Owner: ats_user
--

CREATE TYPE public.securityeventtype AS ENUM (
    'auth_failure',
    'token_replay',
    'expired_token',
    'rate_limit_exceeded',
    'account_locked',
    'suspicious_activity',
    'rls_bypass_attempt'
);


ALTER TYPE public.securityeventtype OWNER TO ats_user;

--
-- Name: generate_candidate_hash(text, text, text); Type: FUNCTION; Schema: public; Owner: ats_user
--

CREATE FUNCTION public.generate_candidate_hash(p_name text, p_email text DEFAULT NULL::text, p_phone text DEFAULT NULL::text) RETURNS character varying
    LANGUAGE plpgsql IMMUTABLE
    AS $$
BEGIN
    RETURN encode(
        digest(
            LOWER(TRIM(COALESCE(p_name, ''))) || '|' ||
            LOWER(TRIM(COALESCE(p_email, ''))) || '|' ||
            REGEXP_REPLACE(COALESCE(p_phone, ''), '[^0-9]', '', 'g'),
            'sha256'
        ),
        'hex'
    );
END;
$$;


ALTER FUNCTION public.generate_candidate_hash(p_name text, p_email text, p_phone text) OWNER TO ats_user;

--
-- Name: log_fsm_transition(); Type: FUNCTION; Schema: public; Owner: ats_user
--

CREATE FUNCTION public.log_fsm_transition() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
        DECLARE
            actor_id_val UUID;
            actor_type_val VARCHAR(20);
            reason_val TEXT;
        BEGIN
            -- Get actor information from session variables
            actor_id_val := current_setting('app.current_user_id', true)::UUID;
            actor_type_val := COALESCE(current_setting('app.actor_type', true), 'SYSTEM');
            reason_val := COALESCE(current_setting('app.transition_reason', true), 'Status transition');
            
            -- Log the transition
            INSERT INTO fsm_transition_logs (
                candidate_id,
                old_status,
                new_status,
                actor_id,
                actor_type,
                reason,
                is_terminal,
                client_id
            ) VALUES (
                NEW.id,
                OLD.status,
                NEW.status,
                actor_id_val,
                actor_type_val,
                reason_val,
                NEW.status = 'LEFT_COMPANY',
                NEW.client_id
            );
            
            RETURN NEW;
        END;
        $$;


ALTER FUNCTION public.log_fsm_transition() OWNER TO ats_user;

--
-- Name: prevent_protected_field_modification(); Type: FUNCTION; Schema: public; Owner: ats_user
--

CREATE FUNCTION public.prevent_protected_field_modification() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
        BEGIN
            -- Prevent client modification of skills, candidate core profile, and blacklist flag
            -- Allow system modifications (when actor_type is SYSTEM in context)
            
            -- Check if this is a system modification by looking for a special session variable
            IF current_setting('app.allow_protected_field_modification', true) != 'true' THEN
                -- Prevent modification of skills
                IF OLD.skills IS DISTINCT FROM NEW.skills THEN
                    RAISE EXCEPTION 'Modification of candidate skills is not allowed';
                END IF;
                
                -- Prevent modification of core profile fields (name, email, phone)
                IF OLD.name IS DISTINCT FROM NEW.name THEN
                    RAISE EXCEPTION 'Modification of candidate name is not allowed';
                END IF;
                
                IF OLD.email IS DISTINCT FROM NEW.email THEN
                    RAISE EXCEPTION 'Modification of candidate email is not allowed';
                END IF;
                
                IF OLD.phone IS DISTINCT FROM NEW.phone THEN
                    RAISE EXCEPTION 'Modification of candidate phone is not allowed';
                END IF;
                
                -- Prevent modification of blacklist flag
                IF OLD.is_blacklisted IS DISTINCT FROM NEW.is_blacklisted THEN
                    RAISE EXCEPTION 'Modification of candidate blacklist status is not allowed';
                END IF;
            END IF;
            
            RETURN NEW;
        END;
        $$;


ALTER FUNCTION public.prevent_protected_field_modification() OWNER TO ats_user;

--
-- Name: update_candidate_hash(); Type: FUNCTION; Schema: public; Owner: ats_user
--

CREATE FUNCTION public.update_candidate_hash() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
        BEGIN
            NEW.candidate_hash = generate_candidate_hash(NEW.name, NEW.email, NEW.phone);
            RETURN NEW;
        END;
        $$;


ALTER FUNCTION public.update_candidate_hash() OWNER TO ats_user;

--
-- Name: update_updated_at_column(); Type: FUNCTION; Schema: public; Owner: ats_user
--

CREATE FUNCTION public.update_updated_at_column() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;


ALTER FUNCTION public.update_updated_at_column() OWNER TO ats_user;

--
-- Name: validate_candidate_status_transition(); Type: FUNCTION; Schema: public; Owner: ats_user
--

CREATE FUNCTION public.validate_candidate_status_transition() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
        BEGIN
            -- Prevent skipping JOINED state when transitioning to LEFT_COMPANY
            IF OLD.status = 'ACTIVE' AND NEW.status = 'LEFT_COMPANY' THEN
                -- Must have been JOINED first - check FSM transition logs
                IF NOT EXISTS (
                    SELECT 1 FROM fsm_transition_logs
                    WHERE candidate_id = NEW.id
                    AND new_status = 'JOINED'
                ) THEN
                    RAISE EXCEPTION 'Cannot transition from ACTIVE to LEFT_COMPANY without first transitioning to JOINED state';
                END IF;
            END IF;
            
            -- Enforce terminal state: no transitions allowed from LEFT_COMPANY (Requirement 3.3)
            IF OLD.status = 'LEFT_COMPANY' AND NEW.status != 'LEFT_COMPANY' THEN
                RAISE EXCEPTION 'LEFT_COMPANY is a terminal state - no further transitions allowed';
            END IF;
            
            -- When transitioning to LEFT_COMPANY, automatically set is_blacklisted to TRUE
            IF NEW.status = 'LEFT_COMPANY' THEN
                NEW.is_blacklisted = TRUE;
            END IF;
            
            RETURN NEW;
        END;
        $$;


ALTER FUNCTION public.validate_candidate_status_transition() OWNER TO ats_user;

--
-- Name: validate_client_context(); Type: FUNCTION; Schema: public; Owner: ats_user
--

CREATE FUNCTION public.validate_client_context() RETURNS boolean
    LANGUAGE plpgsql
    AS $$
BEGIN
    -- Check if current_setting exists and is a valid UUID
    BEGIN
        PERFORM current_setting('app.current_client_id', true)::UUID;
        RETURN true;
    EXCEPTION WHEN OTHERS THEN
        RETURN false;
    END;
END;
$$;


ALTER FUNCTION public.validate_client_context() OWNER TO ats_user;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: activity_logs; Type: TABLE; Schema: public; Owner: ats_user
--

CREATE TABLE public.activity_logs (
    id uuid NOT NULL,
    client_id uuid,
    user_id uuid,
    action_type character varying(50) NOT NULL,
    entity_id uuid,
    details json,
    created_at timestamp without time zone NOT NULL
);


ALTER TABLE public.activity_logs OWNER TO ats_user;

--
-- Name: alembic_version; Type: TABLE; Schema: public; Owner: ats_user
--

CREATE TABLE public.alembic_version (
    version_num character varying(32) NOT NULL
);


ALTER TABLE public.alembic_version OWNER TO ats_user;

--
-- Name: applications; Type: TABLE; Schema: public; Owner: ats_user
--

CREATE TABLE public.applications (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    client_id uuid NOT NULL,
    candidate_id uuid NOT NULL,
    job_title character varying(255),
    application_date timestamp without time zone DEFAULT now() NOT NULL,
    status character varying(50) DEFAULT 'RECEIVED'::character varying NOT NULL,
    flagged_for_review boolean DEFAULT false NOT NULL,
    flag_reason text,
    deleted_at timestamp without time zone,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL,
    job_id uuid,
    source character varying(100) DEFAULT 'MANUAL'::character varying NOT NULL,
    status_updated_at timestamp without time zone NOT NULL,
    notes text,
    applied_by_user_id uuid
);


ALTER TABLE public.applications OWNER TO ats_user;

--
-- Name: audit_logs; Type: TABLE; Schema: public; Owner: ats_user
--

CREATE TABLE public.audit_logs (
    id uuid NOT NULL,
    client_id uuid NOT NULL,
    user_id uuid,
    table_name character varying(255) NOT NULL,
    record_id uuid NOT NULL,
    action character varying(50) NOT NULL,
    old_values json,
    new_values json,
    changes json,
    "timestamp" timestamp without time zone DEFAULT now() NOT NULL,
    ip_address character varying(45),
    user_agent text
);


ALTER TABLE public.audit_logs OWNER TO ats_user;

--
-- Name: candidates; Type: TABLE; Schema: public; Owner: ats_user
--

CREATE TABLE public.candidates (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    client_id uuid NOT NULL,
    name character varying(255) NOT NULL,
    email character varying(255),
    phone character varying(50),
    skills json,
    experience json,
    ctc_current numeric(12,2),
    ctc_expected numeric(12,2),
    status character varying(50) DEFAULT 'ACTIVE'::character varying NOT NULL,
    candidate_hash character varying(64),
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL,
    is_blacklisted boolean DEFAULT false NOT NULL,
    location character varying(255),
    remark text,
    resume_file_path text,
    resume_url text,
    assigned_user_id uuid,
    present_address text,
    permanent_address text,
    date_of_birth date,
    previous_employment json,
    key_skill text,
    company character varying(255),
    is_direct_interview boolean DEFAULT false NOT NULL,
    total_experience_years numeric(5,2),
    notice_period_days integer,
    source character varying(100) DEFAULT 'MANUAL'::character varying NOT NULL,
    linkedin_url character varying(500),
    selected_client_name character varying(255),
    assigned_client_id uuid,
    CONSTRAINT check_left_company_blacklisted CHECK ((((status)::text <> 'LEFT_COMPANY'::text) OR (is_blacklisted = true)))
);


ALTER TABLE public.candidates OWNER TO ats_user;

--
-- Name: clients; Type: TABLE; Schema: public; Owner: ats_user
--

CREATE TABLE public.clients (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    name character varying(255) NOT NULL,
    email_domain character varying(255),
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL,
    industry character varying(100),
    contact_name character varying(255),
    contact_email character varying(255),
    contact_phone character varying(50),
    address text,
    website character varying(500),
    is_active boolean NOT NULL
);


ALTER TABLE public.clients OWNER TO ats_user;

--
-- Name: company_employees; Type: TABLE; Schema: public; Owner: ats_user
--

CREATE TABLE public.company_employees (
    id uuid NOT NULL,
    client_id uuid NOT NULL,
    candidate_id uuid,
    application_id uuid,
    name character varying(255) NOT NULL,
    email character varying(255),
    phone character varying(50),
    role character varying(255),
    department character varying(255),
    date_of_joining date,
    status character varying(50) DEFAULT 'ACTIVE'::character varying NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    notes text,
    created_at timestamp without time zone NOT NULL,
    updated_at timestamp without time zone NOT NULL
);


ALTER TABLE public.company_employees OWNER TO ats_user;

--
-- Name: fsm_transition_logs; Type: TABLE; Schema: public; Owner: ats_user
--

CREATE TABLE public.fsm_transition_logs (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    candidate_id uuid NOT NULL,
    old_status character varying(50) NOT NULL,
    new_status character varying(50) NOT NULL,
    actor_id uuid,
    actor_type character varying(20) DEFAULT 'SYSTEM'::character varying NOT NULL,
    reason text NOT NULL,
    is_terminal boolean DEFAULT false NOT NULL,
    client_id uuid NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.fsm_transition_logs OWNER TO ats_user;

--
-- Name: interview_records; Type: TABLE; Schema: public; Owner: ats_user
--

CREATE TABLE public.interview_records (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    candidate_id uuid NOT NULL,
    client_id uuid NOT NULL,
    company_id uuid NOT NULL,
    interviewer_id uuid NOT NULL,
    interview_date timestamp without time zone NOT NULL,
    notes text,
    rating integer,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    deleted_at timestamp without time zone,
    "position" character varying(255),
    skills json,
    CONSTRAINT interview_records_rating_check CHECK (((rating >= 1) AND (rating <= 5))),
    CONSTRAINT interview_records_rating_range_chk CHECK (((rating IS NULL) OR ((rating >= 1) AND (rating <= 5))))
);


ALTER TABLE public.interview_records OWNER TO ats_user;

--
-- Name: jobs; Type: TABLE; Schema: public; Owner: ats_user
--

CREATE TABLE public.jobs (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    client_id uuid NOT NULL,
    title character varying(255) NOT NULL,
    company_name character varying(255) NOT NULL,
    posting_date date DEFAULT CURRENT_DATE NOT NULL,
    requirements text,
    experience_required integer,
    salary_lpa numeric(10,2),
    location character varying(255),
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL,
    submitted_by_client boolean DEFAULT false NOT NULL,
    closing_date date,
    department character varying(255),
    employment_type character varying(50) DEFAULT 'FULL_TIME'::character varying NOT NULL,
    openings_count integer DEFAULT 1 NOT NULL,
    status character varying(50) DEFAULT 'OPEN'::character varying NOT NULL,
    vacant boolean DEFAULT true NOT NULL
);


ALTER TABLE public.jobs OWNER TO ats_user;

--
-- Name: password_reset_tokens; Type: TABLE; Schema: public; Owner: ats_user
--

CREATE TABLE public.password_reset_tokens (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    user_id uuid NOT NULL,
    token_hash character varying(128) NOT NULL,
    expires_at timestamp without time zone NOT NULL,
    used_at timestamp without time zone,
    requested_ip character varying(45),
    user_agent text,
    created_at timestamp without time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.password_reset_tokens OWNER TO ats_user;

--
-- Name: resume_jobs; Type: TABLE; Schema: public; Owner: ats_user
--

CREATE TABLE public.resume_jobs (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    client_id uuid NOT NULL,
    email_message_id character varying(255),
    file_name character varying(255),
    file_path text,
    status character varying(50) DEFAULT 'PENDING'::character varying NOT NULL,
    error_message text,
    processed_at timestamp without time zone,
    created_at timestamp without time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.resume_jobs OWNER TO ats_user;

--
-- Name: security_audit_logs; Type: TABLE; Schema: public; Owner: ats_user
--

CREATE TABLE public.security_audit_logs (
    id uuid NOT NULL,
    event_type character varying(50) NOT NULL,
    severity character varying(20) NOT NULL,
    client_id uuid,
    user_id uuid,
    ip_address character varying(45),
    user_agent text,
    email character varying(255),
    details json NOT NULL,
    created_at timestamp without time zone NOT NULL,
    CONSTRAINT check_event_type CHECK (((event_type)::text = ANY ((ARRAY['auth_failure'::character varying, 'token_replay'::character varying, 'expired_token'::character varying, 'rate_limit_exceeded'::character varying, 'account_locked'::character varying, 'suspicious_activity'::character varying, 'rls_bypass_attempt'::character varying])::text[]))),
    CONSTRAINT check_severity CHECK (((severity)::text = ANY ((ARRAY['LOW'::character varying, 'MEDIUM'::character varying, 'HIGH'::character varying, 'CRITICAL'::character varying])::text[])))
);


ALTER TABLE public.security_audit_logs OWNER TO ats_user;

--
-- Name: users; Type: TABLE; Schema: public; Owner: ats_user
--

CREATE TABLE public.users (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    email character varying(255) NOT NULL,
    hashed_password character varying(255) NOT NULL,
    full_name character varying(255),
    is_active boolean DEFAULT true NOT NULL,
    client_id uuid NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL,
    role character varying(50) DEFAULT 'client_user'::character varying NOT NULL
);


ALTER TABLE public.users OWNER TO ats_user;

--
-- Data for Name: activity_logs; Type: TABLE DATA; Schema: public; Owner: ats_user
--

COPY public.activity_logs (id, client_id, user_id, action_type, entity_id, details, created_at) FROM stdin;
3a8b50f6-a3a7-413f-8804-ba95e61d943d	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	265468a9-ed94-46a1-ac2d-4b130a1fcff2	CLIENT_CREATED	a3e16bca-3a81-4aff-8db4-c219484af1d7	{"name": "orcl", "email_domain": "gmail.com"}	2026-04-06 16:45:29.016813
dafdba06-451b-44be-b5d8-d0cff650c2d4	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	265468a9-ed94-46a1-ac2d-4b130a1fcff2	HR_DASHBOARD_API_REQUEST	\N	{"endpoint": "/clients/", "method": "POST", "status_code": 201, "duration_ms": 191}	2026-04-06 16:45:29.071123
2834b454-dfb3-4f32-93b8-b99b355eb2ff	a3e16bca-3a81-4aff-8db4-c219484af1d7	fc69ddfb-d533-420d-9cf2-4dd9d2fe3bf9	JOB_CREATED	127cc8c2-7498-4137-9bb9-b2213753acf2	{"title": "sj", "company_name": "orcl", "submitted_by_client": true, "source": "client_portal", "posting_date": "2026-04-06", "closing_date": null, "department": null, "employment_type": "FULL_TIME", "openings_count": 1, "status": "OPEN", "vacant": true}	2026-04-06 16:47:16.419501
7c6fd0c5-debf-4e86-9ebb-cdcc7d34c193	a3e16bca-3a81-4aff-8db4-c219484af1d7	265468a9-ed94-46a1-ac2d-4b130a1fcff2	APPLICATION_CREATED	f08ec5f9-dfb1-42c1-8660-ca5ac09d8e3a	{"table_name": "applications", "audit_action": "CREATE", "new_values": {"id": "f08ec5f9-dfb1-42c1-8660-ca5ac09d8e3a", "client_id": "a3e16bca-3a81-4aff-8db4-c219484af1d7", "candidate_id": "5299a44b-155c-4d9c-9a37-1b82c46dd0f1", "job_id": "127cc8c2-7498-4137-9bb9-b2213753acf2", "job_title": "sj", "application_date": "2026-04-06T16:48:01.146494", "source": "MANUAL", "status": "RECEIVED", "status_updated_at": "2026-04-06T16:48:01.146499", "flagged_for_review": false, "flag_reason": null, "notes": "f", "applied_by_user_id": "265468a9-ed94-46a1-ac2d-4b130a1fcff2", "deleted_at": null, "created_at": "2026-04-06T16:48:01.146500", "updated_at": "2026-04-06T16:48:01.146501"}}	2026-04-06 16:48:01.187756
95552016-206c-4347-92c2-a90eeb91edfb	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	265468a9-ed94-46a1-ac2d-4b130a1fcff2	HR_DASHBOARD_API_REQUEST	\N	{"endpoint": "/applications", "method": "POST", "status_code": 201, "duration_ms": 308}	2026-04-06 16:48:01.317768
\.


--
-- Data for Name: alembic_version; Type: TABLE DATA; Schema: public; Owner: ats_user
--

COPY public.alembic_version (version_num) FROM stdin;
a7b3c1d2e4f5
\.


--
-- Data for Name: applications; Type: TABLE DATA; Schema: public; Owner: ats_user
--

COPY public.applications (id, client_id, candidate_id, job_title, application_date, status, flagged_for_review, flag_reason, deleted_at, created_at, updated_at, job_id, source, status_updated_at, notes, applied_by_user_id) FROM stdin;
f08ec5f9-dfb1-42c1-8660-ca5ac09d8e3a	a3e16bca-3a81-4aff-8db4-c219484af1d7	5299a44b-155c-4d9c-9a37-1b82c46dd0f1	sj	2026-04-06 16:48:01.146494	RECEIVED	f	\N	\N	2026-04-06 16:48:01.1465	2026-04-06 16:48:01.146501	127cc8c2-7498-4137-9bb9-b2213753acf2	MANUAL	2026-04-06 16:48:01.146499	f	265468a9-ed94-46a1-ac2d-4b130a1fcff2
\.


--
-- Data for Name: audit_logs; Type: TABLE DATA; Schema: public; Owner: ats_user
--

COPY public.audit_logs (id, client_id, user_id, table_name, record_id, action, old_values, new_values, changes, "timestamp", ip_address, user_agent) FROM stdin;
86de35d0-59e6-4611-b35a-b6e26a4aef87	a3e16bca-3a81-4aff-8db4-c219484af1d7	265468a9-ed94-46a1-ac2d-4b130a1fcff2	applications	f08ec5f9-dfb1-42c1-8660-ca5ac09d8e3a	CREATE	\N	{"id": "f08ec5f9-dfb1-42c1-8660-ca5ac09d8e3a", "client_id": "a3e16bca-3a81-4aff-8db4-c219484af1d7", "candidate_id": "5299a44b-155c-4d9c-9a37-1b82c46dd0f1", "job_id": "127cc8c2-7498-4137-9bb9-b2213753acf2", "job_title": "sj", "application_date": "2026-04-06T16:48:01.146494", "source": "MANUAL", "status": "RECEIVED", "status_updated_at": "2026-04-06T16:48:01.146499", "flagged_for_review": false, "flag_reason": null, "notes": "f", "applied_by_user_id": "265468a9-ed94-46a1-ac2d-4b130a1fcff2", "deleted_at": null, "created_at": "2026-04-06T16:48:01.146500", "updated_at": "2026-04-06T16:48:01.146501"}	\N	2026-04-06 16:48:01.17292	172.18.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36
\.


--
-- Data for Name: candidates; Type: TABLE DATA; Schema: public; Owner: ats_user
--

COPY public.candidates (id, client_id, name, email, phone, skills, experience, ctc_current, ctc_expected, status, candidate_hash, created_at, updated_at, is_blacklisted, location, remark, resume_file_path, resume_url, assigned_user_id, present_address, permanent_address, date_of_birth, previous_employment, key_skill, company, is_direct_interview, total_experience_years, notice_period_days, source, linkedin_url, selected_client_name, assigned_client_id) FROM stdin;
75b2f21f-3315-466a-bce1-4abf060cf85a	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Dev Gupta	seed.candidate.0001@example.com	+91-9759230078	{"skills": ["Sales", "Kubernetes", "TypeScript", "MySQL", "Python", "Excel"]}	{"years": 1, "current_role": "Backend Developer"}	25.41	26.84	ACTIVE	78f88798052263f05a0c3f704d443e6087a4802c49b1ea2ff46ec07666a2124a	2026-04-06 16:34:52.874382	2026-04-06 16:34:52.874382	f	Remote	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Meridian Works", "title": "Backend Developer", "start_date": "2020-01-01", "end_date": "Present"}]	\N	Meridian Works	f	\N	\N	MANUAL	\N	\N	\N
5404a632-617c-401a-8a9a-29e15997a93d	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Sophia Singh	seed.candidate.0003@example.com	+91-9304393649	{"skills": ["Python", "Figma", "Power BI", "Kubernetes", "Spring"]}	{"years": 5, "current_role": "UI Designer"}	24.98	27.09	ACTIVE	4944c42db507bdc713e11b3ce5750f76fc7ca2e84ff1a2ecc0737006f98d64be	2026-04-06 16:34:52.88031	2026-04-06 16:34:52.88031	f	Bangalore	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Quantum Stack", "title": "UI Designer", "start_date": "2021-01-01", "end_date": "Present"}]	\N	Quantum Stack	f	\N	\N	MANUAL	\N	\N	\N
bb13a05f-5b75-4033-a56c-ca8dfa719cf1	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Liam Reddy	seed.candidate.0004@example.com	+91-9798483634	{"skills": ["TypeScript", "FastAPI", "Marketing", "Spring", "PostgreSQL", "Excel"]}	{"years": 6, "current_role": "Recruitment Specialist"}	27.39	33.18	ACTIVE	1334642992ea1e4308ceba8bc51eec6bd4efc0a21f7303bba0e57a5d236e6649	2026-04-06 16:34:52.88235	2026-04-06 16:34:52.88235	f	San Francisco	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "BlueOrbit Tech", "title": "Recruitment Specialist", "start_date": "2018-01-01", "end_date": "Present"}]	\N	BlueOrbit Tech	f	\N	\N	MANUAL	\N	\N	\N
1113f55b-395a-490d-887a-4441e68ab763	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Aisha Joshi	seed.candidate.0005@example.com	+91-9587897581	{"skills": ["Python", "MySQL", "Marketing", "FastAPI", "PostgreSQL", "Figma"]}	{"years": 4, "current_role": "Marketing Associate"}	4.84	8.95	ACTIVE	a6f10f56d02b39ea73298234bcc2c9cb5de3b6e7a0d18107a2e2198d51744d45	2026-04-06 16:34:52.885467	2026-04-06 16:34:52.885467	f	San Francisco	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Skyline Digital", "title": "Marketing Associate", "start_date": "2018-01-01", "end_date": "Present"}]	\N	Skyline Digital	f	\N	\N	MANUAL	\N	\N	\N
5ee3ae4a-7a64-4150-965a-f9860ccdd4a4	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Akash Mehta	seed.candidate.0006@example.com	+91-9131832585	{"skills": ["Azure", "Kubernetes", "PostgreSQL", "Node.js", "MySQL", "Redis"]}	{"years": 4, "current_role": "Backend Developer"}	18.74	24.67	ACTIVE	6895b58542747a55934a12574178e752a0e7d7dfef45a7dc328dcc003a134dcb	2026-04-06 16:34:52.888995	2026-04-06 16:34:52.888995	f	San Francisco	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Nimbus Cloud", "title": "Backend Developer", "start_date": "2018-01-01", "end_date": "Present"}]	\N	Nimbus Cloud	f	\N	\N	MANUAL	\N	\N	\N
278eafdd-6244-4af8-92da-857eed1d68fb	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Maya Anderson	seed.candidate.0007@example.com	+91-9690414935	{"skills": ["Python", "Azure", "Figma", "Power BI", "AWS", "Redis"]}	{"years": 3, "current_role": "Senior Software Engineer"}	17.98	23.26	ACTIVE	661b7b66faed672d01df98cfddf9ad76ddb96824dac7444ea508c3322ddf4d01	2026-04-06 16:34:52.891511	2026-04-06 16:34:52.891511	f	Mumbai	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Pioneer Health", "title": "Senior Software Engineer", "start_date": "2018-01-01", "end_date": "Present"}]	\N	Pioneer Health	f	\N	\N	MANUAL	\N	\N	\N
2e7a6fed-6cd8-4e67-aacb-a1b190dcdd91	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Olivia Thomas	seed.candidate.0008@example.com	+91-9894237063	{"skills": ["MySQL", "Figma", "Marketing"]}	{"years": 11, "current_role": "Data Analyst"}	25.19	27.29	ACTIVE	831113f52020883b14190eeee7e9c39375d222bf352e53e83de7ac2f9782a34e	2026-04-06 16:34:52.893676	2026-04-06 16:34:52.893676	f	Pune	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Pioneer Health", "title": "Data Analyst", "start_date": "2021-01-01", "end_date": "Present"}]	\N	Pioneer Health	f	\N	\N	MANUAL	\N	\N	\N
b64ed607-d86c-48b5-9df5-b80ee31c45e0	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Anaya Reddy	seed.candidate.0009@example.com	+91-9213813485	{"skills": ["Sales", "Node.js", "Power BI", "Redis", "AWS"]}	{"years": 12, "current_role": "DevOps Engineer"}	9.54	12.38	ACTIVE	390501583720a74c72da422deb2ae26d8f1795666a23d71c374737624a5e6a74	2026-04-06 16:34:52.898246	2026-04-06 16:34:52.898246	f	Kolkata	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Zenith Commerce", "title": "DevOps Engineer", "start_date": "2021-01-01", "end_date": "Present"}]	\N	Zenith Commerce	f	\N	\N	MANUAL	\N	\N	\N
c197e266-1181-4fa9-bc8f-8a0bd8105322	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Aditya Williams	seed.candidate.0010@example.com	+91-9768090570	{"skills": ["PostgreSQL", "Redis", "Sales", "Spring", "Kubernetes"]}	{"years": 11, "current_role": "Product Manager"}	13.70	19.11	ACTIVE	54e94853c86be8c3ccf1acac132c0e2b3e3ba6eaa9567a5bc51edf2ccd1ce3c5	2026-04-06 16:34:52.902879	2026-04-06 16:34:52.902879	f	Toronto	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Acme Systems", "title": "Product Manager", "start_date": "2018-01-01", "end_date": "Present"}]	\N	Acme Systems	f	\N	\N	MANUAL	\N	\N	\N
1745176c-55b7-4491-b806-304eb038b1fe	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Amelia Malhotra	seed.candidate.0011@example.com	+91-9370617461	{"skills": ["Sales", "FastAPI", "MySQL", "AWS"]}	{"years": 8, "current_role": "UI Designer"}	18.46	21.93	ACTIVE	09a3159e0564225b2a219ae5fc355662c07d15fff0c40f91a6bbccf5e1d45e80	2026-04-06 16:34:52.905234	2026-04-06 16:34:52.905234	f	San Francisco	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Pioneer Health", "title": "UI Designer", "start_date": "2022-01-01", "end_date": "Present"}]	\N	Pioneer Health	f	\N	\N	MANUAL	\N	\N	\N
6ec310c3-6254-469f-b645-2ef677890ad0	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Aisha Nair	seed.candidate.0012@example.com	+91-9705986583	{"skills": ["Java", "AWS", "Sales", "Redis", "Spring", "MySQL"]}	{"years": 11, "current_role": "Product Manager"}	11.76	17.96	ACTIVE	090604e80787dfb9218b55aa4732a6a519fb936706289f3e913c988eb503a19a	2026-04-06 16:34:52.90976	2026-04-06 16:34:52.90976	f	Kolkata	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "IronPeak Data", "title": "Product Manager", "start_date": "2021-01-01", "end_date": "Present"}]	\N	IronPeak Data	f	\N	\N	MANUAL	\N	\N	\N
5b49b2d2-b810-4856-9852-0c5a901bc03e	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Arjun Joshi	seed.candidate.0013@example.com	+91-9667928867	{"skills": ["Figma", "React", "PostgreSQL"]}	{"years": 10, "current_role": "UI Designer"}	22.87	23.88	ACTIVE	f5de9e1dec9cb86aa2418a5d13d0aa4f59d05a1ee90dd1940e4d5bff351aa9ac	2026-04-06 16:34:52.915357	2026-04-06 16:34:52.915357	f	Ahmedabad	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Meridian Works", "title": "UI Designer", "start_date": "2022-01-01", "end_date": "Present"}]	\N	Meridian Works	f	\N	\N	MANUAL	\N	\N	\N
c8c20376-9e72-42ff-9226-b006d067146b	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Harper Verma	seed.candidate.0014@example.com	+91-9813524576	{"skills": ["Java", "Kubernetes", "Power BI", "Figma", "Marketing", "Docker"]}	{"years": 6, "current_role": "Marketing Associate"}	17.09	22.01	ACTIVE	aba6a17ed9cceed873ec3e41c8fddc5bdfde2dff0d220e468c9b224f403b14e9	2026-04-06 16:34:52.921167	2026-04-06 16:34:52.921167	f	New York	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Vertex AI", "title": "Marketing Associate", "start_date": "2018-01-01", "end_date": "Present"}]	\N	Vertex AI	f	\N	\N	MANUAL	\N	\N	\N
2c9e2a22-cab0-4f6f-8b8d-bfd979fc5e10	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Aisha Brown	seed.candidate.0015@example.com	+91-9314496947	{"skills": ["Docker", "Azure", "AWS", "MySQL"]}	{"years": 6, "current_role": "Backend Developer"}	7.05	10.52	ACTIVE	eec7535d6399e78c0e76311a9aeb679385b3c30f15888fd2a99bde3260a10e17	2026-04-06 16:34:52.925214	2026-04-06 16:34:52.925214	f	Kolkata	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Quantum Stack", "title": "Backend Developer", "start_date": "2022-01-01", "end_date": "Present"}]	\N	Quantum Stack	f	\N	\N	MANUAL	\N	\N	\N
57177394-821c-4c06-8a47-438112634c2e	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Sophia Nair	seed.candidate.0016@example.com	+91-9173592401	{"skills": ["Java", "Kubernetes", "Redis", "FastAPI"]}	{"years": 11, "current_role": "Senior Software Engineer"}	17.87	21.21	ACTIVE	4bd8b903852d8193fcb31b316dee764dd05c5f15cbf980afb3b15a82d553335d	2026-04-06 16:34:52.930322	2026-04-06 16:34:52.930322	f	Ahmedabad	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Pioneer Health", "title": "Senior Software Engineer", "start_date": "2018-01-01", "end_date": "Present"}]	\N	Pioneer Health	f	\N	\N	MANUAL	\N	\N	\N
4a45fa69-f866-481f-9c23-c85dfe608ed8	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Olivia Thomas	seed.candidate.0017@example.com	+91-9830328965	{"skills": ["Python", "Spring", "Sales", "Node.js", "Django", "React"]}	{"years": 1, "current_role": "UI Designer"}	17.54	21.90	ACTIVE	8e8ba191d0dcae89f5c21356a0c8e671e97188ee36f69555e2631f000837103c	2026-04-06 16:34:52.934852	2026-04-06 16:34:52.934852	f	Hyderabad	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "BrightPath Solutions", "title": "UI Designer", "start_date": "2021-01-01", "end_date": "Present"}]	\N	BrightPath Solutions	f	\N	\N	MANUAL	\N	\N	\N
a0c9d055-dae3-454d-9d0b-0cb0d186ed85	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Maya Johnson	seed.candidate.0018@example.com	+91-9436675468	{"skills": ["Django", "Excel", "Redis", "Docker"]}	{"years": 3, "current_role": "Sales Executive"}	9.40	14.08	ACTIVE	cbf77c4e4f3469eb18119de19b7192ff0b22a01416333a8ecb08d7cf43208de1	2026-04-06 16:34:52.938907	2026-04-06 16:34:52.938907	f	Hyderabad	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Pioneer Health", "title": "Sales Executive", "start_date": "2019-01-01", "end_date": "Present"}]	\N	Pioneer Health	f	\N	\N	MANUAL	\N	\N	\N
9c251d4d-2a2c-4f96-91c2-b1a17968308f	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Rohan Malhotra	seed.candidate.0019@example.com	+91-9550051238	{"skills": ["FastAPI", "Power BI", "Sales", "PostgreSQL", "Java"]}	{"years": 7, "current_role": "Frontend Developer"}	13.37	18.94	ACTIVE	b3d0fd7d5fc6f27faee42ca363ead04369299451baffb509524720c85936ce32	2026-04-06 16:34:52.944935	2026-04-06 16:34:52.944935	f	Remote	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "BlueOrbit Tech", "title": "Frontend Developer", "start_date": "2019-01-01", "end_date": "Present"}]	\N	BlueOrbit Tech	f	\N	\N	MANUAL	\N	\N	\N
864067b0-5f34-46dd-a155-1152c85982e7	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Anika Patel	seed.candidate.0020@example.com	+91-9505863415	{"skills": ["AWS", "Azure", "Marketing", "Node.js"]}	{"years": 12, "current_role": "Data Analyst"}	11.79	19.54	ACTIVE	c33b0165597a3b78cb748c5ad0721610c2d3664926ad1a85eedfeb928b8e025d	2026-04-06 16:34:52.949963	2026-04-06 16:34:52.949963	f	Chennai	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Quantum Stack", "title": "Data Analyst", "start_date": "2020-01-01", "end_date": "Present"}]	\N	Quantum Stack	f	\N	\N	MANUAL	\N	\N	\N
c4c1cbed-2973-465f-baad-7f1cbf868423	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Arjun Iyer	seed.candidate.0021@example.com	+91-9751367857	{"skills": ["Spring", "FastAPI", "TypeScript", "Excel", "Node.js", "Marketing"]}	{"years": 2, "current_role": "Frontend Developer"}	7.89	10.27	ACTIVE	a75940029cade3379bd011f27ef11867b9671145ab4e1ecdc75cb6595a5b5a7c	2026-04-06 16:34:52.955443	2026-04-06 16:34:52.955443	f	Ahmedabad	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "BlueOrbit Tech", "title": "Frontend Developer", "start_date": "2020-01-01", "end_date": "Present"}]	\N	BlueOrbit Tech	f	\N	\N	MANUAL	\N	\N	\N
568d7750-25e2-4596-a6b5-f2dc536c7f94	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Harper Das	seed.candidate.0022@example.com	+91-9218409494	{"skills": ["Kubernetes", "Excel", "React", "Docker", "MySQL"]}	{"years": 7, "current_role": "Sales Executive"}	9.02	10.49	ACTIVE	5ce88246d88532050fe2498b4d7336f447871e999347dc02f80945d70acbe85d	2026-04-06 16:34:52.959511	2026-04-06 16:34:52.959511	f	Pune	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Vertex AI", "title": "Sales Executive", "start_date": "2020-01-01", "end_date": "Present"}]	\N	Vertex AI	f	\N	\N	MANUAL	\N	\N	\N
e5581d22-6445-457f-9436-f6f5073fd7b1	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Olivia Joshi	seed.candidate.0023@example.com	+91-9861521715	{"skills": ["Docker", "TypeScript", "Django"]}	{"years": 1, "current_role": "Sales Executive"}	23.75	31.42	ACTIVE	00f167f7503f804a9e757b099bf000b939a94ccc2ef57853aa868a82d5008e9c	2026-04-06 16:34:52.965036	2026-04-06 16:34:52.965036	f	Chennai	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Pioneer Health", "title": "Sales Executive", "start_date": "2022-01-01", "end_date": "Present"}]	\N	Pioneer Health	f	\N	\N	MANUAL	\N	\N	\N
268fc214-edfd-44d2-9eb6-bc35ec2074ff	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Rohan Nair	seed.candidate.0024@example.com	+91-9204405592	{"skills": ["Power BI", "React", "Redis", "Docker", "Django", "Python"]}	{"years": 9, "current_role": "QA Engineer"}	17.97	23.75	ACTIVE	faa31a1dcc69694b3b8b3b4c7c9f5a48bb1941269fb99b224448148dd6cf9efd	2026-04-06 16:34:52.970776	2026-04-06 16:34:52.970776	f	Delhi	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Acme Systems", "title": "QA Engineer", "start_date": "2022-01-01", "end_date": "Present"}]	\N	Acme Systems	f	\N	\N	MANUAL	\N	\N	\N
d792ceea-2f35-4e77-a9f0-9cf19f5c9510	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Priya Malhotra	seed.candidate.0025@example.com	+91-9366461677	{"skills": ["React", "Docker", "Redis", "Marketing", "Django", "Python"]}	{"years": 10, "current_role": "Data Analyst"}	6.26	12.47	ACTIVE	015df48c755ad9ed4a6930b9bf426c678dec1475abfbc0bfe398509ac08d7ea8	2026-04-06 16:34:52.976159	2026-04-06 16:34:52.976159	f	San Francisco	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Northstar Labs", "title": "Data Analyst", "start_date": "2018-01-01", "end_date": "Present"}]	\N	Northstar Labs	f	\N	\N	MANUAL	\N	\N	\N
783040c1-f03d-4bd4-8c24-f3ac70cdd202	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Anika Brown	seed.candidate.0026@example.com	+91-9742848005	{"skills": ["TypeScript", "Figma", "Marketing", "Java", "FastAPI"]}	{"years": 11, "current_role": "Sales Executive"}	20.64	25.18	ACTIVE	28ae6c795c2b7d7b0cc63de3e3da412dacbf1ae091e755e294d489393f5f3562	2026-04-06 16:34:52.981677	2026-04-06 16:34:52.981677	f	Hyderabad	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Quantum Stack", "title": "Sales Executive", "start_date": "2018-01-01", "end_date": "Present"}]	\N	Quantum Stack	f	\N	\N	MANUAL	\N	\N	\N
73efd218-a114-45ba-9863-70b8f153af66	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Dev Taylor	seed.candidate.0027@example.com	+91-9687170478	{"skills": ["MySQL", "PostgreSQL", "AWS"]}	{"years": 6, "current_role": "Data Analyst"}	24.44	27.52	ACTIVE	b2887444a1e2b90bf333857e752f2465efda221fe18c585b4a9ed814cc9f1039	2026-04-06 16:34:52.985269	2026-04-06 16:34:52.985269	f	New York	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Meridian Works", "title": "Data Analyst", "start_date": "2020-01-01", "end_date": "Present"}]	\N	Meridian Works	f	\N	\N	MANUAL	\N	\N	\N
31fbab5f-f2b6-48ca-aea6-250356c3bcf0	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Akash Williams	seed.candidate.0028@example.com	+91-9200917479	{"skills": ["Redis", "Docker", "Figma", "Python", "Django", "Sales"]}	{"years": 6, "current_role": "Backend Developer"}	15.10	21.72	ACTIVE	4650c1cba58311970492d1fc87b243a68ab1fd3e66d3ebd088cd55f4ae5b4e8f	2026-04-06 16:34:52.99035	2026-04-06 16:34:52.99035	f	Remote	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Vertex AI", "title": "Backend Developer", "start_date": "2018-01-01", "end_date": "Present"}]	\N	Vertex AI	f	\N	\N	MANUAL	\N	\N	\N
799b5a99-0a3f-431d-9be6-f7000a6e32c5	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Aditya Taylor	seed.candidate.0029@example.com	+91-9794484870	{"skills": ["Figma", "TypeScript", "Django", "Node.js"]}	{"years": 1, "current_role": "Data Analyst"}	19.10	20.37	ACTIVE	8cf8982a5f2667baa607e426a7c3975a83117c81e309961037202440ad328a28	2026-04-06 16:34:52.996154	2026-04-06 16:34:52.996154	f	New York	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "IronPeak Data", "title": "Data Analyst", "start_date": "2018-01-01", "end_date": "Present"}]	\N	IronPeak Data	f	\N	\N	MANUAL	\N	\N	\N
7e2e8410-1114-4138-99ea-0d8da8a06b9d	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Anika Mehta	seed.candidate.0030@example.com	+91-9538863736	{"skills": ["Kubernetes", "Power BI", "MySQL", "Redis", "FastAPI", "Sales"]}	{"years": 8, "current_role": "QA Engineer"}	13.28	17.16	ACTIVE	d53c2b1be236653c29f4523039d2373c32e324371959ddccdb725a01c1b3f006	2026-04-06 16:34:53.00222	2026-04-06 16:34:53.00222	f	San Francisco	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "IronPeak Data", "title": "QA Engineer", "start_date": "2021-01-01", "end_date": "Present"}]	\N	IronPeak Data	f	\N	\N	MANUAL	\N	\N	\N
4038eafe-2c9d-4158-97a4-955897b45aee	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Aisha Thomas	seed.candidate.0031@example.com	+91-9981647461	{"skills": ["Marketing", "FastAPI", "Docker", "Django"]}	{"years": 10, "current_role": "Frontend Developer"}	8.95	13.70	ACTIVE	0a532d8b9cf478f66fd5295178d9b027bcc69da09bb2f6e72f29e79be4724dcf	2026-04-06 16:34:53.007643	2026-04-06 16:34:53.007643	f	San Francisco	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Vertex AI", "title": "Frontend Developer", "start_date": "2019-01-01", "end_date": "Present"}]	\N	Vertex AI	f	\N	\N	MANUAL	\N	\N	\N
a7abe327-3145-4258-8f44-e3c352591e4c	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Ethan Sharma	seed.candidate.0032@example.com	+91-9830839433	{"skills": ["TypeScript", "FastAPI", "Redis", "Java"]}	{"years": 9, "current_role": "Sales Executive"}	23.59	30.40	ACTIVE	3638c2af69fe746be3308ca3b21f5d4b64e4316ab01412d837bcebc4f627cecb	2026-04-06 16:34:53.01398	2026-04-06 16:34:53.01398	f	Kolkata	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "BlueOrbit Tech", "title": "Sales Executive", "start_date": "2021-01-01", "end_date": "Present"}]	\N	BlueOrbit Tech	f	\N	\N	MANUAL	\N	\N	\N
b70d4f91-0c7a-45b9-a2d5-c6914a121bd3	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Amelia Anderson	seed.candidate.0033@example.com	+91-9751963982	{"skills": ["Node.js", "Marketing", "Sales"]}	{"years": 3, "current_role": "Backend Developer"}	7.23	8.78	ACTIVE	927dc57a03811535bef0cbdcd713af83d21356fe2187b5d05f1f2b778bd0740d	2026-04-06 16:34:53.019056	2026-04-06 16:34:53.019056	f	Bangalore	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Quantum Stack", "title": "Backend Developer", "start_date": "2019-01-01", "end_date": "Present"}]	\N	Quantum Stack	f	\N	\N	MANUAL	\N	\N	\N
f9b4d5e2-3bb6-466a-a984-3ecfc3645a67	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Dev Taylor	seed.candidate.0034@example.com	+91-9366545899	{"skills": ["MySQL", "Node.js", "Java"]}	{"years": 7, "current_role": "Backend Developer"}	16.15	18.68	ACTIVE	e091044897914f0088d0da9b7543240c389893372eb037eff3b0d878b4ba6f6e	2026-04-06 16:34:53.025169	2026-04-06 16:34:53.025169	f	Hyderabad	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "BlueOrbit Tech", "title": "Backend Developer", "start_date": "2021-01-01", "end_date": "Present"}]	\N	BlueOrbit Tech	f	\N	\N	MANUAL	\N	\N	\N
cd0b5993-68d1-4716-abdf-137b034d20bf	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Kavya Sharma	seed.candidate.0035@example.com	+91-9554956830	{"skills": ["Docker", "Kubernetes", "Java", "Power BI", "AWS"]}	{"years": 4, "current_role": "Full Stack Developer"}	11.19	15.20	ACTIVE	528f344b3e4a2631f3def623cc48d2b55d5339f8742d38d6b731b264a45d9471	2026-04-06 16:34:53.0319	2026-04-06 16:34:53.0319	f	Chennai	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Northstar Labs", "title": "Full Stack Developer", "start_date": "2022-01-01", "end_date": "Present"}]	\N	Northstar Labs	f	\N	\N	MANUAL	\N	\N	\N
1512e140-4d7b-4dda-b80a-b64c4ceec980	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Harper Patel	seed.candidate.0036@example.com	+91-9292529806	{"skills": ["Excel", "Kubernetes", "Node.js", "Power BI", "AWS", "Marketing"]}	{"years": 3, "current_role": "Sales Executive"}	24.68	30.47	ACTIVE	88925a23eaad964eaffea259258a39588eeff047a1e228758c23b334764cbea0	2026-04-06 16:34:53.036498	2026-04-06 16:34:53.036498	f	Remote	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "IronPeak Data", "title": "Sales Executive", "start_date": "2018-01-01", "end_date": "Present"}]	\N	IronPeak Data	f	\N	\N	MANUAL	\N	\N	\N
2bfb6482-c080-499c-9074-26b73340ce91	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Aarav Singh	seed.candidate.0037@example.com	+91-9979159430	{"skills": ["Python", "Java", "Kubernetes", "MySQL", "Sales", "Marketing"]}	{"years": 1, "current_role": "Recruitment Specialist"}	20.16	25.33	ACTIVE	e1f75b67f1fadffc383769994bd15022eeb12a68f7fde91d773360ae47b56ba0	2026-04-06 16:34:53.042743	2026-04-06 16:34:53.042743	f	Chennai	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Pioneer Health", "title": "Recruitment Specialist", "start_date": "2021-01-01", "end_date": "Present"}]	\N	Pioneer Health	f	\N	\N	MANUAL	\N	\N	\N
f93129f2-d88c-4ed3-8272-0c1c8a4fe2da	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Vihaan Kapoor	seed.candidate.0038@example.com	+91-9693110748	{"skills": ["Kubernetes", "MySQL", "Node.js", "React"]}	{"years": 9, "current_role": "Marketing Associate"}	25.62	30.62	ACTIVE	ec8aa784854d7d5293a3ed9c5baba675976c20192920a3cc0a3792700af347cf	2026-04-06 16:34:53.047023	2026-04-06 16:34:53.047023	f	Remote	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Acme Systems", "title": "Marketing Associate", "start_date": "2019-01-01", "end_date": "Present"}]	\N	Acme Systems	f	\N	\N	MANUAL	\N	\N	\N
fdc65dfb-b2d7-4e9c-8ccb-49802d18a924	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Olivia Khan	seed.candidate.0039@example.com	+91-9193342412	{"skills": ["Excel", "Figma", "FastAPI", "Kubernetes"]}	{"years": 8, "current_role": "Full Stack Developer"}	27.35	32.81	ACTIVE	e738307a150d99172bcba6158b3ba77c706e8710ebcc662379c1b2cfce012cb7	2026-04-06 16:34:53.050543	2026-04-06 16:34:53.050543	f	Pune	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Meridian Works", "title": "Full Stack Developer", "start_date": "2020-01-01", "end_date": "Present"}]	\N	Meridian Works	f	\N	\N	MANUAL	\N	\N	\N
da136fc6-3009-4040-b213-e4358ba80c0c	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Noah Brown	seed.candidate.0040@example.com	+91-9850276702	{"skills": ["Azure", "Docker", "Java", "AWS"]}	{"years": 9, "current_role": "Senior Software Engineer"}	23.94	26.13	ACTIVE	146a615b786e55e007cb09ebf3c36bc1f4511f3ee78c954c9b25b969e55905e0	2026-04-06 16:34:53.055537	2026-04-06 16:34:53.055537	f	Bangalore	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Skyline Digital", "title": "Senior Software Engineer", "start_date": "2020-01-01", "end_date": "Present"}]	\N	Skyline Digital	f	\N	\N	MANUAL	\N	\N	\N
91b2c5c8-8f88-469e-afce-fe794f575038	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Liam Johnson	seed.candidate.0041@example.com	+91-9161664224	{"skills": ["Spring", "Django", "PostgreSQL"]}	{"years": 1, "current_role": "Frontend Developer"}	10.37	11.67	ACTIVE	9a724aa2372721e76a27e3df549881d339b4eb03d64b207e65293e8c7a882428	2026-04-06 16:34:53.061752	2026-04-06 16:34:53.061752	f	San Francisco	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "IronPeak Data", "title": "Frontend Developer", "start_date": "2019-01-01", "end_date": "Present"}]	\N	IronPeak Data	f	\N	\N	MANUAL	\N	\N	\N
973505f9-d7ef-42a1-b10a-c5a2d0b6ce19	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Priya Reddy	seed.candidate.0042@example.com	+91-9963653585	{"skills": ["Django", "Docker", "MySQL"]}	{"years": 7, "current_role": "QA Engineer"}	25.49	28.61	ACTIVE	d1b6a6b33cb87c4689eb13857074b2f913505bd6072c9a4c6ba8c9f9e369bfe4	2026-04-06 16:34:53.067239	2026-04-06 16:34:53.067239	f	Toronto	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "BlueOrbit Tech", "title": "QA Engineer", "start_date": "2022-01-01", "end_date": "Present"}]	\N	BlueOrbit Tech	f	\N	\N	MANUAL	\N	\N	\N
c1223420-2510-4e1d-9bb6-ea57ae8d85bf	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Aisha Smith	seed.candidate.0043@example.com	+91-9311868249	{"skills": ["Sales", "Power BI", "Excel", "Python", "Redis"]}	{"years": 6, "current_role": "Full Stack Developer"}	19.98	22.04	ACTIVE	251dc492501eaada6b375ee6ecdf5ca63b6b00d04a6cc307ef38864fc0712013	2026-04-06 16:34:53.073325	2026-04-06 16:34:53.073325	f	Pune	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "BrightPath Solutions", "title": "Full Stack Developer", "start_date": "2020-01-01", "end_date": "Present"}]	\N	BrightPath Solutions	f	\N	\N	MANUAL	\N	\N	\N
e2462388-1d41-410d-8b45-40a6a1b49f12	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Noah Taylor	seed.candidate.0044@example.com	+91-9536963107	{"skills": ["FastAPI", "Kubernetes", "Azure", "MySQL", "Java"]}	{"years": 4, "current_role": "Full Stack Developer"}	13.36	18.70	ACTIVE	015baecb719103cffb0b9891005ab7f07fdbe464fead0fb3c3fd2ca4e067b52a	2026-04-06 16:34:53.079061	2026-04-06 16:34:53.079061	f	Toronto	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Zenith Commerce", "title": "Full Stack Developer", "start_date": "2021-01-01", "end_date": "Present"}]	\N	Zenith Commerce	f	\N	\N	MANUAL	\N	\N	\N
5c1a7863-e058-4e41-a8ae-32c8b0882374	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Aarav Nair	seed.candidate.0045@example.com	+91-9203093198	{"skills": ["Node.js", "Power BI", "Kubernetes", "FastAPI"]}	{"years": 7, "current_role": "Frontend Developer"}	22.73	24.07	ACTIVE	1f1d5952bbae79cc3a7eca560013f692caaca1a49b5a55775fb01663c33be6a9	2026-04-06 16:34:53.082098	2026-04-06 16:34:53.082098	f	Ahmedabad	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Meridian Works", "title": "Frontend Developer", "start_date": "2020-01-01", "end_date": "Present"}]	\N	Meridian Works	f	\N	\N	MANUAL	\N	\N	\N
fc3f2c9f-c1d8-4a5e-8b76-1e97bd66683e	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Akash Singh	seed.candidate.0046@example.com	+91-9261074765	{"skills": ["React", "FastAPI", "Azure"]}	{"years": 11, "current_role": "Full Stack Developer"}	27.99	32.59	ACTIVE	4fb8d2648ac69fa39884b85a745ea8c614c14d45b27659caf2f679e86c417095	2026-04-06 16:34:53.085377	2026-04-06 16:34:53.085377	f	Delhi	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Quantum Stack", "title": "Full Stack Developer", "start_date": "2022-01-01", "end_date": "Present"}]	\N	Quantum Stack	f	\N	\N	MANUAL	\N	\N	\N
c37cb4eb-8f06-4e2f-9b3d-94668e2efe78	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Ethan Anderson	seed.candidate.0047@example.com	+91-9297718280	{"skills": ["TypeScript", "MySQL", "AWS", "React", "Java", "Sales"]}	{"years": 5, "current_role": "DevOps Engineer"}	7.00	12.54	ACTIVE	ea1b7b37835a47eec64eea443c21f0b039a26af02e9843d19d9b165875f53ddb	2026-04-06 16:34:53.088924	2026-04-06 16:34:53.088924	f	Delhi	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "BlueOrbit Tech", "title": "DevOps Engineer", "start_date": "2020-01-01", "end_date": "Present"}]	\N	BlueOrbit Tech	f	\N	\N	MANUAL	\N	\N	\N
0df5b96d-0597-49ac-b747-ea70edc89bdf	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Charlotte Anderson	seed.candidate.0048@example.com	+91-9619838531	{"skills": ["Sales", "Node.js", "TypeScript"]}	{"years": 1, "current_role": "QA Engineer"}	5.26	11.22	ACTIVE	b958ec4e129671f914ae56c69dc0c528402d6a70b03cda1a6b97ff4c83cad5cc	2026-04-06 16:34:53.092964	2026-04-06 16:34:53.092964	f	Hyderabad	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "BrightPath Solutions", "title": "QA Engineer", "start_date": "2021-01-01", "end_date": "Present"}]	\N	BrightPath Solutions	f	\N	\N	MANUAL	\N	\N	\N
809bb135-4d61-4105-a562-9965bd617f25	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Noah Malhotra	seed.candidate.0049@example.com	+91-9345730285	{"skills": ["Marketing", "Azure", "TypeScript", "Kubernetes"]}	{"years": 9, "current_role": "Backend Developer"}	18.22	24.93	ACTIVE	27432e5360c772fdb2f7134c44ef569c78c6235c8fc06fada33850bc9f2e9e18	2026-04-06 16:34:53.09648	2026-04-06 16:34:53.09648	f	Mumbai	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Pioneer Health", "title": "Backend Developer", "start_date": "2021-01-01", "end_date": "Present"}]	\N	Pioneer Health	f	\N	\N	MANUAL	\N	\N	\N
86106346-bcf4-4e35-b61d-0f86a706688d	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Aarav Williams	seed.candidate.0050@example.com	+91-9258461115	{"skills": ["Figma", "Redis", "TypeScript"]}	{"years": 6, "current_role": "Product Manager"}	26.05	33.14	ACTIVE	3d6d082b6199847ff162b68d7ee921ab60b44ecf4233768c4ae7e1b313ca07b0	2026-04-06 16:34:53.099495	2026-04-06 16:34:53.099495	f	San Francisco	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Nimbus Cloud", "title": "Product Manager", "start_date": "2020-01-01", "end_date": "Present"}]	\N	Nimbus Cloud	f	\N	\N	MANUAL	\N	\N	\N
aec767ed-ddee-4b4d-ba1c-89476deaf920	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Vihaan Roy	seed.candidate.0051@example.com	+91-9627057043	{"skills": ["Sales", "Marketing", "Kubernetes"]}	{"years": 1, "current_role": "Marketing Associate"}	15.32	17.29	ACTIVE	60fdc30aa07ff1c8be092f8fb46149d261a7c30e63e4d595534ed443735e6abb	2026-04-06 16:34:53.187664	2026-04-06 16:34:53.187664	f	Toronto	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Pioneer Health", "title": "Marketing Associate", "start_date": "2019-01-01", "end_date": "Present"}]	\N	Pioneer Health	f	\N	\N	MANUAL	\N	\N	\N
3cae5265-4dd9-4b83-b1c3-195cae1a26ce	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Rohan Singh	seed.candidate.0052@example.com	+91-9959641787	{"skills": ["TypeScript", "Power BI", "PostgreSQL"]}	{"years": 4, "current_role": "Backend Developer"}	19.48	24.71	ACTIVE	7c2f33c3345e3c6e21088c0459c26220de3bd51840cd999bb5e47c56c73fa359	2026-04-06 16:34:53.189184	2026-04-06 16:34:53.189184	f	Kolkata	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Vertex AI", "title": "Backend Developer", "start_date": "2019-01-01", "end_date": "Present"}]	\N	Vertex AI	f	\N	\N	MANUAL	\N	\N	\N
c52227ca-134f-48e0-ba63-0c84d679c0ff	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Liam Smith	seed.candidate.0053@example.com	+91-9652782562	{"skills": ["Figma", "React", "Redis", "Django", "Azure", "Power BI"]}	{"years": 12, "current_role": "Senior Software Engineer"}	18.14	24.19	ACTIVE	22ea03407aee9f0b521ec280dbeeddc2d3b7c547a0a95f7cf49ec4d75cb58c1b	2026-04-06 16:34:53.191749	2026-04-06 16:34:53.191749	f	Remote	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "BrightPath Solutions", "title": "Senior Software Engineer", "start_date": "2021-01-01", "end_date": "Present"}]	\N	BrightPath Solutions	f	\N	\N	MANUAL	\N	\N	\N
3254e2da-f8c2-4709-81e5-d18fa11cb8cf	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Sophia Anderson	seed.candidate.0054@example.com	+91-9561716430	{"skills": ["PostgreSQL", "FastAPI", "Power BI", "Kubernetes", "TypeScript", "Figma"]}	{"years": 6, "current_role": "Software Engineer"}	6.88	8.78	ACTIVE	9cbacc6502ad9ffa5d1b46df65ebffba7f5a71c3c3bf9faff513a6c845b1bf75	2026-04-06 16:34:53.193763	2026-04-06 16:34:53.193763	f	Toronto	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "BrightPath Solutions", "title": "Software Engineer", "start_date": "2022-01-01", "end_date": "Present"}]	\N	BrightPath Solutions	f	\N	\N	MANUAL	\N	\N	\N
2a5f630e-7bc5-48c4-89e1-ec8236488dab	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Anaya Thomas	seed.candidate.0055@example.com	+91-9634701256	{"skills": ["Django", "Python", "Spring", "Power BI"]}	{"years": 10, "current_role": "Product Manager"}	3.70	7.45	ACTIVE	990162086a068e0ffebbce0eac71a51c03575aeb7f08fd7520becdfaca404987	2026-04-06 16:34:53.196415	2026-04-06 16:34:53.196415	f	Bangalore	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Skyline Digital", "title": "Product Manager", "start_date": "2019-01-01", "end_date": "Present"}]	\N	Skyline Digital	f	\N	\N	MANUAL	\N	\N	\N
bab22a47-9b48-4157-b6cb-b244f4243333	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Zara Fernandes	seed.candidate.0056@example.com	+91-9596019513	{"skills": ["Python", "Spring", "AWS", "Kubernetes", "Power BI", "FastAPI"]}	{"years": 4, "current_role": "Marketing Associate"}	6.16	7.44	ACTIVE	d204dc61a13afeb6456d6d38d71a8f9deb8ee19efcbc98c11e9b851dda5eb3c6	2026-04-06 16:34:53.199429	2026-04-06 16:34:53.199429	f	Mumbai	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Nimbus Cloud", "title": "Marketing Associate", "start_date": "2018-01-01", "end_date": "Present"}]	\N	Nimbus Cloud	f	\N	\N	MANUAL	\N	\N	\N
fa526840-24ae-4d98-b397-a0d87b1b0680	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Aditya Joshi	seed.candidate.0057@example.com	+91-9543301452	{"skills": ["Django", "AWS", "Figma"]}	{"years": 8, "current_role": "Data Analyst"}	20.70	28.65	ACTIVE	16435316dec96244fd45491102c926161235dbdc0b921ea6032a7002baaf84f4	2026-04-06 16:34:53.201481	2026-04-06 16:34:53.201481	f	Ahmedabad	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Quantum Stack", "title": "Data Analyst", "start_date": "2020-01-01", "end_date": "Present"}]	\N	Quantum Stack	f	\N	\N	MANUAL	\N	\N	\N
10f7f912-00c4-4668-bba9-cc5a94e51706	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Zara Mehta	seed.candidate.0058@example.com	+91-9799179132	{"skills": ["Spring", "Java", "PostgreSQL", "Azure"]}	{"years": 4, "current_role": "Backend Developer"}	24.35	26.77	ACTIVE	10055664fdef9aec807d6e24ecb0d1b2af1f96483e136ffea0f01e23aa608708	2026-04-06 16:34:53.203489	2026-04-06 16:34:53.203489	f	Pune	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "IronPeak Data", "title": "Backend Developer", "start_date": "2019-01-01", "end_date": "Present"}]	\N	IronPeak Data	f	\N	\N	MANUAL	\N	\N	\N
50b2c794-a91e-40ad-be09-b4cb41cfc31b	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Harper Verma	seed.candidate.0059@example.com	+91-9353540297	{"skills": ["Azure", "React", "Docker", "MySQL"]}	{"years": 6, "current_role": "UI Designer"}	16.96	18.17	ACTIVE	aaff712d97675f0e29d7a6b77baa8d696545f6a2dde47465830b3fee6b7a4f20	2026-04-06 16:34:53.206022	2026-04-06 16:34:53.206022	f	New York	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Northstar Labs", "title": "UI Designer", "start_date": "2018-01-01", "end_date": "Present"}]	\N	Northstar Labs	f	\N	\N	MANUAL	\N	\N	\N
79fe99b0-89ff-4b10-b804-14f3d7c0ca0b	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Sophia Malhotra	seed.candidate.0060@example.com	+91-9492353344	{"skills": ["Node.js", "Docker", "TypeScript", "Java", "Excel", "Marketing"]}	{"years": 10, "current_role": "QA Engineer"}	7.89	10.22	ACTIVE	37a960f3a86f0101d99408fdc32217e5ee942c4213c085d736380d4e21bc5e7a	2026-04-06 16:34:53.207526	2026-04-06 16:34:53.207526	f	San Francisco	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Acme Systems", "title": "QA Engineer", "start_date": "2021-01-01", "end_date": "Present"}]	\N	Acme Systems	f	\N	\N	MANUAL	\N	\N	\N
de4f514c-be99-45f9-8ea7-37977b8eb26a	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Maya Roy	seed.candidate.0061@example.com	+91-9324969166	{"skills": ["Power BI", "Java", "Redis", "Docker"]}	{"years": 1, "current_role": "QA Engineer"}	18.93	21.32	ACTIVE	b3201b38c821d862083244059945bea0534630184fe7506e19c0593a9bebc372	2026-04-06 16:34:53.211045	2026-04-06 16:34:53.211045	f	New York	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Zenith Commerce", "title": "QA Engineer", "start_date": "2019-01-01", "end_date": "Present"}]	\N	Zenith Commerce	f	\N	\N	MANUAL	\N	\N	\N
e61a9c22-e2c0-4d37-94e1-7d53d4202f67	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Noah Sharma	seed.candidate.0062@example.com	+91-9911868353	{"skills": ["PostgreSQL", "Azure", "Kubernetes", "FastAPI", "Node.js"]}	{"years": 2, "current_role": "Full Stack Developer"}	24.41	27.11	ACTIVE	88543b5b52f001bd44494374f321a86dcbb83a43060253db8fde4c8413f8ff40	2026-04-06 16:34:53.213576	2026-04-06 16:34:53.213576	f	Mumbai	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Meridian Works", "title": "Full Stack Developer", "start_date": "2020-01-01", "end_date": "Present"}]	\N	Meridian Works	f	\N	\N	MANUAL	\N	\N	\N
03bc6375-bb83-4605-8898-895c64bcbe2b	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Akash Das	seed.candidate.0063@example.com	+91-9255589641	{"skills": ["Kubernetes", "Django", "Redis", "AWS"]}	{"years": 4, "current_role": "Data Analyst"}	4.92	6.41	ACTIVE	ec1c09b82cf74d8170474190a60436884d1bf952b77c5f481ef7c636514c065d	2026-04-06 16:34:53.216115	2026-04-06 16:34:53.216115	f	Chennai	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Quantum Stack", "title": "Data Analyst", "start_date": "2021-01-01", "end_date": "Present"}]	\N	Quantum Stack	f	\N	\N	MANUAL	\N	\N	\N
7205445e-918a-4f31-93e0-4f9390c96e6c	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Harper Nair	seed.candidate.0064@example.com	+91-9961968251	{"skills": ["Power BI", "Docker", "PostgreSQL", "Kubernetes", "Excel"]}	{"years": 6, "current_role": "Backend Developer"}	27.64	30.06	ACTIVE	cc31a8202bf3fc60bdac48d056c920e798e7c9ac0a49b1c64ebcdc129975acba	2026-04-06 16:34:53.21796	2026-04-06 16:34:53.21796	f	San Francisco	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Skyline Digital", "title": "Backend Developer", "start_date": "2019-01-01", "end_date": "Present"}]	\N	Skyline Digital	f	\N	\N	MANUAL	\N	\N	\N
383f8ca7-d7df-4627-8a87-48d0a42cc0bf	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Kavya Brown	seed.candidate.0065@example.com	+91-9551219714	{"skills": ["FastAPI", "Power BI", "MySQL"]}	{"years": 1, "current_role": "UI Designer"}	16.16	23.43	ACTIVE	3ed20e58fe467261623e086228f1a52135dfb96c9dd2bf20334cd0b93f6ab91f	2026-04-06 16:34:53.2235	2026-04-06 16:34:53.2235	f	Chennai	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Vertex AI", "title": "UI Designer", "start_date": "2021-01-01", "end_date": "Present"}]	\N	Vertex AI	f	\N	\N	MANUAL	\N	\N	\N
efe6fa61-7467-4cf7-8931-85082b625caa	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Kavya Brown	seed.candidate.0066@example.com	+91-9288625813	{"skills": ["PostgreSQL", "AWS", "Redis", "MySQL", "Docker"]}	{"years": 5, "current_role": "UI Designer"}	17.99	22.00	ACTIVE	aa4277f4a29b54e98e58b2139b1e7f6a30662e75d4f10731facd784381f17848	2026-04-06 16:34:53.22653	2026-04-06 16:34:53.22653	f	Toronto	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Northstar Labs", "title": "UI Designer", "start_date": "2021-01-01", "end_date": "Present"}]	\N	Northstar Labs	f	\N	\N	MANUAL	\N	\N	\N
b5e2549d-616d-4a43-837c-ec8c04a0e674	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Amelia Nair	seed.candidate.0067@example.com	+91-9292501672	{"skills": ["Excel", "Marketing", "Python", "TypeScript", "Java"]}	{"years": 8, "current_role": "Full Stack Developer"}	18.95	26.51	ACTIVE	fc700bbe7ef7e14718b1fe680c2cc355f8f11b98786be33707e90f7d8e16e0bf	2026-04-06 16:34:53.231063	2026-04-06 16:34:53.231063	f	Remote	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Vertex AI", "title": "Full Stack Developer", "start_date": "2020-01-01", "end_date": "Present"}]	\N	Vertex AI	f	\N	\N	MANUAL	\N	\N	\N
644cf246-7af8-4d19-9fd6-26b8e881878f	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Diya Brown	seed.candidate.0068@example.com	+91-9930456934	{"skills": ["Azure", "Spring", "Docker", "AWS"]}	{"years": 10, "current_role": "Sales Executive"}	14.54	20.24	ACTIVE	74f7a5e35605281951a56c18e3450bb49037c99135adf1db6f2ea08b9bbfcabe	2026-04-06 16:34:53.236895	2026-04-06 16:34:53.236895	f	Remote	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Quantum Stack", "title": "Sales Executive", "start_date": "2021-01-01", "end_date": "Present"}]	\N	Quantum Stack	f	\N	\N	MANUAL	\N	\N	\N
c44546bc-c0b6-4d98-91cb-14b4404f714d	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Charlotte Joshi	seed.candidate.0069@example.com	+91-9820105005	{"skills": ["Spring", "Kubernetes", "Sales", "TypeScript"]}	{"years": 8, "current_role": "Senior Software Engineer"}	10.17	13.21	ACTIVE	ebb0523c8245c50f751435aab889c94e6bf24152e33ae4a35815b4819d36bb42	2026-04-06 16:34:53.24397	2026-04-06 16:34:53.24397	f	San Francisco	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "IronPeak Data", "title": "Senior Software Engineer", "start_date": "2022-01-01", "end_date": "Present"}]	\N	IronPeak Data	f	\N	\N	MANUAL	\N	\N	\N
889000bf-bfea-4eb0-87ef-75343356b466	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Noah Malhotra	seed.candidate.0070@example.com	+91-9775863913	{"skills": ["Excel", "Kubernetes", "Spring", "Node.js", "Django", "Redis"]}	{"years": 3, "current_role": "Frontend Developer"}	22.87	27.63	ACTIVE	efb25fa440ce3d4f1b3aff9197460a43ae2c46388664f39f89d559dfab3a5f55	2026-04-06 16:34:53.250072	2026-04-06 16:34:53.250072	f	Pune	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "IronPeak Data", "title": "Frontend Developer", "start_date": "2022-01-01", "end_date": "Present"}]	\N	IronPeak Data	f	\N	\N	MANUAL	\N	\N	\N
334a80fb-1558-432a-a541-ab31285c6fcf	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Anaya Taylor	seed.candidate.0071@example.com	+91-9717772417	{"skills": ["Python", "AWS", "Java", "Excel"]}	{"years": 5, "current_role": "Product Manager"}	20.98	25.03	ACTIVE	7e79ef3dc134b43d69e261ae375c8ef41a8f93d52cdaab92570d28ab42ed7c1f	2026-04-06 16:34:53.256185	2026-04-06 16:34:53.256185	f	Remote	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Vertex AI", "title": "Product Manager", "start_date": "2022-01-01", "end_date": "Present"}]	\N	Vertex AI	f	\N	\N	MANUAL	\N	\N	\N
508b7c18-91d6-46e7-b673-07be6a4b97de	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Kavya Iyer	seed.candidate.0072@example.com	+91-9814265973	{"skills": ["Kubernetes", "Figma", "Redis", "Power BI", "Python", "Excel"]}	{"years": 6, "current_role": "Sales Executive"}	6.68	12.30	ACTIVE	f1f5a94cad0d2e46baf30f384fbbf376b9d47794b90c48aa41f21e5c9896a09a	2026-04-06 16:34:53.262273	2026-04-06 16:34:53.262273	f	San Francisco	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "BlueOrbit Tech", "title": "Sales Executive", "start_date": "2020-01-01", "end_date": "Present"}]	\N	BlueOrbit Tech	f	\N	\N	MANUAL	\N	\N	\N
9f04f4d4-24ab-4d0a-8c55-720dab1a29ac	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Sophia Iyer	seed.candidate.0073@example.com	+91-9884635202	{"skills": ["Java", "FastAPI", "PostgreSQL"]}	{"years": 1, "current_role": "Sales Executive"}	27.45	34.16	ACTIVE	a58bf8bcb5d4d556d0045cd799a74ac2c02babbfa9f2c721823045ed16fe38a1	2026-04-06 16:34:53.266862	2026-04-06 16:34:53.266862	f	Toronto	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "IronPeak Data", "title": "Sales Executive", "start_date": "2019-01-01", "end_date": "Present"}]	\N	IronPeak Data	f	\N	\N	MANUAL	\N	\N	\N
ad6a8e48-86c9-4c07-9b29-3f5f4e046f09	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Liam Das	seed.candidate.0074@example.com	+91-9501378224	{"skills": ["Django", "Spring", "Docker", "Azure", "Node.js"]}	{"years": 2, "current_role": "Software Engineer"}	24.55	31.33	ACTIVE	bd7e6b6e3a82c333d336b99b25f57e86b23f6c4eac5ed5b90fa54302261da6b9	2026-04-06 16:34:53.271914	2026-04-06 16:34:53.271914	f	Toronto	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Quantum Stack", "title": "Software Engineer", "start_date": "2020-01-01", "end_date": "Present"}]	\N	Quantum Stack	f	\N	\N	MANUAL	\N	\N	\N
a82add8c-35b3-4d01-8f69-377f202092d6	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Anaya Gupta	seed.candidate.0075@example.com	+91-9213833275	{"skills": ["React", "PostgreSQL", "FastAPI", "Kubernetes", "Python", "Sales"]}	{"years": 6, "current_role": "UI Designer"}	14.16	21.56	ACTIVE	39ffa4f5b1d8ca655e7c09b9ead16647fc06a7189132d25bbf9caa47d119680a	2026-04-06 16:34:53.27923	2026-04-06 16:34:53.27923	f	Remote	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Skyline Digital", "title": "UI Designer", "start_date": "2022-01-01", "end_date": "Present"}]	\N	Skyline Digital	f	\N	\N	MANUAL	\N	\N	\N
b221a7cc-749a-4edc-816b-0bfec7ce0b3b	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Aarav Iyer	seed.candidate.0076@example.com	+91-9775323778	{"skills": ["Node.js", "PostgreSQL", "Power BI", "React"]}	{"years": 3, "current_role": "DevOps Engineer"}	12.42	19.68	ACTIVE	8a54b8204ecb07ea87c2c4879aa1c860d21265dc71193a256b6b808a466f8b64	2026-04-06 16:34:53.285841	2026-04-06 16:34:53.285841	f	New York	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "IronPeak Data", "title": "DevOps Engineer", "start_date": "2020-01-01", "end_date": "Present"}]	\N	IronPeak Data	f	\N	\N	MANUAL	\N	\N	\N
73c0870b-9983-49a3-b2fb-02dbfbc06a70	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Maya Singh	seed.candidate.0077@example.com	+91-9966281746	{"skills": ["FastAPI", "Java", "Docker"]}	{"years": 6, "current_role": "Backend Developer"}	7.91	12.05	ACTIVE	2e7af3ae8c1754638ef1307c1b72281e868818040dc9c83067cb1c892774a7df	2026-04-06 16:34:53.292064	2026-04-06 16:34:53.292064	f	Bangalore	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Quantum Stack", "title": "Backend Developer", "start_date": "2021-01-01", "end_date": "Present"}]	\N	Quantum Stack	f	\N	\N	MANUAL	\N	\N	\N
b4cabc4c-1498-46e0-9b97-4360334b0c05	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Sophia Verma	seed.candidate.0078@example.com	+91-9905757297	{"skills": ["AWS", "React", "Spring", "PostgreSQL", "Marketing"]}	{"years": 3, "current_role": "Recruitment Specialist"}	8.78	10.14	ACTIVE	3cb6abc4de79aea20921a6e6a26d1f0d0832f2968742bf9885982141f635a18c	2026-04-06 16:34:53.297026	2026-04-06 16:34:53.297026	f	Toronto	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Acme Systems", "title": "Recruitment Specialist", "start_date": "2022-01-01", "end_date": "Present"}]	\N	Acme Systems	f	\N	\N	MANUAL	\N	\N	\N
3ff20f4e-1a52-4ea7-a171-14bbe27fad2a	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Diya Khan	seed.candidate.0079@example.com	+91-9660757126	{"skills": ["Docker", "PostgreSQL", "AWS", "Kubernetes"]}	{"years": 9, "current_role": "Data Analyst"}	23.44	25.17	ACTIVE	91874d4762aa3f6cb5eb95d48f9ada863005cc6ea5f8e5bdabb1b75c870c0806	2026-04-06 16:34:53.302642	2026-04-06 16:34:53.302642	f	Remote	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Meridian Works", "title": "Data Analyst", "start_date": "2020-01-01", "end_date": "Present"}]	\N	Meridian Works	f	\N	\N	MANUAL	\N	\N	\N
aea6a9a1-061b-4748-875f-0ebeb25dd907	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Aarav Williams	seed.candidate.0080@example.com	+91-9641867492	{"skills": ["TypeScript", "PostgreSQL", "Figma", "Marketing", "Django", "Docker"]}	{"years": 9, "current_role": "Sales Executive"}	16.90	23.06	ACTIVE	c1d18d4c103161b3209862f8532a26d1e089562d7c2b78e256d8fb3ae33e2721	2026-04-06 16:34:53.30924	2026-04-06 16:34:53.30924	f	Remote	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Quantum Stack", "title": "Sales Executive", "start_date": "2021-01-01", "end_date": "Present"}]	\N	Quantum Stack	f	\N	\N	MANUAL	\N	\N	\N
9117d11c-3928-43ff-957a-f2df89901208	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Harper Anderson	seed.candidate.0081@example.com	+91-9732387666	{"skills": ["Kubernetes", "React", "Python", "Spring", "Sales", "Django"]}	{"years": 11, "current_role": "UI Designer"}	23.40	26.99	ACTIVE	15d9a2d0238ed7edf3957e6f028161f91d145cfe8412f2b3ec5e1916cb3e4a21	2026-04-06 16:34:53.315081	2026-04-06 16:34:53.315081	f	Chennai	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Zenith Commerce", "title": "UI Designer", "start_date": "2019-01-01", "end_date": "Present"}]	\N	Zenith Commerce	f	\N	\N	MANUAL	\N	\N	\N
c3c24b69-20b4-4661-b197-40a4234f9e14	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Harper Iyer	seed.candidate.0082@example.com	+91-9813310482	{"skills": ["FastAPI", "Docker", "Azure", "Django"]}	{"years": 10, "current_role": "DevOps Engineer"}	24.31	31.55	ACTIVE	519bdcb1b2f02d5ec2097e81f63c354bfed17e0dd07a8f4765eb2cce27e56539	2026-04-06 16:34:53.320688	2026-04-06 16:34:53.320688	f	Delhi	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Pioneer Health", "title": "DevOps Engineer", "start_date": "2019-01-01", "end_date": "Present"}]	\N	Pioneer Health	f	\N	\N	MANUAL	\N	\N	\N
0524ffba-7fe3-471d-b603-42e0b6d12f5f	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Aisha Patel	seed.candidate.0083@example.com	+91-9326846577	{"skills": ["PostgreSQL", "Power BI", "React", "MySQL"]}	{"years": 6, "current_role": "Data Analyst"}	16.00	19.59	ACTIVE	e124e41c1999fc5c6a5829ae2979abb683197a3ed0d1090872bb82c1c79c5976	2026-04-06 16:34:53.325236	2026-04-06 16:34:53.325236	f	Mumbai	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "BlueOrbit Tech", "title": "Data Analyst", "start_date": "2020-01-01", "end_date": "Present"}]	\N	BlueOrbit Tech	f	\N	\N	MANUAL	\N	\N	\N
3e334768-86ec-48da-8857-699836fbae05	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Diya Sharma	seed.candidate.0084@example.com	+91-9314386338	{"skills": ["Java", "Node.js", "Azure", "Excel"]}	{"years": 5, "current_role": "Backend Developer"}	16.84	24.27	ACTIVE	b8582571af31f266635411f0cd4ebf763a4a8d4f901103ae28fefa3a1aa39275	2026-04-06 16:34:53.331572	2026-04-06 16:34:53.331572	f	Delhi	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Skyline Digital", "title": "Backend Developer", "start_date": "2019-01-01", "end_date": "Present"}]	\N	Skyline Digital	f	\N	\N	MANUAL	\N	\N	\N
eb638e2c-7938-47ee-abb3-95c31ac27de9	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Maya Mehta	seed.candidate.0085@example.com	+91-9881501389	{"skills": ["Python", "Redis", "Docker"]}	{"years": 2, "current_role": "Software Engineer"}	18.66	19.93	ACTIVE	fce81c9453ea3a93782989cb7446fe63f5e57ac357c0b83bb2a9abaab386a106	2026-04-06 16:34:53.337182	2026-04-06 16:34:53.337182	f	Toronto	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Zenith Commerce", "title": "Software Engineer", "start_date": "2018-01-01", "end_date": "Present"}]	\N	Zenith Commerce	f	\N	\N	MANUAL	\N	\N	\N
3342cc9c-0f9e-4044-998b-c2614a2a234a	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Ishaan Anderson	seed.candidate.0086@example.com	+91-9607261322	{"skills": ["Sales", "MySQL", "Figma", "Docker", "AWS"]}	{"years": 5, "current_role": "Full Stack Developer"}	8.72	14.14	ACTIVE	6f9ccdfe23cf2c8674c36a6923ed11b7433cffb15a8c19350193c6fc647cc39a	2026-04-06 16:34:53.341556	2026-04-06 16:34:53.341556	f	Toronto	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Meridian Works", "title": "Full Stack Developer", "start_date": "2021-01-01", "end_date": "Present"}]	\N	Meridian Works	f	\N	\N	MANUAL	\N	\N	\N
680ad5ba-936a-4f8c-8823-90f9cefbbccf	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Ethan Taylor	seed.candidate.0087@example.com	+91-9391056588	{"skills": ["Redis", "Django", "Python", "PostgreSQL", "Spring", "FastAPI"]}	{"years": 3, "current_role": "Full Stack Developer"}	16.12	23.43	ACTIVE	3f704b4de218a5744c874e7bdda650c07dd8191131936c6d6b4dec05a03c6338	2026-04-06 16:34:53.347101	2026-04-06 16:34:53.347101	f	Hyderabad	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Skyline Digital", "title": "Full Stack Developer", "start_date": "2021-01-01", "end_date": "Present"}]	\N	Skyline Digital	f	\N	\N	MANUAL	\N	\N	\N
36d0ba46-3121-442c-a7a2-4449cd768572	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Sophia Williams	seed.candidate.0088@example.com	+91-9216096308	{"skills": ["Django", "Figma", "Power BI", "Java", "Python"]}	{"years": 12, "current_role": "Recruitment Specialist"}	3.22	4.99	ACTIVE	a8dafd683f3294bf461c0bff751e72d0a5366dc295bb41dc4f9e800badc558ec	2026-04-06 16:34:53.352183	2026-04-06 16:34:53.352183	f	Chennai	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Nimbus Cloud", "title": "Recruitment Specialist", "start_date": "2020-01-01", "end_date": "Present"}]	\N	Nimbus Cloud	f	\N	\N	MANUAL	\N	\N	\N
eae0ce04-e305-417c-a13c-8ae77b549381	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Maya Nair	seed.candidate.0089@example.com	+91-9188652772	{"skills": ["React", "Sales", "Power BI", "Figma"]}	{"years": 10, "current_role": "Senior Software Engineer"}	27.92	32.58	ACTIVE	5953b7904dc64cc15011e476c2e44280df2c044421dadcb9800df0e541a9a52d	2026-04-06 16:34:53.358591	2026-04-06 16:34:53.358591	f	San Francisco	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Acme Systems", "title": "Senior Software Engineer", "start_date": "2022-01-01", "end_date": "Present"}]	\N	Acme Systems	f	\N	\N	MANUAL	\N	\N	\N
dd3ff78f-0692-4a35-8e22-b05a7e10a86a	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Ethan Thomas	seed.candidate.0090@example.com	+91-9632888646	{"skills": ["Excel", "FastAPI", "Kubernetes", "PostgreSQL"]}	{"years": 5, "current_role": "Marketing Associate"}	24.58	30.19	ACTIVE	926090586fbca932f8b66fa5ad314f1fd289db2d07706c639b8ad96b8813c0ed	2026-04-06 16:34:53.363979	2026-04-06 16:34:53.363979	f	Pune	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "IronPeak Data", "title": "Marketing Associate", "start_date": "2019-01-01", "end_date": "Present"}]	\N	IronPeak Data	f	\N	\N	MANUAL	\N	\N	\N
2a8d0e05-25d3-4888-b1dd-fdcd922068b7	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Anika Smith	seed.candidate.0091@example.com	+91-9791984742	{"skills": ["MySQL", "FastAPI", "Figma", "Azure", "Java"]}	{"years": 3, "current_role": "Data Analyst"}	3.38	6.50	ACTIVE	13690056134e2e585911390ea9f202a9d2d51bb9976fd7cb8227ef3872993911	2026-04-06 16:34:53.370166	2026-04-06 16:34:53.370166	f	Mumbai	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "BrightPath Solutions", "title": "Data Analyst", "start_date": "2020-01-01", "end_date": "Present"}]	\N	BrightPath Solutions	f	\N	\N	MANUAL	\N	\N	\N
d89a691a-b28e-478a-9454-8ec1b8bb28f7	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Ishaan Smith	seed.candidate.0092@example.com	+91-9940237906	{"skills": ["Azure", "Power BI", "Java"]}	{"years": 12, "current_role": "Full Stack Developer"}	6.76	10.40	ACTIVE	d9f832b3c5cd2989406adae290b8f39471f98b63c59aa8295a025f4487cc3266	2026-04-06 16:34:53.375043	2026-04-06 16:34:53.375043	f	New York	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Nimbus Cloud", "title": "Full Stack Developer", "start_date": "2019-01-01", "end_date": "Present"}]	\N	Nimbus Cloud	f	\N	\N	MANUAL	\N	\N	\N
7ea1d0e3-39a0-46e7-b2ca-cfae722f331d	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Anaya Singh	seed.candidate.0093@example.com	+91-9781129822	{"skills": ["React", "Azure", "AWS", "Java"]}	{"years": 9, "current_role": "Software Engineer"}	6.98	14.41	ACTIVE	09bba8f5d1792543351d4403c3b58c19b2bcda484e683fb9d261c514328235d8	2026-04-06 16:34:53.380583	2026-04-06 16:34:53.380583	f	Kolkata	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Vertex AI", "title": "Software Engineer", "start_date": "2021-01-01", "end_date": "Present"}]	\N	Vertex AI	f	\N	\N	MANUAL	\N	\N	\N
fc488b16-8bd9-4663-8cf2-12347e0dbee5	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Priya Verma	seed.candidate.0094@example.com	+91-9427861852	{"skills": ["AWS", "MySQL", "Azure", "Sales", "Figma", "Kubernetes"]}	{"years": 3, "current_role": "Software Engineer"}	26.07	31.75	ACTIVE	29c2597e7ff30649770dcb52828c816b70d0ef9d31915bf90f056391b88946a8	2026-04-06 16:34:53.38618	2026-04-06 16:34:53.38618	f	Hyderabad	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Northstar Labs", "title": "Software Engineer", "start_date": "2018-01-01", "end_date": "Present"}]	\N	Northstar Labs	f	\N	\N	MANUAL	\N	\N	\N
f67decc0-e43a-4b3a-a6fc-326a1be4fd79	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Liam Joshi	seed.candidate.0095@example.com	+91-9145085124	{"skills": ["Azure", "PostgreSQL", "Excel"]}	{"years": 12, "current_role": "Frontend Developer"}	7.32	10.15	ACTIVE	54a34f8f7f91c0a05f326f827427bfe7f84845e88caba263a474d5dd9fb7200a	2026-04-06 16:34:53.392234	2026-04-06 16:34:53.392234	f	New York	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "BlueOrbit Tech", "title": "Frontend Developer", "start_date": "2020-01-01", "end_date": "Present"}]	\N	BlueOrbit Tech	f	\N	\N	MANUAL	\N	\N	\N
34b9fb1b-7b44-412b-b6f1-90c5bcda0685	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Amelia Malhotra	seed.candidate.0096@example.com	+91-9348454988	{"skills": ["Python", "Node.js", "Excel", "Kubernetes", "Power BI"]}	{"years": 7, "current_role": "UI Designer"}	7.42	10.38	ACTIVE	641ba12f9465b51cbb255ff70237417a9b5a9adf4884c908a828b797014b6adf	2026-04-06 16:34:53.397417	2026-04-06 16:34:53.397417	f	Ahmedabad	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Vertex AI", "title": "UI Designer", "start_date": "2020-01-01", "end_date": "Present"}]	\N	Vertex AI	f	\N	\N	MANUAL	\N	\N	\N
0b7e2c4b-5cfe-487a-8c99-ba290da4865a	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Aarav Gupta	seed.candidate.0097@example.com	+91-9371525158	{"skills": ["PostgreSQL", "Redis", "React"]}	{"years": 12, "current_role": "Backend Developer"}	11.39	18.80	ACTIVE	11ffe86e641022fd9499a5ee0b4942e0dd61d077236fdf6c22a8a7cf482fe0b1	2026-04-06 16:34:53.400922	2026-04-06 16:34:53.400922	f	Hyderabad	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Nimbus Cloud", "title": "Backend Developer", "start_date": "2019-01-01", "end_date": "Present"}]	\N	Nimbus Cloud	f	\N	\N	MANUAL	\N	\N	\N
8aacaf89-bd02-4a0a-b868-c8a1c0db9cce	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Akash Sharma	seed.candidate.0098@example.com	+91-9444357597	{"skills": ["Power BI", "FastAPI", "React", "AWS", "MySQL", "Django"]}	{"years": 2, "current_role": "Recruitment Specialist"}	11.67	18.78	ACTIVE	339004f0073c89d82d240dd36d6f30e846b9aad1d6183a97f6fd662193320222	2026-04-06 16:34:53.405288	2026-04-06 16:34:53.405288	f	Chennai	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Quantum Stack", "title": "Recruitment Specialist", "start_date": "2021-01-01", "end_date": "Present"}]	\N	Quantum Stack	f	\N	\N	MANUAL	\N	\N	\N
424b779e-0b83-488d-a0e0-874d06b8650d	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Amelia Anderson	seed.candidate.0099@example.com	+91-9682608440	{"skills": ["PostgreSQL", "Docker", "Python", "Sales"]}	{"years": 7, "current_role": "Senior Software Engineer"}	8.27	10.95	ACTIVE	a1f539dcef8dc870b653221d5abd57c96efb700d51e1fac8216fb22247bfced5	2026-04-06 16:34:53.407995	2026-04-06 16:34:53.407995	f	Pune	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "IronPeak Data", "title": "Senior Software Engineer", "start_date": "2019-01-01", "end_date": "Present"}]	\N	IronPeak Data	f	\N	\N	MANUAL	\N	\N	\N
83dcf386-cf1f-4bd4-a019-4461fcdfb04b	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Aarav Patel	seed.candidate.0100@example.com	+91-9567659155	{"skills": ["Docker", "FastAPI", "Node.js", "PostgreSQL"]}	{"years": 12, "current_role": "Product Manager"}	12.16	17.02	ACTIVE	3418068f0b4b8931f681087a59f2c73f57258e70b4bf5e6bb437ac3dc7bb220f	2026-04-06 16:34:53.410514	2026-04-06 16:34:53.410514	f	Bangalore	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Nimbus Cloud", "title": "Product Manager", "start_date": "2021-01-01", "end_date": "Present"}]	\N	Nimbus Cloud	f	\N	\N	MANUAL	\N	\N	\N
ec325729-8737-4102-889a-42be2126afdd	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Aisha Roy	seed.candidate.0101@example.com	+91-9199280722	{"skills": ["Java", "TypeScript", "Azure", "Kubernetes", "FastAPI"]}	{"years": 12, "current_role": "Data Analyst"}	16.58	19.15	ACTIVE	5c12a362b869d25b7817a41dcdbe245e361d3704d15b5b24d63a63f9f300903c	2026-04-06 16:42:18.370649	2026-04-06 16:42:18.370649	f	Kolkata	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Pioneer Health", "title": "Data Analyst", "start_date": "2022-01-01", "end_date": "Present"}]	\N	Pioneer Health	f	\N	\N	MANUAL	\N	\N	\N
c975be56-bb1f-468d-a31b-131d46b5354a	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Akash Patel	seed.candidate.0102@example.com	+91-9462197049	{"skills": ["AWS", "Django", "Power BI"]}	{"years": 10, "current_role": "Marketing Associate"}	20.92	26.33	ACTIVE	761591d24270c725b4376d710757307d3a6c7398507d8af63f2f03cc2192ce69	2026-04-06 16:42:18.37523	2026-04-06 16:42:18.37523	f	Toronto	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "IronPeak Data", "title": "Marketing Associate", "start_date": "2019-01-01", "end_date": "Present"}]	\N	IronPeak Data	f	\N	\N	MANUAL	\N	\N	\N
ae1cc5c7-a71a-490a-a0ed-84cc829c94e8	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Anika Thomas	seed.candidate.0103@example.com	+91-9623395035	{"skills": ["Django", "TypeScript", "FastAPI"]}	{"years": 7, "current_role": "Marketing Associate"}	20.14	27.01	ACTIVE	e668b43575d9e974ffca072ceb86a12e730f38db5669f10bb48d2035a51c04aa	2026-04-06 16:42:18.379646	2026-04-06 16:42:18.379646	f	Chennai	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Northstar Labs", "title": "Marketing Associate", "start_date": "2018-01-01", "end_date": "Present"}]	\N	Northstar Labs	f	\N	\N	MANUAL	\N	\N	\N
987b1b5b-b0f5-4d99-8fa6-32c52ba8e37b	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Noah Das	seed.candidate.0104@example.com	+91-9168240815	{"skills": ["Redis", "Django", "Marketing", "Node.js", "PostgreSQL", "Java"]}	{"years": 7, "current_role": "Backend Developer"}	17.51	19.27	ACTIVE	f26bcf0ab21999ce32f96219354e59d8ddca8e7b01d6df034b1d30cd72118ced	2026-04-06 16:42:18.38457	2026-04-06 16:42:18.38457	f	Bangalore	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Acme Systems", "title": "Backend Developer", "start_date": "2018-01-01", "end_date": "Present"}]	\N	Acme Systems	f	\N	\N	MANUAL	\N	\N	\N
a8a9550b-e27f-4ca4-ac14-f4588b59ac13	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Kavya Brown	seed.candidate.0105@example.com	+91-9980590840	{"skills": ["TypeScript", "PostgreSQL", "MySQL", "Docker", "Excel"]}	{"years": 3, "current_role": "Recruitment Specialist"}	11.14	17.82	ACTIVE	f3db7bd41584f10380d5e56853cf1675b1b04b84233468f968decf917d5d092b	2026-04-06 16:42:18.38816	2026-04-06 16:42:18.38816	f	Hyderabad	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Pioneer Health", "title": "Recruitment Specialist", "start_date": "2019-01-01", "end_date": "Present"}]	\N	Pioneer Health	f	\N	\N	MANUAL	\N	\N	\N
e1d8295c-0abe-42c8-9b97-a07154c5407f	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Sophia Khan	seed.candidate.0106@example.com	+91-9619397217	{"skills": ["MySQL", "Marketing", "PostgreSQL", "TypeScript", "Kubernetes"]}	{"years": 3, "current_role": "Product Manager"}	8.41	9.44	ACTIVE	d298c85e4d7f5e6c00a507dead5c974352b2d84c2b926e24dd3a0d0de0281ed4	2026-04-06 16:42:18.392709	2026-04-06 16:42:18.392709	f	Toronto	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "IronPeak Data", "title": "Product Manager", "start_date": "2021-01-01", "end_date": "Present"}]	\N	IronPeak Data	f	\N	\N	MANUAL	\N	\N	\N
d299f58a-17f8-4aad-bd27-6ca9dcb81e24	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Olivia Anderson	seed.candidate.0107@example.com	+91-9199777448	{"skills": ["Figma", "Azure", "Django", "MySQL", "Sales"]}	{"years": 6, "current_role": "UI Designer"}	5.74	12.78	ACTIVE	d96e302dfc10e9cfd00a3ab204922994e5c2a4fcb7d595f949f91a58665ae102	2026-04-06 16:42:18.3966	2026-04-06 16:42:18.3966	f	Hyderabad	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Pioneer Health", "title": "UI Designer", "start_date": "2022-01-01", "end_date": "Present"}]	\N	Pioneer Health	f	\N	\N	MANUAL	\N	\N	\N
31b5603f-7627-46c8-b0dd-a23cd45d7f42	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Kavya Joshi	seed.candidate.0108@example.com	+91-9921735784	{"skills": ["Marketing", "PostgreSQL", "Java", "Docker", "MySQL", "FastAPI"]}	{"years": 5, "current_role": "Frontend Developer"}	11.67	12.92	ACTIVE	9bc2fc9cd46b7a2dfcbffc3331be6610e0c811a64a461b77143af16b2041da5b	2026-04-06 16:42:18.401192	2026-04-06 16:42:18.401192	f	Toronto	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Zenith Commerce", "title": "Frontend Developer", "start_date": "2019-01-01", "end_date": "Present"}]	\N	Zenith Commerce	f	\N	\N	MANUAL	\N	\N	\N
2eb2cc53-53ab-4c92-8288-beb0b20bdd85	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Sophia Roy	seed.candidate.0109@example.com	+91-9117016388	{"skills": ["Python", "TypeScript", "Excel"]}	{"years": 3, "current_role": "Data Analyst"}	11.18	18.58	ACTIVE	c7cc5abe4d05f1d88ab22dc9ac727c5a31ec4c13603d53a33e518763487c091d	2026-04-06 16:42:18.405356	2026-04-06 16:42:18.405356	f	Pune	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Acme Systems", "title": "Data Analyst", "start_date": "2019-01-01", "end_date": "Present"}]	\N	Acme Systems	f	\N	\N	MANUAL	\N	\N	\N
04c4b2e9-c13e-436f-a853-cc2700812905	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Ishaan Anderson	seed.candidate.0110@example.com	+91-9340409145	{"skills": ["Excel", "Marketing", "React"]}	{"years": 10, "current_role": "Marketing Associate"}	24.80	27.64	ACTIVE	937793c63400f1fc7c7880bcc3f410632cd5a62d67df9e1bf78d8d55dcf8eae5	2026-04-06 16:42:18.410832	2026-04-06 16:42:18.410832	f	Remote	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "IronPeak Data", "title": "Marketing Associate", "start_date": "2018-01-01", "end_date": "Present"}]	\N	IronPeak Data	f	\N	\N	MANUAL	\N	\N	\N
50b4b4d7-6ff4-4091-bea2-30c54c72255a	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Charlotte Anderson	seed.candidate.0111@example.com	+91-9123729485	{"skills": ["Django", "TypeScript", "FastAPI", "Power BI", "Python", "MySQL"]}	{"years": 8, "current_role": "Sales Executive"}	4.88	10.54	ACTIVE	a62e280802353e992cc03747ef214d3a4f4e18057aa087fcfe7f05758a3f8df9	2026-04-06 16:42:18.413848	2026-04-06 16:42:18.413848	f	Kolkata	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Quantum Stack", "title": "Sales Executive", "start_date": "2022-01-01", "end_date": "Present"}]	\N	Quantum Stack	f	\N	\N	MANUAL	\N	\N	\N
2525e125-0004-40d4-b334-032d323222b8	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Arjun Thomas	seed.candidate.0112@example.com	+91-9731487615	{"skills": ["React", "Marketing", "AWS", "FastAPI", "TypeScript"]}	{"years": 10, "current_role": "Data Analyst"}	18.84	22.70	ACTIVE	bc7a1e31c8b2d4f2ad34f1415621318ed173d9608c8b1411bac3a7543a08b9ea	2026-04-06 16:42:18.417962	2026-04-06 16:42:18.417962	f	Delhi	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "IronPeak Data", "title": "Data Analyst", "start_date": "2020-01-01", "end_date": "Present"}]	\N	IronPeak Data	f	\N	\N	MANUAL	\N	\N	\N
2f2b4849-be47-43cf-b075-74193b511e8f	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Priya Taylor	seed.candidate.0113@example.com	+91-9182438108	{"skills": ["React", "Python", "Sales", "MySQL", "PostgreSQL"]}	{"years": 11, "current_role": "Recruitment Specialist"}	22.43	28.89	ACTIVE	3f6163b7c5052bfdf0f8ec24e834378e6a6a30d871e56ce180818b78427ad72c	2026-04-06 16:42:18.422118	2026-04-06 16:42:18.422118	f	Delhi	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Acme Systems", "title": "Recruitment Specialist", "start_date": "2022-01-01", "end_date": "Present"}]	\N	Acme Systems	f	\N	\N	MANUAL	\N	\N	\N
97d7be4a-4f3e-4039-80da-82b39c1d2e4f	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Maya Taylor	seed.candidate.0114@example.com	+91-9119660374	{"skills": ["Spring", "Java", "FastAPI", "Python"]}	{"years": 1, "current_role": "UI Designer"}	10.41	11.83	ACTIVE	f0ac6467adc485900e2e83bb421d6d01bc093261f361a6e842731eb6941b70fa	2026-04-06 16:42:18.426963	2026-04-06 16:42:18.426963	f	Bangalore	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "IronPeak Data", "title": "UI Designer", "start_date": "2020-01-01", "end_date": "Present"}]	\N	IronPeak Data	f	\N	\N	MANUAL	\N	\N	\N
449cb01a-2e53-4412-b2af-c805a1dd8f09	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Ethan Johnson	seed.candidate.0115@example.com	+91-9147014336	{"skills": ["Figma", "Sales", "Java", "React"]}	{"years": 7, "current_role": "Data Analyst"}	16.21	21.81	ACTIVE	51e61994c87c2d3fa95ddd13e02f33fcbd04cd82709adfe13dbd3d3e0f96986d	2026-04-06 16:42:18.431026	2026-04-06 16:42:18.431026	f	Hyderabad	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Acme Systems", "title": "Data Analyst", "start_date": "2018-01-01", "end_date": "Present"}]	\N	Acme Systems	f	\N	\N	MANUAL	\N	\N	\N
a7e1bd13-4bc3-4631-8180-1a154dec9c22	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Liam Williams	seed.candidate.0116@example.com	+91-9419469282	{"skills": ["Redis", "MySQL", "Azure", "Power BI"]}	{"years": 11, "current_role": "DevOps Engineer"}	19.86	26.02	ACTIVE	5d64224a1707ff0619c1cc6043ff66901b0db050e58050d88d91fa3fe6c670e7	2026-04-06 16:42:18.436687	2026-04-06 16:42:18.436687	f	Delhi	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Pioneer Health", "title": "DevOps Engineer", "start_date": "2020-01-01", "end_date": "Present"}]	\N	Pioneer Health	f	\N	\N	MANUAL	\N	\N	\N
c82ebf84-f512-44ce-94fb-9b16457099bf	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Noah Smith	seed.candidate.0117@example.com	+91-9514919152	{"skills": ["Figma", "React", "AWS"]}	{"years": 1, "current_role": "QA Engineer"}	12.93	14.10	ACTIVE	024a9ede5befedb85c946e409d5dc62908a862a9ea2ac58060cd4d5ef3721eb8	2026-04-06 16:42:18.441572	2026-04-06 16:42:18.441572	f	Kolkata	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Northstar Labs", "title": "QA Engineer", "start_date": "2020-01-01", "end_date": "Present"}]	\N	Northstar Labs	f	\N	\N	MANUAL	\N	\N	\N
d99f00c5-4d2d-4b1d-b7ed-b11ff9b9dbb7	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Olivia Patel	seed.candidate.0118@example.com	+91-9149347464	{"skills": ["FastAPI", "Figma", "Power BI"]}	{"years": 9, "current_role": "Recruitment Specialist"}	19.20	21.95	ACTIVE	bd17721a8fb30d17ed1e5660245cecdf4e4e320e89c041f2609344d87ffcdd2b	2026-04-06 16:42:18.446075	2026-04-06 16:42:18.446075	f	Delhi	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Vertex AI", "title": "Recruitment Specialist", "start_date": "2020-01-01", "end_date": "Present"}]	\N	Vertex AI	f	\N	\N	MANUAL	\N	\N	\N
d625f1e8-4abe-47c4-9485-3cea7b281f64	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Aarav Iyer	seed.candidate.0119@example.com	+91-9196863871	{"skills": ["Azure", "Sales", "Excel"]}	{"years": 2, "current_role": "DevOps Engineer"}	23.02	27.79	ACTIVE	c803e60c809024cf46fc52f76197b9498e1e3f8bfd8afec478c939bdb4d90e0a	2026-04-06 16:42:18.451315	2026-04-06 16:42:18.451315	f	Kolkata	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Zenith Commerce", "title": "DevOps Engineer", "start_date": "2018-01-01", "end_date": "Present"}]	\N	Zenith Commerce	f	\N	\N	MANUAL	\N	\N	\N
4ef02d25-48ab-4d34-bb04-ebd578b7c5c7	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Rohan Taylor	seed.candidate.0120@example.com	+91-9380432620	{"skills": ["Power BI", "Node.js", "Excel", "Sales", "TypeScript"]}	{"years": 8, "current_role": "Recruitment Specialist"}	16.06	23.63	ACTIVE	ccd38a10b050affacbb7df1fadce0ee2f04aff1a0bed96d87dadefd00d49a7ee	2026-04-06 16:42:18.454968	2026-04-06 16:42:18.454968	f	New York	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Meridian Works", "title": "Recruitment Specialist", "start_date": "2022-01-01", "end_date": "Present"}]	\N	Meridian Works	f	\N	\N	MANUAL	\N	\N	\N
612e53ab-3721-41db-8d32-6f448cfb8d9d	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Anaya Singh	seed.candidate.0121@example.com	+91-9157214016	{"skills": ["MySQL", "FastAPI", "Power BI", "React", "Kubernetes"]}	{"years": 8, "current_role": "Recruitment Specialist"}	27.65	35.49	ACTIVE	f605919f7ed6ca3196045769c89bdb9ba794140acc325158597ab7bc2809764f	2026-04-06 16:42:18.460249	2026-04-06 16:42:18.460249	f	Pune	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Nimbus Cloud", "title": "Recruitment Specialist", "start_date": "2022-01-01", "end_date": "Present"}]	\N	Nimbus Cloud	f	\N	\N	MANUAL	\N	\N	\N
e75a0b7f-13b5-42a3-85ad-0987bf2950f3	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Olivia Gupta	seed.candidate.0122@example.com	+91-9803087912	{"skills": ["Kubernetes", "Azure", "Excel", "Spring", "Figma"]}	{"years": 3, "current_role": "Recruitment Specialist"}	12.77	18.14	ACTIVE	c91e8940d78f7d65c9cf10ce3322234cebf82b2083f83ef65b8678d339c1bf71	2026-04-06 16:42:18.464914	2026-04-06 16:42:18.464914	f	Pune	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Vertex AI", "title": "Recruitment Specialist", "start_date": "2022-01-01", "end_date": "Present"}]	\N	Vertex AI	f	\N	\N	MANUAL	\N	\N	\N
53f6521f-d62d-45cb-a734-e3bb747919c1	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Liam Joshi	seed.candidate.0123@example.com	+91-9121956878	{"skills": ["Python", "Spring", "Django", "Java", "Marketing"]}	{"years": 10, "current_role": "QA Engineer"}	11.62	14.66	ACTIVE	e7ebc774aa610ee6745f0529a58038150d0397b98922698c322c9b8347e7e26a	2026-04-06 16:42:18.469161	2026-04-06 16:42:18.469161	f	Pune	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Zenith Commerce", "title": "QA Engineer", "start_date": "2018-01-01", "end_date": "Present"}]	\N	Zenith Commerce	f	\N	\N	MANUAL	\N	\N	\N
142ae709-96ee-428e-8533-56972450fb50	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Ethan Brown	seed.candidate.0124@example.com	+91-9132479187	{"skills": ["Node.js", "Figma", "Kubernetes", "Docker", "Java"]}	{"years": 7, "current_role": "Frontend Developer"}	3.33	6.99	ACTIVE	983744f379ea07b392f093163d8f9e6b5f4b60352eee692ae1d7b6399c6ef780	2026-04-06 16:42:18.47248	2026-04-06 16:42:18.47248	f	New York	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "BlueOrbit Tech", "title": "Frontend Developer", "start_date": "2022-01-01", "end_date": "Present"}]	\N	BlueOrbit Tech	f	\N	\N	MANUAL	\N	\N	\N
be0d6119-bc4c-40f8-bafb-6b6184980697	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Ishaan Verma	seed.candidate.0125@example.com	+91-9660393515	{"skills": ["React", "Node.js", "TypeScript"]}	{"years": 3, "current_role": "UI Designer"}	20.79	28.40	ACTIVE	7a0a6c33eeac4402505a83a03e49c36a22168fa42bdfb1e2c1cd57932318435f	2026-04-06 16:42:18.476598	2026-04-06 16:42:18.476598	f	Delhi	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Vertex AI", "title": "UI Designer", "start_date": "2019-01-01", "end_date": "Present"}]	\N	Vertex AI	f	\N	\N	MANUAL	\N	\N	\N
d2f75977-e09d-46cb-84ea-e74ce338ff6b	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Amelia Malhotra	seed.candidate.0126@example.com	+91-9757045394	{"skills": ["TypeScript", "Spring", "Kubernetes"]}	{"years": 4, "current_role": "Frontend Developer"}	26.24	28.40	ACTIVE	e34ebe5fc204ef8629f266d01ce81f75d0fe60b6012613b286917caa1858935e	2026-04-06 16:42:18.480752	2026-04-06 16:42:18.480752	f	San Francisco	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Nimbus Cloud", "title": "Frontend Developer", "start_date": "2019-01-01", "end_date": "Present"}]	\N	Nimbus Cloud	f	\N	\N	MANUAL	\N	\N	\N
8135d13d-6e7d-4f8b-bcf0-49a32f8e2b17	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Amelia Smith	seed.candidate.0127@example.com	+91-9666560239	{"skills": ["PostgreSQL", "MySQL", "Azure", "Docker"]}	{"years": 5, "current_role": "Senior Software Engineer"}	27.89	28.93	ACTIVE	c75251d2c03c385931cc0fe7532fa9efd10130e571789a63b09c5be0ea3598f9	2026-04-06 16:42:18.486169	2026-04-06 16:42:18.486169	f	Chennai	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Quantum Stack", "title": "Senior Software Engineer", "start_date": "2020-01-01", "end_date": "Present"}]	\N	Quantum Stack	f	\N	\N	MANUAL	\N	\N	\N
7e7806cf-2840-4e92-952a-007f1844621a	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Vihaan Smith	seed.candidate.0128@example.com	+91-9756288475	{"skills": ["Marketing", "MySQL", "FastAPI", "Spring", "Figma"]}	{"years": 2, "current_role": "Product Manager"}	16.16	19.02	ACTIVE	c091e03942992f883daadcb31cde6145373be8fe1b7ea18c4f66ee66d36b24da	2026-04-06 16:42:18.491787	2026-04-06 16:42:18.491787	f	Toronto	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Meridian Works", "title": "Product Manager", "start_date": "2020-01-01", "end_date": "Present"}]	\N	Meridian Works	f	\N	\N	MANUAL	\N	\N	\N
fe1db4c9-d9bc-4d19-ad8d-cd14bda1a7bb	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Maya Khan	seed.candidate.0129@example.com	+91-9726080769	{"skills": ["Django", "Spring", "Python"]}	{"years": 8, "current_role": "Sales Executive"}	15.19	19.31	ACTIVE	3a1607466a20cad53d7d0af8713c590f8881c7e0e6e8101cee91902051bb78c6	2026-04-06 16:42:18.495334	2026-04-06 16:42:18.495334	f	Pune	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Nimbus Cloud", "title": "Sales Executive", "start_date": "2020-01-01", "end_date": "Present"}]	\N	Nimbus Cloud	f	\N	\N	MANUAL	\N	\N	\N
d1cb487c-f11a-4319-a979-d4049ebfa5b5	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Aarav Brown	seed.candidate.0130@example.com	+91-9602836474	{"skills": ["MySQL", "Sales", "Azure", "Excel"]}	{"years": 7, "current_role": "Backend Developer"}	14.55	22.09	ACTIVE	7284c9223f4287ffd9863f9042ba9bf9828272972d6468481bbbcd864a661bbf	2026-04-06 16:42:18.501641	2026-04-06 16:42:18.501641	f	New York	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Nimbus Cloud", "title": "Backend Developer", "start_date": "2019-01-01", "end_date": "Present"}]	\N	Nimbus Cloud	f	\N	\N	MANUAL	\N	\N	\N
a8cc84c9-22eb-406c-ab6d-d64ad31e015c	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Arjun Brown	seed.candidate.0131@example.com	+91-9805464440	{"skills": ["MySQL", "Spring", "Azure", "Node.js"]}	{"years": 4, "current_role": "UI Designer"}	19.01	22.56	ACTIVE	e52a611e40bee6a2ff45a9f15e02dccfb0febc432d21bffe9b524fa69c11a369	2026-04-06 16:42:18.506231	2026-04-06 16:42:18.506231	f	Toronto	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Nimbus Cloud", "title": "UI Designer", "start_date": "2022-01-01", "end_date": "Present"}]	\N	Nimbus Cloud	f	\N	\N	MANUAL	\N	\N	\N
761477b7-fbbe-40ee-9114-f6d9d326cbc5	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Maya Mehta	seed.candidate.0132@example.com	+91-9798735492	{"skills": ["Power BI", "React", "AWS"]}	{"years": 6, "current_role": "DevOps Engineer"}	17.95	20.49	ACTIVE	373d3fba739fc8ea890e8c8fad9b2b14d59df6dc22712cbd58ff95192c667b75	2026-04-06 16:42:18.512142	2026-04-06 16:42:18.512142	f	Ahmedabad	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Meridian Works", "title": "DevOps Engineer", "start_date": "2021-01-01", "end_date": "Present"}]	\N	Meridian Works	f	\N	\N	MANUAL	\N	\N	\N
6e371b77-c9a8-460b-bfab-130d6e49d11e	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Amelia Patel	seed.candidate.0133@example.com	+91-9611649870	{"skills": ["Power BI", "Python", "TypeScript", "Spring", "Redis", "Sales"]}	{"years": 2, "current_role": "Recruitment Specialist"}	19.71	26.63	ACTIVE	dc877ce7cb47b4557d77b310a2bb096749c18d7e244e6c37ed3309715b9da868	2026-04-06 16:42:18.518724	2026-04-06 16:42:18.518724	f	San Francisco	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "IronPeak Data", "title": "Recruitment Specialist", "start_date": "2018-01-01", "end_date": "Present"}]	\N	IronPeak Data	f	\N	\N	MANUAL	\N	\N	\N
5ed13cc7-1f43-41fe-a4ab-368c3c009fb1	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Ethan Roy	seed.candidate.0134@example.com	+91-9708792469	{"skills": ["Java", "Sales", "Azure", "Node.js", "PostgreSQL"]}	{"years": 3, "current_role": "Senior Software Engineer"}	12.35	19.17	ACTIVE	379b74fe48a5ce575b7a2ec43c86625b789e93306de010e7641d56cc31e8bd23	2026-04-06 16:42:18.525326	2026-04-06 16:42:18.525326	f	Delhi	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Zenith Commerce", "title": "Senior Software Engineer", "start_date": "2018-01-01", "end_date": "Present"}]	\N	Zenith Commerce	f	\N	\N	MANUAL	\N	\N	\N
f8332fab-16ee-4e93-9dbf-88e57a0f7b4d	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Charlotte Anderson	seed.candidate.0135@example.com	+91-9782801529	{"skills": ["Django", "Figma", "Marketing", "Docker"]}	{"years": 12, "current_role": "Backend Developer"}	5.51	6.65	ACTIVE	22d960679bf3c98cd00915b8af8cd75851857a1e6d09add40df912d45037541b	2026-04-06 16:42:18.530306	2026-04-06 16:42:18.530306	f	Ahmedabad	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Skyline Digital", "title": "Backend Developer", "start_date": "2018-01-01", "end_date": "Present"}]	\N	Skyline Digital	f	\N	\N	MANUAL	\N	\N	\N
29f784a1-3851-479b-8dd0-f3d51a1d61e1	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Aditya Kapoor	seed.candidate.0136@example.com	+91-9811648221	{"skills": ["Figma", "React", "Marketing", "Java", "Node.js", "TypeScript"]}	{"years": 2, "current_role": "Backend Developer"}	17.18	18.91	ACTIVE	f461a6b2fa67725252ae657081657bc0a0686c51de6e3fa3776079dd061528f3	2026-04-06 16:42:18.535743	2026-04-06 16:42:18.535743	f	Ahmedabad	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Nimbus Cloud", "title": "Backend Developer", "start_date": "2021-01-01", "end_date": "Present"}]	\N	Nimbus Cloud	f	\N	\N	MANUAL	\N	\N	\N
12afd138-f6ce-479c-b996-b7b672ff0c81	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Maya Fernandes	seed.candidate.0137@example.com	+91-9332303969	{"skills": ["Spring", "FastAPI", "Django", "TypeScript"]}	{"years": 2, "current_role": "Frontend Developer"}	3.11	4.78	ACTIVE	91c731b79a0984b1a941717738995f579d1e8f509b71ceb13f11f86e26a441ab	2026-04-06 16:42:18.543042	2026-04-06 16:42:18.543042	f	Remote	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "BrightPath Solutions", "title": "Frontend Developer", "start_date": "2021-01-01", "end_date": "Present"}]	\N	BrightPath Solutions	f	\N	\N	MANUAL	\N	\N	\N
17459adb-7f3d-4d75-9266-2c8be8db3208	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Ethan Roy	seed.candidate.0138@example.com	+91-9363261067	{"skills": ["Excel", "Node.js", "Python", "MySQL", "Power BI"]}	{"years": 5, "current_role": "DevOps Engineer"}	12.22	16.85	ACTIVE	c037be4796d4fa3c7efa659b789f38da704eade564331c2da067d3b93201f47e	2026-04-06 16:42:18.549238	2026-04-06 16:42:18.549238	f	Bangalore	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Quantum Stack", "title": "DevOps Engineer", "start_date": "2019-01-01", "end_date": "Present"}]	\N	Quantum Stack	f	\N	\N	MANUAL	\N	\N	\N
62c4e656-896a-41c0-88b2-755cfc0d1cf3	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Kavya Malhotra	seed.candidate.0139@example.com	+91-9956679975	{"skills": ["Sales", "Spring", "Excel", "Redis", "Python"]}	{"years": 9, "current_role": "Data Analyst"}	26.34	32.41	ACTIVE	3c062282e0f2f6448d31a718c5e75ef3ae812317321e8fdf97115f4ed3a31a82	2026-04-06 16:42:18.555179	2026-04-06 16:42:18.555179	f	Hyderabad	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "BrightPath Solutions", "title": "Data Analyst", "start_date": "2019-01-01", "end_date": "Present"}]	\N	BrightPath Solutions	f	\N	\N	MANUAL	\N	\N	\N
4b368452-967c-4eb4-a48c-380931cf86a3	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Diya Mehta	seed.candidate.0140@example.com	+91-9784594199	{"skills": ["Power BI", "Java", "Django", "React", "Node.js", "Marketing"]}	{"years": 1, "current_role": "UI Designer"}	4.72	9.36	ACTIVE	b15a23875254a2431318abc2efa60f98d83f8125ec11eccc553f8dbcd51ac7ef	2026-04-06 16:42:18.559716	2026-04-06 16:42:18.559716	f	Bangalore	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Vertex AI", "title": "UI Designer", "start_date": "2018-01-01", "end_date": "Present"}]	\N	Vertex AI	f	\N	\N	MANUAL	\N	\N	\N
e1b7abb1-9b68-4254-af8e-c9b4d868e882	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Maya Johnson	seed.candidate.0141@example.com	+91-9103352952	{"skills": ["Excel", "Marketing", "MySQL", "PostgreSQL"]}	{"years": 6, "current_role": "QA Engineer"}	5.57	8.59	ACTIVE	60e22a027c7f41bb77a64c915c593d83caa3ca82d5eb8e2c602f60c191620c72	2026-04-06 16:42:18.566413	2026-04-06 16:42:18.566413	f	New York	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Zenith Commerce", "title": "QA Engineer", "start_date": "2021-01-01", "end_date": "Present"}]	\N	Zenith Commerce	f	\N	\N	MANUAL	\N	\N	\N
a2f404e9-262d-48c0-a7b5-96a0744d1c01	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Maya Smith	seed.candidate.0142@example.com	+91-9264116672	{"skills": ["Redis", "Power BI", "PostgreSQL", "Sales", "Figma"]}	{"years": 9, "current_role": "Sales Executive"}	12.59	16.36	ACTIVE	9d15255478bf1d01a1e301fd7acfe21a4e1871dc7a45e7d6c79511a8ca1c1081	2026-04-06 16:42:18.573081	2026-04-06 16:42:18.573081	f	Toronto	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Northstar Labs", "title": "Sales Executive", "start_date": "2021-01-01", "end_date": "Present"}]	\N	Northstar Labs	f	\N	\N	MANUAL	\N	\N	\N
07bfda92-da0a-4f84-9931-18125f84be32	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Anika Nair	seed.candidate.0143@example.com	+91-9952373077	{"skills": ["Python", "Marketing", "Excel", "Docker", "AWS"]}	{"years": 9, "current_role": "Backend Developer"}	6.98	11.92	ACTIVE	a42924e0fde540344e5e4215b40cc2b505de4efef2580ab5fc9362b065901b09	2026-04-06 16:42:18.578382	2026-04-06 16:42:18.578382	f	Chennai	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Vertex AI", "title": "Backend Developer", "start_date": "2021-01-01", "end_date": "Present"}]	\N	Vertex AI	f	\N	\N	MANUAL	\N	\N	\N
d62f2aea-034e-4d6d-84a9-a808c46d39aa	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Arjun Sharma	seed.candidate.0144@example.com	+91-9312393705	{"skills": ["Spring", "Azure", "MySQL", "Kubernetes"]}	{"years": 11, "current_role": "Sales Executive"}	3.47	10.81	ACTIVE	b968079c294ede059fa14ccc70b826a147f2ed13328b6f1eb16cdae6d33591d1	2026-04-06 16:42:18.584499	2026-04-06 16:42:18.584499	f	San Francisco	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Pioneer Health", "title": "Sales Executive", "start_date": "2018-01-01", "end_date": "Present"}]	\N	Pioneer Health	f	\N	\N	MANUAL	\N	\N	\N
5f5a0815-fa58-4574-ac6e-1dd9ca4241c9	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Charlotte Brown	seed.candidate.0145@example.com	+91-9643247067	{"skills": ["Azure", "React", "Node.js", "Docker"]}	{"years": 5, "current_role": "Marketing Associate"}	25.81	30.50	ACTIVE	b3318d059bc9b6ffd2ae3f459d3bf6060918c8244a9a035c5c4dc6b34d322de6	2026-04-06 16:42:18.589521	2026-04-06 16:42:18.589521	f	San Francisco	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Quantum Stack", "title": "Marketing Associate", "start_date": "2020-01-01", "end_date": "Present"}]	\N	Quantum Stack	f	\N	\N	MANUAL	\N	\N	\N
11aeaa5c-a95e-44cc-9a22-242f27fcc46d	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Vihaan Nair	seed.candidate.0146@example.com	+91-9366235824	{"skills": ["Python", "Sales", "TypeScript", "Kubernetes"]}	{"years": 2, "current_role": "Recruitment Specialist"}	15.21	18.20	ACTIVE	1f0c94d83f3241e22d164ce316767671f4d71798e1dc7454e6669cd3411dd0b2	2026-04-06 16:42:18.595915	2026-04-06 16:42:18.595915	f	Delhi	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Skyline Digital", "title": "Recruitment Specialist", "start_date": "2020-01-01", "end_date": "Present"}]	\N	Skyline Digital	f	\N	\N	MANUAL	\N	\N	\N
0965faa7-e67e-4529-bad9-e813045b3f14	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Olivia Singh	seed.candidate.0147@example.com	+91-9614826155	{"skills": ["Python", "Azure", "Java"]}	{"years": 12, "current_role": "DevOps Engineer"}	5.42	7.51	ACTIVE	59276ba96ff7ae7d14f8dd2643d5283f04cfac1ac7d1c0cfeeca0819096b97f0	2026-04-06 16:42:18.601222	2026-04-06 16:42:18.601222	f	Mumbai	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Zenith Commerce", "title": "DevOps Engineer", "start_date": "2022-01-01", "end_date": "Present"}]	\N	Zenith Commerce	f	\N	\N	MANUAL	\N	\N	\N
65656e45-405d-456a-98a3-7198ec2496c3	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Aarav Williams	seed.candidate.0148@example.com	+91-9535507604	{"skills": ["TypeScript", "Sales", "AWS"]}	{"years": 1, "current_role": "UI Designer"}	21.25	25.49	ACTIVE	84794ed25b64281b1e3b2ee7d003e967a085aff6ec696854831b5bd6d67271a3	2026-04-06 16:42:18.607373	2026-04-06 16:42:18.607373	f	Mumbai	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Nimbus Cloud", "title": "UI Designer", "start_date": "2021-01-01", "end_date": "Present"}]	\N	Nimbus Cloud	f	\N	\N	MANUAL	\N	\N	\N
3f7610c6-9ab3-4d23-8e90-93ff5b22743c	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Aisha Johnson	seed.candidate.0149@example.com	+91-9778290344	{"skills": ["Docker", "AWS", "Sales", "Kubernetes", "MySQL", "Django"]}	{"years": 11, "current_role": "QA Engineer"}	22.77	27.33	ACTIVE	898e53c8e9230830d4460b7b3c407bb196f2cf32199c926d4298bf32802961a7	2026-04-06 16:42:18.614925	2026-04-06 16:42:18.614925	f	New York	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Skyline Digital", "title": "QA Engineer", "start_date": "2022-01-01", "end_date": "Present"}]	\N	Skyline Digital	f	\N	\N	MANUAL	\N	\N	\N
a9d8ffe6-caf9-45dd-9e26-303edf0e321b	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Diya Verma	seed.candidate.0150@example.com	+91-9401398140	{"skills": ["MySQL", "Power BI", "Marketing", "PostgreSQL", "Docker", "Kubernetes"]}	{"years": 7, "current_role": "Full Stack Developer"}	22.20	25.09	ACTIVE	062bfe60a42cef93ceda444981872a6fa714dfe4cd8f6b0bb2fe23357a5706b2	2026-04-06 16:42:18.622087	2026-04-06 16:42:18.622087	f	San Francisco	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Zenith Commerce", "title": "Full Stack Developer", "start_date": "2022-01-01", "end_date": "Present"}]	\N	Zenith Commerce	f	\N	\N	MANUAL	\N	\N	\N
e5d915dd-e063-413e-a1a9-b5c040cff510	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Ethan Roy	seed.candidate.0151@example.com	+91-9434833238	{"skills": ["PostgreSQL", "Node.js", "MySQL", "Sales", "TypeScript", "Docker"]}	{"years": 3, "current_role": "UI Designer"}	9.42	10.76	ACTIVE	034fba985449ac843171ffd8f1948b8284d1fa416ea80c375ab3ec08e3e542ec	2026-04-06 16:42:18.755339	2026-04-06 16:42:18.755339	f	San Francisco	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "BlueOrbit Tech", "title": "UI Designer", "start_date": "2021-01-01", "end_date": "Present"}]	\N	BlueOrbit Tech	f	\N	\N	MANUAL	\N	\N	\N
57a44073-f4a4-4ebb-b8ff-5cdc40274605	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Akash Williams	seed.candidate.0152@example.com	+91-9355167173	{"skills": ["PostgreSQL", "Java", "Power BI"]}	{"years": 9, "current_role": "Product Manager"}	17.64	23.86	ACTIVE	61637e5bec5bb25027b086df6d5ce200f32612489c731dfa3945762a62e86ced	2026-04-06 16:42:18.760563	2026-04-06 16:42:18.760563	f	San Francisco	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Vertex AI", "title": "Product Manager", "start_date": "2022-01-01", "end_date": "Present"}]	\N	Vertex AI	f	\N	\N	MANUAL	\N	\N	\N
87c8b671-b4cd-40b1-b9e0-318c5ab0dc9e	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Noah Iyer	seed.candidate.0153@example.com	+91-9438442263	{"skills": ["Excel", "Spring", "Java", "Node.js"]}	{"years": 5, "current_role": "Sales Executive"}	20.97	23.21	ACTIVE	f7f85b54b664074cecaedd4b5339991f84a852adb61fd0442eac586573ffad1f	2026-04-06 16:42:18.765313	2026-04-06 16:42:18.765313	f	Hyderabad	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "BrightPath Solutions", "title": "Sales Executive", "start_date": "2021-01-01", "end_date": "Present"}]	\N	BrightPath Solutions	f	\N	\N	MANUAL	\N	\N	\N
98fb175e-02cf-4417-a070-1f49f9c2b43a	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Maya Mehta	seed.candidate.0154@example.com	+91-9732892761	{"skills": ["Sales", "FastAPI", "Figma", "React"]}	{"years": 3, "current_role": "Software Engineer"}	22.01	26.51	ACTIVE	ee12d659d5c6f44238e14ebb605925985dde7e76fbb30e9f5e7c31a071808742	2026-04-06 16:42:18.770417	2026-04-06 16:42:18.770417	f	Pune	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Northstar Labs", "title": "Software Engineer", "start_date": "2020-01-01", "end_date": "Present"}]	\N	Northstar Labs	f	\N	\N	MANUAL	\N	\N	\N
29c617c6-760d-4c27-9ffd-b3072b23d08e	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Harper Das	seed.candidate.0155@example.com	+91-9694591887	{"skills": ["MySQL", "Kubernetes", "Excel", "Python", "Power BI"]}	{"years": 9, "current_role": "Sales Executive"}	23.06	29.37	ACTIVE	56b50128cd6984e8fa5f326cc998ecfd346c443f6f6d62fc127982a7ca03acee	2026-04-06 16:42:18.775847	2026-04-06 16:42:18.775847	f	Delhi	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Acme Systems", "title": "Sales Executive", "start_date": "2018-01-01", "end_date": "Present"}]	\N	Acme Systems	f	\N	\N	MANUAL	\N	\N	\N
89c2bae3-68c9-44d9-821d-4ea0085566c9	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Anika Nair	seed.candidate.0156@example.com	+91-9853476563	{"skills": ["Docker", "PostgreSQL", "FastAPI", "Power BI"]}	{"years": 10, "current_role": "DevOps Engineer"}	18.39	20.85	ACTIVE	beabf46c5081ef80505fcb790072df86c3d09434df3481100968f4bdd7ce230a	2026-04-06 16:42:18.780895	2026-04-06 16:42:18.780895	f	Bangalore	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "BlueOrbit Tech", "title": "DevOps Engineer", "start_date": "2022-01-01", "end_date": "Present"}]	\N	BlueOrbit Tech	f	\N	\N	MANUAL	\N	\N	\N
cbb1e3b4-4963-403f-8c94-694cba99cd3f	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Aditya Malhotra	seed.candidate.0157@example.com	+91-9977092001	{"skills": ["Docker", "AWS", "Power BI", "Python", "Kubernetes"]}	{"years": 9, "current_role": "Backend Developer"}	14.78	15.83	ACTIVE	b383ef3c172bb4fed6c7129ed48d69ba7d7c41a6b9adf843de7d667fc53e5bf9	2026-04-06 16:42:18.783508	2026-04-06 16:42:18.783508	f	Chennai	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Acme Systems", "title": "Backend Developer", "start_date": "2018-01-01", "end_date": "Present"}]	\N	Acme Systems	f	\N	\N	MANUAL	\N	\N	\N
a0d81e9a-fdeb-4fb0-999c-4df5745fc226	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Noah Gupta	seed.candidate.0158@example.com	+91-9941862769	{"skills": ["Kubernetes", "Figma", "Marketing", "Spring"]}	{"years": 3, "current_role": "DevOps Engineer"}	21.85	26.77	ACTIVE	bac0cb3dd9e7346a9d07d68a68d1d451923863fafad3e64e91b19e0945554f15	2026-04-06 16:42:18.789616	2026-04-06 16:42:18.789616	f	Remote	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Vertex AI", "title": "DevOps Engineer", "start_date": "2019-01-01", "end_date": "Present"}]	\N	Vertex AI	f	\N	\N	MANUAL	\N	\N	\N
77fa88bf-781b-46c6-98aa-e3d766f270cb	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Olivia Brown	seed.candidate.0159@example.com	+91-9646414846	{"skills": ["Docker", "TypeScript", "Sales", "Node.js", "PostgreSQL"]}	{"years": 4, "current_role": "Full Stack Developer"}	18.65	23.20	ACTIVE	2c96c6e085949738e3c7cfc1d0fcbc3266ea07c5bbd8b18b858849c30329a8d8	2026-04-06 16:42:18.793677	2026-04-06 16:42:18.793677	f	San Francisco	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Vertex AI", "title": "Full Stack Developer", "start_date": "2021-01-01", "end_date": "Present"}]	\N	Vertex AI	f	\N	\N	MANUAL	\N	\N	\N
bd189255-920c-4487-a092-c16538d9e46f	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Aarav Gupta	seed.candidate.0160@example.com	+91-9700596485	{"skills": ["Python", "Power BI", "Spring", "Java", "PostgreSQL", "Marketing"]}	{"years": 11, "current_role": "Frontend Developer"}	20.49	23.08	ACTIVE	853e86ae5ff4834adfbca0a2363c0f59a87e2021f8cb7127005308ada44fff5e	2026-04-06 16:42:18.797206	2026-04-06 16:42:18.797206	f	Mumbai	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Meridian Works", "title": "Frontend Developer", "start_date": "2020-01-01", "end_date": "Present"}]	\N	Meridian Works	f	\N	\N	MANUAL	\N	\N	\N
d1c8852f-6ece-4e8f-8451-ea2522fed18e	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Maya Patel	seed.candidate.0161@example.com	+91-9427858857	{"skills": ["Figma", "Java", "Spring", "Sales", "Azure", "Kubernetes"]}	{"years": 4, "current_role": "Senior Software Engineer"}	27.15	33.83	ACTIVE	9d53120e6e41c318e62deec39fa2420ba3cef81d65bdc93c09170f5126e5defb	2026-04-06 16:42:18.801436	2026-04-06 16:42:18.801436	f	Chennai	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Vertex AI", "title": "Senior Software Engineer", "start_date": "2020-01-01", "end_date": "Present"}]	\N	Vertex AI	f	\N	\N	MANUAL	\N	\N	\N
6d6510bd-d255-405b-9066-695c67a3a7e5	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Rohan Anderson	seed.candidate.0162@example.com	+91-9181003766	{"skills": ["Spring", "Excel", "Django", "Kubernetes"]}	{"years": 9, "current_role": "Sales Executive"}	20.15	27.88	ACTIVE	343edd16f96733d0d915cf2f6290aa1875e0bc9044b7e360c7a96d9c0d16a9d9	2026-04-06 16:42:18.806355	2026-04-06 16:42:18.806355	f	Pune	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Pioneer Health", "title": "Sales Executive", "start_date": "2018-01-01", "end_date": "Present"}]	\N	Pioneer Health	f	\N	\N	MANUAL	\N	\N	\N
95120d84-2866-4c2d-9da5-554e6346723a	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Anaya Gupta	seed.candidate.0163@example.com	+91-9177319668	{"skills": ["Spring", "Node.js", "Excel", "Power BI", "Python", "FastAPI"]}	{"years": 9, "current_role": "DevOps Engineer"}	4.68	6.70	ACTIVE	12f952a087c9c2709f45e475270047053f2fe43ace77088185934389345b2faa	2026-04-06 16:42:18.810896	2026-04-06 16:42:18.810896	f	New York	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Skyline Digital", "title": "DevOps Engineer", "start_date": "2022-01-01", "end_date": "Present"}]	\N	Skyline Digital	f	\N	\N	MANUAL	\N	\N	\N
f1dca444-474a-4997-ab34-d7f930e30aee	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Aditya Fernandes	seed.candidate.0164@example.com	+91-9593693377	{"skills": ["Redis", "FastAPI", "Figma", "Spring"]}	{"years": 5, "current_role": "Senior Software Engineer"}	23.60	30.19	ACTIVE	0f2deb13bf0ca94a39667e3449ceeaf2cbe46b2ebf7b9c322f9b893231154084	2026-04-06 16:42:18.813933	2026-04-06 16:42:18.813933	f	Delhi	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Acme Systems", "title": "Senior Software Engineer", "start_date": "2020-01-01", "end_date": "Present"}]	\N	Acme Systems	f	\N	\N	MANUAL	\N	\N	\N
d9ec3330-90cc-4b33-9f75-6b0987f018e6	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Anaya Nair	seed.candidate.0165@example.com	+91-9657017483	{"skills": ["TypeScript", "Sales", "Marketing", "Spring", "Redis"]}	{"years": 11, "current_role": "Software Engineer"}	8.59	10.91	ACTIVE	1baa67ff60f4b8884ff259a3b0a79eb7ffaae6de5b226b72c78170ddd6386938	2026-04-06 16:42:18.816507	2026-04-06 16:42:18.816507	f	Chennai	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "BlueOrbit Tech", "title": "Software Engineer", "start_date": "2019-01-01", "end_date": "Present"}]	\N	BlueOrbit Tech	f	\N	\N	MANUAL	\N	\N	\N
695f8be5-f0ee-4d80-9776-3acbc05fa848	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Aisha Malhotra	seed.candidate.0166@example.com	+91-9963409737	{"skills": ["Python", "Redis", "AWS", "React", "Excel"]}	{"years": 4, "current_role": "Recruitment Specialist"}	12.70	20.03	ACTIVE	35c3d5dbc9b343fae2ab293d70386146424470b647eade2999ee241e506f80f8	2026-04-06 16:42:18.821422	2026-04-06 16:42:18.821422	f	Toronto	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Acme Systems", "title": "Recruitment Specialist", "start_date": "2018-01-01", "end_date": "Present"}]	\N	Acme Systems	f	\N	\N	MANUAL	\N	\N	\N
efe456b2-f50a-49af-bbd8-bc94c5871cce	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Olivia Patel	seed.candidate.0167@example.com	+91-9510556059	{"skills": ["Excel", "Figma", "Java"]}	{"years": 4, "current_role": "Frontend Developer"}	14.74	22.65	ACTIVE	86bb46a1f775b9b33dc38d2d8aabe376307a370a28c6a75dd056bb31e116126d	2026-04-06 16:42:18.82595	2026-04-06 16:42:18.82595	f	Chennai	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Vertex AI", "title": "Frontend Developer", "start_date": "2022-01-01", "end_date": "Present"}]	\N	Vertex AI	f	\N	\N	MANUAL	\N	\N	\N
e87365df-580b-47bf-86f3-5f714f6a9535	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Maya Joshi	seed.candidate.0168@example.com	+91-9348362177	{"skills": ["Azure", "FastAPI", "Java", "Marketing"]}	{"years": 7, "current_role": "Senior Software Engineer"}	27.27	31.39	ACTIVE	906490f9e31c859e2c139fb093162823de7cb4f9378704e66cf57cf87d3350cd	2026-04-06 16:42:18.82975	2026-04-06 16:42:18.82975	f	Bangalore	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Acme Systems", "title": "Senior Software Engineer", "start_date": "2020-01-01", "end_date": "Present"}]	\N	Acme Systems	f	\N	\N	MANUAL	\N	\N	\N
c3d66567-5db8-4ace-878b-857f158f4967	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Sophia Mehta	seed.candidate.0169@example.com	+91-9233107400	{"skills": ["Django", "TypeScript", "Azure", "Node.js", "Sales"]}	{"years": 12, "current_role": "Frontend Developer"}	10.54	11.68	ACTIVE	b521cdf37e6b85697615c466b5f341d9d5eb0c4278107a9f652d9b3c065be7d5	2026-04-06 16:42:18.832275	2026-04-06 16:42:18.832275	f	Ahmedabad	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Nimbus Cloud", "title": "Frontend Developer", "start_date": "2019-01-01", "end_date": "Present"}]	\N	Nimbus Cloud	f	\N	\N	MANUAL	\N	\N	\N
a3c31937-901c-4740-a45a-def914c026fc	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Akash Iyer	seed.candidate.0170@example.com	+91-9757581108	{"skills": ["FastAPI", "Sales", "Spring", "TypeScript", "React"]}	{"years": 4, "current_role": "Software Engineer"}	10.42	11.73	ACTIVE	e6058f491d37a0650af4599a626c7aac442eadec8cd17df9861c310ec77553e8	2026-04-06 16:42:18.837927	2026-04-06 16:42:18.837927	f	Kolkata	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Zenith Commerce", "title": "Software Engineer", "start_date": "2018-01-01", "end_date": "Present"}]	\N	Zenith Commerce	f	\N	\N	MANUAL	\N	\N	\N
b818bbb5-bf17-4fda-a0a3-cb430ce9cd8b	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Priya Mehta	seed.candidate.0171@example.com	+91-9156037964	{"skills": ["Redis", "Kubernetes", "FastAPI", "TypeScript", "Docker", "Sales"]}	{"years": 8, "current_role": "DevOps Engineer"}	13.77	19.84	ACTIVE	0d5adf759fe9af6954087be79122684221bb059fed4cba496f2ff39f4863a7e7	2026-04-06 16:42:18.841486	2026-04-06 16:42:18.841486	f	Kolkata	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Pioneer Health", "title": "DevOps Engineer", "start_date": "2021-01-01", "end_date": "Present"}]	\N	Pioneer Health	f	\N	\N	MANUAL	\N	\N	\N
f9872751-b2bd-4197-8d7b-dbaca1c77ccc	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Sophia Johnson	seed.candidate.0172@example.com	+91-9715703607	{"skills": ["PostgreSQL", "AWS", "Kubernetes", "TypeScript"]}	{"years": 10, "current_role": "Frontend Developer"}	24.31	29.84	ACTIVE	5f3a8b0b57ad0e0d056a0b7eb5bd4cefafe24be99c208a6c2ee64081f7014d4f	2026-04-06 16:42:18.845064	2026-04-06 16:42:18.845064	f	Delhi	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Acme Systems", "title": "Frontend Developer", "start_date": "2019-01-01", "end_date": "Present"}]	\N	Acme Systems	f	\N	\N	MANUAL	\N	\N	\N
acc3bd0e-f57c-40dc-a9f4-56fdf440d7e5	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Akash Kapoor	seed.candidate.0173@example.com	+91-9434458520	{"skills": ["Sales", "Node.js", "Spring", "Kubernetes", "React", "Python"]}	{"years": 4, "current_role": "Data Analyst"}	20.46	28.37	ACTIVE	f771ac041758e53f2b938530bea7190004862e716b1263007cfb44e501697cc6	2026-04-06 16:42:18.849106	2026-04-06 16:42:18.849106	f	New York	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Pioneer Health", "title": "Data Analyst", "start_date": "2019-01-01", "end_date": "Present"}]	\N	Pioneer Health	f	\N	\N	MANUAL	\N	\N	\N
1661b6c4-d582-4363-a93a-6a31ff663f0f	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Aisha Verma	seed.candidate.0174@example.com	+91-9807998415	{"skills": ["FastAPI", "MySQL", "Excel", "PostgreSQL", "React"]}	{"years": 8, "current_role": "UI Designer"}	14.54	19.47	ACTIVE	0bc91dd6013e9ed73e92bf0ea5cae809543591b321b213e9c6434389cffe1f94	2026-04-06 16:42:18.853348	2026-04-06 16:42:18.853348	f	Hyderabad	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Meridian Works", "title": "UI Designer", "start_date": "2020-01-01", "end_date": "Present"}]	\N	Meridian Works	f	\N	\N	MANUAL	\N	\N	\N
f0931a58-256f-46b8-a1f6-3a07bd2d6cdc	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Aisha Das	seed.candidate.0175@example.com	+91-9371691992	{"skills": ["Marketing", "MySQL", "AWS", "PostgreSQL", "React", "FastAPI"]}	{"years": 8, "current_role": "Product Manager"}	4.42	7.93	ACTIVE	7a21b5e8916a95c15b8205ae51beec7b5fcec942d32ef8109f32feccf9b1b381	2026-04-06 16:42:18.857452	2026-04-06 16:42:18.857452	f	Kolkata	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "BlueOrbit Tech", "title": "Product Manager", "start_date": "2022-01-01", "end_date": "Present"}]	\N	BlueOrbit Tech	f	\N	\N	MANUAL	\N	\N	\N
5fc14de4-1fba-4b11-9835-6b7d2801ecee	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Sophia Smith	seed.candidate.0176@example.com	+91-9112199395	{"skills": ["Redis", "Marketing", "Excel"]}	{"years": 10, "current_role": "Recruitment Specialist"}	27.03	29.27	ACTIVE	d2bb9820b2276bbef20ffd1f87647624910ba02b8ef8e742c4f16ea8987302cd	2026-04-06 16:42:18.862049	2026-04-06 16:42:18.862049	f	Pune	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "IronPeak Data", "title": "Recruitment Specialist", "start_date": "2018-01-01", "end_date": "Present"}]	\N	IronPeak Data	f	\N	\N	MANUAL	\N	\N	\N
8db9ddd5-5e0c-4593-94b8-7d8ce88cc5f3	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Kavya Fernandes	seed.candidate.0177@example.com	+91-9820166907	{"skills": ["React", "Sales", "Node.js", "MySQL", "Kubernetes", "Excel"]}	{"years": 7, "current_role": "Marketing Associate"}	26.07	32.70	ACTIVE	b96becc81f17b0708885f3b89a97fad17297cc18f04cb419123de4d8a7610633	2026-04-06 16:42:18.865023	2026-04-06 16:42:18.865023	f	Hyderabad	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Meridian Works", "title": "Marketing Associate", "start_date": "2019-01-01", "end_date": "Present"}]	\N	Meridian Works	f	\N	\N	MANUAL	\N	\N	\N
42caad4e-bf5f-4688-8bd2-b2d279793625	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Ethan Patel	seed.candidate.0178@example.com	+91-9848085607	{"skills": ["Excel", "PostgreSQL", "Figma", "Azure", "Python"]}	{"years": 11, "current_role": "Data Analyst"}	23.51	29.84	ACTIVE	8438a7f63b02fb01ffa9e63232568be410ef03ffa6f9585cf923ebd282643379	2026-04-06 16:42:18.868801	2026-04-06 16:42:18.868801	f	Remote	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Nimbus Cloud", "title": "Data Analyst", "start_date": "2020-01-01", "end_date": "Present"}]	\N	Nimbus Cloud	f	\N	\N	MANUAL	\N	\N	\N
49c8e601-8c7b-4372-93f3-7cc36a4ffb9e	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Dev Johnson	seed.candidate.0179@example.com	+91-9536491877	{"skills": ["PostgreSQL", "Sales", "MySQL"]}	{"years": 6, "current_role": "Marketing Associate"}	6.06	8.83	ACTIVE	4aa1ccb5de5d2dcaa45344c99985da2e652c7e1993394e66275f9b6632af74ed	2026-04-06 16:42:18.873116	2026-04-06 16:42:18.873116	f	Pune	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Meridian Works", "title": "Marketing Associate", "start_date": "2018-01-01", "end_date": "Present"}]	\N	Meridian Works	f	\N	\N	MANUAL	\N	\N	\N
580248c0-f058-4fd7-a6af-b28c116237c5	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Vihaan Brown	seed.candidate.0180@example.com	+91-9295578880	{"skills": ["Node.js", "Java", "Redis", "AWS"]}	{"years": 7, "current_role": "Frontend Developer"}	8.68	12.39	ACTIVE	3c28bf92dbccfcb53d462e31e06e1a6ffb723cdb79803d0e5dd711ae1f0f138f	2026-04-06 16:42:18.87671	2026-04-06 16:42:18.87671	f	Bangalore	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Quantum Stack", "title": "Frontend Developer", "start_date": "2020-01-01", "end_date": "Present"}]	\N	Quantum Stack	f	\N	\N	MANUAL	\N	\N	\N
d7dc06c9-3003-45a7-8995-8fd3f3973d77	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Maya Taylor	seed.candidate.0181@example.com	+91-9796600573	{"skills": ["Sales", "React", "Node.js", "MySQL"]}	{"years": 5, "current_role": "UI Designer"}	11.63	16.61	ACTIVE	080cc98b437e895f82c3c6c62aa3a593268c2698c276bb0ddc8fb42eef084a09	2026-04-06 16:42:18.879277	2026-04-06 16:42:18.879277	f	San Francisco	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Skyline Digital", "title": "UI Designer", "start_date": "2022-01-01", "end_date": "Present"}]	\N	Skyline Digital	f	\N	\N	MANUAL	\N	\N	\N
fe7f34d8-591d-4638-a217-12d53998eccc	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Zara Singh	seed.candidate.0182@example.com	+91-9401125331	{"skills": ["Java", "Power BI", "Django", "Azure", "Figma"]}	{"years": 1, "current_role": "DevOps Engineer"}	6.57	9.15	ACTIVE	96f881b7876d3193241e494756201202e787b98f84476d0350e62a1bfbe7ef96	2026-04-06 16:42:18.882525	2026-04-06 16:42:18.882525	f	Ahmedabad	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Vertex AI", "title": "DevOps Engineer", "start_date": "2021-01-01", "end_date": "Present"}]	\N	Vertex AI	f	\N	\N	MANUAL	\N	\N	\N
38fc2a1f-3a59-4542-8bf2-0b239949b3f2	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Amelia Sharma	seed.candidate.0183@example.com	+91-9742477434	{"skills": ["MySQL", "Redis", "Azure"]}	{"years": 6, "current_role": "Senior Software Engineer"}	13.36	19.04	ACTIVE	ff6f4609353abff0afcee5b6e206c1201164eed40cb9d39c3f3654671473ea5d	2026-04-06 16:42:18.887445	2026-04-06 16:42:18.887445	f	Ahmedabad	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Northstar Labs", "title": "Senior Software Engineer", "start_date": "2021-01-01", "end_date": "Present"}]	\N	Northstar Labs	f	\N	\N	MANUAL	\N	\N	\N
db78cc59-08b6-4d88-8a86-ad24ec67c7e7	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Arjun Singh	seed.candidate.0184@example.com	+91-9475485919	{"skills": ["PostgreSQL", "TypeScript", "Docker", "Kubernetes", "Redis", "MySQL"]}	{"years": 3, "current_role": "Product Manager"}	19.74	25.93	ACTIVE	c897cd537931d1205e6891a530539d3d2b2cbd141d9c15fc966df7c42c14653a	2026-04-06 16:42:18.891594	2026-04-06 16:42:18.891594	f	Chennai	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Acme Systems", "title": "Product Manager", "start_date": "2018-01-01", "end_date": "Present"}]	\N	Acme Systems	f	\N	\N	MANUAL	\N	\N	\N
a4954d2b-5bda-4ac3-8e6c-063a16ae41fe	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Vihaan Singh	seed.candidate.0185@example.com	+91-9700718585	{"skills": ["PostgreSQL", "Java", "Node.js", "Azure"]}	{"years": 12, "current_role": "UI Designer"}	19.27	23.79	ACTIVE	056dcf6f664f1aa9caa152bed211d17b91f580bba84941e140b2e405b63056fd	2026-04-06 16:42:18.895249	2026-04-06 16:42:18.895249	f	Mumbai	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Zenith Commerce", "title": "UI Designer", "start_date": "2018-01-01", "end_date": "Present"}]	\N	Zenith Commerce	f	\N	\N	MANUAL	\N	\N	\N
1b7c5074-11b4-415e-a79c-b423da8d6b2c	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Maya Thomas	seed.candidate.0186@example.com	+91-9359403090	{"skills": ["PostgreSQL", "React", "Java"]}	{"years": 2, "current_role": "Software Engineer"}	5.25	11.18	ACTIVE	90c4cc48caec481980e07114d4279ad61b0f2beb7f22a602394e685631929bbd	2026-04-06 16:42:18.899524	2026-04-06 16:42:18.899524	f	Toronto	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Northstar Labs", "title": "Software Engineer", "start_date": "2018-01-01", "end_date": "Present"}]	\N	Northstar Labs	f	\N	\N	MANUAL	\N	\N	\N
35ac2b6a-7541-4d04-a5d4-a2d96c44aad7	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Anaya Mehta	seed.candidate.0187@example.com	+91-9413665628	{"skills": ["Redis", "FastAPI", "React", "Java", "Azure"]}	{"years": 5, "current_role": "Full Stack Developer"}	11.98	19.31	ACTIVE	c5bb86489e82ae2426c3658e27517d4a09f46515e7a9a2ee867dddb85a07726f	2026-04-06 16:42:18.904954	2026-04-06 16:42:18.904954	f	New York	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "BrightPath Solutions", "title": "Full Stack Developer", "start_date": "2021-01-01", "end_date": "Present"}]	\N	BrightPath Solutions	f	\N	\N	MANUAL	\N	\N	\N
3ce354dc-8257-4c73-aad2-005a6f317420	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Ishaan Fernandes	seed.candidate.0188@example.com	+91-9332274201	{"skills": ["Docker", "Kubernetes", "PostgreSQL", "Python"]}	{"years": 7, "current_role": "Data Analyst"}	16.65	18.71	ACTIVE	e72137d3325c2bba4c4c20802a65877e81b54515a400327f386e7d5b3f37d354	2026-04-06 16:42:18.909103	2026-04-06 16:42:18.909103	f	San Francisco	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Vertex AI", "title": "Data Analyst", "start_date": "2021-01-01", "end_date": "Present"}]	\N	Vertex AI	f	\N	\N	MANUAL	\N	\N	\N
3342f8e7-9331-4e9d-b0f3-d1522a221ff3	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Rohan Malhotra	seed.candidate.0189@example.com	+91-9448962893	{"skills": ["Docker", "Excel", "PostgreSQL", "Azure", "Figma", "Marketing"]}	{"years": 7, "current_role": "Product Manager"}	7.13	10.54	ACTIVE	89a44e9fc7f1175ab13959e7b05919ecbfe796670ff03391a2d114f1dbbe51e2	2026-04-06 16:42:18.914209	2026-04-06 16:42:18.914209	f	Delhi	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Quantum Stack", "title": "Product Manager", "start_date": "2022-01-01", "end_date": "Present"}]	\N	Quantum Stack	f	\N	\N	MANUAL	\N	\N	\N
a1e2f84e-1a78-40c9-a5da-351a4e1ddc16	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Aditya Singh	seed.candidate.0190@example.com	+91-9430397999	{"skills": ["React", "Django", "TypeScript", "Spring", "AWS", "Kubernetes"]}	{"years": 10, "current_role": "Software Engineer"}	3.29	9.75	ACTIVE	234f201d6cd6c81d22febb77e62f2a85ecfe5b8daa43e5af68bd6085def508d1	2026-04-06 16:42:18.918157	2026-04-06 16:42:18.918157	f	Toronto	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Meridian Works", "title": "Software Engineer", "start_date": "2018-01-01", "end_date": "Present"}]	\N	Meridian Works	f	\N	\N	MANUAL	\N	\N	\N
3e0095e0-3674-480a-baf6-9f5a2b6861ea	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Harper Williams	seed.candidate.0191@example.com	+91-9484835115	{"skills": ["Figma", "Redis", "Excel", "Sales"]}	{"years": 12, "current_role": "Frontend Developer"}	22.28	29.32	ACTIVE	e39908f887b1aef4935243dc70d27da268bc53164aa1833b6a6d794a050b63b1	2026-04-06 16:42:18.922839	2026-04-06 16:42:18.922839	f	San Francisco	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "IronPeak Data", "title": "Frontend Developer", "start_date": "2019-01-01", "end_date": "Present"}]	\N	IronPeak Data	f	\N	\N	MANUAL	\N	\N	\N
d300a68f-3172-4649-a963-b7d138c0fdaf	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Maya Kapoor	seed.candidate.0192@example.com	+91-9231298605	{"skills": ["MySQL", "Java", "Figma"]}	{"years": 9, "current_role": "UI Designer"}	7.01	14.12	ACTIVE	618d2591ec1e548032bb69f74e4a870a2383e8da8d7e174f17f12c4c1b74ff73	2026-04-06 16:42:18.927983	2026-04-06 16:42:18.927983	f	Hyderabad	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Zenith Commerce", "title": "UI Designer", "start_date": "2020-01-01", "end_date": "Present"}]	\N	Zenith Commerce	f	\N	\N	MANUAL	\N	\N	\N
2fff4181-e9f2-49f9-96a0-dc6656f53018	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Liam Williams	seed.candidate.0193@example.com	+91-9108647848	{"skills": ["Redis", "Spring", "Python", "FastAPI"]}	{"years": 10, "current_role": "Marketing Associate"}	8.47	12.86	ACTIVE	0e0afa558188636063ea6ecf0d042ff6b48457f79968070f872fdc453f6f869d	2026-04-06 16:42:18.930635	2026-04-06 16:42:18.930635	f	Chennai	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Skyline Digital", "title": "Marketing Associate", "start_date": "2021-01-01", "end_date": "Present"}]	\N	Skyline Digital	f	\N	\N	MANUAL	\N	\N	\N
f17bd5ff-950f-4263-8acd-effb20f2b7ad	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Kavya Kapoor	seed.candidate.0194@example.com	+91-9319720688	{"skills": ["Power BI", "Java", "Azure", "Redis", "Python", "PostgreSQL"]}	{"years": 7, "current_role": "Sales Executive"}	25.12	30.89	ACTIVE	21943711cddd078bb05a63a4aae4e95b088448e4b28e9e78709bb04824a49838	2026-04-06 16:42:18.935248	2026-04-06 16:42:18.935248	f	Bangalore	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Pioneer Health", "title": "Sales Executive", "start_date": "2021-01-01", "end_date": "Present"}]	\N	Pioneer Health	f	\N	\N	MANUAL	\N	\N	\N
72bb6366-4657-45e8-a6c9-a15e0dcf970d	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Aditya Johnson	seed.candidate.0195@example.com	+91-9337506519	{"skills": ["Django", "Excel", "Node.js"]}	{"years": 8, "current_role": "Marketing Associate"}	20.84	27.70	ACTIVE	d13f88007482d1ad12c472eb75c05d9db1e6fd8614602dccb5bbe4cef6fc6f27	2026-04-06 16:42:18.941046	2026-04-06 16:42:18.941046	f	Hyderabad	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Quantum Stack", "title": "Marketing Associate", "start_date": "2018-01-01", "end_date": "Present"}]	\N	Quantum Stack	f	\N	\N	MANUAL	\N	\N	\N
9c971ec5-6de3-429f-b5cc-8923ad0343cf	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Priya Smith	seed.candidate.0196@example.com	+91-9161113502	{"skills": ["AWS", "Excel", "Sales", "TypeScript", "Power BI", "Docker"]}	{"years": 3, "current_role": "Marketing Associate"}	3.31	7.51	ACTIVE	32451c1dd7bfc784f04f0877f3abb1f4c73b3fa345b05cf0740ca8b66aabc295	2026-04-06 16:42:18.945327	2026-04-06 16:42:18.945327	f	Hyderabad	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Acme Systems", "title": "Marketing Associate", "start_date": "2022-01-01", "end_date": "Present"}]	\N	Acme Systems	f	\N	\N	MANUAL	\N	\N	\N
2f0dc1cc-0af3-4d67-8bef-f442aee04ceb	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Harper Smith	seed.candidate.0197@example.com	+91-9594568873	{"skills": ["Marketing", "Kubernetes", "Power BI", "Python"]}	{"years": 6, "current_role": "Sales Executive"}	15.92	18.07	ACTIVE	83d95a86d412f28fafd288d6bbb215f9db32e88b234380d586fa5976593a0980	2026-04-06 16:42:18.95001	2026-04-06 16:42:18.95001	f	New York	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Zenith Commerce", "title": "Sales Executive", "start_date": "2018-01-01", "end_date": "Present"}]	\N	Zenith Commerce	f	\N	\N	MANUAL	\N	\N	\N
e0951ec9-6684-4a89-b62e-01507712a2ce	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Aarav Brown	seed.candidate.0198@example.com	+91-9160049390	{"skills": ["Marketing", "Figma", "FastAPI", "AWS", "TypeScript", "Spring"]}	{"years": 12, "current_role": "Data Analyst"}	24.60	32.57	ACTIVE	46573a6abcb9303ada92f4cb4ddac866442de84d4c2d18a676a749718dde7d1d	2026-04-06 16:42:18.954288	2026-04-06 16:42:18.954288	f	Hyderabad	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "Zenith Commerce", "title": "Data Analyst", "start_date": "2018-01-01", "end_date": "Present"}]	\N	Zenith Commerce	f	\N	\N	MANUAL	\N	\N	\N
76c1d05e-8a1e-4f3d-bf4b-af41bdef972f	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Kavya Iyer	seed.candidate.0199@example.com	+91-9483811831	{"skills": ["MySQL", "Python", "Excel", "Java"]}	{"years": 12, "current_role": "DevOps Engineer"}	4.80	7.44	ACTIVE	aade486383bc91d2659645d0c067ba7183d4049966ce07422bbdd8b1c264945c	2026-04-06 16:42:18.958518	2026-04-06 16:42:18.958518	f	Pune	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "BrightPath Solutions", "title": "DevOps Engineer", "start_date": "2022-01-01", "end_date": "Present"}]	\N	BrightPath Solutions	f	\N	\N	MANUAL	\N	\N	\N
f247528b-6b0d-4b46-8142-d5c03fc09c06	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Aditya Das	seed.candidate.0200@example.com	+91-9555758662	{"skills": ["PostgreSQL", "Docker", "Spring", "Marketing", "Power BI", "Excel"]}	{"years": 2, "current_role": "Sales Executive"}	21.62	26.34	ACTIVE	7c807b34d2ee489c3e8a0652830fdf2fb11da97a0814bf857f01cd3b9085f22a	2026-04-06 16:42:18.963961	2026-04-06 16:42:18.963961	f	Hyderabad	Bulk-seeded candidate record	\N	\N	\N	\N	\N	\N	[{"company": "BrightPath Solutions", "title": "Sales Executive", "start_date": "2018-01-01", "end_date": "Present"}]	\N	BrightPath Solutions	f	\N	\N	MANUAL	\N	\N	\N
5299a44b-155c-4d9c-9a37-1b82c46dd0f1	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Kavya Gupta	seed.candidate.0002@example.com	+91-9190410617	{"skills": ["React", "Marketing", "Power BI", "Node.js"]}	{"years": 2, "current_role": "QA Engineer"}	22.24	29.58	ACTIVE	04ac920acdda73f2f1aa8118eace6e9c4fa75a2acc76946d6046c5225b22ccbc	2026-04-06 16:34:52.876912	2026-04-06 16:48:00.995257	f	Kolkata	Bulk-seeded candidate record\n\nf	\N	\N	\N	\N	\N	\N	[{"company": "Nimbus Cloud", "title": "QA Engineer", "start_date": "2019-01-01", "end_date": "Present"}]	\N	Nimbus Cloud	f	\N	\N	MANUAL	\N	\N	a3e16bca-3a81-4aff-8db4-c219484af1d7
\.


--
-- Data for Name: clients; Type: TABLE DATA; Schema: public; Owner: ats_user
--

COPY public.clients (id, name, email_domain, created_at, updated_at, industry, contact_name, contact_email, contact_phone, address, website, is_active) FROM stdin;
1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	Acme Corp	acmecorp.com	2026-04-06 16:34:35.031285	2026-04-06 16:34:35.031285	\N	\N	\N	\N	\N	\N	t
a3e16bca-3a81-4aff-8db4-c219484af1d7	orcl	gmail.com	2026-04-06 16:45:28.928372	2026-04-06 16:45:28.928376	Technology	AMAN ANSARI	iamamanansari786a@gmail.com	+918149404438	GALIB NAGAR NEAR MASJID UMAR FAROOK	https://thiel.com/et-officiis-repellat-et-ea-at.html	t
\.


--
-- Data for Name: company_employees; Type: TABLE DATA; Schema: public; Owner: ats_user
--

COPY public.company_employees (id, client_id, candidate_id, application_id, name, email, phone, role, department, date_of_joining, status, is_active, notes, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: fsm_transition_logs; Type: TABLE DATA; Schema: public; Owner: ats_user
--

COPY public.fsm_transition_logs (id, candidate_id, old_status, new_status, actor_id, actor_type, reason, is_terminal, client_id, created_at) FROM stdin;
\.


--
-- Data for Name: interview_records; Type: TABLE DATA; Schema: public; Owner: ats_user
--

COPY public.interview_records (id, candidate_id, client_id, company_id, interviewer_id, interview_date, notes, rating, created_at, updated_at, deleted_at, "position", skills) FROM stdin;
\.


--
-- Data for Name: jobs; Type: TABLE DATA; Schema: public; Owner: ats_user
--

COPY public.jobs (id, client_id, title, company_name, posting_date, requirements, experience_required, salary_lpa, location, created_at, updated_at, submitted_by_client, closing_date, department, employment_type, openings_count, status, vacant) FROM stdin;
127cc8c2-7498-4137-9bb9-b2213753acf2	a3e16bca-3a81-4aff-8db4-c219484af1d7	sj	orcl	2026-04-06	j	9	99.00	Parbhani, MH	2026-04-06 16:47:16.389365	2026-04-06 16:47:16.389369	t	\N	\N	FULL_TIME	1	OPEN	t
\.


--
-- Data for Name: password_reset_tokens; Type: TABLE DATA; Schema: public; Owner: ats_user
--

COPY public.password_reset_tokens (id, user_id, token_hash, expires_at, used_at, requested_ip, user_agent, created_at) FROM stdin;
\.


--
-- Data for Name: resume_jobs; Type: TABLE DATA; Schema: public; Owner: ats_user
--

COPY public.resume_jobs (id, client_id, email_message_id, file_name, file_path, status, error_message, processed_at, created_at) FROM stdin;
\.


--
-- Data for Name: security_audit_logs; Type: TABLE DATA; Schema: public; Owner: ats_user
--

COPY public.security_audit_logs (id, event_type, severity, client_id, user_id, ip_address, user_agent, email, details, created_at) FROM stdin;
c5e3c0c3-9f86-4368-b785-d2496ede0eda	rate_limit_exceeded	MEDIUM	\N	\N	172.19.0.1	python-requests/2.32.3	admin@acmecorp.com	{"identifier": "172.19.0.1", "limit_type": "login", "attempted_at": "2026-01-11T13:40:34.903566"}	2026-01-11 13:40:35.056923
042aa02c-aca0-420b-8633-f0114f32c450	rate_limit_exceeded	MEDIUM	\N	\N	172.19.0.1	python-requests/2.32.3	admin@acmecorp.com	{"identifier": "172.19.0.1", "limit_type": "login", "attempted_at": "2026-01-11T13:41:50.415297"}	2026-01-11 13:41:50.549861
e5ca1517-30c3-4e39-9b4e-3d0c59056573	rate_limit_exceeded	MEDIUM	\N	\N	172.19.0.1	python-requests/2.32.3	admin@acmecorp.com	{"identifier": "172.19.0.1", "limit_type": "login", "attempted_at": "2026-01-11T13:43:54.445136"}	2026-01-11 13:43:54.504109
ec5efb98-a3c7-4b8e-a56e-8b69ef558903	rate_limit_exceeded	MEDIUM	\N	\N	172.19.0.1	python-requests/2.32.3	admin@acmecorp.com	{"identifier": "172.19.0.1", "limit_type": "login", "attempted_at": "2026-01-11T13:46:39.908038"}	2026-01-11 13:46:39.924523
694711c5-ada2-4b0d-8931-61f29d41fa82	rate_limit_exceeded	MEDIUM	\N	\N	172.19.0.1	python-requests/2.32.3	admin@acmecorp.com	{"identifier": "172.19.0.1", "limit_type": "login", "attempted_at": "2026-01-11T13:47:46.912312"}	2026-01-11 13:47:46.913744
aac8b3af-14ef-4539-b976-dbc8e37ce20c	rate_limit_exceeded	MEDIUM	\N	\N	172.19.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36 Edg/143.0.0.0	iamamanansari786a@gmail.com	{"identifier": "172.19.0.1", "limit_type": "login", "attempted_at": "2026-01-11T16:24:51.670920"}	2026-01-11 16:24:51.734872
3b7c174f-4421-4d62-b80a-1c711170453a	rate_limit_exceeded	MEDIUM	\N	\N	172.19.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36 Edg/143.0.0.0	admin@acmecorp.com	{"identifier": "172.19.0.1", "limit_type": "login", "attempted_at": "2026-01-11T16:29:52.444420"}	2026-01-11 16:29:52.62402
2f3cdf55-2542-4b03-8c93-eab62ec47eb8	rate_limit_exceeded	MEDIUM	\N	\N	172.19.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36 Edg/143.0.0.0	admin@acmecorp.com	{"identifier": "172.19.0.1", "limit_type": "login", "attempted_at": "2026-01-11T16:30:07.487322"}	2026-01-11 16:30:07.510161
1f8a8ce9-aaa4-459f-b426-869cf5f95c19	rate_limit_exceeded	MEDIUM	\N	\N	172.19.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36 Edg/143.0.0.0	admin@acmecorp.com	{"identifier": "172.19.0.1", "limit_type": "login", "attempted_at": "2026-01-11T16:30:41.705365"}	2026-01-11 16:30:41.713044
9c495205-30b7-4466-83b6-a134120982d8	auth_failure	LOW	\N	\N	172.19.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:146.0) Gecko/20100101 Firefox/146.0	iamamanansari786a@gmail.com	{"reason": "user_not_found", "attempted_at": "2026-01-11T16:40:01.404738"}	2026-01-11 16:40:01.422633
d52005cb-78c5-42f3-baba-d357dc0733e6	rate_limit_exceeded	MEDIUM	\N	\N	172.19.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:146.0) Gecko/20100101 Firefox/146.0	iamamanansari786a@gmail.com	{"identifier": "172.19.0.1", "limit_type": "login", "attempted_at": "2026-01-11T16:44:02.866759"}	2026-01-11 16:44:02.896426
90c6046d-e656-4f6f-b6d2-63e22eb81191	rate_limit_exceeded	MEDIUM	\N	\N	172.19.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:146.0) Gecko/20100101 Firefox/146.0	admin@acmecorp.com	{"identifier": "172.19.0.1", "limit_type": "login", "attempted_at": "2026-01-12T16:36:58.687559"}	2026-01-12 16:36:58.822263
e6685c4b-8dfb-4742-98e6-4da11b19c89b	rate_limit_exceeded	MEDIUM	\N	\N	172.19.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:146.0) Gecko/20100101 Firefox/146.0	admin@acmecorp.com	{"identifier": "172.19.0.1", "limit_type": "login", "attempted_at": "2026-01-12T16:37:00.848680"}	2026-01-12 16:37:00.850192
4a390c39-5366-4cd6-b00d-0269fbddaed8	rate_limit_exceeded	MEDIUM	\N	\N	172.19.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:146.0) Gecko/20100101 Firefox/146.0	admin@acmecorp.com	{"identifier": "172.19.0.1", "limit_type": "login", "attempted_at": "2026-01-12T16:37:01.789080"}	2026-01-12 16:37:01.790689
d6f09759-b1c3-4643-81e2-a0c6cf662b7e	rate_limit_exceeded	MEDIUM	\N	\N	172.19.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:146.0) Gecko/20100101 Firefox/146.0	admin@acmecorp.com	{"identifier": "172.19.0.1", "limit_type": "login", "attempted_at": "2026-01-12T16:37:02.512380"}	2026-01-12 16:37:02.513614
0a1555d3-e851-4d0c-a906-d9b551496141	rate_limit_exceeded	MEDIUM	\N	\N	172.19.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:146.0) Gecko/20100101 Firefox/146.0	admin@acmecorp.com	{"identifier": "172.19.0.1", "limit_type": "login", "attempted_at": "2026-01-12T16:37:02.878860"}	2026-01-12 16:37:02.88146
8fa19112-5fb3-4205-ae9d-5d3ae368c035	rate_limit_exceeded	MEDIUM	\N	\N	172.19.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:146.0) Gecko/20100101 Firefox/146.0	admin@acmecorp.com	{"identifier": "172.19.0.1", "limit_type": "login", "attempted_at": "2026-01-12T16:37:03.097320"}	2026-01-12 16:37:03.098371
79196413-5762-4e52-a719-72160176575f	rate_limit_exceeded	MEDIUM	\N	\N	172.19.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:146.0) Gecko/20100101 Firefox/146.0	admin@acmecorp.com	{"identifier": "172.19.0.1", "limit_type": "login", "attempted_at": "2026-01-12T16:37:03.315408"}	2026-01-12 16:37:03.316724
519cc304-2a1d-4be0-8848-32aa4507f07a	rate_limit_exceeded	MEDIUM	\N	\N	172.19.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:146.0) Gecko/20100101 Firefox/146.0	admin@acmecorp.com	{"identifier": "172.19.0.1", "limit_type": "login", "attempted_at": "2026-01-12T16:37:03.537908"}	2026-01-12 16:37:03.53911
7bf15c7e-4455-4b15-b0b6-6976c129639d	rate_limit_exceeded	MEDIUM	\N	\N	172.19.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:146.0) Gecko/20100101 Firefox/146.0	admin@acmecorp.com	{"identifier": "172.19.0.1", "limit_type": "login", "attempted_at": "2026-01-12T16:37:03.765164"}	2026-01-12 16:37:03.766373
52bd8c56-246f-40ba-9b79-88fcaf6cc8cf	rate_limit_exceeded	MEDIUM	\N	\N	172.19.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:146.0) Gecko/20100101 Firefox/146.0	admin@acmecorp.com	{"identifier": "172.19.0.1", "limit_type": "login", "attempted_at": "2026-01-12T16:37:13.875843"}	2026-01-12 16:37:13.964105
858e3224-b33e-478f-b1c3-764983d6a063	rate_limit_exceeded	MEDIUM	\N	\N	172.19.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:146.0) Gecko/20100101 Firefox/146.0	admin@acmecorp.com	{"identifier": "172.19.0.1", "limit_type": "login", "attempted_at": "2026-01-12T16:37:14.492838"}	2026-01-12 16:37:14.494408
27b2713e-1933-49f3-a444-006fc60e3255	rate_limit_exceeded	MEDIUM	\N	\N	172.19.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:146.0) Gecko/20100101 Firefox/146.0	admin@acmecorp.com	{"identifier": "172.19.0.1", "limit_type": "login", "attempted_at": "2026-01-12T16:37:15.357945"}	2026-01-12 16:37:15.360625
3bbc5f1a-9930-4d86-a436-3953675f060c	rate_limit_exceeded	MEDIUM	\N	\N	172.19.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:146.0) Gecko/20100101 Firefox/146.0	admin@acmecorp.com	{"identifier": "172.19.0.1", "limit_type": "login", "attempted_at": "2026-01-12T16:37:24.405147"}	2026-01-12 16:37:24.406145
cd41c73e-008d-41d2-9712-e2df7c60e844	rate_limit_exceeded	MEDIUM	\N	\N	172.19.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:146.0) Gecko/20100101 Firefox/146.0	admin@acmecorp.com	{"identifier": "172.19.0.1", "limit_type": "login", "attempted_at": "2026-01-12T16:37:25.289057"}	2026-01-12 16:37:25.290044
43f3c01d-7582-4acc-88d1-1ea2be207003	rate_limit_exceeded	MEDIUM	\N	\N	172.19.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:146.0) Gecko/20100101 Firefox/146.0	admin@acmecorp.com	{"identifier": "172.19.0.1", "limit_type": "login", "attempted_at": "2026-01-12T16:37:28.599601"}	2026-01-12 16:37:28.60062
88e71474-9116-4086-b4b7-8a878eea262d	rate_limit_exceeded	MEDIUM	\N	\N	172.19.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36	admin@acmecorp.com	{"identifier": "172.19.0.1", "limit_type": "login", "attempted_at": "2026-01-12T16:49:33.644282"}	2026-01-12 16:49:33.829492
f060d218-07ac-4ac9-9663-22f1095b0289	rate_limit_exceeded	MEDIUM	\N	\N	172.19.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36	admin@acmecorp.com	{"identifier": "172.19.0.1", "limit_type": "login", "attempted_at": "2026-01-12T16:50:36.267590"}	2026-01-12 16:50:36.450189
53391b70-d6d3-415f-a031-72b1a08336d3	rate_limit_exceeded	MEDIUM	\N	\N	172.19.0.1	python-requests/2.32.3	admin@acmecorp.com	{"identifier": "172.19.0.1", "limit_type": "login", "attempted_at": "2026-01-12T16:52:54.086724"}	2026-01-12 16:52:56.111661
c0b707fd-b4e6-48cc-96d5-e3977b9f38ca	rate_limit_exceeded	MEDIUM	\N	\N	172.19.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36	admin@acmecorp.com	{"identifier": "172.19.0.1", "limit_type": "login", "attempted_at": "2026-01-12T16:53:06.892272"}	2026-01-12 16:53:08.346876
25a5e7a3-6438-4b72-977c-cbc6d38d6519	rate_limit_exceeded	MEDIUM	\N	\N	172.19.0.1	python-requests/2.32.3	admin@acmecorp.com	{"identifier": "172.19.0.1", "limit_type": "login", "attempted_at": "2026-01-12T16:54:40.667585"}	2026-01-12 16:54:41.364156
e930bf92-f3cf-4404-a83e-e9c5b7638b2d	rate_limit_exceeded	MEDIUM	\N	\N	172.19.0.1	python-requests/2.32.3	admin@acmecorp.com	{"identifier": "172.19.0.1", "limit_type": "login", "attempted_at": "2026-01-12T16:59:47.727381"}	2026-01-12 16:59:47.811228
3a0961a5-192d-45e3-bd72-a19131ed3c8a	rate_limit_exceeded	MEDIUM	\N	\N	172.19.0.1	python-requests/2.32.3	admin@acmecorp.com	{"identifier": "172.19.0.1", "limit_type": "login", "attempted_at": "2026-01-12T17:00:42.174073"}	2026-01-12 17:00:42.264246
4c1f6a46-d8ef-4da5-8f6f-e0f32c9d5b2d	rate_limit_exceeded	MEDIUM	\N	\N	172.19.0.1	python-requests/2.32.3	admin@acmecorp.com	{"identifier": "172.19.0.1", "limit_type": "login", "attempted_at": "2026-01-13T16:42:52.143180"}	2026-01-13 16:42:52.263138
46e8644c-b290-413c-b04d-9e7590fcd1ff	token_replay	HIGH	\N	157aac77-406e-4b40-8222-44f0b6d8f725	\N	\N	admin@acmecorp.com	{"jti": "ffbfe040-8ab9-4e8a-8622-9fb0141dfa98", "attempted_at": "2026-01-16T13:56:58.914870"}	2026-01-16 13:56:58.928958
4e42ebfe-81b5-4d94-9fec-a030056568a3	token_replay	HIGH	\N	157aac77-406e-4b40-8222-44f0b6d8f725	\N	\N	admin@acmecorp.com	{"jti": "edae1e19-b771-4098-8b29-4d478c74c9bf", "attempted_at": "2026-01-16T14:03:25.831943"}	2026-01-16 14:03:25.844507
a5b7b0ed-6e1d-4387-87ae-ea87b10906bd	token_replay	HIGH	\N	157aac77-406e-4b40-8222-44f0b6d8f725	\N	\N	admin@acmecorp.com	{"jti": "ad5c4796-205e-46f1-a9a9-c25a745956ac", "attempted_at": "2026-01-16T14:04:33.606967"}	2026-01-16 14:04:33.609196
5c0f0fb4-4b7c-4bc8-886f-091c08d797f4	token_replay	HIGH	\N	157aac77-406e-4b40-8222-44f0b6d8f725	\N	\N	admin@acmecorp.com	{"jti": "72957e14-1ca9-49da-b7cc-04b7b443abcc", "attempted_at": "2026-01-16T14:04:53.116615"}	2026-01-16 14:04:53.117537
8d07515a-2aa5-4181-9e0f-a7efc16933b8	token_replay	HIGH	\N	157aac77-406e-4b40-8222-44f0b6d8f725	\N	\N	admin@acmecorp.com	{"jti": "c226b62d-ecd3-4056-a906-a872c4eb3f21", "attempted_at": "2026-01-16T14:11:02.638225"}	2026-01-16 14:11:02.68079
\.


--
-- Data for Name: users; Type: TABLE DATA; Schema: public; Owner: ats_user
--

COPY public.users (id, email, hashed_password, full_name, is_active, client_id, created_at, updated_at, role) FROM stdin;
6db382cf-4e28-46be-b9bf-8179ed09243c	client.admin@acmecorp.com	$2b$04$5bm.Pe2FbCzHy3.wyuaTvuWcjtEuzRT06PolkIkjTYaJYjBFBe1.a	Acme Corp Admin	t	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	2026-04-06 16:34:35.051379	2026-04-06 16:34:35.021357	client_admin
265468a9-ed94-46a1-ac2d-4b130a1fcff2	admin@acmecorp.com	$2b$04$tUQa7mXlFHZ/6dFwDWMczO9s2LiF0KPVNSvkRphtd2NRnnzliX2Oe	System Admin	t	1f2f0a72-27f7-4fd3-85e6-47fd47a4a0b6	2026-04-06 16:34:44.125605	2026-04-06 16:42:17.939699	hr_admin
fc69ddfb-d533-420d-9cf2-4dd9d2fe3bf9	client.admin@gmail.com	$2b$04$avr.LGy524ph3XjLjaIPhOBTmKYD9BVJF9Y50mzWQ6veEWBOnBhEe	orcl Admin	t	a3e16bca-3a81-4aff-8db4-c219484af1d7	2026-04-06 16:45:28.95083	2026-04-06 16:45:28.893597	client_admin
\.


--
-- Name: activity_logs activity_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: ats_user
--

ALTER TABLE ONLY public.activity_logs
    ADD CONSTRAINT activity_logs_pkey PRIMARY KEY (id);


--
-- Name: alembic_version alembic_version_pkc; Type: CONSTRAINT; Schema: public; Owner: ats_user
--

ALTER TABLE ONLY public.alembic_version
    ADD CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num);


--
-- Name: applications applications_pkey; Type: CONSTRAINT; Schema: public; Owner: ats_user
--

ALTER TABLE ONLY public.applications
    ADD CONSTRAINT applications_pkey PRIMARY KEY (id);


--
-- Name: audit_logs audit_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: ats_user
--

ALTER TABLE ONLY public.audit_logs
    ADD CONSTRAINT audit_logs_pkey PRIMARY KEY (id);


--
-- Name: candidates candidates_pkey; Type: CONSTRAINT; Schema: public; Owner: ats_user
--

ALTER TABLE ONLY public.candidates
    ADD CONSTRAINT candidates_pkey PRIMARY KEY (id);


--
-- Name: clients clients_pkey; Type: CONSTRAINT; Schema: public; Owner: ats_user
--

ALTER TABLE ONLY public.clients
    ADD CONSTRAINT clients_pkey PRIMARY KEY (id);


--
-- Name: company_employees company_employees_pkey; Type: CONSTRAINT; Schema: public; Owner: ats_user
--

ALTER TABLE ONLY public.company_employees
    ADD CONSTRAINT company_employees_pkey PRIMARY KEY (id);


--
-- Name: fsm_transition_logs fsm_transition_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: ats_user
--

ALTER TABLE ONLY public.fsm_transition_logs
    ADD CONSTRAINT fsm_transition_logs_pkey PRIMARY KEY (id);


--
-- Name: interview_records interview_records_pkey; Type: CONSTRAINT; Schema: public; Owner: ats_user
--

ALTER TABLE ONLY public.interview_records
    ADD CONSTRAINT interview_records_pkey PRIMARY KEY (id);


--
-- Name: jobs jobs_pkey; Type: CONSTRAINT; Schema: public; Owner: ats_user
--

ALTER TABLE ONLY public.jobs
    ADD CONSTRAINT jobs_pkey PRIMARY KEY (id);


--
-- Name: password_reset_tokens password_reset_tokens_pkey; Type: CONSTRAINT; Schema: public; Owner: ats_user
--

ALTER TABLE ONLY public.password_reset_tokens
    ADD CONSTRAINT password_reset_tokens_pkey PRIMARY KEY (id);


--
-- Name: resume_jobs resume_jobs_email_message_id_key; Type: CONSTRAINT; Schema: public; Owner: ats_user
--

ALTER TABLE ONLY public.resume_jobs
    ADD CONSTRAINT resume_jobs_email_message_id_key UNIQUE (email_message_id);


--
-- Name: resume_jobs resume_jobs_pkey; Type: CONSTRAINT; Schema: public; Owner: ats_user
--

ALTER TABLE ONLY public.resume_jobs
    ADD CONSTRAINT resume_jobs_pkey PRIMARY KEY (id);


--
-- Name: security_audit_logs security_audit_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: ats_user
--

ALTER TABLE ONLY public.security_audit_logs
    ADD CONSTRAINT security_audit_logs_pkey PRIMARY KEY (id);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: ats_user
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: ix_company_employees_candidate_id; Type: INDEX; Schema: public; Owner: ats_user
--

CREATE INDEX ix_company_employees_candidate_id ON public.company_employees USING btree (candidate_id);


--
-- Name: ix_company_employees_client_id; Type: INDEX; Schema: public; Owner: ats_user
--

CREATE INDEX ix_company_employees_client_id ON public.company_employees USING btree (client_id);


--
-- Name: ix_jobs_client_id; Type: INDEX; Schema: public; Owner: ats_user
--

CREATE INDEX ix_jobs_client_id ON public.jobs USING btree (client_id);


--
-- Name: ix_jobs_company_name; Type: INDEX; Schema: public; Owner: ats_user
--

CREATE INDEX ix_jobs_company_name ON public.jobs USING btree (company_name);


--
-- Name: ix_jobs_department; Type: INDEX; Schema: public; Owner: ats_user
--

CREATE INDEX ix_jobs_department ON public.jobs USING btree (department);


--
-- Name: ix_jobs_location; Type: INDEX; Schema: public; Owner: ats_user
--

CREATE INDEX ix_jobs_location ON public.jobs USING btree (location);


--
-- Name: ix_jobs_status; Type: INDEX; Schema: public; Owner: ats_user
--

CREATE INDEX ix_jobs_status ON public.jobs USING btree (status);


--
-- Name: ix_jobs_title; Type: INDEX; Schema: public; Owner: ats_user
--

CREATE INDEX ix_jobs_title ON public.jobs USING btree (title);


--
-- Name: ix_jobs_vacant; Type: INDEX; Schema: public; Owner: ats_user
--

CREATE INDEX ix_jobs_vacant ON public.jobs USING btree (vacant);


--
-- Name: ix_password_reset_tokens_token_hash; Type: INDEX; Schema: public; Owner: ats_user
--

CREATE UNIQUE INDEX ix_password_reset_tokens_token_hash ON public.password_reset_tokens USING btree (token_hash);


--
-- Name: ix_password_reset_tokens_user_id; Type: INDEX; Schema: public; Owner: ats_user
--

CREATE INDEX ix_password_reset_tokens_user_id ON public.password_reset_tokens USING btree (user_id);


--
-- Name: ix_users_email; Type: INDEX; Schema: public; Owner: ats_user
--

CREATE UNIQUE INDEX ix_users_email ON public.users USING btree (email);


--
-- Name: uq_applications_one_hired_per_job_active; Type: INDEX; Schema: public; Owner: ats_user
--

CREATE UNIQUE INDEX uq_applications_one_hired_per_job_active ON public.applications USING btree (job_id) WHERE ((job_id IS NOT NULL) AND (deleted_at IS NULL) AND ((status)::text = 'HIRED'::text));


--
-- Name: candidates candidate_status_transition_trigger; Type: TRIGGER; Schema: public; Owner: ats_user
--

CREATE TRIGGER candidate_status_transition_trigger BEFORE UPDATE ON public.candidates FOR EACH ROW WHEN (((old.status)::text IS DISTINCT FROM (new.status)::text)) EXECUTE FUNCTION public.validate_candidate_status_transition();


--
-- Name: candidates log_fsm_transition_trigger; Type: TRIGGER; Schema: public; Owner: ats_user
--

CREATE TRIGGER log_fsm_transition_trigger AFTER UPDATE ON public.candidates FOR EACH ROW WHEN (((old.status)::text IS DISTINCT FROM (new.status)::text)) EXECUTE FUNCTION public.log_fsm_transition();


--
-- Name: candidates prevent_protected_field_modification_trigger; Type: TRIGGER; Schema: public; Owner: ats_user
--

CREATE TRIGGER prevent_protected_field_modification_trigger BEFORE UPDATE ON public.candidates FOR EACH ROW EXECUTE FUNCTION public.prevent_protected_field_modification();


--
-- Name: applications update_applications_updated_at; Type: TRIGGER; Schema: public; Owner: ats_user
--

CREATE TRIGGER update_applications_updated_at BEFORE UPDATE ON public.applications FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- Name: candidates update_candidate_hash_trigger; Type: TRIGGER; Schema: public; Owner: ats_user
--

CREATE TRIGGER update_candidate_hash_trigger BEFORE INSERT OR UPDATE ON public.candidates FOR EACH ROW EXECUTE FUNCTION public.update_candidate_hash();


--
-- Name: candidates update_candidates_updated_at; Type: TRIGGER; Schema: public; Owner: ats_user
--

CREATE TRIGGER update_candidates_updated_at BEFORE UPDATE ON public.candidates FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- Name: clients update_clients_updated_at; Type: TRIGGER; Schema: public; Owner: ats_user
--

CREATE TRIGGER update_clients_updated_at BEFORE UPDATE ON public.clients FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- Name: users update_users_updated_at; Type: TRIGGER; Schema: public; Owner: ats_user
--

CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON public.users FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- Name: activity_logs activity_logs_client_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: ats_user
--

ALTER TABLE ONLY public.activity_logs
    ADD CONSTRAINT activity_logs_client_id_fkey FOREIGN KEY (client_id) REFERENCES public.clients(id);


--
-- Name: activity_logs activity_logs_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: ats_user
--

ALTER TABLE ONLY public.activity_logs
    ADD CONSTRAINT activity_logs_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: applications applications_candidate_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: ats_user
--

ALTER TABLE ONLY public.applications
    ADD CONSTRAINT applications_candidate_id_fkey FOREIGN KEY (candidate_id) REFERENCES public.candidates(id);


--
-- Name: applications applications_client_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: ats_user
--

ALTER TABLE ONLY public.applications
    ADD CONSTRAINT applications_client_id_fkey FOREIGN KEY (client_id) REFERENCES public.clients(id);


--
-- Name: audit_logs audit_logs_client_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: ats_user
--

ALTER TABLE ONLY public.audit_logs
    ADD CONSTRAINT audit_logs_client_id_fkey FOREIGN KEY (client_id) REFERENCES public.clients(id);


--
-- Name: candidates candidates_assigned_client_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: ats_user
--

ALTER TABLE ONLY public.candidates
    ADD CONSTRAINT candidates_assigned_client_id_fkey FOREIGN KEY (assigned_client_id) REFERENCES public.clients(id);


--
-- Name: candidates candidates_assigned_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: ats_user
--

ALTER TABLE ONLY public.candidates
    ADD CONSTRAINT candidates_assigned_user_id_fkey FOREIGN KEY (assigned_user_id) REFERENCES public.users(id);


--
-- Name: candidates candidates_client_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: ats_user
--

ALTER TABLE ONLY public.candidates
    ADD CONSTRAINT candidates_client_id_fkey FOREIGN KEY (client_id) REFERENCES public.clients(id);


--
-- Name: company_employees company_employees_application_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: ats_user
--

ALTER TABLE ONLY public.company_employees
    ADD CONSTRAINT company_employees_application_id_fkey FOREIGN KEY (application_id) REFERENCES public.applications(id);


--
-- Name: company_employees company_employees_candidate_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: ats_user
--

ALTER TABLE ONLY public.company_employees
    ADD CONSTRAINT company_employees_candidate_id_fkey FOREIGN KEY (candidate_id) REFERENCES public.candidates(id);


--
-- Name: company_employees company_employees_client_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: ats_user
--

ALTER TABLE ONLY public.company_employees
    ADD CONSTRAINT company_employees_client_id_fkey FOREIGN KEY (client_id) REFERENCES public.clients(id);


--
-- Name: applications fk_applications_applied_by_user_id_users; Type: FK CONSTRAINT; Schema: public; Owner: ats_user
--

ALTER TABLE ONLY public.applications
    ADD CONSTRAINT fk_applications_applied_by_user_id_users FOREIGN KEY (applied_by_user_id) REFERENCES public.users(id);


--
-- Name: applications fk_applications_job_id_jobs; Type: FK CONSTRAINT; Schema: public; Owner: ats_user
--

ALTER TABLE ONLY public.applications
    ADD CONSTRAINT fk_applications_job_id_jobs FOREIGN KEY (job_id) REFERENCES public.jobs(id);


--
-- Name: fsm_transition_logs fsm_transition_logs_candidate_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: ats_user
--

ALTER TABLE ONLY public.fsm_transition_logs
    ADD CONSTRAINT fsm_transition_logs_candidate_id_fkey FOREIGN KEY (candidate_id) REFERENCES public.candidates(id);


--
-- Name: fsm_transition_logs fsm_transition_logs_client_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: ats_user
--

ALTER TABLE ONLY public.fsm_transition_logs
    ADD CONSTRAINT fsm_transition_logs_client_id_fkey FOREIGN KEY (client_id) REFERENCES public.clients(id);


--
-- Name: interview_records interview_records_candidate_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: ats_user
--

ALTER TABLE ONLY public.interview_records
    ADD CONSTRAINT interview_records_candidate_id_fkey FOREIGN KEY (candidate_id) REFERENCES public.candidates(id);


--
-- Name: interview_records interview_records_client_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: ats_user
--

ALTER TABLE ONLY public.interview_records
    ADD CONSTRAINT interview_records_client_id_fkey FOREIGN KEY (client_id) REFERENCES public.clients(id);


--
-- Name: interview_records interview_records_company_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: ats_user
--

ALTER TABLE ONLY public.interview_records
    ADD CONSTRAINT interview_records_company_id_fkey FOREIGN KEY (company_id) REFERENCES public.clients(id);


--
-- Name: interview_records interview_records_interviewer_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: ats_user
--

ALTER TABLE ONLY public.interview_records
    ADD CONSTRAINT interview_records_interviewer_id_fkey FOREIGN KEY (interviewer_id) REFERENCES public.users(id);


--
-- Name: jobs jobs_client_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: ats_user
--

ALTER TABLE ONLY public.jobs
    ADD CONSTRAINT jobs_client_id_fkey FOREIGN KEY (client_id) REFERENCES public.clients(id);


--
-- Name: password_reset_tokens password_reset_tokens_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: ats_user
--

ALTER TABLE ONLY public.password_reset_tokens
    ADD CONSTRAINT password_reset_tokens_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: resume_jobs resume_jobs_client_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: ats_user
--

ALTER TABLE ONLY public.resume_jobs
    ADD CONSTRAINT resume_jobs_client_id_fkey FOREIGN KEY (client_id) REFERENCES public.clients(id);


--
-- Name: users users_client_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: ats_user
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_client_id_fkey FOREIGN KEY (client_id) REFERENCES public.clients(id);


--
-- Name: applications; Type: ROW SECURITY; Schema: public; Owner: ats_user
--

ALTER TABLE public.applications ENABLE ROW LEVEL SECURITY;

--
-- Name: candidates; Type: ROW SECURITY; Schema: public; Owner: ats_user
--

ALTER TABLE public.candidates ENABLE ROW LEVEL SECURITY;

--
-- Name: applications client_isolation_applications; Type: POLICY; Schema: public; Owner: ats_user
--

CREATE POLICY client_isolation_applications ON public.applications TO authenticated_users USING ((client_id = (current_setting('app.current_client_id'::text, true))::uuid));


--
-- Name: candidates client_isolation_candidates; Type: POLICY; Schema: public; Owner: ats_user
--

CREATE POLICY client_isolation_candidates ON public.candidates TO authenticated_users USING ((client_id = (current_setting('app.current_client_id'::text, true))::uuid));


--
-- Name: fsm_transition_logs client_isolation_fsm_transition_logs; Type: POLICY; Schema: public; Owner: ats_user
--

CREATE POLICY client_isolation_fsm_transition_logs ON public.fsm_transition_logs TO authenticated_users USING ((client_id = (current_setting('app.current_client_id'::text, true))::uuid));


--
-- Name: jobs client_isolation_jobs; Type: POLICY; Schema: public; Owner: ats_user
--

CREATE POLICY client_isolation_jobs ON public.jobs TO authenticated_users USING ((client_id = (current_setting('app.current_client_id'::text, true))::uuid));


--
-- Name: password_reset_tokens client_isolation_password_reset_tokens; Type: POLICY; Schema: public; Owner: ats_user
--

CREATE POLICY client_isolation_password_reset_tokens ON public.password_reset_tokens TO authenticated_users USING ((user_id IN ( SELECT users.id
   FROM public.users
  WHERE (users.client_id = (current_setting('app.current_client_id'::text, true))::uuid))));


--
-- Name: resume_jobs client_isolation_resume_jobs; Type: POLICY; Schema: public; Owner: ats_user
--

CREATE POLICY client_isolation_resume_jobs ON public.resume_jobs TO authenticated_users USING ((client_id = (current_setting('app.current_client_id'::text, true))::uuid));


--
-- Name: users client_isolation_users; Type: POLICY; Schema: public; Owner: ats_user
--

CREATE POLICY client_isolation_users ON public.users TO authenticated_users USING ((client_id = (current_setting('app.current_client_id'::text, true))::uuid));


--
-- Name: fsm_transition_logs; Type: ROW SECURITY; Schema: public; Owner: ats_user
--

ALTER TABLE public.fsm_transition_logs ENABLE ROW LEVEL SECURITY;

--
-- Name: jobs; Type: ROW SECURITY; Schema: public; Owner: ats_user
--

ALTER TABLE public.jobs ENABLE ROW LEVEL SECURITY;

--
-- Name: password_reset_tokens; Type: ROW SECURITY; Schema: public; Owner: ats_user
--

ALTER TABLE public.password_reset_tokens ENABLE ROW LEVEL SECURITY;

--
-- Name: resume_jobs; Type: ROW SECURITY; Schema: public; Owner: ats_user
--

ALTER TABLE public.resume_jobs ENABLE ROW LEVEL SECURITY;

--
-- Name: users; Type: ROW SECURITY; Schema: public; Owner: ats_user
--

ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;

--
-- PostgreSQL database dump complete
--

