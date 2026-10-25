package com.ats.service;

import com.ats.domain.entity.User;
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

    /**
     * Authenticate user credentials and return a JWT.
     */
    @Transactional(readOnly = true)
    public LoginResult login(String email, String password) {
        User user = userRepository.findByEmail(email)
                .orElseThrow(() -> new AtsException("Invalid email or password", HttpStatus.UNAUTHORIZED));

        if (!Boolean.TRUE.equals(user.getIsActive())) {
            throw new AtsException("Account is disabled", HttpStatus.FORBIDDEN);
        }

        // BCryptPasswordEncoder handles $2a$, $2b$, $2y$ formats automatically
        if (!passwordEncoder.matches(password, user.getHashedPassword())) {
            throw new AtsException("Invalid email or password", HttpStatus.UNAUTHORIZED);
        }

        String token = jwtService.generateToken(user);
        log.info("User {} authenticated successfully", email);

        return new LoginResult(token, "bearer", jwtService.getExpirationMs() / 1000, user);
    }

    /**
     * Register a new user (admin-only in production — guarded at controller).
     */
    @Transactional
    public User register(String email, String password, String fullName,
                         UUID clientId, String role) {
        if (userRepository.existsByEmail(email)) {
            throw new AtsException("Email already registered", HttpStatus.CONFLICT);
        }

        User user = User.builder()
                .email(email)
                .hashedPassword(passwordEncoder.encode(password))
                .fullName(fullName)
                .clientId(clientId)
                .isActive(true)
                .build();

        if (role != null) {
            try {
                user.setRole(com.ats.domain.enums.UserRole.valueOf(role));
            } catch (IllegalArgumentException e) {
                throw new AtsException("Invalid role: " + role, HttpStatus.BAD_REQUEST);
            }
        }

        user = userRepository.save(user);
        log.info("Registered new user: {}", email);
        return user;
    }

    /**
     * Change the authenticated user's password.
     */
    @Transactional
    public void changePassword(UUID userId, String currentPassword, String newPassword) {
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
