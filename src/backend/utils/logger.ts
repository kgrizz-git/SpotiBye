export type LogContext = Record<string, unknown>;

/**
 * Structured log calls: message + a context object (rather than string
 * concatenation), matching the existing `console.warn('msg', { ... })`
 * convention elsewhere in the backend so log pipelines (e.g. `wrangler tail
 * --format json`) can parse the context as JSON.
 */
function emit(level: 'info' | 'warn' | 'error', message: string, context?: LogContext): void {
  if (level === 'error') {
    console.error(message, context ?? {});
  } else if (level === 'warn') {
    console.warn(message, context ?? {});
  } else {
    // Golden Principle #5 forbids `console.log`; `console.info` carries the
    // same structured call without violating the rule.
    console.info(message, context ?? {});
  }
}

export const logger = {
  info: (message: string, context?: LogContext) => emit('info', message, context),
  warn: (message: string, context?: LogContext) => emit('warn', message, context),
  error: (message: string, context?: LogContext) => emit('error', message, context),
};
