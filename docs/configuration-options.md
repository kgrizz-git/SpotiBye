# SpotiBye Configuration Options

## Overview

SpotiBye can be configured through environment variables, configuration files, and runtime settings. This guide covers all available configuration options.

## Environment Variables

### Backend Configuration
```bash
# Backend URL (required)
BACKEND_URL=https://api.spotibye.com

# Development backend
BACKEND_URL=http://localhost:8787

# API timeout in seconds
API_TIMEOUT=30

# Maximum retry attempts
MAX_RETRIES=3

# Retry delay in seconds
RETRY_DELAY=1.0
```

### Cache Configuration
```bash
# Cache directory path
CACHE_DIR=~/.spotibye/cache

# Cache TTL in hours
CACHE_TTL=24

# Maximum cache size in MB
MAX_CACHE_SIZE=500

# Enable/disable caching
ENABLE_CACHE=true
```

### Logging Configuration
```bash
# Log level (DEBUG, INFO, WARNING, ERROR)
LOG_LEVEL=INFO

# Log file path
LOG_FILE=~/.spotibye/logs/spotibye.log

# Enable debug mode
DEBUG=false
```

## Configuration Files

### Main Config File
Location: `~/.spotibye/config.json`

```json
{
  "backend": {
    "url": "https://api.spotibye.com",
    "timeout": 30,
    "max_retries": 3,
    "retry_delay": 1.0
  },
  "cache": {
    "directory": "~/.spotibye/cache",
    "ttl_hours": 24,
    "max_size_mb": 500,
    "enabled": true
  },
  "logging": {
    "level": "INFO",
    "file": "~/.spotibye/logs/spotibye.log",
    "debug": false
  },
  "ui": {
    "theme": "light",
    "window_size": "1200x800",
    "show_loading_indicators": true
  }
}
```

### Environment-Specific Configs

#### Development Config
`config.dev.json`
```json
{
  "backend": {
    "url": "http://localhost:8787",
    "timeout": 10,
    "debug": true
  },
  "logging": {
    "level": "DEBUG"
  }
}
```

#### Production Config
`config.prod.json`
```json
{
  "backend": {
    "url": "https://api.spotibye.com",
    "timeout": 30,
    "debug": false
  },
  "logging": {
    "level": "INFO"
  }
}
```

## Runtime Configuration

### Command Line Options
```bash
# Override backend URL
spotibye --backend-url http://localhost:8787

# Enable debug mode
spotibye --debug

# Set log level
spotibye --log-level DEBUG

# Use specific config file
spotibye --config /path/to/config.json

# Clear cache on startup
spotibye --clear-cache
```

### In-App Settings

#### Network Settings
- Connection timeout
- Retry attempts
- Backend URL override

#### Cache Settings
- Clear cache button
- Cache size limit
- Cache TTL adjustment

#### UI Settings
- Theme selection (light/dark)
- Window size/position
- Loading indicators toggle

## Default Values

### Backend Defaults
- URL: `https://api.spotibye.com`
- Timeout: 30 seconds
- Max retries: 3
- Retry delay: 1.0 second

### Cache Defaults
- Directory: `~/.spotibye/cache`
- TTL: 24 hours
- Max size: 500MB
- Enabled: true

### Logging Defaults
- Level: INFO
- File: `~/.spotibye/logs/spotibye.log`
- Debug: false

## Configuration Priority

Settings are applied in this order (highest to lowest priority):
1. Command line arguments
2. Environment variables
3. Config file settings
4. Default values

## Security Considerations

### Sensitive Data
- Never store API keys in config files
- Use environment variables for secrets
- Clear sensitive data from logs

### File Permissions
```bash
# Restrict config file permissions
chmod 600 ~/.spotibye/config.json

# Restrict cache directory
chmod 700 ~/.spotibye/cache
```

## Troubleshooting Configuration

### Common Issues
- **Invalid backend URL**: Check URL format and accessibility
- **Cache directory permissions**: Ensure write access
- **Configuration not loading**: Verify JSON syntax
- **Environment variables not working**: Check variable names

### Debug Configuration
```bash
# Show current configuration
spotibye --show-config

# Validate config file
spotibye --validate-config

# Test backend connection
spotibye --test-connection
```

## Migration Guide

### Upgrading from Older Versions
1. Backup existing config: `cp ~/.spotibye/config.json ~/.spotibye/config.json.bak`
2. Run migration tool: `spotibye --migrate-config`
3. Verify new settings: `spotibye --show-config`

### Reset to Defaults
```bash
# Reset all configuration
spotibye --reset-config

# Reset only cache settings
spotibye --reset-cache-config
```
