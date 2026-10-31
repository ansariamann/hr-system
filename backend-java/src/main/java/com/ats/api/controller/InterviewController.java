package com.ats.api.controller;

import com.ats.domain.entity.InterviewRecord;
import com.ats.domain.entity.User;
import com.ats.domain.repository.CandidateRepository;
import com.ats.domain.repository.InterviewRecordRepository;
import com.ats.domain.repository.JobRepository;
import com.ats.exception.ResourceNotFoundException;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.security.SecurityRequirement;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.RequiredArgsConstructor;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Sort;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;

import java.time.Instant;
import java.util.List;
import java.util.Map;
import java.util.UUID;

/**
 * Interview Record REST controller — /api/v1/interviews/*
 * All endpoints are scoped to the authenticated user's clientId (tenant).
 */
@Tag(name = "Interviews", description = "Direct interview record management")
@RestController
@RequestMapping("/api/v1/interviews")
@SecurityRequirement(name = "bearerAuth")
@RequiredArgsConstructor
public class InterviewController {

    private static final int MAX_PAGE_SIZE = 200;
    private final InterviewRecordRepository interviewRecordRepository;
    private final CandidateRepository candidateRepository;
    private final JobRepository jobRepository;

    @Operation(summary = "List all interview records (paginated, tenant-scoped)")
    @GetMapping
    @PreAuthorize("hasAnyRole('SUPER_ADMIN','ADMIN','HR_MANAGER','HR_RECRUITER','CLIENT_ADMIN','CLIENT_USER')")
    public ResponseEntity<Page<InterviewRecord>> listInterviews(
            @AuthenticationPrincipal User user,
            @RequestParam(defaultValue = "0")  int page,
            @RequestParam(defaultValue = "20") int size) {

        size = Math.min(size, MAX_PAGE_SIZE);
        return ResponseEntity.ok(
                interviewRecordRepository.findAllByClientIdNotDeleted(
                        user.getClientId(),
                        PageRequest.of(page, size, Sort.by("interviewDate").descending())));
    }

    @Operation(summary = "Get interview records for a candidate (tenant-scoped)")
    @GetMapping("/candidate/{candidateId}")
    @PreAuthorize("hasAnyRole('SUPER_ADMIN','ADMIN','HR_MANAGER','HR_RECRUITER','CLIENT_ADMIN','CLIENT_USER')")
    public ResponseEntity<List<InterviewRecord>> getInterviewsByCandidate(
            @AuthenticationPrincipal User user,   // added — fixes missing tenant check
            @PathVariable UUID candidateId) {
        return ResponseEntity.ok(
                interviewRecordRepository.findByCandidateIdAndClientIdNotDeleted(
                        candidateId, user.getClientId()));
    }

    @Operation(summary = "Get an interview record by ID (tenant-scoped)")
    @GetMapping("/{id}")
    @PreAuthorize("hasAnyRole('SUPER_ADMIN','ADMIN','HR_MANAGER','HR_RECRUITER','CLIENT_ADMIN','CLIENT_USER')")
    public ResponseEntity<InterviewRecord> getInterview(
            @AuthenticationPrincipal User user,
            @PathVariable UUID id) {
        InterviewRecord record = interviewRecordRepository
                .findByIdAndClientId(id, user.getClientId())
                .orElseThrow(() -> new ResourceNotFoundException("InterviewRecord", id));
        if (record.isDeleted()) throw new ResourceNotFoundException("InterviewRecord", id);
        return ResponseEntity.ok(record);
    }

    @Operation(summary = "Create a new interview record")
    @PostMapping
    @PreAuthorize("hasAnyRole('SUPER_ADMIN','ADMIN','HR_MANAGER','HR_RECRUITER')")
    @SuppressWarnings("unchecked")
    public ResponseEntity<InterviewRecord> createInterview(
            @AuthenticationPrincipal User user,
            @RequestBody Map<String, Object> body) {

        InterviewRecord record = InterviewRecord.builder()
                .candidateId(UUID.fromString((String) body.get("candidate_id")))
                .clientId(user.getClientId())   // always from principal
                .companyId(body.containsKey("company_id")
                        ? UUID.fromString((String) body.get("company_id"))
                        : user.getClientId())
                .jobId(body.containsKey("job_id")
                        ? UUID.fromString((String) body.get("job_id")) : null)
                .interviewerId(body.containsKey("interviewer_id")
                        ? UUID.fromString((String) body.get("interviewer_id"))
                        : user.getId())
                .interviewDate(body.containsKey("interview_date")
                        ? Instant.parse((String) body.get("interview_date"))
                        : Instant.now())
                .position(body.containsKey("position") ? (String) body.get("position") : null)
                .skills(body.containsKey("skills")
                        ? (List<String>) body.get("skills") : null)
                .notes(body.containsKey("notes") ? (String) body.get("notes") : null)
                .rating(body.containsKey("rating")
                        ? Integer.parseInt(body.get("rating").toString()) : null)
                .build();

        // Enforce foreign-key tenant ownership
        if (user.getClientId() != null) {
            candidateRepository.findByIdAndClientId(record.getCandidateId(), user.getClientId())
                    .orElseThrow(() -> new ResourceNotFoundException("Candidate", record.getCandidateId()));

            if (record.getJobId() != null) {
                jobRepository.findByIdAndClientId(record.getJobId(), user.getClientId())
                        .orElseThrow(() -> new ResourceNotFoundException("Job", record.getJobId()));
            }
        }

        return ResponseEntity.status(HttpStatus.CREATED)
                .body(interviewRecordRepository.save(record));
    }

    @Operation(summary = "Update an interview record (tenant-scoped)")
    @PutMapping("/{id}")
    @PreAuthorize("hasAnyRole('SUPER_ADMIN','ADMIN','HR_MANAGER','HR_RECRUITER')")
    @SuppressWarnings("unchecked")
    public ResponseEntity<InterviewRecord> updateInterview(
            @AuthenticationPrincipal User user,
            @PathVariable UUID id,
            @RequestBody Map<String, Object> body) {

        InterviewRecord record = interviewRecordRepository
                .findByIdAndClientId(id, user.getClientId())
                .orElseThrow(() -> new ResourceNotFoundException("InterviewRecord", id));

        if (body.containsKey("interview_date")) record.setInterviewDate(Instant.parse((String) body.get("interview_date")));
        if (body.containsKey("position"))       record.setPosition((String) body.get("position"));
        if (body.containsKey("notes"))          record.setNotes((String) body.get("notes"));
        if (body.containsKey("rating"))         record.setRating(Integer.parseInt(body.get("rating").toString()));
        if (body.containsKey("skills"))         record.setSkills((List<String>) body.get("skills"));

        return ResponseEntity.ok(interviewRecordRepository.save(record));
    }

    @Operation(summary = "Soft-delete an interview record (hr_manager or above)")
    @DeleteMapping("/{id}")
    @PreAuthorize("hasAnyRole('SUPER_ADMIN','ADMIN','HR_MANAGER')")
    public ResponseEntity<Void> deleteInterview(
            @AuthenticationPrincipal User user,
            @PathVariable UUID id) {
        InterviewRecord record = interviewRecordRepository
                .findByIdAndClientId(id, user.getClientId())
                .orElseThrow(() -> new ResourceNotFoundException("InterviewRecord", id));
        record.setDeletedAt(Instant.now());
        interviewRecordRepository.save(record);
        return ResponseEntity.noContent().build();
    }
}
