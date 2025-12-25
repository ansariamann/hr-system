"""Security API endpoints for RLS bypass prevention and validation."""

from datetime import datetime
from typing import Dict, List, Optional, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
import structlog

from ats_backend.core.database import get_db
from ats_backend.auth.dependencies import get_current_user
from ats_backend.auth.models import User
from ats_backend.security.security_scanner import security_scanner, SecurityScanResult
from ats_backend.security.rls_validator import rls_validator

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/security", tags=["security"])


@router.post("/scan/comprehensive")
async def run_comprehensive_security_scan(
    scan_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Run comprehensive security scan including all RLS tests.
    
    Args:
        scan_id: Optional scan identifier
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        Security scan results
    """
    try:
        logger.info("Starting comprehensive security scan", 
                   user_id=str(current_user.id),
                   client_id=str(current_user.client_id),
                   scan_id=scan_id)
        
        # Run comprehensive security scan
        scan_result = await security_scanner.run_full_security_scan(db, scan_id)
        
        # Generate security report
        security_report = await security_scanner.generate_security_report(scan_result)
        
        return {
            "scan_result": scan_result.to_dict(),
            "security_report": security_report,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error("Comprehensive security scan failed", 
                    user_id=str(current_user.id),
                    error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Security scan failed: {str(e)}"
        )


@router.post("/scan/targeted/{test_type}")
async def run_targeted_security_test(
    test_type: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Run specific security test.
    
    Args:
        test_type: Type of test to run (cross_client_access, unauthenticated_access, policy_integrity)
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        Test results
    """
    valid_test_types = ["cross_client_access", "unauthenticated_access", "policy_integrity"]
    
    if test_type not in valid_test_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid test type. Must be one of: {', '.join(valid_test_types)}"
        )
    
    try:
        logger.info("Running targeted security test", 
                   test_type=test_type,
                   user_id=str(current_user.id),
                   client_id=str(current_user.client_id))
        
        # Run targeted test
        test_result = await security_scanner.run_targeted_rls_test(db, test_type, current_user.client_id)
        
        return {
            "test_type": test_type,
            "result": test_result,
            "timestamp": datetime.utcnow().isoformat(),
            "client_id": str(current_user.client_id)
        }
        
    except Exception as e:
        logger.error("Targeted security test failed", 
                    test_type=test_type,
                    user_id=str(current_user.id),
                    error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Security test failed: {str(e)}"
        )


@router.post("/validate/query")
async def validate_query_security(
    query: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Validate query for SQL injection and RLS bypass attempts.
    
    Args:
        query: SQL query to validate
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        Validation results
    """
    try:
        logger.info("Validating query security", 
                   user_id=str(current_user.id),
                   client_id=str(current_user.client_id),
                   query_length=len(query))
        
        # Validate query security
        is_safe = await rls_validator.validate_query_security(query, current_user.client_id)
        
        return {
            "query_safe": is_safe,
            "query_length": len(query),
            "validation_timestamp": datetime.utcnow().isoformat(),
            "client_id": str(current_user.client_id)
        }
        
    except Exception as e:
        logger.warning("Query validation detected security issue", 
                      user_id=str(current_user.id),
                      error=str(e),
                      query_snippet=query[:100])
        
        return {
            "query_safe": False,
            "security_violation": str(e),
            "query_length": len(query),
            "validation_timestamp": datetime.utcnow().isoformat(),
            "client_id": str(current_user.client_id)
        }


@router.post("/test/cross-client-access")
async def test_cross_client_token_access(
    target_client_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Test cross-client token access prevention.
    
    Args:
        target_client_id: Client ID to attempt access to
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        Cross-client access test results
    """
    try:
        logger.info("Testing cross-client token access", 
                   user_id=str(current_user.id),
                   user_client_id=str(current_user.client_id),
                   target_client_id=str(target_client_id))
        
        # Create token data from current user
        token_data = {
            "sub": str(current_user.id),
            "client_id": str(current_user.client_id),
            "email": current_user.email
        }
        
        # Test cross-client access
        test_result = await security_scanner.validate_token_cross_client_access(
            db, token_data, target_client_id
        )
        
        return {
            "test_result": test_result,
            "user_client_id": str(current_user.client_id),
            "target_client_id": str(target_client_id),
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error("Cross-client access test failed", 
                    user_id=str(current_user.id),
                    error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Cross-client access test failed: {str(e)}"
        )


@router.post("/test/sql-injection")
async def test_sql_injection_protection(
    malicious_inputs: List[str],
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Test SQL injection protection mechanisms.
    
    Args:
        malicious_inputs: List of malicious SQL inputs to test
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        SQL injection protection test results
    """
    if len(malicious_inputs) > 20:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Too many inputs. Maximum 20 allowed per test."
        )
    
    try:
        logger.info("Testing SQL injection protection", 
                   user_id=str(current_user.id),
                   client_id=str(current_user.client_id),
                   input_count=len(malicious_inputs))
        
        # Test SQL injection protection
        test_result = await security_scanner.test_sql_injection_protection(db, malicious_inputs)
        
        return {
            "test_result": test_result,
            "inputs_tested": len(malicious_inputs),
            "client_id": str(current_user.client_id),
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error("SQL injection protection test failed", 
                    user_id=str(current_user.id),
                    error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"SQL injection protection test failed: {str(e)}"
        )


@router.get("/scan/history")
async def get_security_scan_history(
    limit: int = Query(10, ge=1, le=50),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Get security scan history.
    
    Args:
        limit: Maximum number of scans to return
        current_user: Current authenticated user
        
    Returns:
        Security scan history
    """
    try:
        logger.info("Retrieving security scan history", 
                   user_id=str(current_user.id),
                   limit=limit)
        
        # Get scan history
        scan_history = security_scanner.get_scan_history(limit)
        
        return {
            "scan_history": scan_history,
            "total_scans": len(scan_history),
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error("Failed to retrieve scan history", 
                    user_id=str(current_user.id),
                    error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve scan history: {str(e)}"
        )


@router.get("/metrics")
async def get_security_metrics(
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Get security metrics from scan history.
    
    Args:
        current_user: Current authenticated user
        
    Returns:
        Security metrics
    """
    try:
        logger.info("Retrieving security metrics", 
                   user_id=str(current_user.id))
        
        # Get security metrics
        metrics = security_scanner.get_security_metrics()
        
        return {
            "security_metrics": metrics,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error("Failed to retrieve security metrics", 
                    user_id=str(current_user.id),
                    error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve security metrics: {str(e)}"
        )


@router.get("/status")
async def get_security_status(
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Get overall security status.
    
    Args:
        current_user: Current authenticated user
        
    Returns:
        Security status summary
    """
    try:
        logger.info("Retrieving security status", 
                   user_id=str(current_user.id))
        
        # Get recent scan results
        recent_scans = security_scanner.get_scan_history(5)
        metrics = security_scanner.get_security_metrics()
        
        # Determine overall status
        if not recent_scans:
            overall_status = "UNKNOWN"
            recommendation = "Run security scan to assess system status"
        else:
            latest_scan = recent_scans[0]
            if latest_scan["status"] == "PASS" and latest_scan["critical_violations"] == 0:
                overall_status = "SECURE"
                recommendation = "System is secure and production ready"
            elif latest_scan["critical_violations"] > 0:
                overall_status = "CRITICAL"
                recommendation = "Critical security vulnerabilities detected - immediate attention required"
            else:
                overall_status = "WARNING"
                recommendation = "Security issues detected - review and remediate"
        
        return {
            "overall_status": overall_status,
            "recommendation": recommendation,
            "latest_scan": recent_scans[0] if recent_scans else None,
            "metrics": metrics,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error("Failed to retrieve security status", 
                    user_id=str(current_user.id),
                    error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve security status: {str(e)}"
        )