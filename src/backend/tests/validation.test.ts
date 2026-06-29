import { describe, it, expect } from 'vitest';
import { Hono } from 'hono';
import { z } from 'zod';
import { zValidator } from '../validation/z-validator';

describe('zValidator error envelope', () => {
  const schema = z.object({
    redirect_uri: z.string().min(1, 'redirect_uri is required'),
  });

  const app = new Hono();
  app.post('/login', zValidator('json', schema), (c) => c.json({ data: c.req.valid('json') }));

  it('returns the app validation error envelope on schema failure', async () => {
    const response = await app.request('http://localhost/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({}),
    });

    expect(response.status).toBe(400);
    const body = (await response.json()) as { error: { code: string; message: string } };
    expect(body.error.code).toBe('VALIDATION_ERROR');
    expect(body.error.message).toContain('redirect_uri');
  });

  it('preserves a route-specific error code when provided', async () => {
    const codedApp = new Hono();
    codedApp.post(
      '/login',
      zValidator('json', schema, 'MISSING_REDIRECT_URI'),
      (c) => c.json({ data: c.req.valid('json') }),
    );

    const response = await codedApp.request('http://localhost/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({}),
    });

    expect(response.status).toBe(400);
    const body = (await response.json()) as { error: { code: string; message: string } };
    expect(body.error.code).toBe('MISSING_REDIRECT_URI');
    expect(body.error.message).toContain('redirect_uri');
  });
});

describe('formatZodMessage path formatting', () => {
  it('joins nested object paths with dots', async () => {
    const app = new Hono();
    app.post(
      '/test',
      zValidator('json', z.object({ user: z.object({ name: z.string().min(1) }) })),
      (c) => c.json({ ok: true }),
    );
    const response = await app.request('http://localhost/test', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user: {} }),
    });
    expect(response.status).toBe(400);
    const body = (await response.json()) as { error: { message: string } };
    expect(body.error.message).toContain('user.name:');
  });

  it('renders array indices in the path', async () => {
    const app = new Hono();
    app.post(
      '/test',
      zValidator('json', z.object({ items: z.array(z.string().min(1)) })),
      (c) => c.json({ ok: true }),
    );
    const response = await app.request('http://localhost/test', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ items: ['ok', ''] }),
    });
    expect(response.status).toBe(400);
    const body = (await response.json()) as { error: { message: string } };
    expect(body.error.message).toContain('items.1:');
  });

  it('falls back to "request" for empty path (root-level failure)', async () => {
    const app = new Hono();
    app.post('/test', zValidator('json', z.string().min(1)), (c) => c.json({ ok: true }));
    const response = await app.request('http://localhost/test', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(123),
    });
    expect(response.status).toBe(400);
    const body = (await response.json()) as { error: { message: string } };
    expect(body.error.message).toMatch(/^request:/);
  });

  it('joins multiple issues with semicolons', async () => {
    const app = new Hono();
    app.post(
      '/test',
      zValidator('json', z.object({ a: z.string().min(1), b: z.string().min(1) })),
      (c) => c.json({ ok: true }),
    );
    const response = await app.request('http://localhost/test', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({}),
    });
    expect(response.status).toBe(400);
    const body = (await response.json()) as { error: { message: string } };
    expect(body.error.message).toMatch(/a:.*; .*b:/);
  });
});
