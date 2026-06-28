import { describe, it, expect, expectTypeOf } from 'vitest';
import {
  buildExportJobKey,
  buildExportJobDataKey,
  buildExportJobAssemblyKey,
  buildExportFileKey,
  buildXlsxVariantKey,
  buildPrebuiltFormatKey,
  buildBatchKey,
  buildBatchDataKey,
  buildBatchFileKey,
  buildSingleExportKey,
  buildSingleExportDataKey,
  buildSingleExportFileKey,
} from '../routes/export/helpers/cache-keys';

describe('cache-keys helper', () => {
  const jobId = 'job-123';
  const userId = 'user-456';
  const playlistId = 'playlist-789';

  it('buildExportJobKey matches historical key structure', () => {
    expect(buildExportJobKey(jobId, userId)).toBe('export:job:job-123:user-456');
  });

  it('buildExportJobDataKey matches historical key structure', () => {
    expect(buildExportJobDataKey(jobId, userId)).toBe('export:job:job-123:user-456:data');
  });

  it('buildExportJobAssemblyKey matches historical key structure', () => {
    expect(buildExportJobAssemblyKey(jobId, userId)).toBe('export:job:job-123:user-456:assembly');
  });

  it('buildExportFileKey matches historical key structure', () => {
    expect(buildExportFileKey('export:job:123')).toBe('export:job:123:file');
  });

  it('buildXlsxVariantKey matches historical key structure', () => {
    expect(buildXlsxVariantKey('export:job:123', 'rich')).toBe('export:job:123:file:rich');
    expect(buildXlsxVariantKey('export:job:123', 'lite')).toBe('export:job:123:file:lite');

    expectTypeOf(buildXlsxVariantKey).parameter(1).toEqualTypeOf<'rich' | 'lite'>();
  });

  it('buildPrebuiltFormatKey matches historical key structure', () => {
    expect(buildPrebuiltFormatKey('export:job:123', 'csv')).toBe('export:job:123:file:csv');

    expectTypeOf(buildPrebuiltFormatKey).parameter(1).toEqualTypeOf<'csv'>();
  });

  it('buildBatchKey matches historical inline structure', () => {
    expect(buildBatchKey(jobId, userId)).toBe('export:batch:job-123:user-456');
  });

  it('buildBatchDataKey matches historical inline structure', () => {
    expect(buildBatchDataKey(jobId, userId)).toBe('export:batch:job-123:user-456:data');
  });

  it('buildBatchFileKey matches historical inline structure', () => {
    expect(buildBatchFileKey(jobId, userId)).toBe('export:batch:job-123:user-456:file');
  });

  it('buildSingleExportKey matches historical inline structure', () => {
    expect(buildSingleExportKey(playlistId, userId)).toBe('export:playlist-789:user-456');
  });

  it('buildSingleExportDataKey matches historical inline structure', () => {
    expect(buildSingleExportDataKey(playlistId, userId)).toBe('export:playlist-789:user-456:data');
  });

  it('buildSingleExportFileKey matches historical inline structure', () => {
    expect(buildSingleExportFileKey(playlistId, userId)).toBe('export:playlist-789:user-456:file');
  });
});
