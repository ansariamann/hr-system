package com.ats.api.controller;

import com.ats.domain.entity.User;
import com.ats.domain.enums.UserRole;
import com.ats.domain.repository.UserRepository;
import com.ats.exception.AtsException;
import com.ats.exception.ResourceNotFoundException;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.security.SecurityRequirement;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;
import java.util.UUID;

/**
 * User management REST controller — /api/v1/users/*
 * Admins can manage users within their client scope.
 */
@Tag(name = "Users", description = "User management within tenant")
@RestController
@RequestMapping("/api/v1/users")
@SecurityRequirement(name = "bearerAuth")
@RequiredArgsConstructor
public class UserController {

    private final UserRepository userRepository;
    private final PasswordEncoder passwordEncoder;

    @Operation(summary = "List all users for the current tenant")
    @GetMapping
    @PreAuthorize("hasAnyRole('SUPER_ADMIN','ADMIN','HR_MANAGER')")
    public ResponseEntity<List<User>> listUsers(@AuthenticationPrincipal User currentUser) {
        return ResponseEntity.ok(userRepository.findAllByClientId(currentUser.getClientId()));
    }

    @Operation(summary = "Get a user by ID")
    @GetMapping("/{id}")
    public ResponseEntity<User> getUser(
            @AuthenticationPrincipal User currentUser,
            @PathVariable UUID id) {
        User user = userRepository.findById(id)
                .orElseThrow(() -> new ResourceNotFoundException("User", id));

        // Non-admins can only view their own profile
        String role = currentUser.getRole().name();
        if (!currentUser.getId().equals(id)
                && !role.equals("super_admin") && !role.equals("admin") && !role.equals("hr_manager")) {
            return ResponseEntity.status(HttpStatus.FORBIDDEN).build();
        }

        return ResponseEntity.ok(user);
    }

    @Operation(summary = "Update a user")
    @PutMapping("/{id}")
    @PreAuthorize("hasAnyRole('SUPER_ADMIN','ADMIN')")
    public ResponseEntity<User> updateUser(
            @AuthenticationPrincipal User currentUser,
            @PathVariable UUID id,
            @RequestBody Map<String, Object> body) {

        User user = userRepository.findById(id)
                .orElseThrow(() -> new ResourceNotFoundException("User", id));

        // Scope: can only edit users in own client
        if (!user.getClientId().equals(currentUser.getClientId())
                && !currentUser.getRole().name().equals("super_admin")) {
            return ResponseEntity.status(HttpStatus.FORBIDDEN).build();
        }

        if (body.containsKey("full_name"))  user.setFullName((String) body.get("full_name"));
        if (body.containsKey("is_active"))  user.setIsActive((Boolean) body.get("is_active"));
        if (body.containsKey("role")) {
            try {
                user.setRole(UserRole.valueOf((String) body.get("role")));
            } catch (IllegalArgumentException e) {
                throw new AtsException("Invalid role: " + body.get("role"), HttpStatus.BAD_REQUEST);
            }
        }

        return ResponseEntity.ok(userRepository.save(user));
    }

    @Operation(summary = "Deactivate a user")
    @DeleteMapping("/{id}")
    @PreAuthorize("hasAnyRole('SUPER_ADMIN','ADMIN')")
    public ResponseEntity<Map<String, String>> deactivateUser(
            @AuthenticationPrincipal User currentUser,
            @PathVariable UUID id) {

        if (currentUser.getId().equals(id)) {
            throw new AtsException("Cannot deactivate yourself", HttpStatus.BAD_REQUEST);
        }

        User user = userRepository.findById(id)
                .orElseThrow(() -> new ResourceNotFoundException("User", id));
        user.setIsActive(false);
        userRepository.save(user);
        return ResponseEntity.ok(Map.of("message", "User deactivated successfully"));
    }
}
