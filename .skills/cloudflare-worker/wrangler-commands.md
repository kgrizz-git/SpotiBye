# Common Wrangler Commands

## Development

```bash
# Start local development server
wrangler dev

# Start with specific environment
wrangler dev --env staging

# Tail logs from deployed worker
wrangler tail
```

## Deployment

```bash
# Deploy to production
wrangler deploy

# Deploy to specific environment
wrangler deploy --env staging

# Deploy without prompting
wrangler deploy --yes
```

## Secrets

```bash
# List all secrets
wrangler secret list

# Set a secret
wrangler secret put SECRET_NAME

# Delete a secret
wrangler secret delete SECRET_NAME

# Bulk put secrets from file
wrangler secret bulk < secrets.txt
```

## KV Namespaces

```bash
# Create namespace
wrangler kv:namespace create "NAMESPACE_NAME"

# Create preview namespace
wrangler kv:namespace create "NAMESPACE_NAME" --preview

# List keys in namespace
wrangler kv:key list --namespace-id=NAMESPACE_ID

# Put value
wrangler kv:key put "KEY" "VALUE" --namespace-id=NAMESPACE_ID

# Get value
wrangler kv:key get "KEY" --namespace-id=NAMESPACE_ID
```

## Configuration

```bash
# Validate wrangler.toml
wrangler validate

# Show current configuration
wrangler whoami
```
