import { ApplicationStatus, UserRole } from "./enums";

export interface User {
    id: string;
    email: string;
    full_name: string;
    role: UserRole;
    is_active: boolean;
}

export interface Candidate {
    id: string;
    name: string;
    email: string;
    phone?: string;
    skills?: { skills: string[] } | any;
    experience?: any;
    ctc_current?: number;
    ctc_expected?: number;
    status: string; // CandidateStatus
    created_at: string;
    updated_at: string;
}

export interface Application {
    id: string;
    candidate_id: string;
    job_id: string;
    status: ApplicationStatus;
    applied_at: string;
    updated_at: string;
    notes?: string;
    candidate?: Candidate;
    job?: Job;
}

export interface Job {
    id: string;
    title: string;
    description: string;
    department: string;
    location: string;
    is_active: boolean;
}

export interface CandidateFilters {
    status?: ApplicationStatus[];
    search?: string;
    skills?: string[];
    min_experience?: number;
}
