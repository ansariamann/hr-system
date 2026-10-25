package com.ats.api.controller;

import com.ats.domain.entity.CompanyEmployee;
import com.ats.domain.entity.User;
import com.ats.domain.repository.CompanyEmployeeRepository;
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

    private final CompanyEmployeeRepository companyEmployeeRepository;

    @Operation(summary = "List all company employees (paginated)")
    @GetMapping
    public ResponseEntity<Page<CompanyEmployee>> listEmployees(
            @AuthenticationPrincipal User user,
            @RequestParam(defaultValue = "0") int page,
            @RequestParam(defaultValue = "20") int size) {
        return ResponseEntity.ok(
                companyEmployeeRepository.findAllByClientId(
                        user.getClientId(),
                        PageRequest.of(page, size, Sort.by("createdAt").descending())));
    }

    @Operation(summary = "List active employees only")
    @GetMapping("/active")
    public ResponseEntity<List<CompanyEmployee>> listActiveEmployees(
            @AuthenticationPrincipal User user) {
        return ResponseEntity.ok(
                companyEmployeeRepository.findAllByClientIdAndIsActiveTrue(user.getClientId()));
    }

    @Operation(summary = "Get a company employee by ID")
    @GetMapping("/{id}")
    public ResponseEntity<CompanyEmployee> getEmployee(
            @AuthenticationPrincipal User user,
            @PathVariable UUID id) {
        CompanyEmployee employee = companyEmployeeRepository
                .findByIdAndClientId(id, user.getClientId())
                .orElseThrow(() -> new ResourceNotFoundException("CompanyEmployee", id));
        return ResponseEntity.ok(employee);
    }

    @Operation(summary = "Create a company employee manually")
    @PostMapping
    public ResponseEntity<CompanyEmployee> createEmployee(
            @AuthenticationPrincipal User user,
            @RequestBody Map<String, Object> body) {

        CompanyEmployee employee = buildEmployeeFromBody(body, user.getClientId());
        return ResponseEntity.status(HttpStatus.CREATED)
                .body(companyEmployeeRepository.save(employee));
    }

    @Operation(summary = "Update a company employee")
    @PutMapping("/{id}")
    public ResponseEntity<CompanyEmployee> updateEmployee(
            @AuthenticationPrincipal User user,
            @PathVariable UUID id,
            @RequestBody Map<String, Object> body) {

        CompanyEmployee employee = companyEmployeeRepository
                .findByIdAndClientId(id, user.getClientId())
                .orElseThrow(() -> new ResourceNotFoundException("CompanyEmployee", id));

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
    public ResponseEntity<Void> deleteEmployee(
            @AuthenticationPrincipal User user,
            @PathVariable UUID id) {
        CompanyEmployee employee = companyEmployeeRepository
                .findByIdAndClientId(id, user.getClientId())
                .orElseThrow(() -> new ResourceNotFoundException("CompanyEmployee", id));
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
