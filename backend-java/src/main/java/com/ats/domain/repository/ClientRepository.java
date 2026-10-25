package com.ats.domain.repository;

import com.ats.domain.entity.Client;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;
import java.util.UUID;

@Repository
public interface ClientRepository extends JpaRepository<Client, UUID> {

    List<Client> findAllByIsActiveTrue();

    Optional<Client> findByEmailDomain(String emailDomain);

    boolean existsByName(String name);
}
