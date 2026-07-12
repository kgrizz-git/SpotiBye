/**
 * Optional ops helper: flush all `global:reccobeats:` KV keys via paginated list.
 *
 * Usage (from `src/backend` with wrangler auth):
 *   npx tsx ../../scripts/flush-reccobeats-cache.ts
 *
 * Requires CACHE_KV binding from wrangler.toml. Prefer known-key deletes for
 * force-refresh paths; use this only for emergency / maintenance flushes.
 */

import { getPlatformProxy } from 'wrangler';

async function main(): Promise<void> {
  const { env, dispose } = await getPlatformProxy();
  try {
    const kv = (env as { CACHE_KV?: KVNamespace }).CACHE_KV;
    if (!kv) {
      throw new Error('CACHE_KV binding not available');
    }

    const prefix = 'global:reccobeats:';
    let cursor: string | undefined;
    let deleted = 0;
    do {
      const list = await kv.list(cursor ? { prefix, cursor } : { prefix });
      await Promise.all(list.keys.map((key) => kv.delete(key.name)));
      deleted += list.keys.length;
      cursor = list.list_complete ? undefined : list.cursor;
    } while (cursor);

    // eslint-disable-next-line no-console -- ops script
    console.info(`Deleted ${deleted} keys under ${prefix}`);
  } finally {
    await dispose();
  }
}

main().catch((error: unknown) => {
  // eslint-disable-next-line no-console -- ops script
  console.error(error);
  process.exitCode = 1;
});
