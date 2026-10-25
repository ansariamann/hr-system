package com.ats.api.controller;

import com.ats.domain.entity.InterviewRecord;
import com.ats.domain.entity.User;
import com.ats.domain.repository.InterviewRecordRepository;
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
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;

import java.time.Instant;
import java.util.List;
import java.util.Map;
import java.util.UUID;

/**
 * Interview Record REST controller — /api/v1/interviews/*
 */
@Tag(name = "Interviews", description = "Direct interview record management")
@RestController
@RequestMapping("/api/v1/interviews")
@SecurityRequirement(name = "bearerAuth")
@RequiredArgsConstructor
public class InterviewController {

    private final InterviewRecordRepository interviewRecordRepository;

    @Operation(summary = "List all interview records (paginated)")
    @GetMapping
    public ResponseEntity<Page<InterviewRecord>> listInterviews(
            @AuthenticationPrincipal User user,
            @RequestParam(defaultValue = "0") int page,
            @RequestParam(defaultValue = "20") int size) {
        return ResponseEntity.ok(
                interviewRecordRepository.findAllByClientIdNotDeleted(
                        user.getClientId(),
                        PageRequest.of(page, size, Sort.by("interviewDate").descending())));
    }

    @Operation(summary = "Get interview records for a candidate")
    @GetMapping("/candidate/{candidateId}")
    public ResponseEntity<List<InterviewRecord>> getInterviewsByCandidate(
            @PathVariable UUID candidateId) {
        return ResponseEntity.ok(
                interviewRecordRepository.findByCandidateIdNotDeleted(candidateId));
    }

    @Operation(summary = "Get an interview record by ID")
    @GetMapping("/{id}")
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
    @SuppressWarnings("unchecked")
    public ResponseEntity<InterviewRecord> createInterview(
            @AuthenticationPrincipal User user,
            @RequestBody Map<String, Object> body) {

        InterviewRecord record = InterviewRecord.builder()
                .candidateId(UUID.fromString((String) body.get("candidate_id")))
                .clientId(user.getClientId())
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
                        ? (java.util.List<String>) body.get("skills") : null)
                .notes(body.containsKey("notes") ? (String) body.get("notes") : null)
                .rating(body.containsKey("rating")
                        ? Integer.parseInt(body.get("rating").toString()) : null)
                .build();

        return ResponseEntity.status(HttpStatus.CREATED)
                .body(interviewRecordRepository.save(record));
    }

    @Operation(summary = "Update an interview record")
    @PutMapping("/{id}")
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
        if (body.containsKey("skills"))         record.setSkills((java.util.List<String>) body.get("skills"));

        return ResponseEntity.ok(interviewRecordRepository.save(record));
    }

    @Operation(summary = "Soft-delete an interview record")
    @DeleteMapping("/{id}")
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
