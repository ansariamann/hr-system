package com.ats.api.controller;

import com.ats.domain.entity.Candidate;
import com.ats.domain.entity.User;
import com.ats.domain.enums.CandidateStatus;
import com.ats.domain.enums.UserRole;
import com.ats.exception.AtsException;
import com.ats.service.CandidateService;
import com.ats.service.DuplicateDetectionService;
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
 * Candidate REST controller.
 * All mutations require at least hr_recruiter; deletes require hr_manager or above.
 * clientId is ALWAYS derived from the authenticated principal, never the request body.
 */
@Tag(name = "Candidates", description = "Candidate management APIs")
@RestController
@RequestMapping("/api/v1/candidates")
@SecurityRequirement(name = "bearerAuth")
@RequiredArgsConstructor
public class CandidateController {

    /** Hard cap to prevent DoS via large page requests. */
    private static final int MAX_PAGE_SIZE = 200;

    private final CandidateService candidateService;
    private final DuplicateDetectionService duplicateDetectionService;

    private static final java.util.Set<String> ALLOWED_SORT_FIELDS = java.util.Set.of(
            "createdAt", "updatedAt", "name", "email", "totalExperienceYears",
            "status", "location", "company"
    );

    private void assertTenantContext(User user) {
        if (user.getClientId() == null && user.getRole() != UserRole.super_admin) {
            throw new AtsException("Tenant context required", HttpStatus.FORBIDDEN);
        }
    }

    private Candidate sanitizeForRole(Candidate candidate, User user) {
        if (candidate == null) return null;
        if (user.getRole() == UserRole.client_admin || user.getRole() == UserRole.client_user) {
            candidate.setRemark(null);
            candidate.setIsBlacklisted(null);
            candidate.setOtherDetails(null);
            candidate.setCtcCurrent(null);
            candidate.setCtcExpected(null);
        }
        return candidate;
    }

    @Operation(summary = "List all candidates (paginated)")
    @GetMapping
    @PreAuthorize("hasAnyRole('SUPER_ADMIN','ADMIN','HR_MANAGER','HR_RECRUITER','CLIENT_ADMIN','CLIENT_USER')")
    public ResponseEntity<Page<Candidate>> listCandidates(
            @AuthenticationPrincipal User user,
            @RequestParam(defaultValue = "0")  int page,
            @RequestParam(defaultValue = "20") int size,
            @RequestParam(defaultValue = "createdAt") String sortBy,
            @RequestParam(defaultValue = "desc")      String sortDir) {

        assertTenantContext(user);
        size = Math.min(size, MAX_PAGE_SIZE);

        String validSortBy = ALLOWED_SORT_FIELDS.contains(sortBy) ? sortBy : "createdAt";
        Sort sort = sortDir.equalsIgnoreCase("asc")
                ? Sort.by(validSortBy).ascending()
                : Sort.by(validSortBy).descending();

        Page<Candidate> candidates = candidateService.listCandidates(
                user.getClientId(), PageRequest.of(page, size, sort));

        if (user.getRole() == UserRole.client_admin || user.getRole() == UserRole.client_user) {
            candidates.forEach(c -> sanitizeForRole(c, user));
        }

        return ResponseEntity.ok(candidates);
    }

    @Operation(summary = "Get a candidate by ID")
    @GetMapping("/{id}")
    @PreAuthorize("hasAnyRole('SUPER_ADMIN','ADMIN','HR_MANAGER','HR_RECRUITER','CLIENT_ADMIN','CLIENT_USER')")
    public ResponseEntity<Candidate> getCandidate(
            @AuthenticationPrincipal User user,
            @PathVariable UUID id) {
        assertTenantContext(user);
        Candidate candidate = candidateService.getById(id, user.getClientId());
        return ResponseEntity.ok(sanitizeForRole(candidate, user));
    }

    @Operation(summary = "Create a new candidate")
    @PostMapping
    @PreAuthorize("hasAnyRole('SUPER_ADMIN','ADMIN','HR_MANAGER','HR_RECRUITER')")
    public ResponseEntity<Candidate> createCandidate(
            @AuthenticationPrincipal User user,
            @RequestBody Map<String, Object> body) {

        assertTenantContext(user);
        // clientId always comes from the principal — never from the body
        Candidate candidate = buildCandidateFromBody(body, user.getClientId());
        Candidate saved = candidateService.create(candidate, user.getId());
        return ResponseEntity.status(HttpStatus.CREATED).body(saved);
    }

    @Operation(summary = "Update an existing candidate")
    @PutMapping("/{id}")
    @PreAuthorize("hasAnyRole('SUPER_ADMIN','ADMIN','HR_MANAGER','HR_RECRUITER')")
    public ResponseEntity<Candidate> updateCandidate(
            @AuthenticationPrincipal User user,
            @PathVariable UUID id,
            @RequestBody Map<String, Object> body) {

        assertTenantContext(user);
        Candidate updates = buildCandidateFromBody(body, user.getClientId());
        return ResponseEntity.ok(candidateService.update(id, user.getClientId(), updates, user.getId()));
    }

    @Operation(summary = "Delete a candidate")
    @DeleteMapping("/{id}")
    @PreAuthorize("hasAnyRole('SUPER_ADMIN','ADMIN','HR_MANAGER')")
    public ResponseEntity<Void> deleteCandidate(
            @AuthenticationPrincipal User user,
            @PathVariable UUID id) {
        assertTenantContext(user);
        candidateService.delete(id, user.getClientId(), user.getId());
        return ResponseEntity.noContent().build();
    }

    @Operation(summary = "Update candidate status (FSM transition)")
    @PatchMapping("/{id}/status")
    @PreAuthorize("hasAnyRole('SUPER_ADMIN','ADMIN','HR_MANAGER','HR_RECRUITER')")
    public ResponseEntity<Candidate> updateStatus(
            @AuthenticationPrincipal User user,
            @PathVariable UUID id,
            @RequestBody Map<String, String> body) {

        assertTenantContext(user);
        CandidateStatus newStatus;
        try {
            newStatus = CandidateStatus.valueOf(body.get("status").toUpperCase());
        } catch (IllegalArgumentException | NullPointerException e) {
            return ResponseEntity.badRequest().build();
        }

        return ResponseEntity.ok(
                candidateService.updateStatus(id, user.getClientId(), newStatus, user.getId()));
    }

    @Operation(summary = "Check for duplicate candidates")
    @PostMapping("/check-duplicates")
    @PreAuthorize("hasAnyRole('SUPER_ADMIN','ADMIN','HR_MANAGER','HR_RECRUITER')")
    public ResponseEntity<List<Map<String, Object>>> checkDuplicates(
            @AuthenticationPrincipal User user,
            @RequestBody Map<String, String> body) {

        assertTenantContext(user);

        List<DuplicateDetectionService.DuplicateMatch> matches =
                duplicateDetectionService.findDuplicates(
                        user.getClientId(),
                        body.get("name"),
                        body.get("email"),
                        body.get("phone"));

        List<Map<String, Object>> result = matches.stream()
                .map(m -> Map.<String, Object>of(
                        "candidate_id", m.candidate().getId(),
                        "name",         m.candidate().getName(),
                        "email",        m.candidate().getEmail() != null ? m.candidate().getEmail() : "",
                        "score",        m.score(),
                        "reason",       m.reason()))
                .toList();

        return ResponseEntity.ok(result);
    }

    // ─── Private builder — clientId is injected from the principal, NEVER from body ─
    @SuppressWarnings("unchecked")
    private Candidate buildCandidateFromBody(Map<String, Object> body, UUID principalClientId) {
        Candidate.CandidateBuilder builder = Candidate.builder()
                .clientId(principalClientId); // always use the authenticated tenant

        if (body.containsKey("name"))          builder.name((String) body.get("name"));
        if (body.containsKey("email"))         builder.email((String) body.get("email"));
        if (body.containsKey("phone"))         builder.phone((String) body.get("phone"));
        if (body.containsKey("company"))       builder.company((String) body.get("company"));
        if (body.containsKey("location"))      builder.location((String) body.get("location"));
        if (body.containsKey("key_skill"))     builder.keySkill((String) body.get("key_skill"));
        if (body.containsKey("remark"))        builder.remark((String) body.get("remark"));
        if (body.containsKey("linkedin_url"))  builder.linkedinUrl((String) body.get("linkedin_url"));
        if (body.containsKey("source"))        builder.source((String) body.get("source"));
        if (body.containsKey("skills"))        builder.skills((List<String>) body.get("skills"));
        if (body.containsKey("experience"))    builder.experience((List<Map<String, Object>>) body.get("experience"));
        if (body.containsKey("other_details")) builder.otherDetails((Map<String, Object>) body.get("other_details"));
        if (body.containsKey("selected_client_name"))
            builder.selectedClientName((String) body.get("selected_client_name"));

        if (body.containsKey("ctc_current"))
            builder.ctcCurrent(new BigDecimal(body.get("ctc_current").toString()));
        if (body.containsKey("ctc_expected"))
            builder.ctcExpected(new BigDecimal(body.get("ctc_expected").toString()));
        if (body.containsKey("total_experience_years"))
            builder.totalExperienceYears(new BigDecimal(body.get("total_experience_years").toString()));
        if (body.containsKey("notice_period_days"))
            builder.noticePeriodDays(Integer.parseInt(body.get("notice_period_days").toString()));
        if (body.containsKey("date_of_birth"))
            builder.dateOfBirth(LocalDate.parse((String) body.get("date_of_birth")));
        if (body.containsKey("assigned_user_id") && body.get("assigned_user_id") != null
                && !body.get("assigned_user_id").toString().isBlank()) {
            try { builder.assignedUserId(UUID.fromString(body.get("assigned_user_id").toString())); }
            catch (IllegalArgumentException ignored) {}
        }

        // NOTE: client_id from request body is intentionally ignored to prevent mass-assignment.
        return builder.build();
    }
}
