package com.ats.api.controller;

import com.ats.domain.entity.ActivityLog;
import com.ats.domain.entity.User;
import com.ats.domain.repository.ActivityLogRepository;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.security.SecurityRequirement;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.RequiredArgsConstructor;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Sort;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.UUID;

/**
 * Activity Log REST controller — /api/v1/activity-logs/*
 * All queries are scoped to the authenticated user's tenant (clientId).
 */
@Tag(name = "Activity Logs", description = "Audit and activity log access")
@RestController
@RequestMapping("/api/v1/activity-logs")
@SecurityRequirement(name = "bearerAuth")
@RequiredArgsConstructor
public class ActivityLogController {

    private static final int MAX_PAGE_SIZE = 200;
    private final ActivityLogRepository activityLogRepository;

    @Operation(summary = "List activity logs for the current tenant (paginated)")
    @GetMapping
    @PreAuthorize("hasAnyRole('SUPER_ADMIN','ADMIN','HR_MANAGER')")
    public ResponseEntity<Page<ActivityLog>> listActivityLogs(
            @AuthenticationPrincipal User user,
            @RequestParam(defaultValue = "0")  int page,
            @RequestParam(defaultValue = "50") int size) {

        size = Math.min(size, MAX_PAGE_SIZE);
        return ResponseEntity.ok(
                activityLogRepository.findAllByClientIdOrderByCreatedAtDesc(
                        user.getClientId(),
                        PageRequest.of(page, size, Sort.by("createdAt").descending())));
    }

    @Operation(summary = "Get activity logs for a specific entity (tenant-scoped)")
    @GetMapping("/entity/{entityId}")
    @PreAuthorize("hasAnyRole('SUPER_ADMIN','ADMIN','HR_MANAGER')")
    public ResponseEntity<List<ActivityLog>> getLogsForEntity(
            @AuthenticationPrincipal User user,   // was missing — fixed
            @PathVariable UUID entityId) {
        return ResponseEntity.ok(
                activityLogRepository.findByClientIdAndEntityIdOrderByCreatedAtDesc(
                        user.getClientId(), entityId));
    }

    @Operation(summary = "Get activity logs by action type (tenant-scoped)")
    @GetMapping("/type/{actionType}")
    @PreAuthorize("hasAnyRole('SUPER_ADMIN','ADMIN','HR_MANAGER')")
    public ResponseEntity<List<ActivityLog>> getLogsByType(
            @AuthenticationPrincipal User user,
            @PathVariable String actionType) {
        return ResponseEntity.ok(
                activityLogRepository.findByClientIdAndActionTypeOrderByCreatedAtDesc(
                        user.getClientId(), actionType.toUpperCase()));
    }
}
