# Frontend Testing with Pytest

## Test Structure

Tests are in `src/frontend/tests/`:
- Unit tests for services and utilities
- Integration tests for screens and auth
- Fixtures for common test data

## Running Tests

```bash
cd src/frontend

# Run all tests
pytest tests/

# Run specific test file
pytest tests/test_service.py

# Run with verbose output
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=app
```

## Test Patterns

**Unit Tests:**
```python
import pytest
from app.services.service import function_to_test

def test_function_to_test():
    result = function_to_test(input_data)
    assert result == expected
```

**Integration Tests:**
```python
import pytest
from app.screens.screen import Screen

def test_screen_action():
    screen = Screen()
    result = screen.perform_action()
    assert result.is_success()
```

## Fixtures

Define fixtures in `conftest.py`:
```python
@pytest.fixture
def mock_auth():
    return AuthToken(access_token="test_token")
```

## Mocking

Use unittest.mock for external dependencies:
```python
from unittest.mock import Mock, patch

@patch('app.services.spotify.get_playlist')
def test_with_mock(mock_get_playlist):
    mock_get_playlist.return_value = {"tracks": []}
    # test code
```

## Best Practices

- Test happy path and error cases
- Mock external API calls (backend, Spotify)
- Use fixtures for common test data
- Keep tests fast and isolated
- Name tests descriptively
- Run tests before committing
