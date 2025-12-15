# Monitoring and Logging Setup

This guide covers monitoring and logging configuration for the SpotiBye Cloudflare Workers backend.

## Overview

The monitoring system includes:
- Request/response logging
- Performance metrics
- Error tracking
- Health monitoring
- Analytics data collection

## Logging Configuration

### Log Levels
```typescript
enum LogLevel {
  ERROR = 0,
  WARN = 1,
  INFO = 2,
  DEBUG = 3
}

const LOG_LEVELS = {
  development: LogLevel.DEBUG,
  staging: LogLevel.INFO,
  production: LogLevel.WARN
};
```

### Structured Logging
```typescript
interface LogEntry {
  timestamp: string;
  level: string;
  message: string;
  endpoint?: string;
  method?: string;
  statusCode?: number;
  responseTime?: number;
  userId?: string;
  error?: string;
  environment: string;
}

function createLogEntry(
  level: string,
  message: string,
  context: Partial<LogEntry> = {}
): LogEntry {
  return {
    timestamp: new Date().toISOString(),
    level,
    message,
    environment: ENVIRONMENT,
    ...context
  };
}
```

### Logger Implementation
```typescript
class Logger {
  private env: string;
  private minLevel: LogLevel;

  constructor(env: string) {
    this.env = env;
    this.minLevel = LOG_LEVELS[env] || LogLevel.INFO;
  }

  private shouldLog(level: LogLevel): boolean {
    return level <= this.minLevel;
  }

  private log(level: LogLevel, message: string, context: any = {}) {
    if (!this.shouldLog(level)) return;

    const entry = createLogEntry(LogLevel[level], message, context);
    console.log(JSON.stringify(entry));
  }

  error(message: string, context?: any) {
    this.log(LogLevel.ERROR, message, context);
  }

  warn(message: string, context?: any) {
    this.log(LogLevel.WARN, message, context);
  }

  info(message: string, context?: any) {
    this.log(LogLevel.INFO, message, context);
  }

  debug(message: string, context?: any) {
    this.log(LogLevel.DEBUG, message, context);
  }
}
```

## Request Logging Middleware

### Request Logger
```typescript
function withLogging(request: Request, env: Env): Logger {
  const logger = new Logger(env.ENVIRONMENT);
  
  const start = Date.now();
  const url = new URL(request.url);
  
  return {
    logger,
    logRequest: (statusCode: number, error?: string) => {
      const responseTime = Date.now() - start;
      
      logger.info('API Request', {
        endpoint: url.pathname,
        method: request.method,
        statusCode,
        responseTime,
        userAgent: request.headers.get('User-Agent'),
        ip: request.headers.get('CF-Connecting-IP'),
        error
      });
    }
  };
}
```

### Usage in Handlers
```typescript
export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const { logger, logRequest } = withLogging(request, env);
    
    try {
      // Handle request
      const response = await handleRequest(request, env);
      logRequest(response.status);
      return response;
    } catch (error) {
      logger.error('Request failed', {
        error: error.message,
        stack: error.stack
      });
      logRequest(500, error.message);
      return new Response('Internal Server Error', { status: 500 });
    }
  }
};
```

## Metrics Collection

### Cloudflare Analytics Engine
```typescript
interface AnalyticsMetrics {
  endpoint: string;
  method: string;
  statusCode: number;
  responseTime: number;
  userId?: string;
  errorType?: string;
}

function recordMetrics(env: Env, metrics: AnalyticsMetrics) {
  if (!env.ANALYTICS) return;

  env.ANALYTICS.writeDataPoint({
    blobs: [
      metrics.endpoint,
      metrics.method,
      metrics.errorType || 'none'
    ],
    doubles: [
      metrics.responseTime,
      metrics.statusCode
    ],
    indexes: [
      metrics.statusCode
    ]
  });
}
```

### Custom Metrics
```typescript
interface PerformanceMetrics {
  cacheHitRate: number;
  spotifyApiLatency: number;
  kvOperationTime: number;
  memoryUsage: number;
  cpuTime: number;
}

class MetricsCollector {
  private metrics: Map<string, number> = new Map();

  increment(name: string, value: number = 1) {
    const current = this.metrics.get(name) || 0;
    this.metrics.set(name, current + value);
  }

  timing(name: string, value: number) {
    this.metrics.set(`${name}_timing`, value);
  }

  gauge(name: string, value: number) {
    this.metrics.set(name, value);
  }

  getMetrics(): Record<string, number> {
    return Object.fromEntries(this.metrics);
  }

  reset() {
    this.metrics.clear();
  }
}
```

## Error Tracking

### Error Classification
```typescript
enum ErrorType {
  VALIDATION = 'validation',
  AUTHENTICATION = 'authentication',
  AUTHORIZATION = 'authorization',
  RATE_LIMIT = 'rate_limit',
  SPOTIFY_API = 'spotify_api',
  KV_ERROR = 'kv_error',
  WORKER_ERROR = 'worker_error',
  NETWORK_ERROR = 'network_error'
}

function classifyError(error: Error, statusCode: number): ErrorType {
  if (statusCode === 400) return ErrorType.VALIDATION;
  if (statusCode === 401) return ErrorType.AUTHENTICATION;
  if (statusCode === 403) return ErrorType.AUTHORIZATION;
  if (statusCode === 429) return ErrorType.RATE_LIMIT;
  if (error.message.includes('Spotify')) return ErrorType.SPOTIFY_API;
  if (error.message.includes('KV')) return ErrorType.KV_ERROR;
  if (error.message.includes('fetch')) return ErrorType.NETWORK_ERROR;
  return ErrorType.WORKER_ERROR;
}
```

### Error Reporting
```typescript
interface ErrorReport {
  timestamp: string;
  errorType: ErrorType;
  message: string;
  stack?: string;
  endpoint?: string;
  method?: string;
  userId?: string;
  statusCode: number;
  environment: string;
}

function reportError(env: Env, error: Error, context: any = {}) {
  const errorType = classifyError(error, context.statusCode || 500);
  
  const report: ErrorReport = {
    timestamp: new Date().toISOString(),
    errorType,
    message: error.message,
    stack: error.stack,
    endpoint: context.endpoint,
    method: context.method,
    userId: context.userId,
    statusCode: context.statusCode || 500,
    environment: env.ENVIRONMENT
  };

  // Log error
  console.error(JSON.stringify(report));
  
  // Send to external monitoring (optional)
  if (env.ERROR_WEBHOOK) {
    fetch(env.ERROR_WEBHOOK, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(report)
    }).catch(console.error);
  }
}
```

## Health Monitoring

### Health Check Endpoint
```typescript
interface HealthStatus {
  status: 'healthy' | 'unhealthy';
  timestamp: string;
  version: string;
  checks: {
    kv_health: boolean;
    spotify_api: boolean;
    cache_status: boolean;
    memory_usage: number;
  };
  uptime: number;
}

async function healthCheck(env: Env): Promise<HealthStatus> {
  const checks = {
    kv_health: await checkKVHealth(env),
    spotify_api: await checkSpotifyAPI(env),
    cache_status: await checkCacheHealth(env),
    memory_usage: getMemoryUsage()
  };

  const isHealthy = Object.values(checks).every(check => 
    typeof check === 'boolean' ? check : check < 0.9 // memory usage threshold
  );

  return {
    status: isHealthy ? 'healthy' : 'unhealthy',
    timestamp: new Date().toISOString(),
    version: env.VERSION || '1.0.0',
    checks,
    uptime: getUptime()
  };
}

async function checkKVHealth(env: Env): Promise<boolean> {
  try {
    await env.CACHE_KV.get('health-check');
    return true;
  } catch {
    return false;
  }
}

async function checkSpotifyAPI(env: Env): Promise<boolean> {
  try {
    const response = await fetch('https://api.spotify.com/v1/me', {
      headers: { 'Authorization': `Bearer ${env.SPOTIFY_CLIENT_ID}` }
    });
    return response.ok;
  } catch {
    return false;
  }
}
```

## Performance Monitoring

### Response Time Tracking
```typescript
class PerformanceTracker {
  private timers: Map<string, number> = new Map();

  start(name: string) {
    this.timers.set(name, Date.now());
  }

  end(name: string): number {
    const start = this.timers.get(name);
    if (!start) return 0;
    
    const duration = Date.now() - start;
    this.timers.delete(name);
    return duration;
  }

  async measure<T>(name: string, fn: () => Promise<T>): Promise<T> {
    this.start(name);
    try {
      const result = await fn();
      const duration = this.end(name);
      console.log(`Performance: ${name} took ${duration}ms`);
      return result;
    } catch (error) {
      this.end(name);
      throw error;
    }
  }
}
```

### Memory Monitoring
```typescript
function getMemoryUsage(): number {
  // Cloudflare Workers don't expose memory usage directly
  // This is a placeholder for monitoring
  return 0;
}

function monitorMemoryUsage(env: Env) {
  if (env.ENVIRONMENT === 'development') {
    setInterval(() => {
      const usage = getMemoryUsage();
      console.log(`Memory usage: ${(usage * 100).toFixed(2)}%`);
    }, 60000); // Every minute
  }
}
```

## Alert Configuration

### Error Rate Alerts
```typescript
interface AlertThresholds {
  errorRate: number; // percentage
  responseTime: number; // milliseconds
  rateLimitHits: number; // per minute
  kvErrors: number; // per minute
}

const ALERT_THRESHOLDS: Record<string, AlertThresholds> = {
  development: {
    errorRate: 10,
    responseTime: 5000,
    rateLimitHits: 50,
    kvErrors: 10
  },
  staging: {
    errorRate: 5,
    responseTime: 2000,
    rateLimitHits: 20,
    kvErrors: 5
  },
  production: {
    errorRate: 1,
    responseTime: 1000,
    rateLimitHits: 10,
    kvErrors: 2
  }
};
```

### Alert System
```typescript
class AlertManager {
  private counters: Map<string, number> = new Map();
  private lastAlert: Map<string, number> = new Map();

  increment(metric: string) {
    const current = this.counters.get(metric) || 0;
    this.counters.set(metric, current + 1);
  }

  checkAlerts(env: Env) {
    const thresholds = ALERT_THRESHOLDS[env.ENVIRONMENT];
    
    // Check error rate
    const totalRequests = this.counters.get('total_requests') || 0;
    const errors = this.counters.get('errors') || 0;
    const errorRate = totalRequests > 0 ? (errors / totalRequests) * 100 : 0;

    if (errorRate > thresholds.errorRate) {
      this.sendAlert(env, 'high_error_rate', `Error rate: ${errorRate.toFixed(2)}%`);
    }

    // Reset counters periodically
    this.resetCounters();
  }

  private sendAlert(env: Env, type: string, message: string) {
    const now = Date.now();
    const lastAlertTime = this.lastAlert.get(type) || 0;
    
    // Prevent alert spam (minimum 5 minutes between alerts)
    if (now - lastAlertTime < 300000) return;

    this.lastAlert.set(type, now);
    
    console.error(`ALERT: ${type} - ${message}`);
    
    // Send to webhook or monitoring service
    if (env.ALERT_WEBHOOK) {
      fetch(env.ALERT_WEBHOOK, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          type,
          message,
          environment: env.ENVIRONMENT,
          timestamp: new Date().toISOString()
        })
      }).catch(console.error);
    }
  }

  private resetCounters() {
    this.counters.clear();
  }
}
```

## Log Analysis

### Query Examples
```sql
-- Find most frequent errors
SELECT 
  errorType,
  COUNT(*) as error_count,
  AVG(responseTime) as avg_response_time
FROM logs 
WHERE timestamp > NOW() - INTERVAL '1 hour'
  AND statusCode >= 400
GROUP BY errorType
ORDER BY error_count DESC;

-- Find slow endpoints
SELECT 
  endpoint,
  AVG(responseTime) as avg_response_time,
  MAX(responseTime) as max_response_time,
  COUNT(*) as request_count
FROM logs 
WHERE timestamp > NOW() - INTERVAL '1 hour'
GROUP BY endpoint
HAVING AVG(responseTime) > 1000
ORDER BY avg_response_time DESC;

-- User activity analysis
SELECT 
  userId,
  COUNT(*) as request_count,
  COUNT(DISTINCT endpoint) as unique_endpoints
FROM logs 
WHERE timestamp > NOW() - INTERVAL '24 hours'
  AND userId IS NOT NULL
GROUP BY userId
ORDER BY request_count DESC
LIMIT 10;
```

## Dashboard Configuration

### Grafana Dashboard (Optional)
```json
{
  "dashboard": {
    "title": "SpotiBye API Monitoring",
    "panels": [
      {
        "title": "Request Rate",
        "type": "graph",
        "targets": [
          {
            "expr": "sum(rate(requests_total[5m])) by (endpoint)"
          }
        ]
      },
      {
        "title": "Error Rate",
        "type": "graph",
        "targets": [
          {
            "expr": "sum(rate(requests_total{statusCode>=400}[5m])) / sum(rate(requests_total[5m]))"
          }
        ]
      },
      {
        "title": "Response Time",
        "type": "graph",
        "targets": [
          {
            "expr": "histogram_quantile(0.95, rate(response_time_seconds_bucket[5m]))"
          }
        ]
      }
    ]
  }
}
```

## Environment Variables for Monitoring

### Additional Environment Variables
```bash
# Monitoring configuration
ALERT_WEBHOOK=https://hooks.slack.com/services/...
ERROR_WEBHOOK=https://monitoring.example.com/webhook
LOG_LEVEL=info
ENABLE_ANALYTICS=true

# Performance thresholds
MAX_RESPONSE_TIME=1000
MAX_ERROR_RATE=1.0
MEMORY_THRESHOLD=0.9
```

### Update wrangler.toml
```toml
[env.production]
vars = { 
  ENVIRONMENT = "production",
  ALERT_WEBHOOK = "https://hooks.slack.com/services/...",
  ERROR_WEBHOOK = "https://monitoring.example.com/webhook",
  LOG_LEVEL = "warn",
  ENABLE_ANALYTICS = "true"
}
```

## Best Practices

### Performance
- Use structured logging for easy parsing
- Implement sampling for high-volume logs
- Cache frequently accessed data
- Monitor KV operation performance

### Security
- Never log sensitive data (tokens, passwords)
- Sanitize PII from logs
- Use secure channels for alert delivery
- Implement log retention policies

### Reliability
- Implement circuit breakers for external services
- Add health checks for all dependencies
- Monitor error rates and set up alerts
- Implement graceful degradation

This monitoring and logging setup provides comprehensive visibility into the SpotiBye API performance, health, and error patterns.
