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
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.UUID;

/**
 * Activity Log REST controller — /api/v1/activity-logs/*
 */
@Tag(name = "Activity Logs", description = "Audit and activity log access")
@RestController
@RequestMapping("/api/v1/activity-logs")
@SecurityRequirement(name = "bearerAuth")
@RequiredArgsConstructor
public class ActivityLogController {

    private final ActivityLogRepository activityLogRepository;

    @Operation(summary = "List activity logs for the current tenant (paginated)")
    @GetMapping
    public ResponseEntity<Page<ActivityLog>> listActivityLogs(
            @AuthenticationPrincipal User user,
            @RequestParam(defaultValue = "0") int page,
            @RequestParam(defaultValue = "50") int size) {
        return ResponseEntity.ok(
                activityLogRepository.findAllByClientIdOrderByCreatedAtDesc(
                        user.getClientId(),
                        PageRequest.of(page, size)));
    }

    @Operation(summary = "Get activity logs for a specific entity")
    @GetMapping("/entity/{entityId}")
    public ResponseEntity<List<ActivityLog>> getLogsForEntity(
            @PathVariable UUID entityId) {
        return ResponseEntity.ok(
                activityLogRepository.findByEntityIdOrderByCreatedAtDesc(entityId));
    }

    @Operation(summary = "Get activity logs by action type")
    @GetMapping("/type/{actionType}")
    public ResponseEntity<List<ActivityLog>> getLogsByType(
            @AuthenticationPrincipal User user,
            @PathVariable String actionType) {
        return ResponseEntity.ok(
                activityLogRepository.findByClientIdAndActionTypeOrderByCreatedAtDesc(
                        user.getClientId(), actionType.toUpperCase()));
    }
}
