package com.ats.api.controller;

import com.ats.domain.entity.Job;
import com.ats.domain.entity.User;
import com.ats.domain.enums.UserRole;
import com.ats.exception.AtsException;
import com.ats.service.JobService;
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

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.List;
import java.util.Map;
import java.util.UUID;

/**
 * Job REST controller — /api/v1/jobs/*
 */
@Tag(name = "Jobs", description = "Job posting management")
@RestController
@RequestMapping("/api/v1/jobs")
@SecurityRequirement(name = "bearerAuth")
@RequiredArgsConstructor
public class JobController {

    private static final int MAX_PAGE_SIZE = 200;
    private final JobService jobService;

    private void assertTenantContext(User user) {
        if (user.getClientId() == null && user.getRole() != UserRole.super_admin) {
            throw new AtsException("Tenant context required", HttpStatus.FORBIDDEN);
        }
    }

    @Operation(summary = "List all jobs (paginated)")
    @GetMapping
    @PreAuthorize("hasAnyRole('SUPER_ADMIN','ADMIN','HR_MANAGER','HR_RECRUITER','CLIENT_ADMIN','CLIENT_USER')")
    public ResponseEntity<Page<Job>> listJobs(
            @AuthenticationPrincipal User user,
            @RequestParam(defaultValue = "0")  int page,
            @RequestParam(defaultValue = "20") int size) {
        assertTenantContext(user);
        size = Math.min(size, MAX_PAGE_SIZE);
        return ResponseEntity.ok(
                jobService.listJobs(user.getClientId(), PageRequest.of(page, size,
                        Sort.by("createdAt").descending())));
    }

    @Operation(summary = "Get a job by ID")
    @GetMapping("/{id}")
    @PreAuthorize("hasAnyRole('SUPER_ADMIN','ADMIN','HR_MANAGER','HR_RECRUITER','CLIENT_ADMIN','CLIENT_USER')")
    public ResponseEntity<Job> getJob(
            @AuthenticationPrincipal User user,
            @PathVariable UUID id) {
        assertTenantContext(user);
        return ResponseEntity.ok(jobService.getById(id, user.getClientId()));
    }

    @Operation(summary = "Get vacant open jobs")
    @GetMapping("/vacant")
    @PreAuthorize("hasAnyRole('SUPER_ADMIN','ADMIN','HR_MANAGER','HR_RECRUITER','CLIENT_ADMIN','CLIENT_USER')")
    public ResponseEntity<List<Job>> getVacantJobs(@AuthenticationPrincipal User user) {
        assertTenantContext(user);
        return ResponseEntity.ok(jobService.getVacantOpenJobs(user.getClientId()));
    }

    @Operation(summary = "Create a new job posting")
    @PostMapping
    @PreAuthorize("hasAnyRole('SUPER_ADMIN','ADMIN','HR_MANAGER','HR_RECRUITER')")
    public ResponseEntity<Job> createJob(
            @AuthenticationPrincipal User user,
            @RequestBody Map<String, Object> body) {
        assertTenantContext(user);
        // clientId always from principal — body-supplied client_id is ignored (mass-assignment prevention)
        Job job = buildJobFromBody(body, user.getClientId());
        return ResponseEntity.status(HttpStatus.CREATED).body(jobService.create(job));
    }

    @Operation(summary = "Update a job posting")
    @PutMapping("/{id}")
    @PreAuthorize("hasAnyRole('SUPER_ADMIN','ADMIN','HR_MANAGER','HR_RECRUITER')")
    public ResponseEntity<Job> updateJob(
            @AuthenticationPrincipal User user,
            @PathVariable UUID id,
            @RequestBody Map<String, Object> body) {
        assertTenantContext(user);
        Job updates = buildJobFromBody(body, user.getClientId());
        return ResponseEntity.ok(jobService.update(id, user.getClientId(), updates));
    }

    @Operation(summary = "Delete a job posting")
    @DeleteMapping("/{id}")
    @PreAuthorize("hasAnyRole('SUPER_ADMIN','ADMIN','HR_MANAGER')")
    public ResponseEntity<Void> deleteJob(
            @AuthenticationPrincipal User user,
            @PathVariable UUID id) {
        assertTenantContext(user);
        jobService.delete(id, user.getClientId());
        return ResponseEntity.noContent().build();
    }

    private Job buildJobFromBody(Map<String, Object> body, UUID clientId) {
        Job.JobBuilder builder = Job.builder().clientId(clientId);

        if (body.containsKey("title"))            builder.title((String) body.get("title"));
        if (body.containsKey("company_name"))     builder.companyName((String) body.get("company_name"));
        if (body.containsKey("requirements"))     builder.requirements((String) body.get("requirements"));
        if (body.containsKey("department"))       builder.department((String) body.get("department"));
        if (body.containsKey("location"))         builder.location((String) body.get("location"));
        if (body.containsKey("employment_type"))  builder.employmentType((String) body.get("employment_type"));
        if (body.containsKey("status"))           builder.status((String) body.get("status"));
        if (body.containsKey("openings_count"))   builder.openingsCount(Integer.parseInt(body.get("openings_count").toString()));
        if (body.containsKey("experience_required")) builder.experienceRequired(Integer.parseInt(body.get("experience_required").toString()));
        if (body.containsKey("salary_lpa"))       builder.salaryLpa(new BigDecimal(body.get("salary_lpa").toString()));
        if (body.containsKey("vacant"))           builder.vacant((Boolean) body.get("vacant"));
        if (body.containsKey("submitted_by_client")) builder.submittedByClient((Boolean) body.get("submitted_by_client"));
        if (body.containsKey("posting_date"))     builder.postingDate(LocalDate.parse((String) body.get("posting_date")));
        if (body.containsKey("closing_date"))     builder.closingDate(LocalDate.parse((String) body.get("closing_date")));

        return builder.build();
    }
}
