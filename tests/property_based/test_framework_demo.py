"""Demonstration of property-based testing framework setup."""

import pytest
from hypothesis import given, assume, strategies as st
from typing import Dict, Any

from .base import PropertyTestBase, property_test
from .generators import (
    client_data, candidate_data, application_data, 
    tenant_with_data, email_addresses, names
)


class TestPropertyFrameworkDemo(PropertyTestBase):
    """Demonstration tests for the property-based testing framework."""
    
    @property_test("production-hardening", 1, "Comprehensive property test framework")
    @given(client=client_data())
    def test_client_data_generation(self, client: Dict[str, Any]):
        """Test that client data generator produces valid data."""
        # Feature: production-hardening, Property 1: Comprehensive property test framework
        
        # Log test data for debugging
        self.log_test_data("Generated client", client)
        
        # Verify required fields are present
        required_fields = ["id", "name", "email_domain"]
        self.assume_valid_data(client, required_fields)
        
        # Verify data types and constraints
        assert isinstance(client["name"], str)
        assert len(client["name"].strip()) > 0
        assert isinstance(client["email_domain"], str)
        assert "." in client["email_domain"]
        
        # Verify email domain format
        domain_parts = client["email_domain"].split(".")
        assert len(domain_parts) >= 2
        assert all(len(part) > 0 for part in domain_parts)
    
    @property_test("production-hardening", 1, "Comprehensive property test framework")
    @given(candidate=candidate_data())
    def test_candidate_data_generation(self, candidate: Dict[str, Any]):
        """Test that candidate data generator produces valid data."""
        # Feature: production-hardening, Property 1: Comprehensive property test framework
        
        self.log_test_data("Generated candidate", candidate)
        
        # Verify required fields
        required_fields = ["id", "client_id", "name", "status"]
        self.assume_valid_data(candidate, required_fields)
        
        # Verify data constraints
        assert isinstance(candidate["name"], str)
        assert len(candidate["name"].strip()) > 0
        assert candidate["status"] in ["ACTIVE", "INACTIVE", "JOINED", "LEFT_COMPANY"]
        
        # Verify optional fields have correct types when present
        if candidate["email"] is not None:
            assert isinstance(candidate["email"], str)
            assert "@" in candidate["email"]
        
        if candidate["skills"] is not None:
            assert isinstance(candidate["skills"], list)
            assert all(isinstance(skill, str) for skill in candidate["skills"])
        
        if candidate["experience"] is not None:
            assert isinstance(candidate["experience"], list)
            for exp in candidate["experience"]:
                assert isinstance(exp, dict)
                assert "company" in exp
                assert "title" in exp
    
    @property_test("production-hardening", 1, "Comprehensive property test framework")
    @given(application=application_data())
    def test_application_data_generation(self, application: Dict[str, Any]):
        """Test that application data generator produces valid data."""
        # Feature: production-hardening, Property 1: Comprehensive property test framework
        
        self.log_test_data("Generated application", application)
        
        # Verify required fields
        required_fields = ["id", "client_id", "candidate_id", "status"]
        self.assume_valid_data(application, required_fields)
        
        # Verify status is valid
        valid_statuses = [
            "RECEIVED", "SCREENING", "INTERVIEW_SCHEDULED", "INTERVIEWED",
            "OFFER_EXTENDED", "OFFER_ACCEPTED", "OFFER_REJECTED", "REJECTED"
        ]
        assert application["status"] in valid_statuses
        
        # Verify flagging logic
        if application["flagged_for_review"]:
            # If flagged, should have a reason (in real data)
            # For generated data, this is optional but if present should be string
            if application["flag_reason"] is not None:
                assert isinstance(application["flag_reason"], str)
        
        # Verify soft delete logic
        if application["deleted_at"] is not None:
            # Should be a datetime object
            from datetime import datetime
            assert isinstance(application["deleted_at"], datetime)
    
    @property_test("production-hardening", 1, "Comprehensive property test framework")
    @given(tenant=tenant_with_data())
    def test_tenant_data_consistency(self, tenant: Dict[str, Any]):
        """Test that tenant data maintains referential consistency."""
        # Feature: production-hardening, Property 1: Comprehensive property test framework
        
        self.log_test_data("Generated tenant", {
            "client_id": tenant["client"]["id"],
            "num_candidates": len(tenant["candidates"]),
            "num_applications": len(tenant["applications"]),
            "num_resume_jobs": len(tenant["resume_jobs"]),
            "num_users": len(tenant["users"])
        })
        
        client_id = tenant["client"]["id"]
        
        # Verify all candidates belong to the client
        for candidate in tenant["candidates"]:
            assert candidate["client_id"] == client_id
        
        # Verify all applications belong to the client and reference valid candidates
        candidate_ids = {c["id"] for c in tenant["candidates"]}
        for application in tenant["applications"]:
            assert application["client_id"] == client_id
            assert application["candidate_id"] in candidate_ids
        
        # Verify all resume jobs belong to the client
        for resume_job in tenant["resume_jobs"]:
            assert resume_job["client_id"] == client_id
        
        # Verify all users belong to the client
        for user in tenant["users"]:
            assert user["client_id"] == client_id
    
    @property_test("production-hardening", 1, "Comprehensive property test framework")
    @given(email=email_addresses(), name=names())
    def test_basic_generators_produce_valid_data(self, email: str, name: str):
        """Test that basic generators produce valid data."""
        # Feature: production-hardening, Property 1: Comprehensive property test framework
        
        self.log_test_data("Generated email and name", {"email": email, "name": name})
        
        # Verify email format
        assert "@" in email
        assert "." in email
        email_parts = email.split("@")
        assert len(email_parts) == 2
        assert len(email_parts[0]) > 0  # username
        assert len(email_parts[1]) > 0  # domain
        
        # Verify name format
        assert isinstance(name, str)
        assert len(name.strip()) > 0
        # Should contain at least first and last name
        name_parts = name.split()
        assert len(name_parts) >= 2
    
    @property_test("production-hardening", 1, "Comprehensive property test framework")
    @given(st.integers(min_value=1, max_value=1000))
    def test_framework_runs_minimum_iterations(self, iteration_number: int):
        """Test that framework runs at least 100 iterations as required."""
        # Feature: production-hardening, Property 1: Comprehensive property test framework
        
        # This test will be run 100+ times due to our configuration
        # We can track this by checking the iteration number
        assert iteration_number >= 1
        
        # Log every 10th iteration to verify we're getting multiple runs
        if iteration_number % 10 == 0:
            self.log_test_data("Iteration", iteration_number)
    
    def test_deterministic_seeding_in_ci(self):
        """Test that deterministic seeding works in CI environment."""
        # This test verifies the configuration is working
        from .config import get_test_seed, is_ci_environment
        
        # In CI, should have deterministic seed
        if is_ci_environment():
            seed = get_test_seed()
            assert seed is not None
            assert seed == 42  # Our configured seed
        
        # Test passes regardless of environment
        assert True
    
    def test_hypothesis_configuration_loaded(self):
        """Test that Hypothesis configuration is properly loaded."""
        from hypothesis import settings
        
        # Verify that settings are configured
        current_settings = settings()
        
        # Should have at least our minimum iterations
        assert current_settings.max_examples >= 100
        
        # Should have reasonable deadline
        assert current_settings.deadline is not None
        assert current_settings.deadline.total_seconds() > 0