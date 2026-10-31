package com.ats.api.controller;

import com.ats.domain.entity.Client;
import com.ats.domain.entity.User;
import com.ats.domain.enums.UserRole;
import com.ats.domain.repository.ClientRepository;
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

    @Operation(summary = "List all clients — super_admin sees all; others see only their own")
    @GetMapping
    @PreAuthorize("hasAnyRole('SUPER_ADMIN', 'ADMIN', 'HR_ADMIN', 'HR_MANAGER')")
    public ResponseEntity<List<Client>> listClients(@AuthenticationPrincipal User user) {
        if (user.getRole() == UserRole.super_admin) {
            return ResponseEntity.ok(clientRepository.findAll());
        }
        // admins/hr_managers see only their own tenant
        return ResponseEntity.ok(
            clientRepository.findById(user.getClientId())
                .map(List::of)
                .orElse(List.of()));
    }

    @Operation(summary = "Get current user's client")
    @GetMapping("/me")
    public ResponseEntity<Client> getMyClient(@AuthenticationPrincipal User user) {
        if (user.getClientId() == null) {
            throw new AtsException("No client assigned to this account", HttpStatus.FORBIDDEN);
        }
        Client client = clientRepository.findById(user.getClientId())
                .orElseThrow(() -> new ResourceNotFoundException("Client", user.getClientId()));
        return ResponseEntity.ok(client);
    }

    @Operation(summary = "Get client by ID (super_admin: any; others: own tenant only)")
    @GetMapping("/{id}")
    public ResponseEntity<Client> getClient(
            @AuthenticationPrincipal User user,
            @PathVariable UUID id) {

        // Only super_admin may read a different tenant
        boolean isSuperAdmin = user.getRole() == UserRole.super_admin;
        boolean isOwnTenant  = id.equals(user.getClientId());

        if (!isSuperAdmin && !isOwnTenant) {
            return ResponseEntity.status(HttpStatus.FORBIDDEN).build();
        }

        Client client = clientRepository.findById(id)
                .orElseThrow(() -> new ResourceNotFoundException("Client", id));
        return ResponseEntity.ok(client);
    }

    @Operation(summary = "Create a new client (super_admin only)")
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

    @Operation(summary = "Update a client (super_admin: any; admin: own tenant only)")
    @PutMapping("/{id}")
    @PreAuthorize("hasAnyRole('SUPER_ADMIN', 'ADMIN')")
    public ResponseEntity<Client> updateClient(
            @AuthenticationPrincipal User user,
            @PathVariable UUID id,
            @RequestBody Map<String, Object> body) {

        boolean isSuperAdmin = user.getRole() == UserRole.super_admin;
        if (!isSuperAdmin && !id.equals(user.getClientId())) {
            return ResponseEntity.status(HttpStatus.FORBIDDEN).build();
        }

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

    @Operation(summary = "Delete a client (super_admin only)")
    @DeleteMapping("/{id}")
    @PreAuthorize("hasRole('SUPER_ADMIN')")
    public ResponseEntity<Void> deleteClient(
            @AuthenticationPrincipal User user,
            @PathVariable UUID id) {
        // Prevent self-deletion
        if (id.equals(user.getClientId())) {
            throw new AtsException("Cannot delete your own tenant", HttpStatus.BAD_REQUEST);
        }
        Client client = clientRepository.findById(id)
                .orElseThrow(() -> new ResourceNotFoundException("Client", id));
        clientRepository.delete(client);
        return ResponseEntity.noContent().build();
    }

    @Operation(summary = "Invite client admin user (super_admin / admin)")
    @PostMapping("/{id}/invite")
    @PreAuthorize("hasAnyRole('SUPER_ADMIN', 'ADMIN')")
    public ResponseEntity<Map<String, Object>> inviteClientAdmin(
            @AuthenticationPrincipal User user,
            @PathVariable UUID id) {
        // Non-super-admins can only invite into their own tenant
        if (user.getRole() != UserRole.super_admin && !id.equals(user.getClientId())) {
            return ResponseEntity.status(HttpStatus.FORBIDDEN).build();
        }
        Client client = clientRepository.findById(id)
                .orElseThrow(() -> new ResourceNotFoundException("Client", id));
        // TODO: store and verify the invite token; for now it is informational only
        String token = UUID.randomUUID().toString();
        return ResponseEntity.ok(Map.of(
                "client_id", id,
                "client_name", client.getName(),
                "invite_token", token,
                "message", "Invite token generated — deliver via secure channel and implement verification before use."
        ));
    }
}
