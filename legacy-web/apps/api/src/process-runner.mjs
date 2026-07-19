import { spawn } from 'node:child_process';

export class ProcessError extends Error {
  constructor(message, { code, stderr = '' } = {}) {
    super(message);
    this.name = 'ProcessError';
    this.code = code;
    this.stderr = stderr;
  }
}

export function runProcess(command, args, options = {}) {
  const {
    cwd,
    timeoutMs = 30_000,
    maxOutputBytes = 6 * 1024 * 1024,
    signal,
    onStdoutLine,
    onStderrLine
  } = options;

  return new Promise((resolve, reject) => {
    const controller = new AbortController();
    const child = spawn(command, args, {
      cwd,
      shell: false,
      windowsHide: true,
      signal: controller.signal,
      stdio: ['ignore', 'pipe', 'pipe']
    });

    let stdout = '';
    let stderr = '';
    let settled = false;
    let stdoutPending = '';
    let stderrPending = '';

    const finish = (callback) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      signal?.removeEventListener('abort', abort);
      callback();
    };

    const abort = () => controller.abort();
    signal?.addEventListener('abort', abort, { once: true });
    if (signal?.aborted) abort();

    const consume = (chunk, stream) => {
      const text = chunk.toString('utf8');
      if (stream === 'stdout') {
        stdout += text;
        stdoutPending += text;
        const lines = stdoutPending.split(/\r?\n/);
        stdoutPending = lines.pop() ?? '';
        lines.forEach((line) => onStdoutLine?.(line));
      } else {
        stderr += text;
        stderrPending += text;
        const lines = stderrPending.split(/\r?\n/);
        stderrPending = lines.pop() ?? '';
        lines.forEach((line) => onStderrLine?.(line));
      }
      if (Buffer.byteLength(stdout) + Buffer.byteLength(stderr) > maxOutputBytes) {
        controller.abort();
      }
    };

    child.stdout.on('data', (chunk) => consume(chunk, 'stdout'));
    child.stderr.on('data', (chunk) => consume(chunk, 'stderr'));

    child.once('error', (error) => finish(() => {
      if (error.name === 'AbortError') {
        reject(new ProcessError('El proceso fue cancelado o excedió sus límites.'));
      } else if (error.code === 'ENOENT') {
        reject(new ProcessError(`No se encontró el ejecutable requerido: ${command}`));
      } else {
        reject(error);
      }
    }));

    child.once('close', (code) => finish(() => {
      if (stdoutPending) onStdoutLine?.(stdoutPending);
      if (stderrPending) onStderrLine?.(stderrPending);
      if (code === 0) resolve({ stdout, stderr });
      else reject(new ProcessError('La plataforma no pudo procesar este enlace.', { code, stderr }));
    }));

    const timer = setTimeout(() => controller.abort(), timeoutMs);
    timer.unref?.();
  });
}
