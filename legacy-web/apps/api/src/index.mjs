import { config } from './config.mjs';
import { JobStore } from './job-store.mjs';
import { createServer } from './server.mjs';

const jobs = new JobStore(config);
await jobs.initialize();

const server = createServer(config, jobs);
server.listen(config.port, config.host, () => {
  console.log(`BeeTales API disponible en http://${config.host}:${config.port}`);
});

const shutdown = () => server.close(() => process.exit(0));
process.on('SIGINT', shutdown);
process.on('SIGTERM', shutdown);
