package com.ats.api.controller;

import com.ats.domain.entity.Candidate;
import com.ats.domain.entity.User;
import com.ats.domain.enums.CandidateStatus;
import com.ats.service.CandidateService;
import com.ats.service.DuplicateDetectionService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.security.SecurityRequirement;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Sort;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.List;
import java.util.Map;
import java.util.UUID;

/**
 * Candidate REST controller.
 * Maps to /api/v1/candidates/* matching the Python FastAPI candidates router.
 */
@Tag(name = "Candidates", description = "Candidate management APIs")
@RestController
@RequestMapping("/api/v1/candidates")
@SecurityRequirement(name = "bearerAuth")
@RequiredArgsConstructor
public class CandidateController {

    private final CandidateService candidateService;
    private final DuplicateDetectionService duplicateDetectionService;

    @Operation(summary = "List all candidates (paginated)")
    @GetMapping
    public ResponseEntity<Page<Candidate>> listCandidates(
            @AuthenticationPrincipal User user,
            @RequestParam(defaultValue = "0") int page,
            @RequestParam(defaultValue = "20") int size,
            @RequestParam(defaultValue = "createdAt") String sortBy,
            @RequestParam(defaultValue = "desc") String sortDir) {

        Sort sort = sortDir.equalsIgnoreCase("asc")
                ? Sort.by(sortBy).ascending()
                : Sort.by(sortBy).descending();

        Page<Candidate> candidates = candidateService.listCandidates(
                user.getClientId(), PageRequest.of(page, size, sort));

        return ResponseEntity.ok(candidates);
    }

    @Operation(summary = "Get a candidate by ID")
    @GetMapping("/{id}")
    public ResponseEntity<Candidate> getCandidate(
            @AuthenticationPrincipal User user,
            @PathVariable UUID id) {
        return ResponseEntity.ok(candidateService.getById(id, user.getClientId()));
    }

    @Operation(summary = "Create a new candidate")
    @PostMapping
    public ResponseEntity<Candidate> createCandidate(
            @AuthenticationPrincipal User user,
            @RequestBody Map<String, Object> body) {

        Candidate candidate = buildCandidateFromBody(body, user.getClientId());
        Candidate saved = candidateService.create(candidate, user.getId());
        return ResponseEntity.status(HttpStatus.CREATED).body(saved);
    }

    @Operation(summary = "Update an existing candidate")
    @PutMapping("/{id}")
    public ResponseEntity<Candidate> updateCandidate(
            @AuthenticationPrincipal User user,
            @PathVariable UUID id,
            @RequestBody Map<String, Object> body) {

        Candidate updates = buildCandidateFromBody(body, user.getClientId());
        return ResponseEntity.ok(candidateService.update(id, user.getClientId(), updates, user.getId()));
    }

    @Operation(summary = "Delete a candidate")
    @DeleteMapping("/{id}")
    public ResponseEntity<Void> deleteCandidate(
            @AuthenticationPrincipal User user,
            @PathVariable UUID id) {
        candidateService.delete(id, user.getClientId(), user.getId());
        return ResponseEntity.noContent().build();
    }

    @Operation(summary = "Update candidate status (FSM transition)")
    @PatchMapping("/{id}/status")
    public ResponseEntity<Candidate> updateStatus(
            @AuthenticationPrincipal User user,
            @PathVariable UUID id,
            @RequestBody Map<String, String> body) {

        CandidateStatus newStatus;
        try {
            newStatus = CandidateStatus.valueOf(body.get("status").toUpperCase());
        } catch (IllegalArgumentException e) {
            return ResponseEntity.badRequest().build();
        }

        return ResponseEntity.ok(
                candidateService.updateStatus(id, user.getClientId(), newStatus, user.getId()));
    }

    @Operation(summary = "Check for duplicate candidates")
    @PostMapping("/check-duplicates")
    public ResponseEntity<List<Map<String, Object>>> checkDuplicates(
            @AuthenticationPrincipal User user,
            @RequestBody Map<String, String> body) {

        List<DuplicateDetectionService.DuplicateMatch> matches =
                duplicateDetectionService.findDuplicates(
                        user.getClientId(),
                        body.get("name"),
                        body.get("email"),
                        body.get("phone"));

        List<Map<String, Object>> result = matches.stream()
                .map(m -> Map.<String, Object>of(
                        "candidate_id", m.candidate().getId(),
                        "name", m.candidate().getName(),
                        "email", m.candidate().getEmail() != null ? m.candidate().getEmail() : "",
                        "score", m.score(),
                        "reason", m.reason()))
                .toList();

        return ResponseEntity.ok(result);
    }

    // ─── Builder helper (avoids a full DTO class for brevity) ───────────
    @SuppressWarnings("unchecked")
    private Candidate buildCandidateFromBody(Map<String, Object> body, UUID clientId) {
        Candidate.CandidateBuilder builder = Candidate.builder().clientId(clientId);

        if (body.containsKey("name"))           builder.name((String) body.get("name"));
        if (body.containsKey("email"))          builder.email((String) body.get("email"));
        if (body.containsKey("phone"))          builder.phone((String) body.get("phone"));
        if (body.containsKey("company"))        builder.company((String) body.get("company"));
        if (body.containsKey("location"))       builder.location((String) body.get("location"));
        if (body.containsKey("key_skill"))      builder.keySkill((String) body.get("key_skill"));
        if (body.containsKey("remark"))         builder.remark((String) body.get("remark"));
        if (body.containsKey("linkedin_url"))   builder.linkedinUrl((String) body.get("linkedin_url"));
        if (body.containsKey("source"))         builder.source((String) body.get("source"));
        if (body.containsKey("skills"))         builder.skills((List<String>) body.get("skills"));
        if (body.containsKey("experience"))     builder.experience((List<java.util.Map<String, Object>>) body.get("experience"));
        if (body.containsKey("other_details"))  builder.otherDetails((Map<String, Object>) body.get("other_details"));

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
        if (body.containsKey("assigned_user_id"))
            builder.assignedUserId(UUID.fromString((String) body.get("assigned_user_id")));

        return builder.build();
    }
}
