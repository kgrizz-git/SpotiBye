# Common Wrangler Commands

Run these from `src/backend`. The project has two environments, `development`
and `production`, which map to the `spotibye-backend-development` and
`spotibye-backend-production` Workers. Always pass `--env` to commands that
touch a deployed Worker. Without it, Wrangler targets a stray top-level
`spotibye-backend` Worker that belongs to neither environment.

## Development

```bash
# Start local development server
npm run dev

# Tail logs from a deployed worker
wrangler tail --env production   # or --env development
```

## Deployment

```bash
# Deploy with release metadata (preferred)
npm run deploy:dev
npm run deploy:prod

# Compile and check without uploading
wrangler deploy --env production --dry-run
```

`npm run deploy` deliberately fails. A raw `wrangler deploy --env <env>` skips
the `RELEASE_SHA`, `RELEASE_VERSION`, and `DEPLOYED_AT` metadata that `/health`
reports.

## Deployments and Rollback

```bash
wrangler deployments list --env production
wrangler rollback --env production <version-id>
```

## Secrets

```bash
wrangler secret list --env production
wrangler secret put SECRET_NAME --env production
wrangler secret delete SECRET_NAME --env production
wrangler secret bulk secrets.json --env production
```

## KV Namespaces

```bash
# Create namespace
wrangler kv namespace create NAMESPACE_NAME

# List, get, and put keys
wrangler kv key list --namespace-id=NAMESPACE_ID
wrangler kv key get "KEY" --namespace-id=NAMESPACE_ID
wrangler kv key put "KEY" "VALUE" --namespace-id=NAMESPACE_ID
```

## Account

```bash
wrangler whoami
```
