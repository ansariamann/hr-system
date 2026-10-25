package com.ats.domain.repository;

import com.ats.domain.entity.Candidate;
import com.ats.domain.enums.CandidateStatus;
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
public interface CandidateRepository extends JpaRepository<Candidate, UUID>,
        JpaSpecificationExecutor<Candidate> {

    Page<Candidate> findAllByClientId(UUID clientId, Pageable pageable);

    List<Candidate> findAllByClientIdAndStatus(UUID clientId, CandidateStatus status);

    Optional<Candidate> findByIdAndClientId(UUID id, UUID clientId);

    boolean existsByIdAndClientId(UUID id, UUID clientId);

    @Query("SELECT c FROM Candidate c WHERE c.clientId = :clientId AND c.candidateHash = :hash")
    Optional<Candidate> findByClientIdAndHash(@Param("clientId") UUID clientId,
                                               @Param("hash") String hash);

    @Query("SELECT c FROM Candidate c WHERE c.clientId = :clientId " +
           "AND (LOWER(c.email) = LOWER(:email) OR c.phone = :phone)")
    List<Candidate> findPotentialDuplicates(@Param("clientId") UUID clientId,
                                             @Param("email") String email,
                                             @Param("phone") String phone);

    long countByClientId(UUID clientId);

    long countByClientIdAndStatus(UUID clientId, CandidateStatus status);
}
