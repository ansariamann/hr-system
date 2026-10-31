package com.ats.service;

import com.ats.domain.entity.User;
import com.ats.domain.enums.UserRole;
import com.ats.domain.repository.PasswordResetTokenRepository;
import com.ats.domain.repository.UserRepository;
import com.ats.exception.AtsException;
import com.ats.exception.ResourceNotFoundException;
import com.ats.security.jwt.JwtService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.HttpStatus;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.UUID;

/**
 * Authentication service — login, register, password change.
 * Password hashing via BCryptPasswordEncoder, compatible with
 * Python passlib $2b$ format stored in PostgreSQL.
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class AuthService {

    private final UserRepository userRepository;
    private final PasswordResetTokenRepository resetTokenRepository;
    private final PasswordEncoder passwordEncoder;
    private final JwtService jwtService;

    private static final int MIN_PASSWORD_LENGTH = 8;

    /** Pre-computed dummy bcrypt hash to equalize authentication timing and prevent user enumeration. */
    private static final String DUMMY_BCRYPT_HASH =
            "$2a$10$wTf4M68sN0aW279R6x4t3uKqYxO24vF8f/n5B6dE9Xf3tSg8tC6i2";

    /**
     * Authenticate user credentials and return a JWT.
     * Timing: always executes passwordEncoder.matches even for nonexistent users.
     */
    @Transactional(readOnly = true)
    public LoginResult login(String email, String password) {
        User user = userRepository.findByEmail(email.toLowerCase().trim())
                .orElse(null);

        String hashToCheck = (user != null && user.getHashedPassword() != null)
                ? user.getHashedPassword()
                : DUMMY_BCRYPT_HASH;
        boolean passwordMatches = passwordEncoder.matches(password != null ? password : "", hashToCheck);

        if (user == null || !passwordMatches) {
            throw new AtsException("Invalid email or password", HttpStatus.UNAUTHORIZED);
        }

        if (!Boolean.TRUE.equals(user.getIsActive())) {
            throw new AtsException("Account is disabled", HttpStatus.FORBIDDEN);
        }

        String token = jwtService.generateToken(user);
        log.info("User {} authenticated successfully", email);

        return new LoginResult(token, "bearer", jwtService.getExpirationMs() / 1000, user);
    }

    /**
     * Register a new user.
     * The caller's principal is passed so role escalation beyond the caller's
     * own level is rejected.
     *
     * @param caller    the authenticated user performing the registration
     * @param email     new user's email
     * @param password  plaintext password (validated for length)
     * @param fullName  display name
     * @param clientId  tenant to assign — if null defaults to the caller's tenant
     * @param roleStr   role name string; caller cannot grant above their own role
     */
    @Transactional
    public User register(User caller, String email, String password, String fullName,
                         UUID clientId, String roleStr) {

        if (password == null || password.length() < MIN_PASSWORD_LENGTH) {
            throw new AtsException(
                "Password must be at least " + MIN_PASSWORD_LENGTH + " characters", HttpStatus.BAD_REQUEST);
        }
        if (userRepository.existsByEmail(email.toLowerCase().trim())) {
            throw new AtsException("Email already registered", HttpStatus.CONFLICT);
        }

        // Resolve role — default to the lowest role in the caller's scope
        UserRole targetRole;
        if (roleStr != null && !roleStr.isBlank()) {
            try {
                targetRole = UserRole.valueOf(roleStr);
            } catch (IllegalArgumentException e) {
                throw new AtsException("Invalid role: " + roleStr, HttpStatus.BAD_REQUEST);
            }
        } else {
            targetRole = UserRole.client_user;
        }

        // Privilege check: ordinal increases with lower privilege
        if (targetRole.ordinal() < caller.getRole().ordinal()) {
            throw new AtsException(
                "You cannot grant the role '" + targetRole + "' — it exceeds your own privilege level.",
                HttpStatus.FORBIDDEN);
        }

        // Tenant: non-super-admins can only create users in their own tenant
        UUID resolvedClientId = clientId;
        if (caller.getRole() != UserRole.super_admin) {
            resolvedClientId = caller.getClientId(); // ignore any supplied clientId
        }

        if (targetRole != UserRole.super_admin && resolvedClientId == null) {
            throw new AtsException("A client organization (clientId) is required for all non-super_admin accounts.", HttpStatus.BAD_REQUEST);
        }

        User user = User.builder()
                .email(email.toLowerCase().trim())
                .hashedPassword(passwordEncoder.encode(password))
                .fullName(fullName)
                .clientId(resolvedClientId)
                .role(targetRole)
                .isActive(true)
                .build();

        user = userRepository.save(user);
        log.info("Registered new user: {} with role: {}", email, targetRole);
        return user;
    }

    /**
     * Change the authenticated user's password.
     */
    @Transactional
    public void changePassword(UUID userId, String currentPassword, String newPassword) {
        if (newPassword == null || newPassword.length() < MIN_PASSWORD_LENGTH) {
            throw new AtsException(
                "New password must be at least " + MIN_PASSWORD_LENGTH + " characters",
                HttpStatus.BAD_REQUEST);
        }

        User user = userRepository.findById(userId)
                .orElseThrow(() -> new ResourceNotFoundException("User", userId));

        if (!passwordEncoder.matches(currentPassword, user.getHashedPassword())) {
            throw new AtsException("Current password is incorrect", HttpStatus.BAD_REQUEST);
        }

        user.setHashedPassword(passwordEncoder.encode(newPassword));
        userRepository.save(user);
        log.info("Password changed for user: {}", userId);
    }

    /**
     * Get current user details.
     */
    @Transactional(readOnly = true)
    public User getCurrentUser(UUID userId) {
        return userRepository.findById(userId)
                .orElseThrow(() -> new ResourceNotFoundException("User", userId));
    }

    public record LoginResult(String accessToken, String tokenType, long expiresIn, User user) {}
}
