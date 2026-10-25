package com.ats.domain.repository;

import com.ats.domain.entity.InterviewRecord;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;
import java.util.UUID;

@Repository
public interface InterviewRecordRepository extends JpaRepository<InterviewRecord, UUID> {

    @Query("SELECT i FROM InterviewRecord i WHERE i.clientId = :clientId AND i.deletedAt IS NULL")
    Page<InterviewRecord> findAllByClientIdNotDeleted(@Param("clientId") UUID clientId, Pageable pageable);

    @Query("SELECT i FROM InterviewRecord i WHERE i.candidateId = :candidateId AND i.deletedAt IS NULL")
    List<InterviewRecord> findByCandidateIdNotDeleted(@Param("candidateId") UUID candidateId);

    Optional<InterviewRecord> findByIdAndClientId(UUID id, UUID clientId);
}
