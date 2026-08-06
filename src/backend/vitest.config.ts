import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    environment: 'node',
    globals: true,
    setupFiles: ['./tests/setup.ts'],
    typecheck: {
      enabled: true,
      checker: 'tsc',
      include: ['tests/**/*.test.ts'],
      exclude: ['**/node_modules/**'],
      tsconfig: './tsconfig.json',
    },
    coverage: {
      reporter: ['text', 'lcov'],
      include: ['src/**/*.ts'],
    },
  },
});
