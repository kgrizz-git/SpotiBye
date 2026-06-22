import { describe, it, expect, vi, afterEach } from 'vitest';
import { SpotifyAuthService } from '../services/spotify-auth';

describe('SpotifyAuthService PKCE', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('generates a base64url code_verifier of valid length and charset', () => {
    const auth = new SpotifyAuthService('client-id', 'client-secret');
    const verifier = auth.generateCodeVerifier();

    // 32 random bytes -> 43 base64url chars (no padding)
    expect(verifier).toHaveLength(43);
    expect(verifier).toMatch(/^[A-Za-z0-9_-]+$/);

    // High entropy: two calls should not collide
    expect(auth.generateCodeVerifier()).not.toBe(verifier);
  });

  it('derives the S256 challenge per the RFC 7636 test vector', async () => {
    const auth = new SpotifyAuthService('client-id', 'client-secret');
    // RFC 7636 Appendix B.
    const verifier = 'dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk';
    const challenge = await auth.computeCodeChallenge(verifier);
    expect(challenge).toBe('E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM');
  });

  it('includes the code_challenge and S256 method in the authorize URL', () => {
    const auth = new SpotifyAuthService('client-id', 'client-secret');
    const url = auth.getAuthUrl('http://localhost:3000/callback', 'state-123', 'challenge-abc');
    const params = new URL(url).searchParams;
    expect(params.get('code_challenge')).toBe('challenge-abc');
    expect(params.get('code_challenge_method')).toBe('S256');
    expect(params.get('state')).toBe('state-123');
  });

  it('omits PKCE params from the authorize URL when no challenge is given', () => {
    const auth = new SpotifyAuthService('client-id', 'client-secret');
    const url = auth.getAuthUrl('http://localhost:3000/callback', 'state-123');
    const params = new URL(url).searchParams;
    expect(params.has('code_challenge')).toBe(false);
    expect(params.has('code_challenge_method')).toBe(false);
  });

  it('sends the code_verifier in the token exchange body', async () => {
    const auth = new SpotifyAuthService('client-id', 'client-secret');
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ access_token: 'a', refresh_token: 'r', expires_in: 3600 }),
    });
    vi.stubGlobal('fetch', fetchMock);

    await auth.exchangeCodeForTokens('the-code', 'http://localhost:3000/callback', 'the-verifier');

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [, init] = fetchMock.mock.calls[0];
    const body = init.body as URLSearchParams;
    expect(body.get('code_verifier')).toBe('the-verifier');
    expect(body.get('grant_type')).toBe('authorization_code');
    expect(body.get('code')).toBe('the-code');
  });

  it('omits code_verifier when none is provided', async () => {
    const auth = new SpotifyAuthService('client-id', 'client-secret');
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ access_token: 'a', refresh_token: 'r', expires_in: 3600 }),
    });
    vi.stubGlobal('fetch', fetchMock);

    await auth.exchangeCodeForTokens('the-code', 'http://localhost:3000/callback');

    const [, init] = fetchMock.mock.calls[0];
    const body = init.body as URLSearchParams;
    expect(body.has('code_verifier')).toBe(false);
  });
});

describe('SpotifyAuthService construction', () => {
  it('throws when both credentials are empty', () => {
    expect(() => new SpotifyAuthService()).toThrow('Spotify clientId and clientSecret are required');
  });

  it('throws when clientId is empty', () => {
    expect(() => new SpotifyAuthService('', 'secret')).toThrow('Spotify clientId and clientSecret are required');
  });

  it('throws when clientSecret is empty', () => {
    expect(() => new SpotifyAuthService('id', '')).toThrow('Spotify clientId and clientSecret are required');
  });

  it('does not throw when both credentials are provided', () => {
    expect(() => new SpotifyAuthService('id', 'secret')).not.toThrow();
  });
});
