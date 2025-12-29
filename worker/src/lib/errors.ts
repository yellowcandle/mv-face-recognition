/**
 * Custom Error Classes for Cloudflare Worker
 * Provides structured error handling with proper HTTP status codes
 */

/**
 * Error details interface
 */
export interface ErrorDetails {
  [key: string]: unknown;
}

/**
 * Error JSON response structure
 */
export interface ErrorResponse {
  error: {
    code: string;
    message: string;
    details: ErrorDetails;
    timestamp: string;
  };
}

/**
 * Error information for logging
 */
export interface ErrorInfo {
  code: string;
  message: string;
  statusCode: number;
  details: ErrorDetails;
  stack?: string;
}

/**
 * CORS headers type
 */
export interface CorsHeaders {
  [key: string]: string;
}

/**
 * Base class for all application errors
 */
export class AppError extends Error {
  public statusCode: number;
  public code: string;
  public readonly details: ErrorDetails;
  public readonly timestamp: string;

  constructor(
    message: string,
    statusCode: number = 500,
    code: string = 'INTERNAL_ERROR',
    details: ErrorDetails = {}
  ) {
    super(message);
    this.name = this.constructor.name;
    this.statusCode = statusCode;
    this.code = code;
    this.details = details;
    this.timestamp = new Date().toISOString();

    const captureStackTrace = (Error as unknown as {
      captureStackTrace?: (targetObject: object, constructorOpt?: Function) => void;
    }).captureStackTrace;
    if (captureStackTrace) {
      captureStackTrace(this, this.constructor as unknown as Function);
    }
  }

  /**
   * Serialize error for API response
   */
  toJSON(): ErrorResponse {
    return {
      error: {
        code: this.code,
        message: this.message,
        details: this.details,
        timestamp: this.timestamp,
      },
    };
  }

  /**
   * Create HTTP Response from error
   */
  toResponse(corsHeaders: CorsHeaders = {}): Response {
    return new Response(JSON.stringify(this.toJSON()), {
      status: this.statusCode,
      headers: {
        'Content-Type': 'application/json',
        ...corsHeaders,
      },
    });
  }
}

/**
 * Client-side errors (4xx)
 */
export class ValidationError extends AppError {
  constructor(message: string, field: string | null = null, details: ErrorDetails = {}) {
    super(message, 400, 'VALIDATION_ERROR', { field, ...details });
  }
}

export class NotFoundError extends AppError {
  constructor(resource: string, identifier: string | null = null) {
    super(
      `${resource} not found${identifier ? `: ${identifier}` : ''}`,
      404,
      'NOT_FOUND',
      { resource, identifier }
    );
  }
}

export class UnauthorizedError extends AppError {
  constructor(message: string = 'Authentication required') {
    super(message, 401, 'UNAUTHORIZED', {});
  }
}

export class ForbiddenError extends AppError {
  constructor(message: string = 'Access denied') {
    super(message, 403, 'FORBIDDEN', {});
  }
}

export class RateLimitError extends AppError {
  constructor(retryAfter: number = 60) {
    super('Rate limit exceeded', 429, 'RATE_LIMIT_EXCEEDED', { retryAfter });
  }
}

export class BadRequestError extends AppError {
  constructor(message: string, details: ErrorDetails = {}) {
    super(message, 400, 'BAD_REQUEST', details);
  }
}

/**
 * Server-side errors (5xx)
 */
export class InternalError extends AppError {
  public readonly cause: Error | null;

  constructor(message: string = 'Internal server error', cause: Error | null = null) {
    super(message, 500, 'INTERNAL_ERROR', { cause: cause?.message });
    this.cause = cause;
  }
}

export class ServiceUnavailableError extends AppError {
  public readonly cause: Error | null;

  constructor(service: string, cause: Error | null = null) {
    super(`Service unavailable: ${service}`, 503, 'SERVICE_UNAVAILABLE', {
      service,
      cause: cause?.message,
    });
    this.cause = cause;
  }
}

export class StorageError extends AppError {
  public readonly cause: Error | null;

  constructor(operation: string, resource: string, cause: Error | null = null) {
    super(`Storage error during ${operation}: ${resource}`, 500, 'STORAGE_ERROR', {
      operation,
      resource,
      cause: cause?.message,
    });
    this.cause = cause;
  }
}

/**
 * Video processing specific errors
 */
export class VideoNotFoundError extends NotFoundError {
  constructor(videoId: string) {
    super('Video', videoId);
    this.code = 'VIDEO_NOT_FOUND';
  }
}

export class MetadataNotFoundError extends NotFoundError {
  constructor(videoId: string) {
    super('Video metadata', videoId);
    this.code = 'METADATA_NOT_FOUND';
  }
}

export class InvalidRangeError extends BadRequestError {
  constructor(details: ErrorDetails = {}) {
    super('Invalid range request', details);
    this.code = 'INVALID_RANGE';
    this.statusCode = 416; // Range Not Satisfiable
  }
}

/**
 * Error factory for common error scenarios
 */
export const ErrorFactory = {
  validation: (message: string, field?: string) => new ValidationError(message, field ?? null),
  notFound: (resource: string, id?: string) => new NotFoundError(resource, id ?? null),
  videoNotFound: (videoId: string) => new VideoNotFoundError(videoId),
  metadataNotFound: (videoId: string) => new MetadataNotFoundError(videoId),
  unauthorized: (message?: string) => new UnauthorizedError(message),
  forbidden: (message?: string) => new ForbiddenError(message),
  rateLimit: (retryAfter?: number) => new RateLimitError(retryAfter),
  internal: (message?: string, cause?: Error) => new InternalError(message, cause ?? null),
  storage: (operation: string, resource: string, cause?: Error) =>
    new StorageError(operation, resource, cause ?? null),
  badRequest: (message: string, details?: ErrorDetails) => new BadRequestError(message, details),
  invalidRange: (details?: ErrorDetails) => new InvalidRangeError(details),
};

/**
 * Worker handler function type
 */
export type WorkerHandler = (
  request: Request,
  env: unknown,
  ctx: ExecutionContext
) => Promise<Response>;

/**
 * Error handler middleware for worker
 * Wraps async handlers to catch and format errors
 */
export function withErrorHandling(
  handler: WorkerHandler,
  corsHeaders: CorsHeaders = {}
): WorkerHandler {
  return async (request: Request, env: unknown, ctx: ExecutionContext): Promise<Response> => {
    try {
      return await handler(request, env, ctx);
    } catch (error) {
      // If it's already an AppError, use its response
      if (error instanceof AppError) {
        return error.toResponse(corsHeaders);
      }

      // For unknown errors, wrap in InternalError
      const unknownError = error as Error;
      const internalError = new InternalError('An unexpected error occurred', unknownError);

      // Log the original error for debugging
      console.error('[UNHANDLED ERROR]', {
        message: unknownError.message,
        stack: unknownError.stack,
        name: unknownError.name,
      });

      return internalError.toResponse(corsHeaders);
    }
  };
}

/**
 * Utility to check if an error is retryable
 */
export function isRetryableError(error: Error | AppError): boolean {
  if (error instanceof ServiceUnavailableError) return true;
  if (error instanceof StorageError) return true;
  if ('statusCode' in error) {
    const statusCode = (error as AppError).statusCode;
    if (statusCode >= 500 && statusCode !== 501) return true;
  }
  return false;
}

/**
 * Utility to extract error info for logging
 */
export function extractErrorInfo(error: Error | AppError): ErrorInfo {
  if (error instanceof AppError) {
    return {
      code: error.code,
      message: error.message,
      statusCode: error.statusCode,
      details: error.details,
      stack: error.stack,
    };
  }

  return {
    code: 'UNKNOWN_ERROR',
    message: error.message || 'Unknown error',
    statusCode: 500,
    details: {},
    stack: error.stack,
  };
}
