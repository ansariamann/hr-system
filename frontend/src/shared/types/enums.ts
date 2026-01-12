export enum ApplicationStatus {
    // Initial states
    NEW = "new",
    SCREENING = "screening",

    // Active process
    INTERVIEW_SCHEDULED = "interview_scheduled",
    INTERVIEW_COMPLETED = "interview_completed",
    TECHNICAL_REVIEW = "technical_review",

    // Decision
    OFFER_PENDING = "offer_pending",
    OFFER_EXTENDED = "offer_extended",
    OFFER_ACCEPTED = "offer_accepted",

    // Final states
    HIRED = "hired",
    REJECTED = "rejected",
    WITHDRAWN = "withdrawn"
}

export enum InterviewType {
    PHONE_SCREEN = "phone_screen",
    TECHNICAL_ROUND = "technical_round",
    SYSTEM_DESIGN = "system_design",
    CULTURAL_FIT = "cultural_fit",
    HR_ROUND = "hr_round"
}

export enum UserRole {
    ADMIN = "admin",
    RECRUITER = "recruiter",
    TRAINEE = "trainee",
    CLIENT = "client"
}

export enum CandidateStatus {
    ACTIVE = "ACTIVE",
    INACTIVE = "INACTIVE",
    LEFT = "LEFT",
    HIRED = "HIRED",
    REJECTED = "REJECTED"
}
