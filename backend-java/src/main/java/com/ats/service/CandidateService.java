package com.ats.service;

import com.ats.domain.entity.ActivityLog;
import com.ats.domain.entity.Candidate;
import com.ats.domain.enums.CandidateStatus;
import com.ats.domain.repository.ActivityLogRepository;
import com.ats.domain.repository.CandidateRepository;
import com.ats.exception.BusinessRuleException;
import com.ats.exception.ResourceNotFoundException;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.Map;
import java.util.UUID;

/**
 * Candidate service — CRUD + status transitions.
 * All operations are scoped to the authenticated client_id (tenant).
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class CandidateService {

    private final CandidateRepository candidateRepository;
    private final ActivityLogRepository activityLogRepository;
    private final DuplicateDetectionService duplicateDetectionService;

    @Transactional(readOnly = true)
    public Page<Candidate> listCandidates(UUID clientId, Pageable pageable) {
        return candidateRepository.findAllByClientId(clientId, pageable);
    }

    @Transactional(readOnly = true)
    public Candidate getById(UUID id, UUID clientId) {
        return candidateRepository.findByIdAndClientId(id, clientId)
                .orElseThrow(() -> new ResourceNotFoundException("Candidate", id));
    }

    @Transactional
    public Candidate create(Candidate candidate, UUID actorId) {
        // Check for duplicates
        var duplicates = duplicateDetectionService.findDuplicates(
                candidate.getClientId(), candidate.getName(),
                candidate.getEmail(), candidate.getPhone());

        if (!duplicates.isEmpty() && duplicates.get(0).score() == 1.0) {
            throw new BusinessRuleException(
                    "Duplicate candidate detected: " + duplicates.get(0).reason() +
                    " (existing id=" + duplicates.get(0).candidate().getId() + ")");
        }

        Candidate saved = candidateRepository.save(candidate);

        logActivity(saved.getClientId(), actorId, "CANDIDATE_CREATED", saved.getId(),
                Map.of("name", saved.getName()));

        log.info("Candidate created: {} for client {}", saved.getId(), saved.getClientId());
        return saved;
    }

    @Transactional
    public Candidate update(UUID id, UUID clientId, Candidate updates, UUID actorId) {
        Candidate existing = getById(id, clientId);

        if (updates.getName() != null)        existing.setName(updates.getName());
        if (updates.getEmail() != null)       existing.setEmail(updates.getEmail());
        if (updates.getPhone() != null)       existing.setPhone(updates.getPhone());
        if (updates.getCompany() != null)     existing.setCompany(updates.getCompany());
        if (updates.getLocation() != null)    existing.setLocation(updates.getLocation());
        if (updates.getSkills() != null)      existing.setSkills(updates.getSkills());
        if (updates.getExperience() != null)  existing.setExperience(updates.getExperience());
        if (updates.getCtcCurrent() != null)  existing.setCtcCurrent(updates.getCtcCurrent());
        if (updates.getCtcExpected() != null) existing.setCtcExpected(updates.getCtcExpected());
        if (updates.getNoticePeriodDays() != null) existing.setNoticePeriodDays(updates.getNoticePeriodDays());
        if (updates.getLinkedinUrl() != null) existing.setLinkedinUrl(updates.getLinkedinUrl());
        if (updates.getKeySkill() != null)    existing.setKeySkill(updates.getKeySkill());
        if (updates.getRemark() != null)      existing.setRemark(updates.getRemark());
        if (updates.getOtherDetails() != null) existing.setOtherDetails(updates.getOtherDetails());
        if (updates.getAssignedUserId() != null) existing.setAssignedUserId(updates.getAssignedUserId());
        if (updates.getTotalExperienceYears() != null) existing.setTotalExperienceYears(updates.getTotalExperienceYears());
        if (updates.getDateOfBirth() != null) existing.setDateOfBirth(updates.getDateOfBirth());
        if (updates.getPreviousEmployment() != null) existing.setPreviousEmployment(updates.getPreviousEmployment());

        Candidate saved = candidateRepository.save(existing);
        logActivity(clientId, actorId, "CANDIDATE_UPDATED", id, Map.of("name", saved.getName()));
        return saved;
    }

    @Transactional
    public void delete(UUID id, UUID clientId, UUID actorId) {
        Candidate candidate = getById(id, clientId);
        candidateRepository.delete(candidate);
        logActivity(clientId, actorId, "CANDIDATE_DELETED", id,
                Map.of("name", candidate.getName()));
    }

    @Transactional
    public Candidate updateStatus(UUID id, UUID clientId, CandidateStatus newStatus, UUID actorId) {
        Candidate candidate = getById(id, clientId);
        CandidateStatus old = candidate.getStatus();

        // Terminal state guard (mirrors Python FSM)
        if (old == CandidateStatus.LEFT_COMPANY || old == CandidateStatus.REJECTED) {
            throw new BusinessRuleException(
                    "Cannot transition from terminal state " + old);
        }

        candidate.setStatus(newStatus);
        Candidate saved = candidateRepository.save(candidate);

        logActivity(clientId, actorId, "CANDIDATE_STATUS_CHANGED", id,
                Map.of("from", old.name(), "to", newStatus.name()));

        return saved;
    }

    @Transactional
    public Candidate updateResumeFilePath(UUID id, UUID clientId, String filePath, String resumeUrl) {
        Candidate candidate = getById(id, clientId);
        candidate.setResumeFilePath(filePath);
        if (resumeUrl != null) candidate.setResumeUrl(resumeUrl);
        return candidateRepository.save(candidate);
    }

    private void logActivity(UUID clientId, UUID userId, String actionType, UUID entityId, Map<String, Object> details) {
        try {
            activityLogRepository.save(ActivityLog.builder()
                    .clientId(clientId)
                    .userId(userId)
                    .actionType(actionType)
                    .entityId(entityId)
                    .details(details)
                    .build());
        } catch (Exception e) {
            log.warn("Failed to write activity log: {}", e.getMessage());
        }
    }
}
