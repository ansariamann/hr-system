package com.ats.domain.enums;

/**
 * Application status states mirroring the Python FSM.
 */
public enum ApplicationStatus {
    RECEIVED,
    SCREENING,
    SHORTLISTED,
    HR_INTERVIEW,
    TECHNICAL_INTERVIEW,
    CLIENT_INTERVIEW,
    OFFER_EXTENDED,
    OFFER_ACCEPTED,
    HIRED,
    REJECTED,
    WITHDRAWN,
    ON_HOLD
}
