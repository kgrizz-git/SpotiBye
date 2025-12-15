"""Performance tests for API endpoints."""

from __future__ import annotations

import time
import concurrent.futures
from typing import Any

import pytest

from tests.conftest import auth_headers, mock_spotify_data


class TestPerformance:
    """Test API endpoint performance."""
    
    def test_health_check_performance(self, client: Any, performance_monitor: Any) -> None:
        """Test health check endpoint performance."""
        performance_monitor.start_monitoring()
        
        # Make multiple requests
        for _ in range(100):
            response = client.get("/health")
            assert response.status_code == 200
        
        results = performance_monitor.stop_monitoring()
        
        # Performance assertions
        assert results["duration"] < 5.0  # Should complete within 5 seconds
        assert results["peak_memory"] < 50 * 1024 * 1024  # Less than 50MB peak memory
        assert results["avg_memory"] < 20 * 1024 * 1024  # Less than 20MB average memory
    
    def test_auth_verification_performance(self, client: Any, auth_headers: dict[str, str], performance_monitor: Any) -> None:
        """Test authentication verification performance."""
        performance_monitor.start_monitoring()
        
        # Make multiple authenticated requests
        for _ in range(50):
            response = client.get("/auth/verify", headers=auth_headers)
            assert response.status_code == 200
        
        results = performance_monitor.stop_monitoring()
        
        # Performance assertions
        assert results["duration"] < 3.0  # Should complete within 3 seconds
        assert results["peak_memory"] < 30 * 1024 * 1024  # Less than 30MB peak memory
    
    def test_concurrent_requests(self, client: Any) -> None:
        """Test API performance under concurrent load."""
        def make_request() -> tuple[int, float]:
            """Make a single request and return status and response time."""
            start_time = time.time()
            response = client.get("/health")
            end_time = time.time()
            return response.status_code, end_time - start_time
        
        # Make 50 concurrent requests
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(make_request) for _ in range(50)]
            results = [future.result() for future in futures]
        
        # Analyze results
        status_codes, response_times = zip(*results)
        
        # All requests should succeed
        assert all(status == 200 for status in status_codes)
        
        # Performance assertions
        avg_response_time = sum(response_times) / len(response_times)
        max_response_time = max(response_times)
        
        assert avg_response_time < 0.1  # Average response time under 100ms
        assert max_response_time < 0.5  # Maximum response time under 500ms
    
    def test_jwt_token_performance(self, performance_monitor: Any) -> None:
        """Test JWT token creation and verification performance."""
        from src.spotibye_backend.auth.jwt_handler import create_access_token, verify_token
        
        performance_monitor.start_monitoring()
        
        # Create and verify many tokens
        tokens = []
        for i in range(1000):
            user_data = {"sub": f"user_{i}", "username": f"user_{i}"}
            token = create_access_token(user_data)
            tokens.append(token)
        
        # Verify all tokens
        for token in tokens:
            payload = verify_token(token)
            assert payload is not None
        
        results = performance_monitor.stop_monitoring()
        
        # Performance assertions
        assert results["duration"] < 10.0  # Should complete within 10 seconds
        assert results["peak_memory"] < 100 * 1024 * 1024  # Less than 100MB peak memory
    
    def test_api_docs_performance(self, client: Any, performance_monitor: Any) -> None:
        """Test API documentation generation performance."""
        performance_monitor.start_monitoring()
        
        # Test OpenAPI spec generation
        response = client.get("/openapi.json")
        assert response.status_code == 200
        
        # Parse JSON to ensure it's valid
        spec = response.json()
        assert "paths" in spec
        assert "components" in spec
        
        results = performance_monitor.stop_monitoring()
        
        # Performance assertions
        assert results["duration"] < 2.0  # Should complete within 2 seconds
        assert results["peak_memory"] < 20 * 1024 * 1024  # Less than 20MB peak memory
    
    def test_memory_usage_stability(self, client: Any, auth_headers: dict[str, str]) -> None:
        """Test that memory usage remains stable over time."""
        import psutil
        
        process = psutil.Process()
        initial_memory = process.memory_info().rss
        
        # Make many requests over time
        for batch in range(10):
            for _ in range(100):
                client.get("/health")
                client.get("/auth/verify", headers=auth_headers)
            
            # Check memory after each batch
            current_memory = process.memory_info().rss
            memory_growth = current_memory - initial_memory
            
            # Memory growth should be reasonable
            assert memory_growth < 50 * 1024 * 1024  # Less than 50MB growth
    
    def test_response_size_performance(self, client: Any) -> None:
        """Test that response sizes are reasonable."""
        # Test various endpoints
        endpoints = [
            "/health",
            "/auth/verify",
            "/openapi.json"
        ]
        
        for endpoint in endpoints:
            response = client.get(endpoint)
            assert response.status_code == 200
            
            # Check response size
            content_size = len(response.content)
            
            # Response should be reasonably sized
            if endpoint == "/openapi.json":
                assert content_size < 100 * 1024  # OpenAPI spec under 100KB
            else:
                assert content_size < 10 * 1024  # Other responses under 10KB
    
    def test_rate_limiting_performance(self, client: Any, rate_limiter: Any) -> None:
        """Test rate limiting performance under load."""
        # Simulate high request rate
        allowed_requests = 0
        total_requests = 200
        
        for i in range(total_requests):
            if rate_limiter.is_allowed(f"client_{i % 10}"):  # 10 different clients
                allowed_requests += 1
        
        # Should allow reasonable number of requests
        assert allowed_requests > total_requests * 0.8  # At least 80% allowed
    
    def test_error_handling_performance(self, client: Any) -> None:
        """Test that error handling doesn't impact performance significantly."""
        # Test various error conditions
        error_endpoints = [
            "/nonexistent",
            "/api/playlists",  # Should return 401 without auth
            "/auth/verify"     # Should return 403 without auth
        ]
        
        start_time = time.time()
        
        for endpoint in error_endpoints:
            for _ in range(10):
                response = client.get(endpoint)
                # Should return error status (4xx or 5xx)
                assert response.status_code >= 400
        
        end_time = time.time()
        total_time = end_time - start_time
        
        # Error handling should be fast
        assert total_time < 2.0  # All error requests within 2 seconds
    
    def test_concurrent_authentication(self, client: Any, performance_monitor: Any) -> None:
        """Test concurrent authentication requests."""
        from src.spotibye_backend.auth.jwt_handler import create_access_token
        
        # Create multiple tokens
        tokens = []
        for i in range(20):
            user_data = {"sub": f"user_{i}", "username": f"user_{i}"}
            token = create_access_token(user_data)
            tokens.append(token)
        
        performance_monitor.start_monitoring()
        
        def verify_token(token: str) -> tuple[int, float]:
            """Verify a token and return status and time."""
            start_time = time.time()
            headers = {"Authorization": f"Bearer {token}"}
            response = client.get("/auth/verify", headers=headers)
            end_time = time.time()
            return response.status_code, end_time - start_time
        
        # Make concurrent verification requests
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(verify_token, token) for token in tokens]
            results = [future.result() for future in futures]
        
        results = performance_monitor.stop_monitoring()
        
        # All requests should succeed
        status_codes, response_times = zip(*results)
        assert all(status == 200 for status in status_codes)
        
        # Performance assertions
        assert results["duration"] < 5.0  # Should complete within 5 seconds
        assert max(response_times) < 1.0  # No single request should take more than 1 second


class TestLoadTesting:
    """Load testing for API endpoints."""
    
    def test_sustained_load(self, client: Any) -> None:
        """Test API performance under sustained load."""
        duration_seconds = 10
        start_time = time.time()
        request_count = 0
        error_count = 0
        
        while time.time() - start_time < duration_seconds:
            response = client.get("/health")
            request_count += 1
            
            if response.status_code != 200:
                error_count += 1
            
            # Small delay to prevent overwhelming the system
            time.sleep(0.01)
        
        # Load testing assertions
        assert request_count > 100  # Should handle at least 100 requests in 10 seconds
        assert error_count == 0     # No errors during sustained load
        assert request_count / duration_seconds > 10  # At least 10 requests per second
    
    def test_burst_load(self, client: Any) -> None:
        """Test API performance under burst load."""
        burst_size = 50
        
        def make_request() -> int:
            """Make a single request and return status."""
            response = client.get("/health")
            return response.status_code
        
        # Make burst of concurrent requests
        with concurrent.futures.ThreadPoolExecutor(max_workers=burst_size) as executor:
            futures = [executor.submit(make_request) for _ in range(burst_size)]
            results = [future.result() for future in futures]
        
        # All requests should succeed
        assert all(status == 200 for status in results)
    
    def test_memory_leak_detection(self, client: Any) -> None:
        """Test for potential memory leaks."""
        import gc
        import psutil
        
        process = psutil.Process()
        
        # Force garbage collection
        gc.collect()
        initial_memory = process.memory_info().rss
        
        # Make many requests
        for _ in range(1000):
            response = client.get("/health")
            assert response.status_code == 200
            
            # Periodically force garbage collection
            if _ % 100 == 0:
                gc.collect()
        
        # Final garbage collection
        gc.collect()
        final_memory = process.memory_info().rss
        
        # Check for memory leaks
        memory_growth = final_memory - initial_memory
        assert memory_growth < 20 * 1024 * 1024  # Less than 20MB growth after 1000 requests


if __name__ == "__main__":
    pytest.main([__file__])
