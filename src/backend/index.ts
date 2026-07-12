import { Hono } from 'hono';
import { cors } from 'hono/cors';
import { logger } from 'hono/logger';
import { authRoutes } from './routes/auth';
import { spotifyRoutes } from './routes/spotify';
import { analysisRoutes } from './routes/analysis';
import { exportRoutes } from './routes/export';
import { errorHandler } from './middleware/error';
import { envValidationMiddleware } from './middleware/env';
import { AnalysisJobService } from './services/analysis-job';
import type { AnalysisQueueMessage } from './types/analysis-queue';
import type { Env } from './types/env';
import { AnalysisQueueMessagePayloadSchema } from './validation/schemas/queue';
import { NonRetryableError } from './types/errors';
export { AnalysisStatusObject } from './services/analysis-status-object';

const app = new Hono<{ Bindings: Env }>();

// Global middleware
app.use('*', logger());
app.use('*', envValidationMiddleware);
app.use('*', cors({
  origin: ['http://localhost:3000', 'https://spotibye.com'],
  allowMethods: ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
  allowHeaders: ['Content-Type', 'Authorization'],
  credentials: true,
}));

// Error handling middleware
app.onError(errorHandler);

// Health check endpoint
app.get('/health', (c) => {
  const env = c.env;

  return c.json({
    data: {
      status: 'healthy',
      service: 'spotibye-backend',
      environment: env.ENVIRONMENT,
      release_sha: env.RELEASE_SHA ?? 'unknown',
      release_version: env.RELEASE_VERSION ?? 'unknown',
      deployed_at: env.DEPLOYED_AT ?? 'unknown',
      timestamp: new Date().toISOString(),
    },
  });
});


// API routes
app.route('/auth', authRoutes);
app.route('/spotify', spotifyRoutes);
app.route('/analysis', analysisRoutes);
app.route('/export', exportRoutes);

// 404 handler
app.notFound((c) => {
  const requestId = crypto.randomUUID();
  return c.json(
    {
      error: {
        code: 'NOT_FOUND',
        message: 'Not Found',
        request_id: requestId,
        timestamp: new Date().toISOString(),
        details: {
          path: c.req.path,
          method: c.req.method,
        },
      },
    },
    404
  );
});

export default {
  fetch: app.fetch,
  async queue(batch: MessageBatch<AnalysisQueueMessage>, env: Env, _ctx: ExecutionContext): Promise<void> {
    const jobService = new AnalysisJobService(env);

    for (const message of batch.messages) {
      const payloadResult = AnalysisQueueMessagePayloadSchema.safeParse(message.body);
      if (!payloadResult.success) {
        console.error(
          `[Queue] Invalid message body for job ${message.body?.job_id ?? 'unknown'}:`,
          payloadResult.error.flatten(),
        );
        message.ack();
        continue;
      }

      const body = {
        ...payloadResult.data,
        attempt: message.attempts,
      };

      try {
        await jobService.process(body);
        console.error(JSON.stringify({ event: 'QUEUE_JOB_COMPLETED', job_id: body.job_id }));
        message.ack();
      } catch (error) {
        const isNonRetryable =
          error instanceof NonRetryableError ||
          (error as { code?: string }).code === 'AUTH_REQUIRED' ||
          (error as { code?: string }).code === 'NON_RETRYABLE';

        if (isNonRetryable) {
          try { await jobService.markFailed(body, error); } catch { /* swallow KV failure */ }
          message.ack();
          continue;
        }

        console.error(JSON.stringify({ event: 'QUEUE_JOB_FAILED', job_id: body.job_id, attempt: message.attempts }));
        if (message.attempts >= 3) {
          try {
            await jobService.markFailed(body, error);
          } catch (markFailedError) {
            console.error(`[Queue] markFailed threw for job ${body.job_id}; acking anyway:`, markFailedError);
          }
          message.ack();
          continue;
        }

        message.retry();
      }
    }
  },
};
