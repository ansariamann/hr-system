#!/usr/bin/env python3
"""CLI tool for running comprehensive security scans."""

import asyncio
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ats_backend.core.database import db_manager
from ats_backend.core.config import settings
from ats_backend.security.security_scanner import security_scanner
from ats_backend.security.rls_validator import rls_validator


async def run_comprehensive_scan(output_file: str = None, verbose: bool = False, ci_mode: bool = False):
    """Run comprehensive security scan and output results."""
    if not ci_mode:
        print("🔒 Starting comprehensive security scan...")
        print(f"Database: {settings.postgres_db}")
        print(f"Environment: {settings.environment}")
        print("-" * 50)
    
    try:
        # Initialize database
        db_manager.initialize()
        
        # Get database session
        with db_manager.get_session() as db:
            # Run comprehensive security scan
            scan_result = await security_scanner.run_full_security_scan(db)
            
            # Generate security report
            security_report = await security_scanner.generate_security_report(scan_result)
            
            # Run compliance validation
            compliance_result = await security_scanner.run_compliance_validation(db)
            
            # Print results (unless in CI mode)
            if not ci_mode:
                print_scan_results(scan_result, security_report, verbose)
                print_compliance_results(compliance_result, verbose)
            
            # Save to file if requested or in CI mode
            output_path = output_file or ("security-scan-report.json" if ci_mode else None)
            if output_path:
                save_results_to_file(scan_result, security_report, compliance_result, output_path)
                if not ci_mode:
                    print(f"\n📄 Results saved to: {output_path}")
            
            # Return exit code based on results
            is_ready = scan_result.is_production_ready() and compliance_result.get("overall_status") == "PASS"
            if is_ready:
                if not ci_mode:
                    print("\n✅ System is PRODUCTION READY")
                return 0
            else:
                critical_violations = scan_result.critical_violations + compliance_result.get("critical_violations", 0)
                if not ci_mode:
                    print(f"\n❌ System has {critical_violations} CRITICAL VIOLATIONS")
                return 1
                
    except Exception as e:
        if not ci_mode:
            print(f"\n💥 Security scan failed: {str(e)}")
        return 1
    finally:
        db_manager.close()


async def run_compliance_validation(framework: str = "ALL", output_file: str = None, verbose: bool = False):
    """Run compliance validation against security frameworks."""
    print(f"🔍 Running compliance validation for {framework}...")
    print("-" * 50)
    
    try:
        # Initialize database
        db_manager.initialize()
        
        # Get database session
        with db_manager.get_session() as db:
            # Run compliance validation
            compliance_result = await security_scanner.run_compliance_validation(db, framework)
            
            # Print results
            print_compliance_results(compliance_result, verbose)
            
            # Save to file if requested
            if output_file:
                with open(output_file, 'w') as f:
                    json.dump(compliance_result, f, indent=2, default=str)
                print(f"\n📄 Results saved to: {output_file}")
            
            # Return exit code based on results
            if compliance_result.get("overall_status") == "PASS":
                print(f"\n✅ Compliance validation PASSED for {framework}")
                return 0
            else:
                critical_violations = compliance_result.get("critical_violations", 0)
                print(f"\n❌ Compliance validation FAILED with {critical_violations} critical violations")
                return 1
                
    except Exception as e:
        print(f"\n💥 Compliance validation failed: {str(e)}")
        return 1
    finally:
        db_manager.close()


async def run_penetration_test(test_type: str = "basic", verbose: bool = False):
    """Run automated penetration testing."""
    print(f"🎯 Running penetration test: {test_type}")
    print("-" * 50)
    
    try:
        # Initialize database
        db_manager.initialize()
        
        # Get database session
        with db_manager.get_session() as db:
            # Run penetration test
            pentest_result = await security_scanner.run_penetration_test(db, test_type)
            
            # Print results
            print_pentest_results(pentest_result, verbose)
            
            # Return exit code based on results
            if pentest_result.get("overall_status") == "PASS":
                print(f"\n✅ Penetration test PASSED")
                return 0
            else:
                vulnerabilities = pentest_result.get("vulnerabilities_found", 0)
                print(f"\n❌ Penetration test found {vulnerabilities} vulnerabilities")
                return 1
                
    except Exception as e:
        print(f"\n💥 Penetration test failed: {str(e)}")
        return 1
    finally:
        db_manager.close()


def print_pentest_results(pentest_result, verbose: bool = False):
    """Print formatted penetration test results."""
    print(f"Test Type: {pentest_result.get('test_type', 'Unknown')}")
    print(f"Status: {pentest_result.get('overall_status', 'Unknown')}")
    print(f"Vulnerabilities Found: {pentest_result.get('vulnerabilities_found', 0)}")
    print(f"Tests Executed: {pentest_result.get('tests_executed', 0)}")
    
    if verbose or pentest_result.get('vulnerabilities_found', 0) > 0:
        print("\n🎯 Penetration Test Results:")
        for test in pentest_result.get('test_results', []):
            status_icon = "✅" if test['passed'] else "❌"
            print(f"  {status_icon} {test['test_name']}")
            
            if not test['passed'] and test.get('vulnerabilities'):
                for vuln in test['vulnerabilities']:
                    severity_icon = "🔴" if vuln.get('severity') == "CRITICAL" else "🟡"
                    print(f"    {severity_icon} {vuln.get('type', 'Unknown')}: {vuln.get('description', 'No description')}")


async def run_targeted_test(test_type: str, verbose: bool = False):
    """Run specific security test."""
    print(f"🎯 Running targeted security test: {test_type}")
    print("-" * 50)
    
    try:
        # Initialize database
        db_manager.initialize()
        
        # Get database session
        with db_manager.get_session() as db:
            # Run targeted test
            test_result = await security_scanner.run_targeted_rls_test(db, test_type)
            
            # Print results
            print_test_results(test_result, verbose)
            
            # Return exit code based on results
            if test_result["passed"]:
                print(f"\n✅ Test {test_type} PASSED")
                return 0
            else:
                print(f"\n❌ Test {test_type} FAILED with {len(test_result['violations'])} violations")
                return 1
                
    except Exception as e:
        print(f"\n💥 Security test failed: {str(e)}")
        return 1
    finally:
        db_manager.close()


async def validate_query(query: str):
    """Validate a SQL query for security issues."""
    print("🔍 Validating query security...")
    print(f"Query: {query[:100]}{'...' if len(query) > 100 else ''}")
    print("-" * 50)
    
    try:
        # Validate query
        is_safe = await rls_validator.validate_query_security(query)
        
        if is_safe:
            print("✅ Query is SAFE")
            return 0
        else:
            print("❌ Query is UNSAFE")
            return 1
            
    except Exception as e:
        print(f"❌ Query validation failed: {str(e)}")
        return 1


def print_scan_results(scan_result, security_report, verbose: bool = False):
    """Print formatted scan results."""
    print(f"Scan ID: {scan_result.scan_id}")
    print(f"Status: {scan_result.status}")
    print(f"Timestamp: {scan_result.timestamp}")
    print(f"Tests Run: {scan_result.results['tests_run']}")
    print(f"Tests Passed: {scan_result.results['tests_passed']}")
    print(f"Tests Failed: {scan_result.results['tests_failed']}")
    print(f"Critical Violations: {scan_result.critical_violations}")
    print(f"Total Violations: {scan_result.total_violations}")
    
    if verbose or scan_result.results['tests_failed'] > 0:
        print("\n📋 Test Results:")
        for test_result in scan_result.results['test_results']:
            status_icon = "✅" if test_result['passed'] else "❌"
            print(f"  {status_icon} {test_result['test_name']}")
            
            if not test_result['passed'] and test_result['violations']:
                for violation in test_result['violations']:
                    print(f"    - {violation['type']}: {violation['description']}")
    
    if security_report['recommendations']:
        print("\n💡 Recommendations:")
        for rec in security_report['recommendations']:
            priority_icon = "🔴" if rec['priority'] == "CRITICAL" else "🟡"
            print(f"  {priority_icon} [{rec['priority']}] {rec['description']}")
            print(f"    Action: {rec['action']}")


def print_test_results(test_result, verbose: bool = False):
    """Print formatted test results."""
    status_icon = "✅" if test_result['passed'] else "❌"
    print(f"{status_icon} Test: {test_result['test_name']}")
    print(f"Status: {'PASSED' if test_result['passed'] else 'FAILED'}")
    print(f"Violations: {len(test_result['violations'])}")
    
    if verbose or not test_result['passed']:
        if test_result['violations']:
            print("\n🚨 Violations:")
            for violation in test_result['violations']:
                print(f"  - {violation['type']}: {violation['description']}")
        
        if test_result['details']:
            print("\n📊 Details:")
            for key, value in test_result['details'].items():
                print(f"  {key}: {value}")


def print_compliance_results(compliance_result, verbose: bool = False):
    """Print formatted compliance results."""
    print(f"\n📋 COMPLIANCE VALIDATION:")
    print(f"Overall Status: {compliance_result.get('overall_status', 'UNKNOWN')}")
    print(f"Compliance Score: {compliance_result.get('compliance_score', 0):.1%}")
    print(f"Critical Violations: {compliance_result.get('critical_violations', 0)}")
    print(f"Total Checks: {compliance_result.get('total_checks', 0)}")
    print(f"Passed Checks: {compliance_result.get('passed_checks', 0)}")
    
    if verbose or compliance_result.get('critical_violations', 0) > 0:
        print("\n📋 Compliance Check Results:")
        for check in compliance_result.get('check_results', []):
            status_icon = "✅" if check['passed'] else "❌"
            print(f"  {status_icon} {check['check_name']} - {check['category']}")
            
            if not check['passed'] and check.get('violations'):
                for violation in check['violations']:
                    print(f"    - {violation.get('type', 'Unknown')}: {violation.get('description', 'No description')}")
    
    if compliance_result.get('recommendations'):
        print("\n💡 Compliance Recommendations:")
        for rec in compliance_result['recommendations']:
            priority_icon = "🔴" if rec['priority'] == "CRITICAL" else "🟡"
            print(f"  {priority_icon} [{rec['priority']}] {rec['description']}")


def save_results_to_file(scan_result, security_report, compliance_result, output_file: str):
    """Save scan results to JSON file."""
    output_data = {
        "scan_result": scan_result.to_dict(),
        "security_report": security_report,
        "compliance_result": compliance_result,
        "generated_at": datetime.utcnow().isoformat(),
        "passed": scan_result.is_production_ready() and compliance_result.get("overall_status") == "PASS"
    }
    
    with open(output_file, 'w') as f:
        json.dump(output_data, f, indent=2, default=str)


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(description="ATS Security Scanner CLI")
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Comprehensive scan command
    scan_parser = subparsers.add_parser('scan', help='Run comprehensive security scan')
    scan_parser.add_argument('--output', '-o', help='Output file for results (JSON)')
    scan_parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    scan_parser.add_argument('--ci-mode', action='store_true', help='CI mode (minimal output)')
    
    # Compliance validation command
    compliance_parser = subparsers.add_parser('compliance', help='Run compliance validation')
    compliance_parser.add_argument('--output', '-o', help='Output file for results (JSON)')
    compliance_parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    compliance_parser.add_argument('--framework', choices=['SOC2', 'ISO27001', 'GDPR', 'ALL'], 
                                  default='ALL', help='Compliance framework to validate against')
    
    # Penetration testing command
    pentest_parser = subparsers.add_parser('pentest', help='Run penetration testing')
    pentest_parser.add_argument('type', choices=['basic', 'advanced', 'rls_focused'], 
                               default='basic', help='Type of penetration test to run')
    pentest_parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    
    # Targeted test command
    test_parser = subparsers.add_parser('test', help='Run targeted security test')
    test_parser.add_argument('type', choices=['cross_client_access', 'unauthenticated_access', 'policy_integrity'],
                           help='Type of test to run')
    test_parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    
    # Query validation command
    query_parser = subparsers.add_parser('validate', help='Validate SQL query security')
    query_parser.add_argument('query', help='SQL query to validate')
    
    # History command
    history_parser = subparsers.add_parser('history', help='Show scan history')
    history_parser.add_argument('--limit', '-l', type=int, default=10, help='Number of scans to show')
    
    # Metrics command
    metrics_parser = subparsers.add_parser('metrics', help='Show security metrics')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    # Run appropriate command
    if args.command == 'scan':
        return asyncio.run(run_comprehensive_scan(args.output, args.verbose, getattr(args, 'ci_mode', False)))
    elif args.command == 'compliance':
        return asyncio.run(run_compliance_validation(args.framework, args.output, args.verbose))
    elif args.command == 'pentest':
        return asyncio.run(run_penetration_test(args.type, args.verbose))
    elif args.command == 'test':
        return asyncio.run(run_targeted_test(args.type, args.verbose))
    elif args.command == 'validate':
        return asyncio.run(validate_query(args.query))
    elif args.command == 'history':
        scan_history = security_scanner.get_scan_history(args.limit)
        print(f"📈 Security Scan History (last {len(scan_history)} scans):")
        print("-" * 50)
        for scan in scan_history:
            status_icon = "✅" if scan['status'] == 'PASS' else "❌"
            print(f"{status_icon} {scan['scan_id']} - {scan['timestamp']} - {scan['status']}")
            print(f"   Critical: {scan['critical_violations']}, Total: {scan['total_violations']}")
        return 0
    elif args.command == 'metrics':
        metrics = security_scanner.get_security_metrics()
        print("📊 Security Metrics:")
        print("-" * 50)
        print(f"Total Scans: {metrics['total_scans']}")
        print(f"Average Violations: {metrics['avg_violations']:.1f}")
        print(f"Production Ready Rate: {metrics['production_ready_rate']:.1f}%")
        if metrics['last_scan_timestamp']:
            print(f"Last Scan: {metrics['last_scan_timestamp']}")
        return 0


if __name__ == "__main__":
    sys.exit(main())