import { describe, it, expect } from 'vitest';
import {
  parseXlsxRenderMode,
  resolveRequestedFormat,
  resolveStoredFormat,
  formatHttpMeta,
  resolveIncludeAudioFeatures,
  resolveStepSize,
} from '../routes/export/helpers/format';

describe('format helper', () => {
  describe('parseXlsxRenderMode', () => {
    it('returns rich or lite if parsed correctly', () => {
      expect(parseXlsxRenderMode('rich')).toBe('rich');
      expect(parseXlsxRenderMode('lite')).toBe('lite');
      expect(parseXlsxRenderMode('RICH')).toBe('rich');
    });

    it('defaults to auto on invalid or missing inputs', () => {
      expect(parseXlsxRenderMode(undefined)).toBe('auto');
      expect(parseXlsxRenderMode('')).toBe('auto');
      expect(parseXlsxRenderMode('invalid')).toBe('auto');
    });
  });

  describe('resolveRequestedFormat', () => {
    it('identifies formats correctly', () => {
      expect(resolveRequestedFormat({ format: 'csv' })).toBe('csv');
      expect(resolveRequestedFormat({ format: 'JSON' })).toBe('json');
      expect(resolveRequestedFormat({ format: 'xlsx' })).toBe('xlsx');
      expect(resolveRequestedFormat({})).toBe('xlsx');
    });
  });

  describe('resolveStoredFormat', () => {
    it('handles untrusted formats', () => {
      expect(resolveStoredFormat('csv')).toBe('csv');
      expect(resolveStoredFormat('json')).toBe('json');
      expect(resolveStoredFormat('xlsx')).toBe('xlsx');
      expect(resolveStoredFormat('invalid')).toBe('xlsx');
    });
  });

  describe('formatHttpMeta', () => {
    it('returns Content-Type and extension', () => {
      expect(formatHttpMeta('csv')).toEqual(['text/csv; charset=utf-8', 'csv']);
      expect(formatHttpMeta('json')).toEqual(['application/json; charset=utf-8', 'json']);
      expect(formatHttpMeta('xlsx')).toEqual(['application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 'xlsx']);
    });
  });

  describe('resolveIncludeAudioFeatures', () => {
    it('detects audio features flag', () => {
      expect(resolveIncludeAudioFeatures({ include_audio_features: true })).toBe(true);
      expect(resolveIncludeAudioFeatures({ include_audio_features: false })).toBe(false);
      expect(resolveIncludeAudioFeatures({})).toBe(false);
    });
  });

  describe('resolveStepSize', () => {
    it('resolves step size boundaries correctly', () => {
      expect(resolveStepSize({ max_playlists_per_step: 2 })).toBe(2);
      expect(resolveStepSize({ chunk_size: 3 })).toBe(3);
      expect(resolveStepSize({ chunk_size: 5 })).toBe(3); // Cap at 3
      expect(resolveStepSize({ chunk_size: 0 })).toBe(1); // Min at 1
      expect(resolveStepSize({})).toBe(1);
    });
  });
});
