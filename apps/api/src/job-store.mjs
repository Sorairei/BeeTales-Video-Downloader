import crypto from 'node:crypto';
import fs from 'node:fs/promises';
import path from 'node:path';
import { downloadMedia } from './media-service.mjs';

const publicJob = (job) => ({
  id: job.id,
  status: job.status,
  progress: Math.round(job.progress),
  type: job.request.type,
  title: job.title,
  error: job.error,
  createdAt: job.createdAt,
  expiresAt: job.expiresAt,
  fileUrl: job.status === 'ready' ? `/api/v1/downloads/${job.id}/file` : null
});

export class JobStore {
  constructor(config) {
    this.config = config;
    this.jobs = new Map();
    this.queue = [];
    this.running = 0;
    this.cleanupTimer = setInterval(() => this.cleanup(), 60_000);
    this.cleanupTimer.unref?.();
  }

  async initialize() {
    await fs.mkdir(this.config.tempRoot, { recursive: true });
  }

  create(request, title = '') {
    const active = [...this.jobs.values()].filter((job) => !['failed', 'expired', 'cancelled'].includes(job.status));
    if (active.length >= this.config.maxActiveJobs) throw new RangeError('El servicio alcanzó su límite de trabajos activos.');

    const id = crypto.randomUUID();
    const now = Date.now();
    const job = {
      id,
      request,
      title,
      status: 'queued',
      progress: 0,
      error: null,
      filePath: null,
      directory: path.join(this.config.tempRoot, id),
      controller: new AbortController(),
      createdAt: new Date(now).toISOString(),
      expiresAt: new Date(now + this.config.jobTtlMs).toISOString()
    };
    this.jobs.set(id, job);
    this.queue.push(job);
    this.drain();
    return publicJob(job);
  }

  get(id) {
    const job = this.jobs.get(id);
    return job ? publicJob(job) : null;
  }

  getFile(id) {
    const job = this.jobs.get(id);
    if (!job || job.status !== 'ready' || !job.filePath) return null;
    return { path: job.filePath, type: job.request.type, title: job.title };
  }

  async cancel(id) {
    const job = this.jobs.get(id);
    if (!job) return false;
    job.controller.abort();
    job.status = 'cancelled';
    this.queue = this.queue.filter((candidate) => candidate.id !== id);
    await this.removeFiles(job);
    return true;
  }

  async run(job) {
    this.running += 1;
    job.status = 'downloading';
    try {
      await fs.mkdir(job.directory, { recursive: true });
      job.filePath = await downloadMedia(
        job.request,
        job.directory,
        this.config,
        job.controller.signal,
        (progress) => { job.progress = progress; }
      );
      job.progress = 100;
      job.status = 'ready';
    } catch (error) {
      if (job.status !== 'cancelled') {
        job.status = 'failed';
        job.error = error.name === 'ProcessError' ? error.message : 'No fue posible completar la descarga.';
      }
      await this.removeFiles(job);
    } finally {
      this.running -= 1;
      this.drain();
    }
  }

  drain() {
    while (this.running < this.config.maxConcurrentJobs && this.queue.length) {
      const job = this.queue.shift();
      if (job.status === 'queued') void this.run(job);
    }
  }

  async removeFiles(job) {
    await fs.rm(job.directory, { recursive: true, force: true }).catch(() => {});
  }

  async cleanup() {
    const now = Date.now();
    for (const [id, job] of this.jobs) {
      if (new Date(job.expiresAt).getTime() <= now) {
        job.controller.abort();
        job.status = 'expired';
        await this.removeFiles(job);
        this.jobs.delete(id);
      }
    }
  }
}
