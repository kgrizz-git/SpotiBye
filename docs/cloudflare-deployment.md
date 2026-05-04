# Cloudflare Worker Deployment

This document explains how the automated Cloudflare worker deployment works and how to set it up.

## Overview

The SpotiBye backend uses a single Cloudflare worker that is automatically deployed when changes are pushed to the `src/backend/` directory.

## Deployment Workflow

### Automatic Triggers

1. **Development Deployment**:
   - Triggers on push to `main` branch when backend files change
   - Deploys to development environment
   - Runs tests and linting first

2. **Production Deployment**:
   - Triggers on version tags (e.g., `v1.0.0`)
   - Deploys to production environment
   - Requires all tests to pass

3. **Manual Deployment**:
   - Can be triggered manually via GitHub Actions
   - Useful for testing and debugging

### Workflow Steps

1. **Test Phase**: Runs unit tests and linting
2. **Deploy Phase**: Deploys to appropriate Cloudflare environment
3. **Verification**: Creates deployment info artifact

## Required GitHub Secrets

To enable automatic deployment, add these secrets to your GitHub repository:

### Cloudflare Credentials

1. **CLOUDFLARE_API_TOKEN**
   - Get from Cloudflare dashboard → My Profile → API Tokens
   - Required permissions:
     - Account: `Cloudflare Workers:Edit`
     - Zone: `Zone:Read` (if using custom domains)
     - Account: `Account:Cloudflare Pages:Edit`

2. **CLOUDFLARE_ACCOUNT_ID**
   - Get from Cloudflare dashboard → Right sidebar → Account ID
   - Format: 32-character hexadecimal string

### How to Add Secrets

1. Go to your GitHub repository
2. Navigate to **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret**
4. Add each secret with the exact name and value

## Environment Configuration

### Development Environment
- Uses development KV namespaces
- Environment variable: `ENVIRONMENT = "development"`
- Auto-deploys on main branch pushes

### Production Environment
- Uses production KV namespaces
- Environment variable: `ENVIRONMENT = "production"`
- Deploys only on version tags

## Manual Deployment

If you need to deploy manually:

```bash
cd src/backend

# Development deployment
npm run deploy --env development

# Production deployment
npm run deploy --env production
```

## Monitoring Deployment

### GitHub Actions
- Check the **Actions** tab in your GitHub repository
- View workflow runs and their status
- Download deployment info artifacts

### Cloudflare Dashboard
- Monitor worker logs and metrics
- Check KV namespace usage
- Verify deployment status

## Troubleshooting

### Common Issues

1. **Missing Secrets**
   - Ensure all required GitHub secrets are set
   - Check secret names match exactly

2. **Permission Errors**
   - Verify Cloudflare API token has correct permissions
   - Check account ID is correct

3. **Build Failures**
   - Check test output in workflow logs
   - Ensure all dependencies are installed

### Debugging

1. View workflow logs in GitHub Actions
2. Check worker logs in Cloudflare dashboard
3. Test locally with `npm run dev`

## Version Management

The worker version is tracked through:
- Git tags for production releases
- Package.json version updates
- Deployment info artifacts

## Security Notes

- API tokens are stored securely in GitHub secrets
- Worker secrets are managed separately via Wrangler
- Environment isolation prevents cross-contamination
