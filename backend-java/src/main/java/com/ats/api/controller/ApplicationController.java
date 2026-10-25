package com.ats.api.controller;

import com.ats.domain.entity.Application;
import com.ats.domain.entity.User;
import com.ats.domain.enums.ApplicationStatus;
import com.ats.service.ApplicationService;
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
import java.util.Map;
import java.util.UUID;

/**
 * Application REST controller — /api/v1/applications/*
 */
@Tag(name = "Applications", description = "Job application lifecycle management")
@RestController
@RequestMapping("/api/v1/applications")
@SecurityRequirement(name = "bearerAuth")
@RequiredArgsConstructor
public class ApplicationController {

    private final ApplicationService applicationService;

    @Operation(summary = "List all applications (paginated)")
    @GetMapping
    public ResponseEntity<Page<Application>> listApplications(
            @AuthenticationPrincipal User user,
            @RequestParam(defaultValue = "0") int page,
            @RequestParam(defaultValue = "20") int size) {
        return ResponseEntity.ok(
                applicationService.listApplications(user.getClientId(),
                        PageRequest.of(page, size, Sort.by("applicationDate").descending())));
    }

    @Operation(summary = "Get an application by ID")
    @GetMapping("/{id}")
    public ResponseEntity<Application> getApplication(
            @AuthenticationPrincipal User user,
            @PathVariable UUID id) {
        return ResponseEntity.ok(applicationService.getById(id, user.getClientId()));
    }

    @Operation(summary = "Create a new application")
    @PostMapping
    public ResponseEntity<Application> createApplication(
            @AuthenticationPrincipal User user,
            @RequestBody Map<String, Object> body) {

        Application application = Application.builder()
                .clientId(user.getClientId())
                .candidateId(UUID.fromString((String) body.get("candidate_id")))
                .jobId(body.containsKey("job_id") ? UUID.fromString((String) body.get("job_id")) : null)
                .jobTitle(body.containsKey("job_title") ? (String) body.get("job_title") : null)
                .source(body.containsKey("source") ? (String) body.get("source") : "MANUAL")
                .notes(body.containsKey("notes") ? (String) body.get("notes") : null)
                .appliedByUserId(user.getId())
                .applicationDate(Instant.now())
                .status(ApplicationStatus.RECEIVED)
                .build();

        return ResponseEntity.status(HttpStatus.CREATED)
                .body(applicationService.create(application));
    }

    @Operation(summary = "Transition application status (FSM)")
    @PatchMapping("/{id}/status")
    public ResponseEntity<Application> updateStatus(
            @AuthenticationPrincipal User user,
            @PathVariable UUID id,
            @RequestBody Map<String, String> body) {

        ApplicationStatus targetStatus;
        try {
            targetStatus = ApplicationStatus.valueOf(body.get("status").toUpperCase());
        } catch (IllegalArgumentException e) {
            return ResponseEntity.badRequest().build();
        }

        return ResponseEntity.ok(
                applicationService.updateStatus(id, user.getClientId(), targetStatus, user.getId()));
    }

    @Operation(summary = "Acknowledge HR interview")
    @PostMapping("/{id}/hr-interview-acknowledge")
    public ResponseEntity<Application> acknowledgeHrInterview(
            @AuthenticationPrincipal User user,
            @PathVariable UUID id,
            @RequestBody(required = false) Map<String, String> body) {

        String note = body != null ? body.get("note") : null;
        return ResponseEntity.ok(
                applicationService.acknowledgeHrInterview(id, user.getClientId(), user.getId(), note));
    }

    @Operation(summary = "Flag application for review")
    @PostMapping("/{id}/flag")
    public ResponseEntity<Application> flagForReview(
            @AuthenticationPrincipal User user,
            @PathVariable UUID id,
            @RequestBody Map<String, String> body) {
        return ResponseEntity.ok(
                applicationService.flagForReview(id, user.getClientId(), body.get("reason")));
    }

    @Operation(summary = "Soft delete an application")
    @DeleteMapping("/{id}")
    public ResponseEntity<Void> deleteApplication(
            @AuthenticationPrincipal User user,
            @PathVariable UUID id) {
        applicationService.softDelete(id, user.getClientId());
        return ResponseEntity.noContent().build();
    }
}
