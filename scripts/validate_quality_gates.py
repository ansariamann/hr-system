#!/usr/bin/env python3
"""
Quality Gates Validation Script

This script validates that all quality gates pass before allowing deployment.
It checks security scan results, test results, and enforces quality standards.
"""

import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Tuple, Any
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class QualityGateValidator:
    """Validates all quality gates for CI pipeline"""
    
    def __init__(self):
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.passed_gates: List[str] = []
        
    def validate_security_scans(self) -> bool:
        """Validate security scan results"""
        logger.info("Validating security scan results...")
        
        # Check Bandit results
        bandit_path = Path("security-reports/bandit-report.json")
        if bandit_path.exists():
            with open(bandit_path) as f:
                bandit_data = json.load(f)
                high_severity = [r for r in bandit_data.get("results", []) 
                               if r.get("issue_severity") == "HIGH"]
                if high_severity:
                    self.errors.append(f"Bandit found {len(high_severity)} high-severity security issues")
                else:
                    self.passed_gates.append("Bandit security scan")
        else:
            self.warnings.append("Bandit report not found")
            
        # Check Safety results
        safety_path = Path("security-reports/safety-report.json")
        if safety_path.exists():
            with open(safety_path) as f:
                safety_data = json.load(f)
                vulnerabilities = safety_data.get("vulnerabilities", [])
                if vulnerabilities:
                    self.errors.append(f"Safety found {len(vulnerabilities)} vulnerabilities")
                else:
                    self.passed_gates.append("Safety vulnerability scan")
        else:
            self.warnings.append("Safety report not found")
            
        # Check Semgrep results
        semgrep_path = Path("security-reports/semgrep-report.json")
        if semgrep_path.exists():
            with open(semgrep_path) as f:
                semgrep_data = json.load(f)
                results = semgrep_data.get("results", [])
                high_severity = [r for r in results 
                               if r.get("extra", {}).get("severity") in ["ERROR", "WARNING"]]
                if high_severity:
                    self.errors.append(f"Semgrep found {len(high_severity)} security issues")
                else:
                    self.passed_gates.append("Semgrep security scan")
        else:
            self.warnings.append("Semgrep report not found")
            
        # Check custom security scanner
        custom_scan_path = Path("security-reports/security-scan-report.json")
        if custom_scan_path.exists():
            with open(custom_scan_path) as f:
                scan_data = json.load(f)
                if not scan_data.get("passed", False):
                    self.errors.append("Custom security scan failed")
                else:
                    self.passed_gates.append("Custom security scan")
        else:
            self.warnings.append("Custom security scan report not found")
            
        return len(self.errors) == 0
        
    def validate_property_tests(self) -> bool:
        """Validate property-based test results"""
        logger.info("Validating property-based test results...")
        
        test_results_path = Path("property-test-results/property-test-results.xml")
        if not test_results_path.exists():
            self.errors.append("Property test results not found")
            return False
            
        try:
            tree = ET.parse(test_results_path)
            root = tree.getroot()
            
            # Check for test failures
            failures = int(root.get("failures", 0))
            errors = int(root.get("errors", 0))
            tests = int(root.get("tests", 0))
            
            if failures > 0:
                self.errors.append(f"Property tests had {failures} failures")
                
            if errors > 0:
                self.errors.append(f"Property tests had {errors} errors")
                
            if tests == 0:
                self.errors.append("No property tests were executed")
                
            # Validate minimum test coverage
            required_properties = [
                "test_comprehensive_property_test_framework",
                "test_comprehensive_authentication_security", 
                "test_rls_bypass_prevention",
                "test_abuse_protection_enforcement",
                "test_authentication_requirement_enforcement",
                "test_comprehensive_fsm_invariant_enforcement",
                "test_comprehensive_sse_reliability",
                "test_comprehensive_metrics_collection",
                "test_backup_and_restore_reliability",
                "test_comprehensive_system_robustness",
                "test_ci_regression_prevention"
            ]
            
            executed_tests = [tc.get("name") for tc in root.findall(".//testcase")]
            missing_properties = [prop for prop in required_properties 
                                if not any(prop in test for test in executed_tests)]
            
            if missing_properties:
                self.errors.append(f"Missing required property tests: {missing_properties}")
                
            if failures == 0 and errors == 0 and tests > 0 and not missing_properties:
                self.passed_gates.append(f"Property-based tests ({tests} tests)")
                
        except ET.ParseError as e:
            self.errors.append(f"Failed to parse property test results: {e}")
            
        return len([e for e in self.errors if "Property" in e]) == 0
        
    def validate_integration_tests(self) -> bool:
        """Validate integration test results"""
        logger.info("Validating integration test results...")
        
        test_results_path = Path("integration-test-results/integration-test-results.xml")
        if not test_results_path.exists():
            self.errors.append("Integration test results not found")
            return False
            
        try:
            tree = ET.parse(test_results_path)
            root = tree.getroot()
            
            failures = int(root.get("failures", 0))
            errors = int(root.get("errors", 0))
            tests = int(root.get("tests", 0))
            
            if failures > 0:
                self.errors.append(f"Integration tests had {failures} failures")
                
            if errors > 0:
                self.errors.append(f"Integration tests had {errors} errors")
                
            if tests == 0:
                self.warnings.append("No integration tests were executed")
            elif failures == 0 and errors == 0:
                self.passed_gates.append(f"Integration tests ({tests} tests)")
                
        except ET.ParseError as e:
            self.errors.append(f"Failed to parse integration test results: {e}")
            
        return len([e for e in self.errors if "Integration" in e]) == 0
        
    def validate_code_quality(self) -> bool:
        """Validate code quality metrics"""
        logger.info("Validating code quality metrics...")
        
        # This would integrate with tools like SonarQube, CodeClimate, etc.
        # For now, we'll do basic validation
        
        # Check for critical files existence
        critical_files = [
            "src/ats_backend/core/config.py",
            "src/ats_backend/auth/security.py", 
            "src/ats_backend/security/middleware.py",
            "src/ats_backend/core/observability.py",
            "src/ats_backend/core/disaster_recovery.py"
        ]
        
        missing_files = [f for f in critical_files if not Path(f).exists()]
        if missing_files:
            self.errors.append(f"Critical files missing: {missing_files}")
        else:
            self.passed_gates.append("Critical files present")
            
        return len([e for e in self.errors if "Critical files" in e]) == 0
        
    def validate_deployment_readiness(self) -> bool:
        """Validate deployment readiness"""
        logger.info("Validating deployment readiness...")
        
        # Check environment configurations
        env_files = ["environments/.env.dev", "environments/.env.staging", "environments/.env.prod"]
        missing_envs = [f for f in env_files if not Path(f).exists()]
        
        if missing_envs:
            self.errors.append(f"Missing environment files: {missing_envs}")
        else:
            self.passed_gates.append("Environment configurations")
            
        # Check Docker configurations
        docker_files = ["Dockerfile", "docker-compose.yml", "docker-compose.prod.yml"]
        missing_docker = [f for f in docker_files if not Path(f).exists()]
        
        if missing_docker:
            self.errors.append(f"Missing Docker files: {missing_docker}")
        else:
            self.passed_gates.append("Docker configurations")
            
        return len([e for e in self.errors if any(x in e for x in ["environment", "Docker"])]) == 0
        
    def generate_report(self) -> Dict[str, Any]:
        """Generate comprehensive quality gate report"""
        return {
            "passed_gates": self.passed_gates,
            "errors": self.errors,
            "warnings": self.warnings,
            "total_gates": len(self.passed_gates) + len(self.errors),
            "success_rate": len(self.passed_gates) / (len(self.passed_gates) + len(self.errors)) if (len(self.passed_gates) + len(self.errors)) > 0 else 0,
            "overall_status": "PASS" if len(self.errors) == 0 else "FAIL"
        }
        
    def run_all_validations(self) -> bool:
        """Run all quality gate validations"""
        logger.info("Starting quality gate validation...")
        
        validations = [
            ("Security Scans", self.validate_security_scans),
            ("Property Tests", self.validate_property_tests),
            ("Integration Tests", self.validate_integration_tests),
            ("Code Quality", self.validate_code_quality),
            ("Deployment Readiness", self.validate_deployment_readiness)
        ]
        
        all_passed = True
        for name, validation_func in validations:
            try:
                result = validation_func()
                if not result:
                    all_passed = False
                    logger.error(f"{name} validation failed")
                else:
                    logger.info(f"{name} validation passed")
            except Exception as e:
                logger.error(f"{name} validation error: {e}")
                self.errors.append(f"{name} validation error: {e}")
                all_passed = False
                
        return all_passed

def main():
    """Main entry point"""
    validator = QualityGateValidator()
    
    try:
        success = validator.run_all_validations()
        report = validator.generate_report()
        
        # Print summary
        print("\n" + "="*60)
        print("QUALITY GATE VALIDATION SUMMARY")
        print("="*60)
        print(f"Overall Status: {report['overall_status']}")
        print(f"Success Rate: {report['success_rate']:.1%}")
        print(f"Passed Gates: {len(report['passed_gates'])}")
        print(f"Failed Gates: {len(report['errors'])}")
        print(f"Warnings: {len(report['warnings'])}")
        
        if report['passed_gates']:
            print(f"\n✅ PASSED GATES:")
            for gate in report['passed_gates']:
                print(f"  - {gate}")
                
        if report['errors']:
            print(f"\n❌ FAILED GATES:")
            for error in report['errors']:
                print(f"  - {error}")
                
        if report['warnings']:
            print(f"\n⚠️  WARNINGS:")
            for warning in report['warnings']:
                print(f"  - {warning}")
                
        print("="*60)
        
        # Save report
        with open("quality-gate-report.json", "w") as f:
            json.dump(report, f, indent=2)
            
        if not success:
            print("\n🚫 QUALITY GATES FAILED - BLOCKING DEPLOYMENT")
            sys.exit(1)
        else:
            print("\n✅ ALL QUALITY GATES PASSED - DEPLOYMENT APPROVED")
            sys.exit(0)
            
    except Exception as e:
        logger.error(f"Quality gate validation failed with error: {e}")
        print(f"\n💥 VALIDATION ERROR: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()