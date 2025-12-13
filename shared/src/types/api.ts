/**
 * API request/response types
 */

export interface ApiResponse<T = unknown> {
  success: boolean;
  data?: T;
  error?: string;
  message?: string;
}

export interface PaginatedResponse<T> extends ApiResponse<T[]> {
  page: number;
  pageSize: number;
  total: number;
  totalPages: number;
}

export interface SearchRequest {
  query: string;
  limit?: number;
  offset?: number;
  filters?: Record<string, unknown>;
}

export interface SearchResult {
  id: string;
  score: number;
  content: string;
  metadata?: Record<string, unknown>;
}

