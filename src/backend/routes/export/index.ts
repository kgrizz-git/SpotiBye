import { Hono } from 'hono';
import { authMiddleware } from '../../middleware/auth';
import { jobsApp } from './jobs';
import { playlistsApp } from './playlists';
import { playlistApp } from './playlist';
import type { Env } from '../../types/env';
import type { Variables } from '../../types/variables';

const app = new Hono<{ Bindings: Env; Variables: Variables }>();
app.use('*', authMiddleware);
app.route('/jobs', jobsApp);
app.route('/playlists', playlistsApp);
app.route('/playlist', playlistApp);

export { app as exportRoutes };
