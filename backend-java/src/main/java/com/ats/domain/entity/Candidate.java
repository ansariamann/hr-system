package com.ats.domain.entity;

import com.ats.domain.enums.CandidateStatus;
import com.fasterxml.jackson.annotation.JsonIgnore;
import io.hypersistence.utils.hibernate.type.json.JsonType;
import jakarta.persistence.*;
import lombok.*;
import org.hibernate.annotations.Type;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.List;
import java.util.Map;
import java.util.UUID;

/**
 * Candidate entity representing job applicants.
 * Maps to the 'candidates' PostgreSQL table (RLS-protected by client_id).
 *
 * <p>JSON columns (skills, experience, previous_employment, other_details)
 * are mapped via Hypersistence Utils JsonType for proper JSONB handling.
 */
@Entity
@Table(name = "candidates",
        indexes = {
                @Index(name = "idx_candidates_client_id", columnList = "client_id"),
                @Index(name = "idx_candidates_hash", columnList = "candidate_hash"),
                @Index(name = "idx_candidates_email", columnList = "email")
        })
@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class Candidate extends BaseEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    @Column(name = "id", updatable = false, nullable = false)
    private UUID id;

    @Column(name = "client_id")
    private UUID clientId;

    @JsonIgnore
    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "client_id", insertable = false, updatable = false)
    private Client client;

    @Column(name = "name", nullable = false, length = 255)
    private String name;

    @Column(name = "email", length = 255)
    private String email;

    @Column(name = "phone", length = 50)
    private String phone;

    @Column(name = "company", length = 255)
    private String company;

    @Column(name = "location", length = 255)
    private String location;

    @Column(name = "date_of_birth")
    private LocalDate dateOfBirth;

    @Type(JsonType.class)
    @Column(name = "previous_employment", columnDefinition = "jsonb")
    private List<Map<String, Object>> previousEmployment;

    @Column(name = "key_skill", columnDefinition = "TEXT")
    private String keySkill;

    @JsonIgnore
    @Column(name = "resume_file_path", columnDefinition = "TEXT")
    private String resumeFilePath;

    @Column(name = "resume_url", columnDefinition = "TEXT")
    private String resumeUrl;

    @Column(name = "assigned_user_id")
    private UUID assignedUserId;

    @JsonIgnore
    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "assigned_user_id", insertable = false, updatable = false)
    private User assignedUser;

    @Type(JsonType.class)
    @Column(name = "skills", columnDefinition = "jsonb")
    private List<String> skills;

    @Type(JsonType.class)
    @Column(name = "experience", columnDefinition = "jsonb")
    private List<Map<String, Object>> experience;

    @Column(name = "ctc_current", precision = 12, scale = 2)
    private BigDecimal ctcCurrent;

    @Column(name = "ctc_expected", precision = 12, scale = 2)
    private BigDecimal ctcExpected;

    @Column(name = "total_experience_years", precision = 5, scale = 2)
    private BigDecimal totalExperienceYears;

    @Column(name = "notice_period_days")
    private Integer noticePeriodDays;

    @Column(name = "source", nullable = false, length = 100)
    @Builder.Default
    private String source = "MANUAL";

    @Column(name = "linkedin_url", length = 500)
    private String linkedinUrl;

    @Column(name = "selected_client_name", length = 255)
    private String selectedClientName;

    @Enumerated(EnumType.STRING)
    @Column(name = "status", nullable = false, length = 50)
    @Builder.Default
    private CandidateStatus status = CandidateStatus.ACTIVE;

    @Column(name = "is_blacklisted", nullable = false)
    @Builder.Default
    private Boolean isBlacklisted = false;

    @Column(name = "is_direct_interview", nullable = false)
    @Builder.Default
    private Boolean isDirectInterview = false;

    @Column(name = "candidate_hash", length = 64)
    private String candidateHash;

    @Column(name = "remark", columnDefinition = "TEXT")
    private String remark;

    @Type(JsonType.class)
    @Column(name = "other_details", columnDefinition = "jsonb")
    private Map<String, Object> otherDetails;

    // ─── Relationships ──────────────────────────────────────────────────
    @JsonIgnore
    @OneToMany(mappedBy = "candidate", cascade = CascadeType.ALL, orphanRemoval = true, fetch = FetchType.LAZY)
    private List<Application> applications;
}
