import eslint from '@eslint/js';
import tseslint from 'typescript-eslint';
import globals from 'globals';

export default tseslint.config(
  eslint.configs.recommended,
  ...tseslint.configs.recommended,
  {
    files: ['**/*.ts'],
    languageOptions: {
      ecmaVersion: 'latest',
      sourceType: 'module',
      globals: { ...globals.es2022, ...globals.worker },
    },
    rules: {
      '@typescript-eslint/no-unused-vars': ['error', { argsIgnorePattern: '^_' }],
      '@typescript-eslint/no-explicit-any': 'error',
      '@typescript-eslint/explicit-function-return-type': 'off',
      '@typescript-eslint/explicit-module-boundary-types': 'off',
      '@typescript-eslint/no-empty-function': 'off',
      'prefer-const': 'error',
      'no-var': 'error',
      'no-restricted-imports': [
        'error',
        {
          patterns: [
            {
              group: ['../routes/*', './routes/*'],
              message:
                'Services must not import from routes. Extract shared logic into a service or types file instead.',
            },
            {
              group: ['../middleware/*', './middleware/*'],
              message:
                'Services must not import from middleware. If you need auth context, receive it as a parameter from the route handler.',
            },
          ],
        },
      ],
    },
  },
  {
    files: ['routes/**/*.ts'],
    rules: {
      'no-restricted-imports': [
        'error',
        {
          patterns: [
            {
              group: ['../routes/*', '../analysis', '../auth', '../spotify'],
              message:
                'Routes must not import from other routes. Extract shared logic into a service in services/ instead.',
            },
          ],
        },
      ],
    },
  },
  {
    files: ['tests/**/*.test.ts'],
    rules: {
      'no-restricted-imports': 'off',
      '@typescript-eslint/no-explicit-any': 'warn',
    },
  },
  {
    files: ['index.ts'],
    rules: { 'no-restricted-imports': 'off' },
  },
  { ignores: ['dist/', 'node_modules/', '.wrangler/'] },
);
