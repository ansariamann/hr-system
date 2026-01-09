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
    first_name: string;
    last_name: string;
    email: string;
    phone?: string;
    linkedin_url?: string;
    portfolio_url?: string;
    resume_url?: string;
    skills: string[];
    total_years_experience: number;
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
