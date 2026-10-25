package com.ats.api.controller;

import com.ats.domain.entity.Client;
import com.ats.domain.entity.User;
import com.ats.domain.repository.ClientRepository;
import com.ats.exception.ResourceNotFoundException;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.security.SecurityRequirement;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;
import java.util.UUID;

/**
 * Client REST controller — /api/v1/clients/*
 * CRUD is restricted to admin roles; users can GET their own client.
 */
@Tag(name = "Clients", description = "Client (tenant) management")
@RestController
@RequestMapping("/api/v1/clients")
@SecurityRequirement(name = "bearerAuth")
@RequiredArgsConstructor
public class ClientController {

    private final ClientRepository clientRepository;

    @Operation(summary = "List all clients (admin only)")
    @GetMapping
    @PreAuthorize("hasAnyRole('SUPER_ADMIN', 'ADMIN')")
    public ResponseEntity<List<Client>> listClients() {
        return ResponseEntity.ok(clientRepository.findAll());
    }

    @Operation(summary = "Get current user's client")
    @GetMapping("/me")
    public ResponseEntity<Client> getMyClient(@AuthenticationPrincipal User user) {
        Client client = clientRepository.findById(user.getClientId())
                .orElseThrow(() -> new ResourceNotFoundException("Client", user.getClientId()));
        return ResponseEntity.ok(client);
    }

    @Operation(summary = "Get client by ID (admin or own client)")
    @GetMapping("/{id}")
    public ResponseEntity<Client> getClient(
            @AuthenticationPrincipal User user,
            @PathVariable UUID id) {
        // Non-admins can only access their own client
        if (!user.getClientId().equals(id)) {
            String role = user.getRole().name();
            if (!role.equals("super_admin") && !role.equals("admin")) {
                return ResponseEntity.status(HttpStatus.FORBIDDEN).build();
            }
        }
        Client client = clientRepository.findById(id)
                .orElseThrow(() -> new ResourceNotFoundException("Client", id));
        return ResponseEntity.ok(client);
    }

    @Operation(summary = "Create a new client (super admin only)")
    @PostMapping
    @PreAuthorize("hasRole('SUPER_ADMIN')")
    public ResponseEntity<Client> createClient(@RequestBody Map<String, Object> body) {
        Client client = Client.builder()
                .name((String) body.get("name"))
                .industry((String) body.get("industry"))
                .contactName((String) body.get("contact_name"))
                .contactEmail((String) body.get("contact_email"))
                .contactPhone((String) body.get("contact_phone"))
                .address((String) body.get("address"))
                .website((String) body.get("website"))
                .emailDomain((String) body.get("email_domain"))
                .isActive(true)
                .build();

        return ResponseEntity.status(HttpStatus.CREATED).body(clientRepository.save(client));
    }

    @Operation(summary = "Update a client")
    @PutMapping("/{id}")
    @PreAuthorize("hasAnyRole('SUPER_ADMIN', 'ADMIN')")
    public ResponseEntity<Client> updateClient(
            @PathVariable UUID id,
            @RequestBody Map<String, Object> body) {

        Client client = clientRepository.findById(id)
                .orElseThrow(() -> new ResourceNotFoundException("Client", id));

        if (body.containsKey("name"))          client.setName((String) body.get("name"));
        if (body.containsKey("industry"))      client.setIndustry((String) body.get("industry"));
        if (body.containsKey("contact_name"))  client.setContactName((String) body.get("contact_name"));
        if (body.containsKey("contact_email")) client.setContactEmail((String) body.get("contact_email"));
        if (body.containsKey("contact_phone")) client.setContactPhone((String) body.get("contact_phone"));
        if (body.containsKey("address"))       client.setAddress((String) body.get("address"));
        if (body.containsKey("website"))       client.setWebsite((String) body.get("website"));
        if (body.containsKey("is_active"))     client.setIsActive((Boolean) body.get("is_active"));

        return ResponseEntity.ok(clientRepository.save(client));
    }
}
