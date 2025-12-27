/**
 * Structured Logger for Cloudflare Workers
 *
 * Provides configurable log levels and structured metadata output.
 * Designed for production use with minimal performance overhead.
 *
 * @example
 * import { logger, LogLevel } from './lib/logger';
 *
 * logger.info('Request received', { method: 'GET', path: '/api/videos' });
 * logger.error('Failed to process', { error: err.message, stack: err.stack });
 */

/**
 * Log levels in order of severity
 */
export enum LogLevel {
  DEBUG = 0,
  INFO = 1,
  WARN = 2,
  ERROR = 3,
  NONE = 4  // Disable all logging
}

/**
 * Structured metadata for logging
 */
export interface LogMetadata {
  [key: string]: unknown;
}

/**
 * HTTP request metadata
 */
export interface RequestMetadata {
  method: string;
  path: string;
  status?: number;
  durationMs?: number;
  userAgent?: string;
}

/**
 * Map string log level names to numeric values
 */
const LogLevelMap: Record<string, LogLevel> = {
  'debug': LogLevel.DEBUG,
  'info': LogLevel.INFO,
  'warn': LogLevel.WARN,
  'error': LogLevel.ERROR,
  'none': LogLevel.NONE
};

/**
 * Logger class with configurable log levels and structured output
 */
export class Logger {
  private level: LogLevel;

  /**
   * @param level - Minimum log level to output (default: INFO)
   */
  constructor(level: LogLevel = LogLevel.INFO) {
    this.level = level;
  }

  /**
   * Set the log level from environment or string
   * @param level - Log level name or number
   */
  setLevel(level: string | LogLevel): void {
    if (typeof level === 'string') {
      this.level = LogLevelMap[level.toLowerCase()] ?? LogLevel.INFO;
    } else {
      this.level = level;
    }
  }

  /**
   * Format metadata for structured logging
   * @param meta - Metadata object
   * @returns Formatted metadata string
   */
  private formatMeta(meta: LogMetadata | Error): string {
    if (!meta || (typeof meta === 'object' && Object.keys(meta).length === 0)) {
      return '';
    }
    try {
      return ' | ' + JSON.stringify(meta);
    } catch {
      return ' | [unserializable metadata]';
    }
  }

  /**
   * Get ISO timestamp
   * @returns ISO timestamp
   */
  private getTimestamp(): string {
    return new Date().toISOString();
  }

  /**
   * Debug level log - verbose information for development
   * @param message - Log message
   * @param meta - Optional structured metadata
   */
  debug(message: string, meta: LogMetadata = {}): void {
    if (this.level <= LogLevel.DEBUG) {
      console.log(`[${this.getTimestamp()}] [DEBUG] ${message}${this.formatMeta(meta)}`);
    }
  }

  /**
   * Info level log - general operational information
   * @param message - Log message
   * @param meta - Optional structured metadata
   */
  info(message: string, meta: LogMetadata = {}): void {
    if (this.level <= LogLevel.INFO) {
      console.log(`[${this.getTimestamp()}] [INFO] ${message}${this.formatMeta(meta)}`);
    }
  }

  /**
   * Warn level log - potentially harmful situations
   * @param message - Log message
   * @param meta - Optional structured metadata
   */
  warn(message: string, meta: LogMetadata = {}): void {
    if (this.level <= LogLevel.WARN) {
      console.warn(`[${this.getTimestamp()}] [WARN] ${message}${this.formatMeta(meta)}`);
    }
  }

  /**
   * Error level log - error events that might still allow the application to continue
   * @param message - Log message
   * @param meta - Optional structured metadata or Error object
   */
  error(message: string, meta: LogMetadata | Error = {}): void {
    if (this.level <= LogLevel.ERROR) {
      // If meta is an Error object, extract useful info
      let formattedMeta: LogMetadata = {};
      if (meta instanceof Error) {
        formattedMeta = { error: meta.message, stack: meta.stack };
      } else {
        formattedMeta = meta;
      }
      console.error(`[${this.getTimestamp()}] [ERROR] ${message}${this.formatMeta(formattedMeta)}`);
    }
  }

  /**
   * Log HTTP request with standard format
   * @param request - Fetch API Request object
   * @param status - Response status code
   * @param durationMs - Request duration in milliseconds
   */
  request(request: Request, status: number | null = null, durationMs: number | null = null): void {
    const url = new URL(request.url);
    const meta: RequestMetadata = {
      method: request.method,
      path: url.pathname,
      status: status ?? undefined,
      durationMs: durationMs ?? undefined,
      userAgent: request.headers.get('User-Agent')?.substring(0, 100) ?? undefined
    };

    // Remove undefined values
    Object.keys(meta).forEach(key => {
      const k = key as keyof RequestMetadata;
      if (meta[k] === undefined) {
        delete meta[k];
      }
    });

    if (status !== null && status >= 400) {
      this.warn(`HTTP ${request.method} ${url.pathname}`, meta as LogMetadata);
    } else {
      this.info(`HTTP ${request.method} ${url.pathname}`, meta as LogMetadata);
    }
  }
}

/**
 * Default logger instance - use INFO level in production
 * Can be reconfigured using logger.setLevel() or by passing LOG_LEVEL env var
 */
export const logger = new Logger(LogLevel.INFO);

/**
 * Environment interface for logger initialization
 */
interface LoggerEnv {
  LOG_LEVEL?: string;
}

/**
 * Initialize logger from environment
 * Call this at worker startup if you have access to env
 * @param env - Cloudflare Worker environment bindings
 */
export function initLogger(env: LoggerEnv): void {
  if (env?.LOG_LEVEL) {
    logger.setLevel(env.LOG_LEVEL);
  }
}

export default logger;
