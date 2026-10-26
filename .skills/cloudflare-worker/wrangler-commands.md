# Common Wrangler Commands

Run these from `src/backend`. Wrangler is a local dev dependency, so call it
with `npx wrangler` after `npm ci`. The project has two environments, `development`
and `production`, which map to the `spotibye-backend-development` and
`spotibye-backend-production` Workers. Always pass `--env` to commands that
touch a deployed Worker. Without it, Wrangler targets a stray top-level
`spotibye-backend` Worker that belongs to neither environment.

## Development

```bash
# Start local development server
npm run dev

# Tail logs from a deployed worker
npx wrangler tail --env production   # or --env development
```

## Deployment

```bash
# Deploy with release metadata (preferred)
npm run deploy:dev
npm run deploy:prod

# Compile and check without uploading
npx wrangler deploy --env production --dry-run
```

`npm run deploy` deliberately fails. A raw `wrangler deploy --env <env>` skips
the `RELEASE_SHA`, `RELEASE_VERSION`, and `DEPLOYED_AT` metadata that `/health`
reports.

## Deployments and Rollback

```bash
npx wrangler deployments list --env production
npx wrangler rollback --env production <version-id>
```

## Secrets

```bash
npx wrangler secret list --env production
npx wrangler secret put SECRET_NAME --env production
npx wrangler secret delete SECRET_NAME --env production
npx wrangler secret bulk secrets.json --env production
```

## KV Namespaces

```bash
# Create namespace
npx wrangler kv namespace create NAMESPACE_NAME

# List, get, and put keys
npx wrangler kv key list --namespace-id=NAMESPACE_ID
npx wrangler kv key get "KEY" --namespace-id=NAMESPACE_ID
npx wrangler kv key put "KEY" "VALUE" --namespace-id=NAMESPACE_ID
```

## Account

```bash
npx wrangler whoami
```
