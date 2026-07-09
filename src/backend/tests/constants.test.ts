import { describe, it, expect } from 'vitest';
import { MUSIC_KEYS } from '../utils/constants';

describe('MUSIC_KEYS', () => {
  it('has 12 pitch classes starting at C', () => {
    expect(MUSIC_KEYS.length).toBe(12);
    expect(MUSIC_KEYS[0]).toBe('C');
  });
});
