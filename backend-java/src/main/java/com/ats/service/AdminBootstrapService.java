package com.ats.service;

import com.ats.domain.entity.User;
import com.ats.domain.enums.UserRole;
import com.ats.domain.repository.UserRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.ApplicationArguments;
import org.springframework.boot.ApplicationRunner;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;

import java.util.UUID;

/**
 * On first startup: if no super_admin exists and BOOTSTRAP_ADMIN_EMAIL +
 * BOOTSTRAP_ADMIN_PASSWORD are set, creates one.
 * This replaces the seeded SQL credentials so production never ships with
 * known passwords in migrations.
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class AdminBootstrapService implements ApplicationRunner {

    private final UserRepository userRepository;
    private final PasswordEncoder passwordEncoder;

    @Value("${app.bootstrap.admin-email:}")
    private String bootstrapEmail;

    @Value("${app.bootstrap.admin-password:}")
    private String bootstrapPassword;

    private static final UUID DEFAULT_CLIENT_ID =
            UUID.fromString("11111111-1111-1111-1111-111111111111");

    @Override
    @Transactional
    public void run(ApplicationArguments args) {
        if (bootstrapEmail.isBlank() || bootstrapPassword.isBlank()) {
            log.info("Bootstrap: BOOTSTRAP_ADMIN_EMAIL / BOOTSTRAP_ADMIN_PASSWORD not set — skipping admin creation.");
            return;
        }
        if (userRepository.existsByRole(UserRole.super_admin)) {
            log.info("Bootstrap: a super_admin already exists — skipping.");
            return;
        }
        if (bootstrapPassword.length() < 12) {
            log.warn("Bootstrap: BOOTSTRAP_ADMIN_PASSWORD is shorter than 12 characters — refusing to create admin.");
            return;
        }

        User admin = User.builder()
                .email(bootstrapEmail.toLowerCase().trim())
                .hashedPassword(passwordEncoder.encode(bootstrapPassword))
                .fullName("System Administrator")
                .role(UserRole.super_admin)
                .clientId(DEFAULT_CLIENT_ID)
                .isActive(true)
                .build();

        userRepository.save(admin);
        log.info("Bootstrap: created super_admin account for '{}'.", bootstrapEmail);
        log.info("Bootstrap: IMPORTANT — change this password immediately and remove the env vars.");
    }
}

