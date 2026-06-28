import { describe, it, expect } from 'vitest';
import { validateEnvBindings } from '../validation/schemas/env';
import { createTestEnv } from './helpers/env';

describe('EnvBindingsSchema', () => {
  it('accepts a complete test environment', () => {
    expect(() => validateEnvBindings(createTestEnv())).not.toThrow();
  });

  it('rejects missing required secrets', () => {
    expect(() => validateEnvBindings(createTestEnv({ JWT_SECRET: '' }))).toThrow(
      /Invalid Worker environment bindings/,
    );
  });
});
