package com.ats.api.controller;

import com.ats.domain.entity.CompanyEmployee;
import com.ats.domain.entity.User;
import com.ats.domain.enums.UserRole;
import com.ats.domain.repository.CompanyEmployeeRepository;
import com.ats.exception.AtsException;
import com.ats.exception.ResourceNotFoundException;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.security.SecurityRequirement;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.RequiredArgsConstructor;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Sort;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;

import java.time.LocalDate;
import java.util.List;
import java.util.Map;
import java.util.UUID;

/**
 * Company Employee REST controller — /api/v1/company-employees/*
 * Manages employees within a client company (auto-created on HIRED, or manual).
 */
@Tag(name = "Company Employees", description = "Company employee management")
@RestController
@RequestMapping("/api/v1/company-employees")
@SecurityRequirement(name = "bearerAuth")
@RequiredArgsConstructor
public class CompanyEmployeeController {

    private static final int MAX_PAGE_SIZE = 200;

    private final CompanyEmployeeRepository companyEmployeeRepository;

    @Operation(summary = "List all company employees (paginated)")
    @GetMapping
    @PreAuthorize("hasAnyRole('SUPER_ADMIN','ADMIN','HR_MANAGER','HR_RECRUITER','CLIENT_ADMIN','CLIENT_USER')")
    public ResponseEntity<Page<CompanyEmployee>> listEmployees(
            @AuthenticationPrincipal User user,
            @RequestParam(defaultValue = "0") int page,
            @RequestParam(defaultValue = "20") int size) {

        size = Math.min(size, MAX_PAGE_SIZE);

        if (user.getClientId() == null) {
            if (user.getRole() == UserRole.super_admin) {
                return ResponseEntity.ok(companyEmployeeRepository.findAll(
                        PageRequest.of(page, size, Sort.by("createdAt").descending())));
            }
            throw new AtsException("Tenant context required", HttpStatus.FORBIDDEN);
        }

        return ResponseEntity.ok(
                companyEmployeeRepository.findAllByClientId(
                        user.getClientId(),
                        PageRequest.of(page, size, Sort.by("createdAt").descending())));
    }

    @Operation(summary = "List active employees only")
    @GetMapping("/active")
    @PreAuthorize("hasAnyRole('SUPER_ADMIN','ADMIN','HR_MANAGER','HR_RECRUITER','CLIENT_ADMIN','CLIENT_USER')")
    public ResponseEntity<List<CompanyEmployee>> listActiveEmployees(
            @AuthenticationPrincipal User user) {

        if (user.getClientId() == null) {
            if (user.getRole() == UserRole.super_admin) {
                return ResponseEntity.ok(companyEmployeeRepository.findAll());
            }
            throw new AtsException("Tenant context required", HttpStatus.FORBIDDEN);
        }

        return ResponseEntity.ok(
                companyEmployeeRepository.findAllByClientIdAndIsActiveTrue(user.getClientId()));
    }

    @Operation(summary = "Get a company employee by ID")
    @GetMapping("/{id}")
    @PreAuthorize("hasAnyRole('SUPER_ADMIN','ADMIN','HR_MANAGER','HR_RECRUITER','CLIENT_ADMIN','CLIENT_USER')")
    public ResponseEntity<CompanyEmployee> getEmployee(
            @AuthenticationPrincipal User user,
            @PathVariable UUID id) {

        CompanyEmployee employee;
        if (user.getClientId() == null) {
            if (user.getRole() == UserRole.super_admin) {
                employee = companyEmployeeRepository.findById(id)
                        .orElseThrow(() -> new ResourceNotFoundException("CompanyEmployee", id));
            } else {
                throw new AtsException("Tenant context required", HttpStatus.FORBIDDEN);
            }
        } else {
            employee = companyEmployeeRepository
                    .findByIdAndClientId(id, user.getClientId())
                    .orElseThrow(() -> new ResourceNotFoundException("CompanyEmployee", id));
        }

        return ResponseEntity.ok(employee);
    }

    @Operation(summary = "Create a company employee manually")
    @PostMapping
    @PreAuthorize("hasAnyRole('SUPER_ADMIN','ADMIN','HR_MANAGER','CLIENT_ADMIN')")
    public ResponseEntity<CompanyEmployee> createEmployee(
            @AuthenticationPrincipal User user,
            @RequestBody Map<String, Object> body) {

        UUID targetClientId = user.getClientId();
        if (targetClientId == null) {
            if (user.getRole() == UserRole.super_admin && body.containsKey("client_id")) {
                targetClientId = UUID.fromString((String) body.get("client_id"));
            } else {
                throw new AtsException("A client tenant ID is required to create an employee", HttpStatus.BAD_REQUEST);
            }
        }

        CompanyEmployee employee = buildEmployeeFromBody(body, targetClientId);
        return ResponseEntity.status(HttpStatus.CREATED)
                .body(companyEmployeeRepository.save(employee));
    }

    @Operation(summary = "Update a company employee")
    @PutMapping("/{id}")
    @PreAuthorize("hasAnyRole('SUPER_ADMIN','ADMIN','HR_MANAGER','CLIENT_ADMIN')")
    public ResponseEntity<CompanyEmployee> updateEmployee(
            @AuthenticationPrincipal User user,
            @PathVariable UUID id,
            @RequestBody Map<String, Object> body) {

        CompanyEmployee employee;
        if (user.getClientId() == null) {
            if (user.getRole() == UserRole.super_admin) {
                employee = companyEmployeeRepository.findById(id)
                        .orElseThrow(() -> new ResourceNotFoundException("CompanyEmployee", id));
            } else {
                throw new AtsException("Tenant context required", HttpStatus.FORBIDDEN);
            }
        } else {
            employee = companyEmployeeRepository
                    .findByIdAndClientId(id, user.getClientId())
                    .orElseThrow(() -> new ResourceNotFoundException("CompanyEmployee", id));
        }

        if (body.containsKey("name"))           employee.setName((String) body.get("name"));
        if (body.containsKey("email"))          employee.setEmail((String) body.get("email"));
        if (body.containsKey("phone"))          employee.setPhone((String) body.get("phone"));
        if (body.containsKey("role"))           employee.setRole((String) body.get("role"));
        if (body.containsKey("department"))     employee.setDepartment((String) body.get("department"));
        if (body.containsKey("status"))         employee.setStatus((String) body.get("status"));
        if (body.containsKey("notes"))          employee.setNotes((String) body.get("notes"));
        if (body.containsKey("is_active"))      employee.setIsActive((Boolean) body.get("is_active"));
        if (body.containsKey("date_of_joining"))
            employee.setDateOfJoining(LocalDate.parse((String) body.get("date_of_joining")));

        return ResponseEntity.ok(companyEmployeeRepository.save(employee));
    }

    @Operation(summary = "Delete a company employee")
    @DeleteMapping("/{id}")
    @PreAuthorize("hasAnyRole('SUPER_ADMIN','ADMIN','HR_MANAGER','CLIENT_ADMIN')")
    public ResponseEntity<Void> deleteEmployee(
            @AuthenticationPrincipal User user,
            @PathVariable UUID id) {

        CompanyEmployee employee;
        if (user.getClientId() == null) {
            if (user.getRole() == UserRole.super_admin) {
                employee = companyEmployeeRepository.findById(id)
                        .orElseThrow(() -> new ResourceNotFoundException("CompanyEmployee", id));
            } else {
                throw new AtsException("Tenant context required", HttpStatus.FORBIDDEN);
            }
        } else {
            employee = companyEmployeeRepository
                    .findByIdAndClientId(id, user.getClientId())
                    .orElseThrow(() -> new ResourceNotFoundException("CompanyEmployee", id));
        }

        companyEmployeeRepository.delete(employee);
        return ResponseEntity.noContent().build();
    }

    private CompanyEmployee buildEmployeeFromBody(Map<String, Object> body, UUID clientId) {
        CompanyEmployee.CompanyEmployeeBuilder builder = CompanyEmployee.builder()
                .clientId(clientId);

        if (body.containsKey("name"))           builder.name((String) body.get("name"));
        if (body.containsKey("email"))          builder.email((String) body.get("email"));
        if (body.containsKey("phone"))          builder.phone((String) body.get("phone"));
        if (body.containsKey("role"))           builder.role((String) body.get("role"));
        if (body.containsKey("department"))     builder.department((String) body.get("department"));
        if (body.containsKey("notes"))          builder.notes((String) body.get("notes"));
        if (body.containsKey("candidate_id"))
            builder.candidateId(UUID.fromString((String) body.get("candidate_id")));
        if (body.containsKey("application_id"))
            builder.applicationId(UUID.fromString((String) body.get("application_id")));
        if (body.containsKey("date_of_joining"))
            builder.dateOfJoining(LocalDate.parse((String) body.get("date_of_joining")));

        return builder.build();
    }
}
