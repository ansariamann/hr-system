package com.ats.api.controller;

import com.ats.api.dto.request.LoginRequest;
import com.ats.api.dto.request.RegisterRequest;
import com.ats.api.dto.response.TokenResponse;
import com.ats.domain.entity.User;
import com.ats.service.AuthService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.security.SecurityRequirement;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

/**
 * Authentication controller.
 * Maps to /api/v1/auth/* matching the Python FastAPI auth router.
 */
@Tag(name = "Authentication", description = "Login, register, and password management")
@RestController
@RequestMapping("/api/v1/auth")
@RequiredArgsConstructor
public class AuthController {

    private final AuthService authService;

    @Operation(summary = "Login with email and password")
    @PostMapping("/login")
    public ResponseEntity<TokenResponse> login(@Valid @RequestBody LoginRequest request) {
        AuthService.LoginResult result = authService.login(request.getEmail(), request.getPassword());
        User user = result.user();

        TokenResponse response = TokenResponse.builder()
                .accessToken(result.accessToken())
                .tokenType(result.tokenType())
                .expiresIn(result.expiresIn())
                .userId(user.getId())
                .clientId(user.getClientId())
                .email(user.getEmail())
                .fullName(user.getFullName())
                .role(user.getRole().name())
                .build();

        return ResponseEntity.ok(response);
    }

    @Operation(summary = "Register a new user (admin only)")
    @SecurityRequirement(name = "bearerAuth")
    @PostMapping("/register")
    @PreAuthorize("hasAnyRole('SUPER_ADMIN', 'ADMIN')")
    public ResponseEntity<Map<String, Object>> register(
            @AuthenticationPrincipal User caller,
            @Valid @RequestBody RegisterRequest request) {

        // Role and clientId are validated inside AuthService against the caller's privilege
        User user = authService.register(
                caller,
                request.getEmail(),
                request.getPassword(),
                request.getFullName(),
                request.getClientId(),
                request.getRole()
        );

        return ResponseEntity.status(HttpStatus.CREATED).body(Map.of(
                "id", user.getId(),
                "email", user.getEmail(),
                "full_name", user.getFullName() != null ? user.getFullName() : "",
                "role", user.getRole().name(),
                "client_id", user.getClientId() != null ? user.getClientId() : ""
        ));
    }

    @Operation(summary = "Get current authenticated user")
    @SecurityRequirement(name = "bearerAuth")
    @GetMapping("/me")
    public ResponseEntity<Map<String, Object>> getCurrentUser(@AuthenticationPrincipal User user) {
        return ResponseEntity.ok(Map.of(
                "id", user.getId(),
                "email", user.getEmail(),
                "full_name", user.getFullName() != null ? user.getFullName() : "",
                "role", user.getRole().name(),
                "client_id", user.getClientId() != null ? user.getClientId() : "",
                "is_active", user.getIsActive()
        ));
    }

    @Operation(summary = "Change password for authenticated user")
    @SecurityRequirement(name = "bearerAuth")
    @PostMapping("/change-password")
    public ResponseEntity<Map<String, String>> changePassword(
            @AuthenticationPrincipal User user,
            @RequestBody Map<String, String> body) {
        authService.changePassword(user.getId(), body.get("current_password"), body.get("new_password"));
        return ResponseEntity.ok(Map.of("message", "Password changed successfully"));
    }

    @Operation(summary = "Verify token validity")
    @SecurityRequirement(name = "bearerAuth")
    @GetMapping("/verify")
    public ResponseEntity<Map<String, Object>> verifyToken(@AuthenticationPrincipal User user) {
        return ResponseEntity.ok(Map.of(
                "valid", true,
                "user_id", user.getId(),
                "client_id", user.getClientId() != null ? user.getClientId() : "",
                "role", user.getRole().name()
        ));
    }
}
