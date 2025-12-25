# Property-Based Testing Framework

This directory contains the property-based testing framework for the ATS backend production hardening. The framework uses [Hypothesis](https://hypothesis.readthedocs.io/) to generate test data and validate system properties across all possible inputs.

## Overview

Property-based testing validates universal properties that should hold true for all valid inputs, rather than testing specific examples. This approach provides mathematical confidence in system correctness by exploring the entire input space.

## Framework Components

### Core Files

- `config.py` - Configuration for Hypothesis with CI/dev profiles
- `base.py` - Base classes and utilities for property tests
- `generators.py` - Smart test data generators for ATS domain objects
- `test_framework_demo.py` - Demonstration of framework capabilities

### Configuration Profiles

- **production_hardening** (default): 100 iterations, deterministic seeding
- **ci**: Optimized for CI with quiet output and deterministic seeding
- **dev**: 1000 iterations, verbose output, randomized seeding

## Usage

### Running Property Tests

```bash
# Run all property-based tests (default profile)
make test-property

# Run in development mode (more examples)
make test-property-dev

# Run in CI mode (deterministic)
make test-property-ci

# Run with verbose statistics
make pbt-verbose

# Run framework demo
make pbt-demo
```

### Writing Property Tests

```python
from hypothesis import given
from .base import PropertyTestBase, property_test
from .generators import client_data, candidate_data

class TestMyFeature(PropertyTestBase):

    @property_test("production-hardening", 1, "My property description")
    @given(client=client_data())
    def test_my_property(self, client):
        """Test that my property holds for all clients."""
        # Feature: production-hardening, Property 1: My property description

        # Log test data for debugging
        self.log_test_data("Generated client", client)

        # Test your property here
        assert some_property_holds(client)
```

## Test Data Generators

### Available Generators

- `client_data()` - Generate realistic client/tenant data
- `candidate_data()` - Generate candidate profiles with skills/experience
- `application_data()` - Generate job applications with status tracking
- `resume_job_data()` - Generate resume processing jobs
- `user_data()` - Generate user authentication data
- `tenant_with_data()` - Generate complete tenant with all related data
- `email_content()` - Generate email content for ingestion testing

### Generator Features

- **Realistic Data**: Generators produce data that resembles real-world usage
- **Referential Integrity**: Related data maintains proper foreign key relationships
- **Constraint Awareness**: Generators respect business rules and constraints
- **Configurable**: Generators accept parameters for specific test scenarios

### Example Generator Usage

```python
from hypothesis import given
from .generators import tenant_with_data

@given(tenant=tenant_with_data())
def test_tenant_isolation(tenant):
    client_id = tenant["client"]["id"]

    # All candidates belong to the client
    for candidate in tenant["candidates"]:
        assert candidate["client_id"] == client_id

    # All applications reference valid candidates
    candidate_ids = {c["id"] for c in tenant["candidates"]}
    for application in tenant["applications"]:
        assert application["candidate_id"] in candidate_ids
```

## Base Classes

### PropertyTestBase

Base class providing common utilities:

- Test data logging and debugging
- Mock database session creation
- Data validation helpers

### MultiTenantPropertyTest

Specialized for multi-tenant testing:

- Tenant isolation verification
- Cross-tenant access prevention
- Data ownership validation

### SecurityPropertyTest

Focused on security properties:

- Sensitive data exposure checks
- Authentication requirement verification
- Authorization enforcement validation

### FSMPropertyTest

For finite state machine testing:

- State validity verification
- Transition rule enforcement
- Terminal state immutability

## Configuration

### Environment Variables

- `HYPOTHESIS_PROFILE` - Set testing profile (production_hardening/ci/dev)
- `CI` - Automatically detected, enables deterministic seeding
- `TESTING` - Set to "1" for test mode

### Hypothesis Settings

- **Minimum Iterations**: 100 (as per requirements)
- **Maximum Iterations**: 1000 (development mode)
- **Deterministic Seeding**: Enabled in CI for reproducibility
- **Example Database**: Stores failing examples for regression testing
- **Deadline**: 60 seconds per test case

## Best Practices

### Writing Effective Properties

1. **Universal Quantification**: Properties should hold for ALL valid inputs
2. **Clear Assertions**: Use descriptive assertion messages
3. **Data Logging**: Log test data for debugging failed cases
4. **Assumption Management**: Use `assume()` to filter invalid inputs
5. **Requirement Traceability**: Reference specific requirements in comments

### Debugging Failed Tests

1. **Check Logs**: Review logged test data from failed cases
2. **Reproduce Locally**: Use saved examples from `.hypothesis_examples/`
3. **Simplify Generators**: Reduce complexity to isolate issues
4. **Add Assumptions**: Filter out edge cases that aren't relevant

### Performance Considerations

1. **Generator Efficiency**: Keep generators fast and simple
2. **Assumption Overhead**: Minimize rejected examples with good assumptions
3. **Test Isolation**: Ensure tests don't interfere with each other
4. **Resource Cleanup**: Clean up resources after tests

## Integration with CI

The framework is designed for CI integration:

- **Deterministic Results**: Same seed produces same test cases
- **Fast Execution**: Optimized for CI time constraints
- **Clear Reporting**: Detailed failure information for debugging
- **Regression Prevention**: Failed examples stored for future runs

## Troubleshooting

### Common Issues

1. **Slow Tests**: Reduce max_examples or optimize generators
2. **Flaky Tests**: Check for non-deterministic behavior
3. **Memory Usage**: Monitor generator memory consumption
4. **Timeout Errors**: Increase deadline or optimize test logic

### Debug Commands

```bash
# Run with detailed statistics
make pbt-verbose

# Run single test with debugging
pytest tests/property_based/test_framework_demo.py::TestPropertyFrameworkDemo::test_client_data_generation -v -s

# Check Hypothesis database
ls tests/property_based/.hypothesis_examples/
```

## Requirements Validation

This framework validates Requirements 1.1, 1.2, 1.3, and 1.5:

- ✅ **1.1**: Uses Hypothesis framework with randomized data generation
- ✅ **1.2**: Runs minimum 100 iterations per property test
- ✅ **1.3**: Deterministic seeding for CI reproducibility
- ✅ **1.5**: Avoids hardcoded IDs and fixed test data

The framework provides mathematical confidence in system correctness through comprehensive property validation across all possible inputs.
