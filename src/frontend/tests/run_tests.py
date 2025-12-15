"""Test runner for frontend backend integration."""

from __future__ import annotations

import logging
import sys
from typing import Dict, Any

from .test_framework import BackendTestFramework
from .test_auth import TestAuthenticationFlow
from .test_ui import TestUIFunctionality
from .test_performance import TestPerformance
from .test_cache import TestCachePerformance
from .test_ui_responsiveness import TestUIResponsiveness
from .test_configuration import TestConfiguration

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def run_ui_responsiveness_tests_only() -> Dict[str, Any]:
    """Run only UI responsiveness tests."""
    framework = BackendTestFramework()
    
    if not framework.setup_mock_backend():
        return {'success': False, 'message': 'Failed to setup mock backend'}
    
    try:
        ui_responsiveness_tests = TestUIResponsiveness(framework)
        return ui_responsiveness_tests.run_all_tests()
    finally:
        framework.teardown_mock_backend()


def run_configuration_tests_only() -> Dict[str, Any]:
    """Run only configuration tests."""
    framework = BackendTestFramework()
    
    try:
        config_tests = TestConfiguration(framework)
        return config_tests.run_all_tests()
    finally:
        # Configuration tests don't need mock backend
        pass


def run_all_tests() -> Dict[str, Any]:
    """Run all backend integration tests."""
    framework = BackendTestFramework()
    
    print("Starting backend integration tests...")
    
    # Setup mock backend
    if not framework.setup_mock_backend():
        return {'success': False, 'message': 'Failed to setup mock backend'}
    
    try:
        # Run authentication tests
        auth_tests = TestAuthenticationFlow(framework)
        auth_results = auth_tests.run_all_tests()
        
        # Clear results for next test suite
        framework.clear_results()
        
        # Run UI functionality tests
        ui_tests = TestUIFunctionality(framework)
        ui_results = ui_tests.run_all_tests()
        
        # Clear results for next test suite
        framework.clear_results()
        
        # Run performance tests
        perf_tests = TestPerformance(framework)
        perf_results = perf_tests.run_all_tests()
        
        # Get overall summary
        all_results = framework.get_test_results()
        summary = framework.get_summary()
        
        print(f"\nTest Results Summary:")
        print(f"Total Tests: {summary['total_tests']}")
        print(f"Passed: {summary['passed_tests']}")
        print(f"Failed: {summary['failed_tests']}")
        print(f"Success Rate: {summary['success_rate']:.1f}%")
        
        return {
            'success': True,
            'auth_results': auth_results,
            'ui_results': ui_results,
            'performance_results': perf_results,
            'overall_summary': summary
        }
        
    finally:
        # Cleanup
        framework.teardown_mock_backend()


def run_auth_tests_only() -> Dict[str, Any]:
    """Run only authentication tests."""
    framework = BackendTestFramework()
    
    if not framework.setup_mock_backend():
        return {'success': False, 'message': 'Failed to setup mock backend'}
    
    try:
        auth_tests = TestAuthenticationFlow(framework)
        return auth_tests.run_all_tests()
    finally:
        framework.teardown_mock_backend()


def run_ui_tests_only() -> Dict[str, Any]:
    """Run only UI functionality tests."""
    framework = BackendTestFramework()
    
    if not framework.setup_mock_backend():
        return {'success': False, 'message': 'Failed to setup mock backend'}
    
    try:
        ui_tests = TestUIFunctionality(framework)
        return ui_tests.run_all_tests()
    finally:
        framework.teardown_mock_backend()


def run_performance_tests_only() -> Dict[str, Any]:
    """Run only performance tests."""
    framework = BackendTestFramework()
    
    if not framework.setup_mock_backend():
        return {'success': False, 'message': 'Failed to setup mock backend'}
    
    try:
        perf_tests = TestPerformance(framework)
        return perf_tests.run_all_tests()
    finally:
        framework.teardown_mock_backend()


def run_cache_tests_only() -> Dict[str, Any]:
    """Run only cache performance tests."""
    framework = BackendTestFramework()
    
    if not framework.setup_mock_backend():
        return {'success': False, 'message': 'Failed to setup mock backend'}
    
    try:
        cache_tests = TestCachePerformance(framework)
        return cache_tests.run_all_tests()
    finally:
        framework.teardown_mock_backend()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        test_type = sys.argv[1].lower()
        
        if test_type == "auth":
            results = run_auth_tests_only()
        elif test_type == "ui":
            results = run_ui_tests_only()
        elif test_type == "performance":
            results = run_performance_tests_only()
        elif test_type == "cache":
            results = run_cache_tests_only()
        elif test_type == "ui-responsiveness":
            results = run_ui_responsiveness_tests_only()
        elif test_type == "config":
            results = run_configuration_tests_only()
        else:
            print(f"Unknown test type: {test_type}")
            print("Available: auth, ui, performance, cache, ui-responsiveness, config")
            sys.exit(1)
    else:
        results = run_all_tests()
    
    # Exit with appropriate code
    sys.exit(0 if results['success'] else 1)
