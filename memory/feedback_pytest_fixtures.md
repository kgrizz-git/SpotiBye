---
name: pytest class fixture pattern
description: How to make custom test classes pytest-visible without breaking existing structure
type: feedback
---

Pytest skips test classes that have `__init__` constructors (emits `PytestCollectionWarning`, silently collects 0 tests). To fix:

1. Remove `__init__` from the test class
2. Add `@pytest.fixture(autouse=True)` method to inject dependencies (e.g. mock server URL, client objects)
3. Create a session-scoped fixture in `conftest.py` for expensive shared resources (mock server)
4. Use `port=0` + capture actual bound port (`self.port = self.server.server_address[1]`) for test servers to avoid port conflicts
5. Replace `return False` / custom framework recording with `assert` / `pytest.fail()` so failures propagate

**Why:** This project had 6 test classes (TestAuthenticationFlow, TestUIFunctionality, etc.) that were never run by the pre-push pytest hook because they all had `__init__`. They were only runnable via `run_tests.py` which was not in any hook.

**How to apply:** Any new test class in `src/frontend/tests/` should use `@pytest.fixture(autouse=True)` for setup instead of `__init__`. The session-scoped `mock_backend_server` fixture in `conftest.py` is already available.
