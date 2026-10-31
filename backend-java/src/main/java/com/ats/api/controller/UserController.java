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

    /** Returns the highest role this principal is allowed to assign. */
    private UserRole maxAssignableRole(User principal) {
        return switch (principal.getRole()) {
            case super_admin -> UserRole.super_admin;
            case admin       -> UserRole.admin;
            case hr_manager  -> UserRole.hr_manager;
            default          -> UserRole.client_user; // client_admin/client_user cannot promote
        };
    }

    /** True if the role being assigned is within the caller's authority. */
    private boolean canAssignRole(User principal, UserRole target) {
        return target.ordinal() >= maxAssignableRole(principal).ordinal();
        // ordinal: super_admin=0 … client_user=5; higher ordinal = lower privilege
    }

    @Operation(summary = "List all users for the current tenant")
    @GetMapping
    @PreAuthorize("hasAnyRole('SUPER_ADMIN','ADMIN','HR_MANAGER')")
    public ResponseEntity<List<User>> listUsers(@AuthenticationPrincipal User currentUser) {
        if (currentUser.getRole() == UserRole.super_admin) {
            return ResponseEntity.ok(userRepository.findAll());
        }
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
        boolean isSelf = currentUser.getId().equals(id);
        boolean isSameTenant = user.getClientId() != null
                && user.getClientId().equals(currentUser.getClientId());
        boolean isElevated = currentUser.getRole() == UserRole.super_admin
                || ((currentUser.getRole() == UserRole.admin || currentUser.getRole() == UserRole.hr_manager)
                    && isSameTenant);

        if (!isSelf && !isElevated) {
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

        // Scope: super_admin can edit anyone; others only within their own tenant
        if (currentUser.getRole() != UserRole.super_admin) {
            if (currentUser.getClientId() == null) {
                return ResponseEntity.status(HttpStatus.FORBIDDEN).build();
            }
            boolean sameTenant = user.getClientId() != null
                    && user.getClientId().equals(currentUser.getClientId());
            if (!sameTenant) {
                return ResponseEntity.status(HttpStatus.FORBIDDEN).build();
            }
            // Rank check: callers cannot modify or demote a user of equal or higher rank
            if (user.getRole().ordinal() <= currentUser.getRole().ordinal()) {
                throw new AtsException(
                        "Cannot modify an account with equal or higher privilege level than your own.",
                        HttpStatus.FORBIDDEN);
            }
        }

        if (body.containsKey("full_name"))  user.setFullName((String) body.get("full_name"));
        if (body.containsKey("is_active"))  user.setIsActive((Boolean) body.get("is_active"));

        // Role change: caller can only assign roles ≤ their own
        if (body.containsKey("role")) {
            UserRole requested;
            try {
                requested = UserRole.valueOf((String) body.get("role"));
            } catch (IllegalArgumentException e) {
                throw new AtsException("Invalid role: " + body.get("role"), HttpStatus.BAD_REQUEST);
            }
            if (!canAssignRole(currentUser, requested)) {
                throw new AtsException(
                    "You cannot assign the role '" + requested + "' — it exceeds your own privilege level.",
                    HttpStatus.FORBIDDEN);
            }
            user.setRole(requested);
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

        // Scope check
        if (currentUser.getRole() != UserRole.super_admin) {
            if (currentUser.getClientId() == null) {
                return ResponseEntity.status(HttpStatus.FORBIDDEN).build();
            }
            boolean sameTenant = user.getClientId() != null
                    && user.getClientId().equals(currentUser.getClientId());
            if (!sameTenant) {
                return ResponseEntity.status(HttpStatus.FORBIDDEN).build();
            }
            // Rank check: callers cannot deactivate a user of equal or higher rank
            if (user.getRole().ordinal() <= currentUser.getRole().ordinal()) {
                throw new AtsException(
                        "Cannot deactivate an account with equal or higher privilege level than your own.",
                        HttpStatus.FORBIDDEN);
            }
        }

        user.setIsActive(false);
        userRepository.save(user);
        return ResponseEntity.ok(Map.of("message", "User deactivated successfully"));
    }
}
