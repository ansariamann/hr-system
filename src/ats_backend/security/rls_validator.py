"""RLS bypass prevention and validation system."""

import asyncio
import re
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from uuid import UUID, uuid4

from sqlalchemy import text, inspect
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
import structlog

from ats_backend.core.database import get_db
from ats_backend.core.session_context import set_client_context, clear_client_context
from ats_backend.auth.security import SecurityLogger, SecurityEventType, SecurityEventSeverity
from ats_backend.models.client import Client
from ats_backend.models.candidate import Candidate
from ats_backend.models.application import Application
from ats_backend.models.resume_job import ResumeJob

logger = structlog.get_logger(__name__)


class RLSBypassAttempt(Exception):
    """Exception raised when RLS bypass attempt is detected."""
    pass


class SQLInjectionAttempt(Exception):
    """Exception raised when SQL injection attempt is detected."""
    pass


class RLSValidator:
    """Comprehensive RLS bypass prevention and validation system."""
    
    # SQL injection patterns to detect
    SQL_INJECTION_PATTERNS = [
        r"(?i)(union\s+select)",
        r"(?i)(drop\s+table)",
        r"(?i)(delete\s+from)",
        r"(?i)(insert\s+into)",
        r"(?i)(update\s+\w+\s+set)",
        r"(?i)(alter\s+table)",
        r"(?i)(create\s+table)",
        r"(?i)(exec\s*\()",
        r"(?i)(execute\s*\()",
        r"(?i)(sp_executesql)",
        r"(?i)(xp_cmdshell)",
        r"(?i)(--\s*$)",
        r"(?i)(/\*.*\*/)",
        r"(?i)(;\s*drop)",
        r"(?i)(;\s*delete)",
        r"(?i)(;\s*insert)",
        r"(?i)(;\s*update)",
        r"(?i)('\s*or\s*'1'\s*=\s*'1)",
        r"(?i)('\s*or\s*1\s*=\s*1)",
        r"(?i)(\"\s*or\s*\"1\"\s*=\s*\"1)",
        r"(?i)(\"\s*or\s*1\s*=\s*1)",
        r"(?i)(0x[0-9a-f]+)",
        r"(?i)(char\s*\(\s*\d+\s*\))",
        r"(?i)(ascii\s*\(\s*)",
        r"(?i)(substring\s*\(\s*)",
        r"(?i)(waitfor\s+delay)",
        r"(?i)(benchmark\s*\(\s*)",
        r"(?i)(sleep\s*\(\s*)",
        r"(?i)(pg_sleep\s*\(\s*)",
    ]
    
    # RLS bypass patterns
    RLS_BYPASS_PATTERNS = [
        r"(?i)(set\s+app\.current_client_id)",
        r"(?i)(current_setting\s*\(\s*['\"]app\.current_client_id)",
        r"(?i)(reset\s+app\.current_client_id)",
        r"(?i)(set\s+local\s+app\.current_client_id)",
        r"(?i)(set\s+session\s+app\.current_client_id)",
        r"(?i)(disable\s+row\s+level\s+security)",
        r"(?i)(alter\s+table\s+\w+\s+disable\s+row\s+level\s+security)",
        r"(?i)(drop\s+policy)",
        r"(?i)(alter\s+policy)",
        r"(?i)(create\s+policy)",
        r"(?i)(bypass\s+rls)",
        r"(?i)(security_definer)",
        r"(?i)(security_invoker)",
    ]
    
    # Tables with RLS enabled
    RLS_PROTECTED_TABLES = [
        "candidates",
        "applications", 
        "resume_jobs"
    ]
    
    def __init__(self):
        self.security_logger = SecurityLogger()
    
    async def validate_query_security(self, query: str, client_id: Optional[UUID] = None) -> bool:
        """Validate that a query doesn't contain SQL injection or RLS bypass attempts.
        
        Args:
            query: SQL query to validate
            client_id: Current client ID for logging
            
        Returns:
            True if query is safe, False otherwise
            
        Raises:
            SQLInjectionAttempt: If SQL injection detected
            RLSBypassAttempt: If RLS bypass attempt detected
        """
        # Check for RLS bypass patterns first (more specific)
        for pattern in self.RLS_BYPASS_PATTERNS:
            if re.search(pattern, query):
                logger.critical("RLS bypass attempt detected", 
                              pattern=pattern, 
                              query_snippet=query[:100],
                              client_id=str(client_id) if client_id else None)
                raise RLSBypassAttempt(f"RLS bypass pattern detected: {pattern}")
        
        # Check for SQL injection patterns
        for pattern in self.SQL_INJECTION_PATTERNS:
            if re.search(pattern, query):
                logger.warning("SQL injection attempt detected", 
                             pattern=pattern, 
                             query_snippet=query[:100],
                             client_id=str(client_id) if client_id else None)
                raise SQLInjectionAttempt(f"SQL injection pattern detected: {pattern}")
        
        return True
    
    async def test_cross_client_access_prevention(self, db: Session) -> Dict[str, Any]:
        """Test that clients cannot access each other's data.
        
        Args:
            db: Database session
            
        Returns:
            Test results dictionary
        """
        results = {
            "test_name": "cross_client_access_prevention",
            "passed": True,
            "violations": [],
            "details": {}
        }
        
        try:
            # Create two test clients
            client1_id = uuid4()
            client2_id = uuid4()
            
            # Create test data for client1
            test_candidate_1 = {
                "id": uuid4(),
                "client_id": client1_id,
                "name": "Test Candidate 1",
                "email": "test1@example.com"
            }
            
            # Create test data for client2
            test_candidate_2 = {
                "id": uuid4(),
                "client_id": client2_id,
                "name": "Test Candidate 2", 
                "email": "test2@example.com"
            }
            
            # Insert test data (bypassing RLS for setup)
            db.execute(text("SET LOCAL row_security = off"))
            
            db.execute(text("""
                INSERT INTO candidates (id, client_id, name, email, created_at, updated_at)
                VALUES (:id1, :client_id1, :name1, :email1, NOW(), NOW()),
                       (:id2, :client_id2, :name2, :email2, NOW(), NOW())
            """), {
                "id1": test_candidate_1["id"],
                "client_id1": test_candidate_1["client_id"],
                "name1": test_candidate_1["name"],
                "email1": test_candidate_1["email"],
                "id2": test_candidate_2["id"],
                "client_id2": test_candidate_2["client_id"],
                "name2": test_candidate_2["name"],
                "email2": test_candidate_2["email"]
            })
            
            db.execute(text("SET LOCAL row_security = on"))
            db.commit()
            
            # Test 1: Client1 should only see their own data
            set_client_context(db, client1_id)
            
            client1_results = db.execute(text("""
                SELECT id, client_id, name FROM candidates
            """)).fetchall()
            
            client1_candidate_ids = [str(row[0]) for row in client1_results]
            
            if str(test_candidate_2["id"]) in client1_candidate_ids:
                results["passed"] = False
                results["violations"].append({
                    "type": "cross_client_data_access",
                    "description": "Client1 can see Client2's candidate data",
                    "client_id": str(client1_id),
                    "accessed_data": str(test_candidate_2["id"])
                })
            
            # Test 2: Client2 should only see their own data
            set_client_context(db, client2_id)
            
            client2_results = db.execute(text("""
                SELECT id, client_id, name FROM candidates
            """)).fetchall()
            
            client2_candidate_ids = [str(row[0]) for row in client2_results]
            
            if str(test_candidate_1["id"]) in client2_candidate_ids:
                results["passed"] = False
                results["violations"].append({
                    "type": "cross_client_data_access",
                    "description": "Client2 can see Client1's candidate data",
                    "client_id": str(client2_id),
                    "accessed_data": str(test_candidate_1["id"])
                })
            
            # Test 3: Attempt direct RLS bypass
            try:
                # Try to bypass RLS by setting different client context
                db.execute(text(f"SET LOCAL app.current_client_id = '{client1_id}'"))
                
                bypass_results = db.execute(text("""
                    SELECT id, client_id FROM candidates WHERE client_id = :target_client_id
                """), {"target_client_id": client2_id}).fetchall()
                
                if len(bypass_results) > 0:
                    results["passed"] = False
                    results["violations"].append({
                        "type": "rls_bypass_success",
                        "description": "Successfully bypassed RLS to access other client's data",
                        "method": "direct_context_manipulation"
                    })
                    
            except Exception as e:
                # This is expected - RLS should prevent the bypass
                logger.debug("RLS bypass attempt properly blocked", error=str(e))
            
            # Test 4: Attempt SQL injection to bypass RLS
            malicious_queries = [
                "'; SET app.current_client_id = '{client2_id}'; SELECT * FROM candidates WHERE '1'='1",
                f"' UNION SELECT id, client_id, name, email, phone FROM candidates WHERE client_id = '{client2_id}' --",
                f"'; DROP POLICY client_isolation_candidates ON candidates; SELECT * FROM candidates --"
            ]
            
            for malicious_query in malicious_queries:
                try:
                    # This should be blocked by input validation
                    await self.validate_query_security(malicious_query, client1_id)
                    results["violations"].append({
                        "type": "sql_injection_not_detected",
                        "description": "Malicious query passed validation",
                        "query": malicious_query[:100]
                    })
                    results["passed"] = False
                except (SQLInjectionAttempt, RLSBypassAttempt):
                    # This is expected - malicious queries should be blocked
                    pass
            
            results["details"] = {
                "client1_visible_candidates": len(client1_results),
                "client2_visible_candidates": len(client2_results),
                "test_candidates_created": 2
            }
            
            # Cleanup test data
            db.execute(text("SET LOCAL row_security = off"))
            db.execute(text("""
                DELETE FROM candidates WHERE id IN (:id1, :id2)
            """), {"id1": test_candidate_1["id"], "id2": test_candidate_2["id"]})
            db.execute(text("SET LOCAL row_security = on"))
            db.commit()
            
        except Exception as e:
            logger.error("Cross-client access test failed", error=str(e))
            results["passed"] = False
            results["violations"].append({
                "type": "test_execution_error",
                "description": str(e)
            })
        
        return results
    
    async def test_unauthenticated_access_prevention(self, db: Session) -> Dict[str, Any]:
        """Test that unauthenticated requests cannot access or modify data.
        
        Args:
            db: Database session
            
        Returns:
            Test results dictionary
        """
        results = {
            "test_name": "unauthenticated_access_prevention",
            "passed": True,
            "violations": [],
            "details": {}
        }
        
        try:
            # Clear any existing client context
            clear_client_context(db)
            
            # Test 1: Try to read data without client context
            try:
                candidates = db.execute(text("SELECT COUNT(*) FROM candidates")).scalar()
                if candidates > 0:
                    results["passed"] = False
                    results["violations"].append({
                        "type": "unauthenticated_read_access",
                        "description": "Can read candidate data without authentication",
                        "records_accessed": candidates
                    })
            except Exception as e:
                # This is expected - should fail without client context
                logger.debug("Unauthenticated read properly blocked", error=str(e))
            
            # Test 2: Try to insert data without client context
            try:
                test_id = uuid4()
                db.execute(text("""
                    INSERT INTO candidates (id, client_id, name, email, created_at, updated_at)
                    VALUES (:id, :client_id, :name, :email, NOW(), NOW())
                """), {
                    "id": test_id,
                    "client_id": uuid4(),
                    "name": "Unauthorized Candidate",
                    "email": "unauthorized@example.com"
                })
                db.commit()
                
                # If we get here, the insert succeeded (bad)
                results["passed"] = False
                results["violations"].append({
                    "type": "unauthenticated_write_access",
                    "description": "Can insert data without authentication",
                    "inserted_record_id": str(test_id)
                })
                
                # Cleanup
                db.execute(text("DELETE FROM candidates WHERE id = :id"), {"id": test_id})
                db.commit()
                
            except Exception as e:
                # This is expected - should fail without client context
                logger.debug("Unauthenticated write properly blocked", error=str(e))
            
            # Test 3: Try to update data without client context
            try:
                db.execute(text("""
                    UPDATE candidates SET name = 'Hacked Name' WHERE name LIKE '%Test%'
                """))
                affected_rows = db.execute(text("SELECT ROW_COUNT()")).scalar()
                
                if affected_rows > 0:
                    results["passed"] = False
                    results["violations"].append({
                        "type": "unauthenticated_update_access",
                        "description": "Can update data without authentication",
                        "affected_rows": affected_rows
                    })
                    
            except Exception as e:
                # This is expected - should fail without client context
                logger.debug("Unauthenticated update properly blocked", error=str(e))
            
            # Test 4: Try to delete data without client context
            try:
                db.execute(text("DELETE FROM candidates WHERE name LIKE '%Test%'"))
                affected_rows = db.execute(text("SELECT ROW_COUNT()")).scalar()
                
                if affected_rows > 0:
                    results["passed"] = False
                    results["violations"].append({
                        "type": "unauthenticated_delete_access",
                        "description": "Can delete data without authentication",
                        "affected_rows": affected_rows
                    })
                    
            except Exception as e:
                # This is expected - should fail without client context
                logger.debug("Unauthenticated delete properly blocked", error=str(e))
            
        except Exception as e:
            logger.error("Unauthenticated access test failed", error=str(e))
            results["passed"] = False
            results["violations"].append({
                "type": "test_execution_error",
                "description": str(e)
            })
        
        return results
    
    async def test_rls_policy_integrity(self, db: Session) -> Dict[str, Any]:
        """Test that RLS policies are properly configured and cannot be bypassed.
        
        Args:
            db: Database session
            
        Returns:
            Test results dictionary
        """
        results = {
            "test_name": "rls_policy_integrity",
            "passed": True,
            "violations": [],
            "details": {}
        }
        
        try:
            # Test 1: Verify RLS is enabled on protected tables
            for table_name in self.RLS_PROTECTED_TABLES:
                rls_status = db.execute(text("""
                    SELECT relrowsecurity 
                    FROM pg_class 
                    WHERE relname = :table_name
                """), {"table_name": table_name}).scalar()
                
                if not rls_status:
                    results["passed"] = False
                    results["violations"].append({
                        "type": "rls_not_enabled",
                        "description": f"RLS not enabled on table {table_name}",
                        "table": table_name
                    })
            
            # Test 2: Verify RLS policies exist
            for table_name in self.RLS_PROTECTED_TABLES:
                policies = db.execute(text("""
                    SELECT COUNT(*) 
                    FROM pg_policies 
                    WHERE tablename = :table_name
                """), {"table_name": table_name}).scalar()
                
                if policies == 0:
                    results["passed"] = False
                    results["violations"].append({
                        "type": "no_rls_policies",
                        "description": f"No RLS policies found for table {table_name}",
                        "table": table_name
                    })
            
            # Test 3: Verify policy conditions are correct
            for table_name in self.RLS_PROTECTED_TABLES:
                policy_details = db.execute(text("""
                    SELECT policyname, qual 
                    FROM pg_policies 
                    WHERE tablename = :table_name
                """), {"table_name": table_name}).fetchall()
                
                for policy_name, condition in policy_details:
                    if "app.current_client_id" not in condition:
                        results["passed"] = False
                        results["violations"].append({
                            "type": "incorrect_policy_condition",
                            "description": f"Policy {policy_name} on {table_name} doesn't use client_id",
                            "table": table_name,
                            "policy": policy_name,
                            "condition": condition
                        })
            
            # Test 4: Test policy bypass attempts
            bypass_attempts = [
                "SET row_security = off",
                "ALTER TABLE candidates DISABLE ROW LEVEL SECURITY",
                "DROP POLICY client_isolation_candidates ON candidates",
                "CREATE POLICY bypass_policy ON candidates FOR ALL TO PUBLIC USING (true)"
            ]
            
            for attempt in bypass_attempts:
                try:
                    db.execute(text(attempt))
                    db.commit()
                    
                    # If we get here, the bypass succeeded (bad)
                    results["passed"] = False
                    results["violations"].append({
                        "type": "policy_bypass_success",
                        "description": f"Successfully executed policy bypass: {attempt}",
                        "bypass_query": attempt
                    })
                    
                except Exception as e:
                    # This is expected - bypass attempts should fail
                    logger.debug("Policy bypass properly blocked", attempt=attempt, error=str(e))
                    db.rollback()
            
            results["details"] = {
                "tables_checked": len(self.RLS_PROTECTED_TABLES),
                "bypass_attempts_tested": len(bypass_attempts)
            }
            
        except Exception as e:
            logger.error("RLS policy integrity test failed", error=str(e))
            results["passed"] = False
            results["violations"].append({
                "type": "test_execution_error",
                "description": str(e)
            })
        
        return results
    
    async def run_comprehensive_security_scan(self, db: Session) -> Dict[str, Any]:
        """Run comprehensive security scan for RLS vulnerabilities.
        
        Args:
            db: Database session
            
        Returns:
            Comprehensive security scan results
        """
        scan_results = {
            "scan_timestamp": datetime.utcnow().isoformat(),
            "overall_status": "PASS",
            "tests_run": 0,
            "tests_passed": 0,
            "tests_failed": 0,
            "critical_violations": 0,
            "test_results": [],
            "summary": {}
        }
        
        try:
            # Run all security tests
            tests = [
                self.test_cross_client_access_prevention,
                self.test_unauthenticated_access_prevention,
                self.test_rls_policy_integrity
            ]
            
            for test_func in tests:
                try:
                    test_result = await test_func(db)
                    scan_results["test_results"].append(test_result)
                    scan_results["tests_run"] += 1
                    
                    if test_result["passed"]:
                        scan_results["tests_passed"] += 1
                    else:
                        scan_results["tests_failed"] += 1
                        scan_results["overall_status"] = "FAIL"
                        
                        # Count critical violations
                        for violation in test_result["violations"]:
                            if violation["type"] in [
                                "cross_client_data_access",
                                "rls_bypass_success", 
                                "unauthenticated_write_access",
                                "policy_bypass_success"
                            ]:
                                scan_results["critical_violations"] += 1
                
                except Exception as e:
                    logger.error("Security test failed", test=test_func.__name__, error=str(e))
                    scan_results["tests_run"] += 1
                    scan_results["tests_failed"] += 1
                    scan_results["overall_status"] = "FAIL"
            
            # Generate summary
            scan_results["summary"] = {
                "total_violations": sum(len(test["violations"]) for test in scan_results["test_results"]),
                "critical_violations": scan_results["critical_violations"],
                "pass_rate": f"{(scan_results['tests_passed'] / scan_results['tests_run'] * 100):.1f}%" if scan_results["tests_run"] > 0 else "0%",
                "recommendation": "PRODUCTION_READY" if scan_results["overall_status"] == "PASS" else "REQUIRES_IMMEDIATE_ATTENTION"
            }
            
            # Log security scan results
            if scan_results["critical_violations"] > 0:
                logger.critical("Critical security vulnerabilities detected", 
                              critical_violations=scan_results["critical_violations"],
                              total_violations=scan_results["summary"]["total_violations"])
            else:
                logger.info("Security scan completed", 
                          status=scan_results["overall_status"],
                          tests_passed=scan_results["tests_passed"],
                          tests_failed=scan_results["tests_failed"])
            
        except Exception as e:
            logger.error("Security scan failed", error=str(e))
            scan_results["overall_status"] = "ERROR"
            scan_results["error"] = str(e)
        
        return scan_results
    
    async def log_security_violation(self, db: Session, violation_type: str, 
                                   details: Dict[str, Any], client_id: Optional[UUID] = None):
        """Log security violation to audit log.
        
        Args:
            db: Database session
            violation_type: Type of security violation
            details: Violation details
            client_id: Optional client ID
        """
        try:
            severity = SecurityEventSeverity.CRITICAL if violation_type in [
                "rls_bypass_success", "cross_client_data_access", "policy_bypass_success"
            ] else SecurityEventSeverity.HIGH
            
            self.security_logger.log_security_event(
                db=db,
                event_type=SecurityEventType.RLS_BYPASS_ATTEMPT,
                severity=severity,
                details=details,
                client_id=client_id
            )
            
        except Exception as e:
            logger.error("Failed to log security violation", error=str(e))


# Global RLS validator instance
rls_validator = RLSValidator()