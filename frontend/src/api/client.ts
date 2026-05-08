import type { ApiResponse, ErrorDetail } from '@/api/types';

export class ApiClientError extends Error {
  readonly status: number;
  readonly payload?: ErrorDetail;

  constructor(message: string, status: number, payload?: ErrorDetail) {
    super(message);
    this.name = 'ApiClientError';
    this.status = status;
    this.payload = payload;
  }
}

interface RequestOptions extends Omit<RequestInit, 'body'> {
  body?: unknown;
}

function buildUrl(path: string, query?: Record<string, string | number | boolean | undefined>) {
  const url = new URL(path, window.location.origin);
  if (query) {
    Object.entries(query).forEach(([key, value]) => {
      if (value !== undefined) {
        url.searchParams.set(key, String(value));
      }
    });
  }
  return `${url.pathname}${url.search}`;
}

async function request<T>(
  method: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE',
  path: string,
  options?: RequestOptions,
  query?: Record<string, string | number | boolean | undefined>,
): Promise<T> {
  const response = await fetch(buildUrl(path, query), {
    method,
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
    body: options?.body !== undefined ? JSON.stringify(options.body) : undefined,
    signal: options?.signal,
    mode: 'cors',
  });

  let parsed: ApiResponse<T> | null = null;
  try {
    parsed = (await response.json()) as ApiResponse<T>;
  } catch {
    if (!response.ok) {
      throw new ApiClientError(`HTTP ${response.status}`, response.status);
    }
  }

  if (!response.ok) {
    throw new ApiClientError(
      parsed?.error?.message ?? `HTTP ${response.status}`,
      response.status,
      parsed?.error ?? undefined,
    );
  }

  if (!parsed?.ok || parsed.data === null) {
    throw new ApiClientError(parsed?.error?.message ?? 'API returned empty data', response.status, parsed?.error ?? undefined);
  }

  return parsed.data;
}

export const apiClient = {
  get<T>(path: string, query?: Record<string, string | number | boolean | undefined>, options?: RequestOptions) {
    return request<T>('GET', path, options, query);
  },
  post<T>(path: string, body?: unknown, options?: RequestOptions) {
    return request<T>('POST', path, { ...options, body });
  },
  put<T>(path: string, body?: unknown, options?: RequestOptions) {
    return request<T>('PUT', path, { ...options, body });
  },
  patch<T>(path: string, body?: unknown, options?: RequestOptions) {
    return request<T>('PATCH', path, { ...options, body });
  },
  delete<T>(path: string, options?: RequestOptions) {
    return request<T>('DELETE', path, options);
  },
};
