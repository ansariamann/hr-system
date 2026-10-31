package com.ats.service;

import com.ats.domain.entity.Application;
import com.ats.domain.entity.Candidate;
import com.ats.domain.entity.CompanyEmployee;
import com.ats.domain.enums.ApplicationStatus;
import com.ats.domain.repository.ApplicationRepository;
import com.ats.domain.repository.CandidateRepository;
import com.ats.domain.repository.CompanyEmployeeRepository;
import com.ats.domain.repository.JobRepository;
import com.ats.exception.ResourceNotFoundException;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.Instant;
import java.util.UUID;


/**
 * Application service — CRUD and FSM-delegated status transitions.
 * On HIRED transition, auto-creates a CompanyEmployee record.
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class ApplicationService {

    private final ApplicationRepository applicationRepository;
    private final ApplicationFsmService fsmService;
    private final CompanyEmployeeRepository companyEmployeeRepository;
    private final CandidateRepository candidateRepository;
    private final JobRepository jobRepository;

    @Transactional(readOnly = true)
    public Page<Application> listApplications(UUID clientId, Pageable pageable) {
        return applicationRepository.findAllByClientIdNotDeleted(clientId, pageable);
    }

    @Transactional(readOnly = true)
    public Application getById(UUID id, UUID clientId) {
        return applicationRepository.findByIdAndClientId(id, clientId)
                .filter(a -> !a.isDeleted())
                .orElseThrow(() -> new ResourceNotFoundException("Application", id));
    }

    @Transactional
    public Application create(Application application) {
        // Enforce foreign-key tenant ownership
        if (application.getClientId() != null) {
            candidateRepository.findByIdAndClientId(application.getCandidateId(), application.getClientId())
                    .orElseThrow(() -> new ResourceNotFoundException("Candidate", application.getCandidateId()));

            if (application.getJobId() != null) {
                jobRepository.findByIdAndClientId(application.getJobId(), application.getClientId())
                        .orElseThrow(() -> new ResourceNotFoundException("Job", application.getJobId()));
            }
        }

        Application saved = applicationRepository.save(application);
        log.info("Application created: {} for candidate {}", saved.getId(), saved.getCandidateId());
        return saved;
    }

    @Transactional
    public Application updateStatus(UUID id, UUID clientId, ApplicationStatus targetStatus, UUID actorId) {
        Application application = fsmService.transition(id, clientId, targetStatus, actorId);

        // Auto-create company employee on HIRED
        if (targetStatus == ApplicationStatus.HIRED) {
            createCompanyEmployeeFromApplication(application);
        }

        return application;
    }

    @Transactional
    public Application acknowledgeHrInterview(UUID id, UUID clientId, UUID actorId, String note) {
        Application application = applicationRepository.findByIdAndClientId(id, clientId)
                .orElseThrow(() -> new ResourceNotFoundException("Application", id));

        application.setHrInterviewAcknowledged(true);
        application.setHrInterviewAcknowledgedAt(Instant.now());
        application.setHrInterviewAcknowledgedBy(actorId);
        application.setHrInterviewAckNote(note);

        return applicationRepository.save(application);
    }

    @Transactional
    public void softDelete(UUID id, UUID clientId) {
        Application application = getById(id, clientId);
        application.softDelete();
        applicationRepository.save(application);
        log.info("Application soft-deleted: {}", id);
    }

    @Transactional
    public Application flagForReview(UUID id, UUID clientId, String reason) {
        Application application = getById(id, clientId);
        application.setFlaggedForReview(true);
        application.setFlagReason(reason);
        return applicationRepository.save(application);
    }

    private void createCompanyEmployeeFromApplication(Application application) {
        // Skip if already exists
        if (companyEmployeeRepository.existsByCandidateIdAndClientId(
                application.getCandidateId(), application.getClientId())) {
            return;
        }

        // Fetch candidate explicitly to avoid lazy-load issues
        Candidate candidate = candidateRepository
                .findByIdAndClientId(application.getCandidateId(), application.getClientId())
                .orElse(null);

        CompanyEmployee employee = CompanyEmployee.builder()
                .clientId(application.getClientId())
                .candidateId(application.getCandidateId())
                .applicationId(application.getId())
                .name(candidate != null ? candidate.getName() : "Unknown")
                .email(candidate != null ? candidate.getEmail() : null)
                .phone(candidate != null ? candidate.getPhone() : null)
                .dateOfJoining(java.time.LocalDate.now())
                .status("ACTIVE")
                .isActive(true)
                .build();

        companyEmployeeRepository.save(employee);
        log.info("CompanyEmployee auto-created for hired candidate {}", application.getCandidateId());
    }
}
