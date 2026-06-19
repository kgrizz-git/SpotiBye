import { config } from 'dotenv';

// Load test environment variables
config({ path: '.env.test' });

// Set global test environment variables
process.env.ENVIRONMENT = 'test';
process.env.JWT_SECRET = 'test-jwt-secret-for-testing-only';
process.env.SPOTIFY_CLIENT_ID = 'test-client-id';
process.env.SPOTIFY_CLIENT_SECRET = 'test-client-secret';
