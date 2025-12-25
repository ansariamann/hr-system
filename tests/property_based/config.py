"""Configuration for property-based testing framework."""

from hypothesis import settings, Verbosity
from hypothesis.database import DirectoryBasedExampleDatabase
import os


# Property-based testing configuration
class PropertyTestConfig:
    """Configuration class for property-based testing."""
    
    # Minimum iterations per property test as per requirements
    MIN_ITERATIONS = 100
    
    # Maximum iterations for thorough testing
    MAX_ITERATIONS = 1000
    
    # Deterministic seeding for CI reproducibility
    DETERMINISTIC_SEED = 42
    
    # Database for example storage (for regression testing)
    EXAMPLE_DATABASE_PATH = "tests/property_based/.hypothesis_examples"
    
    # Verbosity settings
    VERBOSITY = Verbosity.normal
    
    # Timeout settings (in seconds)
    DEADLINE = 60000  # 60 seconds per test case
    
    @classmethod
    def configure_hypothesis(cls):
        """Configure Hypothesis with production-ready settings."""
        # Create example database directory if it doesn't exist
        os.makedirs(cls.EXAMPLE_DATABASE_PATH, exist_ok=True)
        
        # Configure Hypothesis settings
        settings.register_profile(
            "production_hardening",
            max_examples=cls.MIN_ITERATIONS,
            deadline=cls.DEADLINE,
            verbosity=cls.VERBOSITY,
            database=DirectoryBasedExampleDatabase(cls.EXAMPLE_DATABASE_PATH),
            print_blob=True,   # Print failing examples
        )
        
        # Configure CI profile with deterministic seeding
        settings.register_profile(
            "ci",
            max_examples=cls.MIN_ITERATIONS,
            deadline=cls.DEADLINE,
            verbosity=Verbosity.quiet,
            database=None,  # derandomize requires database=None
            derandomize=True,
            print_blob=True,
        )
        
        # Configure development profile with more examples
        settings.register_profile(
            "dev",
            max_examples=cls.MAX_ITERATIONS,
            deadline=cls.DEADLINE,
            verbosity=Verbosity.verbose,
            database=DirectoryBasedExampleDatabase(cls.EXAMPLE_DATABASE_PATH),
            print_blob=True,
        )
        
        # Set default profile based on environment
        profile = os.getenv("HYPOTHESIS_PROFILE", "production_hardening")
        settings.load_profile(profile)


# Initialize configuration
PropertyTestConfig.configure_hypothesis()


# Utility functions for test setup
def get_test_seed():
    """Get deterministic seed for CI or random seed for development."""
    if os.getenv("CI") or os.getenv("HYPOTHESIS_PROFILE") == "ci":
        return PropertyTestConfig.DETERMINISTIC_SEED
    return None


def is_ci_environment():
    """Check if running in CI environment."""
    return bool(os.getenv("CI"))


def get_max_examples():
    """Get maximum examples based on environment."""
    if is_ci_environment():
        return PropertyTestConfig.MIN_ITERATIONS
    return PropertyTestConfig.MAX_ITERATIONS