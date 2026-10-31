package com.ats.domain.entity;

import com.fasterxml.jackson.annotation.JsonIgnore;
import jakarta.persistence.*;
import lombok.*;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.List;
import java.util.UUID;

/**
 * Job posting entity.
 * Maps to the 'jobs' PostgreSQL table.
 */
@Entity
@Table(name = "jobs",
        indexes = {
                @Index(name = "idx_jobs_client_id", columnList = "client_id"),
                @Index(name = "idx_jobs_status", columnList = "status")
        })
@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class Job extends BaseEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    @Column(name = "id", updatable = false, nullable = false)
    private UUID id;

    @Column(name = "client_id", nullable = true)
    private UUID clientId;

    @JsonIgnore
    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "client_id", insertable = false, updatable = false)
    private Client client;

    @Column(name = "title", nullable = false, length = 255)
    private String title;

    @Column(name = "company_name", nullable = false, length = 255)
    private String companyName;

    @Column(name = "posting_date", nullable = false)
    @Builder.Default
    private LocalDate postingDate = LocalDate.now();

    @Column(name = "closing_date")
    private LocalDate closingDate;

    @Column(name = "requirements", columnDefinition = "TEXT")
    private String requirements;

    @Column(name = "department", length = 255)
    private String department;

    @Column(name = "employment_type", nullable = false, length = 50)
    @Builder.Default
    private String employmentType = "FULL_TIME";

    @Column(name = "experience_required")
    private Integer experienceRequired;

    @Column(name = "salary_lpa", precision = 10, scale = 2)
    private BigDecimal salaryLpa;

    @Column(name = "location", length = 255)
    private String location;

    @Column(name = "openings_count", nullable = false)
    @Builder.Default
    private Integer openingsCount = 1;

    @Column(name = "status", nullable = false, length = 50)
    @Builder.Default
    private String status = "OPEN";

    @Column(name = "vacant", nullable = false)
    @Builder.Default
    private Boolean vacant = true;

    @Column(name = "submitted_by_client", nullable = false)
    @Builder.Default
    private Boolean submittedByClient = false;

    // ─── Relationships ──────────────────────────────────────────────────
    @JsonIgnore
    @OneToMany(mappedBy = "job", fetch = FetchType.LAZY)
    private List<Application> applications;
}
