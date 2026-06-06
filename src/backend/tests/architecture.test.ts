/**
 * Architecture enforcement test.
 *
 * Validates that the layer dependency rules defined in ARCHITECTURE.md are not violated.
 * Rules:
 *   - services/ must not import from routes/ or middleware/
 *   - routes/ must not import from other routes/
 *   - All api.spotify.com fetch calls must be in services/spotify.ts only
 *
 * These tests catch architectural drift that ESLint cannot catch statically
 * (e.g., dynamic imports, patterns that bypass no-restricted-imports).
 */

import { describe, it, expect } from 'vitest';
import * as fs from 'fs';
import * as path from 'path';

const ROOT = path.resolve(__dirname, '..');

function readLines(filePath: string): string[] {
  return fs.readFileSync(filePath, 'utf-8').split('\n');
}

function getFilesInDir(dir: string): string[] {
  return fs.readdirSync(dir)
    .filter((f) => f.endsWith('.ts') && !f.endsWith('.test.ts'))
    .map((f) => path.join(dir, f)); // nosemgrep: path-join-resolve-traversal
}

function extractImports(lines: string[]): string[] {
  return lines
    .filter((l) => l.match(/^import\s/))
    .map((l) => {
      const match = l.match(/from\s+['"]([^'"]+)['"]/);
      return match ? match[1] : '';
    })
    .filter(Boolean);
}

// ── Services must not import from routes or middleware ──────────────────────

describe('services/ layer', () => {
  const serviceFiles = getFilesInDir(path.join(ROOT, 'services'));

  for (const file of serviceFiles) {
    const filename = path.basename(file);
    const lines = readLines(file);
    const imports = extractImports(lines);

    it(`${filename} must not import from routes/`, () => {
      const violations = imports.filter((i) => i.includes('../routes') || i.startsWith('./routes'));
      expect(violations, `Violation in services/${filename}: ${violations.join(', ')}`).toHaveLength(0);
    });

    it(`${filename} must not import from middleware/`, () => {
      const violations = imports.filter((i) => i.includes('../middleware') || i.startsWith('./middleware'));
      expect(violations, `Violation in services/${filename}: ${violations.join(', ')}`).toHaveLength(0);
    });
  }
});

// ── Routes must not import from other routes ────────────────────────────────

describe('routes/ layer', () => {
  const routeFiles = getFilesInDir(path.join(ROOT, 'routes'));

  for (const file of routeFiles) {
    const filename = path.basename(file);
    const lines = readLines(file);
    const imports = extractImports(lines);

    it(`${filename} must not import from other routes`, () => {
      const violations = imports.filter((i) => i.includes('../routes') || i.startsWith('./routes'));
      expect(violations, `Violation in routes/${filename}: ${violations.join(', ')}`).toHaveLength(0);
    });
  }
});

// ── Spotify API calls must only be in services/spotify.ts ──────────────────

describe('Spotify API fetch discipline', () => {
  const allDirs = ['routes', 'middleware', 'services'].map((d) => path.join(ROOT, d)); // nosemgrep: path-join-resolve-traversal
  const SPOTIFY_API_HOST = 'api.spotify.com';

  for (const dir of allDirs) {
    const files = getFilesInDir(dir);
    const dirName = path.basename(dir);

    for (const file of files) {
      const filename = path.basename(file);

      // Skip the one allowed file
      if (dirName === 'services' && filename === 'spotify.ts') continue;
      if (dirName === 'services' && filename === 'spotify-auth.ts') continue;

      it(`${dirName}/${filename} must not fetch api.spotify.com directly`, () => {
        const content = fs.readFileSync(file, 'utf-8');
        const lines = content.split('\n');
        const violations = lines
          .map((l, i) => ({ line: l, num: i + 1 }))
          .filter(({ line }) => line.includes(SPOTIFY_API_HOST));
        expect(
          violations,
          `Direct Spotify API call found in ${dirName}/${filename}:\n` +
            violations.map(({ line, num }) => `  Line ${num}: ${line.trim()}`).join('\n'),
        ).toHaveLength(0);
      });
    }
  }
});
