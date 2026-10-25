package com.ats.domain.repository;

import com.ats.domain.entity.CompanyEmployee;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;
import java.util.UUID;

@Repository
public interface CompanyEmployeeRepository extends JpaRepository<CompanyEmployee, UUID> {

    Page<CompanyEmployee> findAllByClientId(UUID clientId, Pageable pageable);

    List<CompanyEmployee> findAllByClientIdAndIsActiveTrue(UUID clientId);

    Optional<CompanyEmployee> findByIdAndClientId(UUID id, UUID clientId);

    Optional<CompanyEmployee> findByCandidateIdAndClientId(UUID candidateId, UUID clientId);

    boolean existsByCandidateIdAndClientId(UUID candidateId, UUID clientId);
}
