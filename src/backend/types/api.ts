export interface ApiResponse<T = any> {
  data?: T;
  error?: ApiError;
  meta?: {
    timestamp: string;
    pagination?: {
      page: number;
      limit: number;
      total: number;
      total_pages: number;
    };
  };
}

export interface ApiError {
  code: string;
  message: string;
  timestamp: string;
  details?: any;
}

export interface ErrorResponse {
  error: ApiError;
}

export interface SuccessResponse<T> {
  data: T;
  meta: {
    timestamp: string;
  };
}
