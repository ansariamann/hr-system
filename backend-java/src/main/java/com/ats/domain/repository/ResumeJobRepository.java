package com.ats.domain.repository;

import com.ats.domain.entity.ResumeJob;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.UUID;

@Repository
public interface ResumeJobRepository extends JpaRepository<ResumeJob, UUID> {
    List<ResumeJob> findAllByClientIdOrderByCreatedAtDesc(UUID clientId);
    List<ResumeJob> findAllByStatus(String status);
}
