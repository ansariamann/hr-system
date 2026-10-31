package com.ats.domain.repository;

import com.ats.domain.entity.Job;
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
public interface JobRepository extends JpaRepository<Job, UUID>,
        JpaSpecificationExecutor<Job> {

    Page<Job> findAllByClientId(UUID clientId, Pageable pageable);

    List<Job> findAllByClientIdAndStatus(UUID clientId, String status);

    Optional<Job> findByIdAndClientId(UUID id, UUID clientId);

    @Query("SELECT j FROM Job j WHERE j.clientId = :clientId AND j.vacant = true AND j.status = 'OPEN'")
    List<Job> findVacantOpenJobsByClient(@Param("clientId") UUID clientId);

    @Query("SELECT j FROM Job j WHERE j.vacant = true AND j.status = 'OPEN'")
    List<Job> findVacantOpenJobs();

    long countByClientId(UUID clientId);
}
