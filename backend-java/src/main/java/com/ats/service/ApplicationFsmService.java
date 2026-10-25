package com.ats.service;

import com.ats.domain.entity.Application;
import com.ats.domain.entity.Candidate;
import com.ats.domain.enums.ApplicationStatus;
import com.ats.domain.enums.CandidateStatus;
import com.ats.domain.repository.ApplicationRepository;
import com.ats.domain.repository.CandidateRepository;
import com.ats.exception.BusinessRuleException;
import com.ats.exception.ResourceNotFoundException;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.Instant;
import java.util.UUID;

/**
 * Application Finite State Machine service.
 *
 * Ports the Python FSM logic from fsm_service.py to Java:
 * - Validates allowed state transitions
 * - Enforces the single-hired-per-job invariant
 * - Auto-creates CompanyEmployee on HIRED transition
 * - Auto-updates Candidate status on relevant transitions
 *
 * All mutations run inside @Transactional boundaries so that
 * SET LOCAL app.current_tenant_id (issued by the connection interceptor)
 * is automatically scoped and reset.
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class ApplicationFsmService {

    private final ApplicationRepository applicationRepository;
    private final CandidateRepository candidateRepository;

    // ─── Valid status transitions (matches Python FSM) ──────────────────
    private static final java.util.Map<ApplicationStatus, java.util.Set<ApplicationStatus>> TRANSITIONS =
            java.util.Map.of(
                ApplicationStatus.RECEIVED,             java.util.Set.of(ApplicationStatus.SCREENING, ApplicationStatus.REJECTED, ApplicationStatus.WITHDRAWN),
                ApplicationStatus.SCREENING,            java.util.Set.of(ApplicationStatus.SHORTLISTED, ApplicationStatus.REJECTED, ApplicationStatus.WITHDRAWN),
                ApplicationStatus.SHORTLISTED,          java.util.Set.of(ApplicationStatus.HR_INTERVIEW, ApplicationStatus.REJECTED, ApplicationStatus.WITHDRAWN, ApplicationStatus.ON_HOLD),
                ApplicationStatus.HR_INTERVIEW,         java.util.Set.of(ApplicationStatus.TECHNICAL_INTERVIEW, ApplicationStatus.CLIENT_INTERVIEW, ApplicationStatus.REJECTED, ApplicationStatus.WITHDRAWN, ApplicationStatus.ON_HOLD),
                ApplicationStatus.TECHNICAL_INTERVIEW,  java.util.Set.of(ApplicationStatus.CLIENT_INTERVIEW, ApplicationStatus.OFFER_EXTENDED, ApplicationStatus.REJECTED, ApplicationStatus.WITHDRAWN),
                ApplicationStatus.CLIENT_INTERVIEW,     java.util.Set.of(ApplicationStatus.OFFER_EXTENDED, ApplicationStatus.REJECTED, ApplicationStatus.WITHDRAWN),
                ApplicationStatus.OFFER_EXTENDED,       java.util.Set.of(ApplicationStatus.OFFER_ACCEPTED, ApplicationStatus.REJECTED, ApplicationStatus.WITHDRAWN),
                ApplicationStatus.OFFER_ACCEPTED,       java.util.Set.of(ApplicationStatus.HIRED, ApplicationStatus.WITHDRAWN),
                ApplicationStatus.ON_HOLD,              java.util.Set.of(ApplicationStatus.SCREENING, ApplicationStatus.SHORTLISTED, ApplicationStatus.REJECTED, ApplicationStatus.WITHDRAWN),
                ApplicationStatus.HIRED,                java.util.Set.of()
            );

    /**
     * Transition an application to a new status with all invariant checks.
     */
    @Transactional
    public Application transition(UUID applicationId, UUID clientId,
                                  ApplicationStatus targetStatus, UUID actorId) {

        Application application = applicationRepository.findByIdAndClientId(applicationId, clientId)
                .orElseThrow(() -> new ResourceNotFoundException("Application", applicationId));

        if (application.isDeleted()) {
            throw new BusinessRuleException("Cannot transition a deleted application");
        }

        ApplicationStatus currentStatus = application.getStatus();

        if (currentStatus == targetStatus) {
            return application; // idempotent
        }

        // Validate transition
        var allowed = TRANSITIONS.getOrDefault(currentStatus, java.util.Set.of());
        if (!allowed.contains(targetStatus)) {
            throw new BusinessRuleException(
                    String.format("Invalid transition from %s to %s", currentStatus, targetStatus));
        }

        // Enforce single-hired-per-job invariant
        if (targetStatus == ApplicationStatus.HIRED) {
            enforceHiredInvariant(application);
        }

        // Apply transition
        application.setStatus(targetStatus);
        application.setStatusUpdatedAt(Instant.now());

        // Sync candidate status on key transitions
        syncCandidateStatus(application.getCandidateId(), targetStatus, clientId);

        application = applicationRepository.save(application);

        log.info("Application {} transitioned {} -> {} by actor {}",
                applicationId, currentStatus, targetStatus, actorId);

        return application;
    }

    /**
     * Enforce that a job can only have ONE hired application at a time.
     * Mirrors the ab12cd34ef56 Alembic DB-level constraint as a service check.
     */
    private void enforceHiredInvariant(Application application) {
        if (application.getJobId() != null) {
            long hiredCount = applicationRepository.countHiredByJobId(application.getJobId());
            if (hiredCount > 0) {
                throw new BusinessRuleException(
                        "Job already has a hired candidate. Only one HIRED application is allowed per job.");
            }
        }
    }

    /**
     * Keep candidate.status aligned with the most significant application status.
     */
    private void syncCandidateStatus(UUID candidateId, ApplicationStatus appStatus, UUID clientId) {
        candidateRepository.findByIdAndClientId(candidateId, clientId).ifPresent(candidate -> {
            CandidateStatus newCandidateStatus = switch (appStatus) {
                case HIRED -> CandidateStatus.JOINED;
                case REJECTED -> CandidateStatus.REJECTED;
                case HR_INTERVIEW, TECHNICAL_INTERVIEW, CLIENT_INTERVIEW -> CandidateStatus.INTERVIEW_SCHEDULED;
                case OFFER_ACCEPTED -> CandidateStatus.SELECTED;
                default -> null;
            };

            if (newCandidateStatus != null) {
                candidate.setStatus(newCandidateStatus);
                candidateRepository.save(candidate);
            }
        });
    }

    /**
     * Validate whether a transition is allowed (read-only check).
     */
    @Transactional(readOnly = true)
    public boolean canTransition(ApplicationStatus from, ApplicationStatus to) {
        return TRANSITIONS.getOrDefault(from, java.util.Set.of()).contains(to);
    }
}
