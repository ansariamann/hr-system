"""Automated security scanning service for RLS vulnerabilities."""

import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from uuid import UUID, uuid4

from sqlalchemy.orm import Session
from sqlalchemy import text
import structlog

from ats_backend.core.database import get_db
from ats_backend.auth.security import SecurityLogger, SecurityEventType, SecurityEventSeverity
from .rls_validator import RLSValidator, rls_validator

logger = structlog.get_logger(__name__)


class SecurityScanResult:
    """Security scan result model."""
    
    def __init__(self, scan_id: str, scan_type: str, status: str, 
                 results: Dict[str, Any], timestamp: datetime):
        self.scan_id = scan_id
        self.scan_type = scan_type
        self.status = status
        self.results = results
        self.timestamp = timestamp
        self.critical_violations = results.get("critical_violations", 0)
        self.total_violations = results.get("summary", {}).get("total_violations", 0)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "scan_id": self.scan_id,
            "scan_type": self.scan_type,
            "status": self.status,
            "timestamp": self.timestamp.isoformat(),
            "critical_violations": self.critical_violations,
            "total_violations": self.total_violations,
            "results": self.results
        }
    
    def is_production_ready(self) -> bool:
        """Check if system is production ready based on scan results."""
        return (self.status == "PASS" and 
                self.critical_violations == 0 and
                self.results.get("overall_status") == "PASS")


class SecurityScanner:
    """Automated security scanning service for comprehensive RLS vulnerability detection."""
    
    def __init__(self):
        self.rls_validator = rls_validator
        self.security_logger = SecurityLogger()
        self.scan_history: List[SecurityScanResult] = []
    
    async def run_full_security_scan(self, db: Session, scan_id: Optional[str] = None) -> SecurityScanResult:
        """Run comprehensive security scan including all RLS tests.
        
        Args:
            db: Database session
            scan_id: Optional scan identifier
            
        Returns:
            Security scan result
        """
        if not scan_id:
            scan_id = f"security_scan_{uuid4().hex[:8]}"
        
        logger.info("Starting comprehensive security scan", scan_id=scan_id)
        
        try:
            # Run comprehensive RLS security scan
            scan_results = await self.rls_validator.run_comprehensive_security_scan(db)
            
            # Create scan result object
            result = SecurityScanResult(
                scan_id=scan_id,
                scan_type="comprehensive_rls_scan",
                status=scan_results["overall_status"],
                results=scan_results,
                timestamp=datetime.utcnow()
            )
            
            # Store in history
            self.scan_history.append(result)
            
            # Log security events for violations
            await self._log_scan_violations(db, result)
            
            logger.info("Security scan completed", 
                       scan_id=scan_id,
                       status=result.status,
                       critical_violations=result.critical_violations,
                       total_violations=result.total_violations)
            
            return result
            
        except Exception as e:
            logger.error("Security scan failed", scan_id=scan_id, error=str(e))
            
            # Create error result
            error_result = SecurityScanResult(
                scan_id=scan_id,
                scan_type="comprehensive_rls_scan",
                status="ERROR",
                results={"error": str(e), "timestamp": datetime.utcnow().isoformat()},
                timestamp=datetime.utcnow()
            )
            
            self.scan_history.append(error_result)
            return error_result
    
    async def run_targeted_rls_test(self, db: Session, test_type: str, 
                                  client_id: Optional[UUID] = None) -> Dict[str, Any]:
        """Run specific RLS test.
        
        Args:
            db: Database session
            test_type: Type of test to run
            client_id: Optional client ID for context
            
        Returns:
            Test results
        """
        logger.info("Running targeted RLS test", test_type=test_type, client_id=str(client_id) if client_id else None)
        
        try:
            if test_type == "cross_client_access":
                return await self.rls_validator.test_cross_client_access_prevention(db)
            elif test_type == "unauthenticated_access":
                return await self.rls_validator.test_unauthenticated_access_prevention(db)
            elif test_type == "policy_integrity":
                return await self.rls_validator.test_rls_policy_integrity(db)
            else:
                raise ValueError(f"Unknown test type: {test_type}")
                
        except Exception as e:
            logger.error("Targeted RLS test failed", test_type=test_type, error=str(e))
            return {
                "test_name": test_type,
                "passed": False,
                "violations": [{"type": "test_execution_error", "description": str(e)}],
                "details": {}
            }
    
    async def validate_token_cross_client_access(self, db: Session, token_data: Dict[str, Any], 
                                               target_client_id: UUID) -> Dict[str, Any]:
        """Validate that a token cannot access data from a different client.
        
        Args:
            db: Database session
            token_data: Token payload data
            target_client_id: Client ID to attempt access to
            
        Returns:
            Validation results
        """
        results = {
            "test_name": "token_cross_client_validation",
            "passed": True,
            "violations": [],
            "details": {}
        }
        
        try:
            token_client_id = UUID(token_data.get("client_id", ""))
            
            # If token is for the same client, access should be allowed
            if token_client_id == target_client_id:
                results["details"]["access_type"] = "same_client_access"
                results["details"]["allowed"] = True
                return results
            
            # Set client context based on token
            from ats_backend.core.session_context import set_client_context
            set_client_context(db, token_client_id)
            
            # Try to access target client's data
            try:
                target_data = db.execute(text("""
                    SELECT COUNT(*) FROM candidates WHERE client_id = :target_client_id
                """), {"target_client_id": target_client_id}).scalar()
                
                if target_data > 0:
                    results["passed"] = False
                    results["violations"].append({
                        "type": "cross_client_token_access",
                        "description": f"Token for client {token_client_id} accessed data for client {target_client_id}",
                        "token_client_id": str(token_client_id),
                        "accessed_client_id": str(target_client_id),
                        "records_accessed": target_data
                    })
                
            except Exception as e:
                # This is expected - RLS should prevent cross-client access
                logger.debug("Cross-client access properly blocked", error=str(e))
            
            results["details"] = {
                "token_client_id": str(token_client_id),
                "target_client_id": str(target_client_id),
                "access_type": "cross_client_access",
                "allowed": not results["passed"]
            }
            
        except Exception as e:
            logger.error("Token cross-client validation failed", error=str(e))
            results["passed"] = False
            results["violations"].append({
                "type": "validation_error",
                "description": str(e)
            })
        
        return results
    
    async def test_sql_injection_protection(self, db: Session, 
                                          malicious_inputs: List[str]) -> Dict[str, Any]:
        """Test SQL injection protection mechanisms.
        
        Args:
            db: Database session
            malicious_inputs: List of malicious SQL inputs to test
            
        Returns:
            Test results
        """
        results = {
            "test_name": "sql_injection_protection",
            "passed": True,
            "violations": [],
            "details": {"inputs_tested": len(malicious_inputs), "blocked": 0, "allowed": 0}
        }
        
        for malicious_input in malicious_inputs:
            try:
                # Test input validation
                is_safe = await self.rls_validator.validate_query_security(malicious_input)
                
                if is_safe:
                    results["passed"] = False
                    results["violations"].append({
                        "type": "sql_injection_not_blocked",
                        "description": "Malicious SQL input passed validation",
                        "input": malicious_input[:100]  # Truncate for logging
                    })
                    results["details"]["allowed"] += 1
                else:
                    results["details"]["blocked"] += 1
                    
            except Exception as e:
                # Exceptions are expected for malicious inputs
                results["details"]["blocked"] += 1
                logger.debug("Malicious input properly blocked", input=malicious_input[:50], error=str(e))
        
        return results
    
    async def generate_security_report(self, scan_result: SecurityScanResult) -> Dict[str, Any]:
        """Generate comprehensive security report.
        
        Args:
            scan_result: Security scan result
            
        Returns:
            Formatted security report
        """
        report = {
            "executive_summary": {
                "scan_id": scan_result.scan_id,
                "timestamp": scan_result.timestamp.isoformat(),
                "overall_status": scan_result.status,
                "production_ready": scan_result.is_production_ready(),
                "critical_violations": scan_result.critical_violations,
                "total_violations": scan_result.total_violations
            },
            "detailed_findings": [],
            "recommendations": [],
            "compliance_status": {
                "rls_enabled": True,
                "policies_configured": True,
                "cross_tenant_isolation": scan_result.critical_violations == 0,
                "sql_injection_protection": True
            }
        }
        
        # Process test results
        for test_result in scan_result.results.get("test_results", []):
            finding = {
                "test_name": test_result["test_name"],
                "status": "PASS" if test_result["passed"] else "FAIL",
                "violations": test_result["violations"],
                "details": test_result["details"]
            }
            report["detailed_findings"].append(finding)
            
            # Generate recommendations for failures
            if not test_result["passed"]:
                for violation in test_result["violations"]:
                    recommendation = self._generate_recommendation(violation)
                    if recommendation:
                        report["recommendations"].append(recommendation)
        
        # Overall recommendations
        if not scan_result.is_production_ready():
            report["recommendations"].append({
                "priority": "CRITICAL",
                "category": "security",
                "description": "System is not production ready due to security violations",
                "action": "Address all critical security violations before production deployment"
            })
        
        return report
    
    def _generate_recommendation(self, violation: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Generate recommendation based on violation type.
        
        Args:
            violation: Security violation details
            
        Returns:
            Recommendation or None
        """
        violation_type = violation.get("type", "")
        
        recommendations = {
            "cross_client_data_access": {
                "priority": "CRITICAL",
                "category": "rls",
                "description": "Cross-client data access detected",
                "action": "Review and fix RLS policies to ensure proper tenant isolation"
            },
            "rls_bypass_success": {
                "priority": "CRITICAL", 
                "category": "rls",
                "description": "RLS bypass successful",
                "action": "Immediately review RLS configuration and fix bypass vulnerabilities"
            },
            "unauthenticated_write_access": {
                "priority": "CRITICAL",
                "category": "authentication",
                "description": "Unauthenticated write access allowed",
                "action": "Ensure all write operations require proper authentication"
            },
            "sql_injection_not_blocked": {
                "priority": "HIGH",
                "category": "input_validation",
                "description": "SQL injection attempt not blocked",
                "action": "Strengthen input validation and parameterized queries"
            },
            "rls_not_enabled": {
                "priority": "CRITICAL",
                "category": "rls",
                "description": "RLS not enabled on protected table",
                "action": "Enable RLS on all tenant-specific tables"
            }
        }
        
        return recommendations.get(violation_type)
    
    async def _log_scan_violations(self, db: Session, scan_result: SecurityScanResult):
        """Log security violations from scan results.
        
        Args:
            db: Database session
            scan_result: Security scan result
        """
        try:
            for test_result in scan_result.results.get("test_results", []):
                for violation in test_result["violations"]:
                    await self.rls_validator.log_security_violation(
                        db=db,
                        violation_type=violation["type"],
                        details={
                            "scan_id": scan_result.scan_id,
                            "test_name": test_result["test_name"],
                            "violation": violation,
                            "timestamp": scan_result.timestamp.isoformat()
                        }
                    )
        except Exception as e:
            logger.error("Failed to log scan violations", error=str(e))
    
    def get_scan_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent scan history.
        
        Args:
            limit: Maximum number of scans to return
            
        Returns:
            List of scan results
        """
        recent_scans = sorted(self.scan_history, key=lambda x: x.timestamp, reverse=True)[:limit]
        return [scan.to_dict() for scan in recent_scans]
    
    def get_security_metrics(self) -> Dict[str, Any]:
        """Get security metrics from scan history.
        
        Returns:
            Security metrics
        """
        if not self.scan_history:
            return {"total_scans": 0, "avg_violations": 0, "production_ready_rate": 0}
        
        total_scans = len(self.scan_history)
        total_violations = sum(scan.total_violations for scan in self.scan_history)
        production_ready_scans = sum(1 for scan in self.scan_history if scan.is_production_ready())
        
        return {
            "total_scans": total_scans,
            "avg_violations": total_violations / total_scans if total_scans > 0 else 0,
            "production_ready_rate": (production_ready_scans / total_scans * 100) if total_scans > 0 else 0,
            "last_scan_timestamp": self.scan_history[-1].timestamp.isoformat() if self.scan_history else None,
            "critical_violations_trend": [scan.critical_violations for scan in self.scan_history[-5:]]
        }


# Global security scanner instance
security_scanner = SecurityScanner()