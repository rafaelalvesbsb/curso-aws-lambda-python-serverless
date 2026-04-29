"""
Pytest configuration and shared fixtures.

This file contains:
- Pytest markers configuration
- Shared fixtures for all tests
- Test environment setup
"""

import pytest


def pytest_configure(config):
    """Configure pytest markers."""
    config.addinivalue_line(
        "markers",
        "integration: marks tests as integration tests (require real credentials/services)"
    )
    config.addinivalue_line(
        "markers",
        "unit: marks tests as unit tests (no external dependencies)"
    )
    config.addinivalue_line(
        "markers",
        "slow: marks tests as slow running (deselect with '-m \"not slow\"')"
    )


@pytest.fixture(scope="session")
def test_config():
    """Test configuration shared across all tests."""
    return {
        "btg_base_url": "https://api.btgpactual.com",
        "timeout": 30.0,
        "retry_attempts": 5,
    }
