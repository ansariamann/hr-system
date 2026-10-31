package com.ats.security.jwt;

import com.ats.config.TenantContext;
import com.ats.domain.entity.User;
import com.ats.domain.repository.UserRepository;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.lang.NonNull;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.web.authentication.WebAuthenticationDetailsSource;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;
import java.util.List;
import java.util.UUID;

/**
 * Servlet filter that:
 * 1. Extracts the Bearer JWT from Authorization header.
 * 2. Validates the token and loads the user.
 * 3. Sets {@link TenantContext} for PostgreSQL RLS.
 * 4. Populates the Spring SecurityContext.
 * 5. Clears TenantContext in the finally block to prevent leaks.
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class JwtAuthenticationFilter extends OncePerRequestFilter {

    private final JwtService jwtService;
    private final UserRepository userRepository;

    @Override
    protected void doFilterInternal(
            @NonNull HttpServletRequest request,
            @NonNull HttpServletResponse response,
            @NonNull FilterChain filterChain) throws ServletException, IOException {

        try {
            String token = extractToken(request);

            if (token != null && jwtService.validateToken(token)) {
                UUID userId = jwtService.extractUserId(token);
                UUID clientId = jwtService.extractClientId(token);
                String role = jwtService.extractRole(token);

                User user = userRepository.findById(userId).orElse(null);
                if (user != null && Boolean.TRUE.equals(user.getIsActive())) {
                    // Authoritative role and tenant from DB (prevents privilege persistence after demotion or tenant re-assignment)
                    String roleStr = user.getRole() != null ? user.getRole().name().toUpperCase() : "CLIENT_USER";
                    var authorities = List.of(
                            new SimpleGrantedAuthority("ROLE_" + roleStr),
                            new SimpleGrantedAuthority(roleStr)
                    );

                    if (user.getClientId() != null) {
                        TenantContext.setCurrentTenantId(user.getClientId().toString());
                    }

                    var authToken = new UsernamePasswordAuthenticationToken(user, null, authorities);
                    authToken.setDetails(new WebAuthenticationDetailsSource().buildDetails(request));
                    SecurityContextHolder.getContext().setAuthentication(authToken);
                }
            }

            filterChain.doFilter(request, response);

        } catch (Exception e) {
            log.error("Authentication filter exception: {}", e.getMessage(), e);
            filterChain.doFilter(request, response);
        } finally {
            // Always clear tenant context to prevent pool reuse leaks
            TenantContext.clear();
        }
    }

    private String extractToken(HttpServletRequest request) {
        String header = request.getHeader("Authorization");
        if (header != null && header.startsWith("Bearer ")) {
            return header.substring(7);
        }
        return null;
    }
}
