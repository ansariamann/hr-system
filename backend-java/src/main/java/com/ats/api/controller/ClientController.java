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

    @Operation(summary = "List all clients (admin/hr only)")
    @GetMapping
    @PreAuthorize("hasAnyRole('SUPER_ADMIN', 'ADMIN', 'HR_ADMIN', 'HR_MANAGER')")
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
            String role = user.getRole().name().toLowerCase();
            if (!role.contains("admin") && !role.contains("manager")) {
                return ResponseEntity.status(HttpStatus.FORBIDDEN).build();
            }
        }
        Client client = clientRepository.findById(id)
                .orElseThrow(() -> new ResourceNotFoundException("Client", id));
        return ResponseEntity.ok(client);
    }

    @Operation(summary = "Create a new client (admin/hr)")
    @PostMapping
    @PreAuthorize("hasAnyRole('SUPER_ADMIN', 'ADMIN', 'HR_ADMIN')")
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
    @PreAuthorize("hasAnyRole('SUPER_ADMIN', 'ADMIN', 'HR_ADMIN')")
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
        if (body.containsKey("email_domain"))  client.setEmailDomain((String) body.get("email_domain"));
        if (body.containsKey("is_active"))     client.setIsActive((Boolean) body.get("is_active"));

        return ResponseEntity.ok(clientRepository.save(client));
    }

    @Operation(summary = "Delete a client")
    @DeleteMapping("/{id}")
    @PreAuthorize("hasAnyRole('SUPER_ADMIN', 'ADMIN')")
    public ResponseEntity<Void> deleteClient(@PathVariable UUID id) {
        Client client = clientRepository.findById(id)
                .orElseThrow(() -> new ResourceNotFoundException("Client", id));
        clientRepository.delete(client);
        return ResponseEntity.noContent().build();
    }

    @Operation(summary = "Invite client admin user")
    @PostMapping("/{id}/invite")
    @PreAuthorize("hasAnyRole('SUPER_ADMIN', 'ADMIN', 'HR_ADMIN')")
    public ResponseEntity<Map<String, Object>> inviteClientAdmin(@PathVariable UUID id) {
        Client client = clientRepository.findById(id)
                .orElseThrow(() -> new ResourceNotFoundException("Client", id));
        String token = UUID.randomUUID().toString();
        String inviteLink = "http://localhost:5173/client/login?inviteToken=" + token + "&clientId=" + id;
        return ResponseEntity.ok(Map.of(
                "client_id", id,
                "client_name", client.getName(),
                "invite_link", inviteLink,
                "message", "Invitation link generated successfully for " + client.getName()
        ));
    }
}
