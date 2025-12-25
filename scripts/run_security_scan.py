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


async def run_comprehensive_scan(output_file: str = None, verbose: bool = False):
    """Run comprehensive security scan and output results."""
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
            
            # Print results
            print_scan_results(scan_result, security_report, verbose)
            
            # Save to file if requested
            if output_file:
                save_results_to_file(scan_result, security_report, output_file)
                print(f"\n📄 Results saved to: {output_file}")
            
            # Return exit code based on results
            if scan_result.is_production_ready():
                print("\n✅ System is PRODUCTION READY")
                return 0
            else:
                print(f"\n❌ System has {scan_result.critical_violations} CRITICAL VIOLATIONS")
                return 1
                
    except Exception as e:
        print(f"\n💥 Security scan failed: {str(e)}")
        return 1
    finally:
        db_manager.close()


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


def save_results_to_file(scan_result, security_report, output_file: str):
    """Save scan results to JSON file."""
    output_data = {
        "scan_result": scan_result.to_dict(),
        "security_report": security_report,
        "generated_at": datetime.utcnow().isoformat()
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
        return asyncio.run(run_comprehensive_scan(args.output, args.verbose))
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