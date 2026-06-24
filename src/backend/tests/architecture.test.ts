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
  let results: string[] = [];
  if (!fs.existsSync(dir)) return results;
  const list = fs.readdirSync(dir);
  for (const file of list) {
    const filePath = path.join(dir, file); // nosemgrep: path-join-resolve-traversal
    const stat = fs.statSync(filePath);
    if (stat && stat.isDirectory()) {
      results = results.concat(getFilesInDir(filePath));
    } else if (file.endsWith('.ts') && !file.endsWith('.test.ts')) {
      results.push(filePath);
    }
  }
  return results;
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

function isSameFamily(sourceFile: string, resolvedImport: string): boolean {
  const sourceNormalized = sourceFile.replace(/\\/g, '/');
  const importNormalized = resolvedImport.replace(/\\/g, '/');

  const sourceRoutesIndex = sourceNormalized.indexOf('/routes/');
  const importRoutesIndex = importNormalized.indexOf('/routes/');

  if (sourceRoutesIndex === -1 || importRoutesIndex === -1) {
    return true;
  }

  const sourceRelative = sourceNormalized.substring(sourceRoutesIndex + '/routes/'.length);
  const importRelative = importNormalized.substring(importRoutesIndex + '/routes/'.length);

  const sourceFamily = sourceRelative.split('/')[0].replace(/\.ts$/, '');
  const importFamily = importRelative.split('/')[0].replace(/\.ts$/, '');

  if (sourceRelative.endsWith('.ts') && !sourceRelative.includes('/') && sourceFamily === importFamily) {
    return true;
  }

  return sourceFamily === importFamily;
}

describe('routes/ layer', () => {
  const routeFiles = getFilesInDir(path.join(ROOT, 'routes'));

  for (const file of routeFiles) {
    const testName = path.relative(ROOT, file);
    const lines = readLines(file);
    const imports = extractImports(lines);

    it(`${testName} must not import from other routes`, () => {
      const relativeImports = imports.filter((i) => i.startsWith('.'));
      const violations = relativeImports.filter((i) => {
        const resolved = path.resolve(path.dirname(file), i);
        if (!resolved.includes(path.join(ROOT, 'routes'))) {
          return false;
        }
        return !isSameFamily(file, resolved);
      });
      expect(violations, `Violation in ${testName}: ${violations.join(', ')}`).toHaveLength(0);
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
