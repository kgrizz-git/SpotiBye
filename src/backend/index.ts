import { Hono } from 'hono';
import { cors } from 'hono/cors';
import { logger } from 'hono/logger';
import { authRoutes } from './routes/auth';
import { spotifyRoutes } from './routes/spotify';
import { analysisRoutes } from './routes/analysis';
import { exportRoutes } from './routes/export';
import { errorHandler } from './middleware/error';
import { AnalysisJobService } from './services/analysis-job';
import type { AnalysisQueueMessage } from './types/analysis-queue';
import type { Env } from './types/env';

const app = new Hono<{ Bindings: Env }>();

// Global middleware
app.use('*', logger());
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
  return c.json({
    status: 'healthy',
    service: 'spotibye-backend',
    timestamp: new Date().toISOString()
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
      const body = {
        ...message.body,
        attempt: message.attempts,
      };

      try {
        await jobService.process(body);
        message.ack();
      } catch (error) {
        if (message.attempts >= 3) {
          await jobService.markFailed(body, error);
          message.ack();
          continue;
        }

        message.retry();
      }
    }
  },
};
