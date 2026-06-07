# Backend Testing with Vitest

## Test Structure

Tests are in `src/backend/tests/`:
- Unit tests for services and utilities
- Integration tests for routes
- Performance tests for critical paths

## Running Tests

```bash
cd src/backend

# Run all tests
npm run test:run

# Run tests in watch mode
npm run test:watch

# Run tests with coverage
npm run test:coverage

# Run specific test file
npx vitest tests/spotify.test.ts
```

## Test Patterns

**Unit Tests:**
```typescript
import { describe, it, expect } from 'vitest'
import { functionToTest } from '../services/service'

describe('functionToTest', () => {
  it('should do something', () => {
    const result = functionToTest(input)
    expect(result).toBe(expected)
  })
})
```

**Integration Tests:**
```typescript
import { describe, it, expect } from 'vitest'
import { app } from '../index'

describe('POST /api/endpoint', () => {
  it('should return 200', async () => {
    const response = await app.request('/api/endpoint', {
      method: 'POST',
      body: JSON.stringify({ data })
    })
    expect(response.status).toBe(200)
  })
})
```

## Mocking

Use vi.mock for external dependencies:
```typescript
import { vi } from 'vitest'

vi.mock('../services/spotify', () => ({
  getPlaylist: vi.fn()
}))
```

## Best Practices

- Test happy path and error cases
- Mock external API calls (Spotify)
- Use describe blocks to group related tests
- Keep tests fast and isolated
- Run tests before committing
