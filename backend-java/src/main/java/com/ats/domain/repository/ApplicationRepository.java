package com.ats.domain.repository;

import com.ats.domain.entity.Application;
import com.ats.domain.enums.ApplicationStatus;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.JpaSpecificationExecutor;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;
import java.util.UUID;

@Repository
public interface ApplicationRepository extends JpaRepository<Application, UUID>,
        JpaSpecificationExecutor<Application> {

    @Query("SELECT a FROM Application a WHERE a.clientId = :clientId AND a.deletedAt IS NULL")
    Page<Application> findAllByClientIdNotDeleted(@Param("clientId") UUID clientId, Pageable pageable);

    @Query("SELECT a FROM Application a WHERE a.clientId = :clientId AND a.candidateId = :candidateId AND a.deletedAt IS NULL")
    List<Application> findByCandidateAndClient(@Param("clientId") UUID clientId,
                                                @Param("candidateId") UUID candidateId);

    @Query("SELECT a FROM Application a WHERE a.jobId = :jobId AND a.status = :status AND a.deletedAt IS NULL")
    List<Application> findByJobIdAndStatus(@Param("jobId") UUID jobId,
                                           @Param("status") ApplicationStatus status);

    @Query("SELECT COUNT(a) FROM Application a WHERE a.jobId = :jobId AND a.status = 'HIRED' AND a.deletedAt IS NULL")
    long countHiredByJobId(@Param("jobId") UUID jobId);

    Optional<Application> findByIdAndClientId(UUID id, UUID clientId);

    long countByClientIdAndStatus(UUID clientId, ApplicationStatus status);

    @Query("SELECT a FROM Application a WHERE a.clientId = :clientId AND a.status = :status AND a.deletedAt IS NULL")
    List<Application> findAllByClientIdAndStatus(@Param("clientId") UUID clientId,
                                                  @Param("status") ApplicationStatus status);
}
