package com.ats.api.controller;

import com.ats.domain.entity.Candidate;
import com.ats.domain.entity.ResumeJob;
import com.ats.domain.entity.User;
import com.ats.domain.repository.ResumeJobRepository;
import com.ats.resume.ResumeParserService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.security.SecurityRequirement;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

import java.io.File;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.nio.file.StandardCopyOption;
import java.util.*;

@Slf4j
@Tag(name = "Resume Ingestion", description = "Endpoints for single and bulk resume file upload and parsing")
@RestController
@RequestMapping("/api/v1/candidates")
@SecurityRequirement(name = "bearerAuth")
@RequiredArgsConstructor
public class ResumeUploadController {

    private final ResumeParserService resumeParserService;
    private final ResumeJobRepository resumeJobRepository;

    @Value("${app.storage.upload-dir:./uploads}")
    private String uploadDir;

    private static final Set<String> ALLOWED_EXTENSIONS = Set.of("pdf", "docx", "doc", "txt", "rtf");

    private String validateAndSanitizeFilename(String rawFilename) {
        if (rawFilename == null || rawFilename.isBlank()) {
            return "resume.pdf";
        }
        // Extract base filename without path components to prevent path traversal
        String sanitized = Paths.get(rawFilename).getFileName().toString().replaceAll("[^a-zA-Z0-9._-]", "_");
        int dotIndex = sanitized.lastIndexOf('.');
        if (dotIndex == -1 || dotIndex == sanitized.length() - 1) {
            throw new IllegalArgumentException("File must have a valid extension: " + ALLOWED_EXTENSIONS);
        }
        String ext = sanitized.substring(dotIndex + 1).toLowerCase();
        if (!ALLOWED_EXTENSIONS.contains(ext)) {
            throw new IllegalArgumentException("Unsupported file format: ." + ext + ". Allowed: " + ALLOWED_EXTENSIONS);
        }
        return sanitized;
    }

    @Operation(summary = "Upload single resume and auto-create candidate")
    @PostMapping(value = {"/upload-resume", "/upload"}, consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    @PreAuthorize("hasAnyRole('SUPER_ADMIN','ADMIN','HR_MANAGER','HR_RECRUITER')")
    public ResponseEntity<Candidate> uploadResume(
            @AuthenticationPrincipal User user,
            @RequestParam("file") MultipartFile file) {  // clientId param removed — always from principal

        UUID effectiveClientId = user.getClientId();
        UUID userId = user.getId();

        if (file.isEmpty()) {
            return ResponseEntity.badRequest().build();
        }

        try {
            String originalName = validateAndSanitizeFilename(file.getOriginalFilename());
            Path targetDir = Paths.get(uploadDir);
            if (!Files.exists(targetDir)) {
                Files.createDirectories(targetDir);
            }

            String savedFileName = UUID.randomUUID() + "_" + originalName;
            Path targetPath = targetDir.resolve(savedFileName);

            Files.copy(file.getInputStream(), targetPath, StandardCopyOption.REPLACE_EXISTING);

            Candidate created = resumeParserService.parseAndIngest(
                    targetPath.toFile(), originalName, effectiveClientId, userId);

            return ResponseEntity.status(HttpStatus.CREATED).body(created);

        } catch (IllegalArgumentException e) {
            log.warn("Invalid resume file uploaded: {}", e.getMessage());
            return ResponseEntity.badRequest().build();
        } catch (IOException e) {
            log.error("Failed to process uploaded resume: {}", e.getMessage(), e);
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).build();
        }
    }

    @Operation(summary = "Bulk upload multiple resumes and auto-create candidates")
    @PostMapping(value = "/bulk-upload", consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    @PreAuthorize("hasAnyRole('SUPER_ADMIN','ADMIN','HR_MANAGER','HR_RECRUITER')")
    public ResponseEntity<Map<String, Object>> bulkUploadResumes(
            @AuthenticationPrincipal User user,
            @RequestParam("files") MultipartFile[] files) {  // clientId param removed — always from principal

        UUID effectiveClientId = user.getClientId();
        UUID userId = user.getId();

        if (files == null || files.length == 0) {
            return ResponseEntity.badRequest().body(Map.of("error", "No files provided"));
        }

        List<Candidate> createdCandidates = new ArrayList<>();
        List<Map<String, String>> errors = new ArrayList<>();

        Path targetDir = Paths.get(uploadDir);
        try {
            if (!Files.exists(targetDir)) {
                Files.createDirectories(targetDir);
            }
        } catch (IOException e) {
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
                    .body(Map.of("error", "Failed to initialize storage"));
        }

        for (MultipartFile file : files) {
            if (file.isEmpty()) continue;
            String originalName = file.getOriginalFilename() != null ? file.getOriginalFilename() : "resume.pdf";
            try {
                originalName = validateAndSanitizeFilename(originalName);
                String savedFileName = UUID.randomUUID() + "_" + originalName;
                Path targetPath = targetDir.resolve(savedFileName);
                Files.copy(file.getInputStream(), targetPath, StandardCopyOption.REPLACE_EXISTING);

                Candidate c = resumeParserService.parseAndIngest(
                        targetPath.toFile(), originalName, effectiveClientId, userId);
                createdCandidates.add(c);
            } catch (Exception e) {
                log.warn("Failed to parse file {}: {}", originalName, e.getMessage());
                errors.add(Map.of("file", originalName, "error", e.getMessage()));
            }
        }

        Map<String, Object> response = new LinkedHashMap<>();
        response.put("totalReceived", files.length);
        response.put("succeededCount", createdCandidates.size());
        response.put("failedCount", errors.size());
        response.put("candidates", createdCandidates);
        response.put("errors", errors);

        return ResponseEntity.ok(response);
    }

    @Operation(summary = "List all resume ingestion processing jobs")
    @GetMapping("/resume-jobs")
    @PreAuthorize("hasAnyRole('SUPER_ADMIN','ADMIN','HR_MANAGER','HR_RECRUITER')")
    public ResponseEntity<List<ResumeJob>> listResumeJobs(@AuthenticationPrincipal User user) {
        // Always scope to the authenticated tenant
        return ResponseEntity.ok(resumeJobRepository.findAllByClientIdOrderByCreatedAtDesc(user.getClientId()));
    }
}

