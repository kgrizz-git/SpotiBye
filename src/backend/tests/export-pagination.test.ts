import { describe, it, expect, vi, afterEach } from 'vitest';
import { ExportService } from '../services/export';
import { SpotifyService } from '../services/spotify';

function makeItem(id: string) {
  return {
    track: {
      id,
      name: `Track ${id}`,
      artists: [{ name: 'Artist' }],
      album: { name: 'Album' },
      duration_ms: 180000,
    },
  };
}

// A raw Spotify page that contains `raw` entries but only `valid` resolvable
// tracks (the rest are local/unavailable items the normalizer drops).
function page(valid: number, raw: number, total: number) {
  return {
    total,
    rawCount: raw,
    items: Array.from({ length: valid }, (_, i) => makeItem(`${total}-${raw}-${i}`)),
  };
}

describe('Export pagination with local/unavailable items', () => {
  afterEach(() => vi.restoreAllMocks());

  it('does not stop early when a full raw page has filtered-out items', async () => {
    const service = new ExportService('token');
    vi.spyOn(SpotifyService.prototype, 'getPlaylist').mockResolvedValue({
      id: 'pl', name: 'PL', owner: { display_name: 'me' },
    } as any);

    // 200 total items: two full raw pages (100 raw each) with 95 valid tracks,
    // then an empty page. Filtered count (95) < limit (100) must NOT stop the loop.
    const tracksSpy = vi.spyOn(SpotifyService.prototype, 'getPlaylistTracks')
      .mockResolvedValueOnce(page(95, 100, 200) as any)
      .mockResolvedValueOnce(page(95, 100, 200) as any)
      .mockResolvedValueOnce(page(0, 0, 200) as any);

    const result = await service.generatePlaylistExport('pl', { includeAudioFeatures: false });

    // Advanced by raw page size: offsets 0, 100, 200.
    expect(tracksSpy.mock.calls.map((c) => c[2])).toEqual([0, 100, 200]);
    expect(result.tracks).toHaveLength(190);
  });

  it('stops on a short raw page without an extra request', async () => {
    const service = new ExportService('token');
    vi.spyOn(SpotifyService.prototype, 'getPlaylist').mockResolvedValue({
      id: 'pl', name: 'PL', owner: { display_name: 'me' },
    } as any);
    const tracksSpy = vi.spyOn(SpotifyService.prototype, 'getPlaylistTracks')
      .mockResolvedValueOnce(page(40, 50, 50) as any);

    const result = await service.generatePlaylistExport('pl', { includeAudioFeatures: false });

    expect(tracksSpy).toHaveBeenCalledTimes(1);
    expect(result.tracks).toHaveLength(40);
  });
});
