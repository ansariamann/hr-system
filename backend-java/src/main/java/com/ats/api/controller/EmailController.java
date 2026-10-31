package com.ats.api.controller;

import com.ats.domain.entity.User;
import com.ats.email.EmailIngestionService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.security.SecurityRequirement;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;
import java.util.UUID;

@Tag(name = "Email Ingestion", description = "IMAP email mailbox poller and resume pipeline")
@RestController
@RequestMapping("/api/v1/email")
@SecurityRequirement(name = "bearerAuth")
@RequiredArgsConstructor
public class EmailController {

    private final EmailIngestionService emailIngestionService;

    @Operation(summary = "Trigger immediate IMAP mailbox poll for resumes")
    @PostMapping({"/poll", "/poll-imap"})
    @PreAuthorize("hasAnyRole('SUPER_ADMIN','ADMIN','HR_MANAGER')")
    public ResponseEntity<EmailIngestionService.PollResult> pollMailbox(@AuthenticationPrincipal User user) {
        EmailIngestionService.PollResult result = emailIngestionService.pollInbox(user.getClientId(), user.getId());
        return ResponseEntity.ok(result);
    }

    @Operation(summary = "Get IMAP poller configuration and health status")
    @GetMapping("/status")
    @PreAuthorize("hasAnyRole('SUPER_ADMIN','ADMIN','HR_MANAGER')")
    public ResponseEntity<Map<String, Object>> getStatus() {
        return ResponseEntity.ok(emailIngestionService.getStatus());
    }
}

