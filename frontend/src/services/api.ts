/**
 * Centralized API client for backend communication
 */

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api";

interface ApiResponse<T> {
  data?: T;
  error?: string;
}

async function fetchApi<T>(
  endpoint: string,
  options?: RequestInit
): Promise<ApiResponse<T>> {
  try {
    const response = await fetch(`${API_BASE_URL}${endpoint}`, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...options?.headers,
      },
    });

    if (!response.ok) {
      const error = await response.text();
      return {
        error: `HTTP ${response.status}: ${error || response.statusText}`,
      };
    }

    const data = await response.json();
    return { data };
  } catch (error) {
    return {
      error: error instanceof Error ? error.message : "Network error",
    };
  }
}

export const api = {
  workspace: {
    get: async () => {
      return fetchApi<{
        path: string;
        clients: Array<{
          id: string;
          name: string;
          gstin?: string;
          createdAt: string;
          updatedAt: string;
          metadata: Record<string, unknown>;
        }>;
        createdAt: string;
      }>("/workspace");
    },
    clients: {
      list: async () => {
        return fetchApi<
          Array<{
            id: string;
            name: string;
            gstin?: string;
            createdAt: string;
            updatedAt: string;
            metadata: Record<string, unknown>;
          }>
        >("/workspace/clients");
      },
      get: async (clientId: string) => {
        return fetchApi<{
          id: string;
          name: string;
          gstin?: string;
          createdAt: string;
          updatedAt: string;
          metadata: Record<string, unknown>;
        }>(`/workspace/clients/${clientId}`);
      },
      create: async (data: {
        name: string;
        gstin?: string;
        metadata?: Record<string, unknown>;
      }) => {
        return fetchApi<{
          id: string;
          name: string;
          gstin?: string;
          createdAt: string;
          updatedAt: string;
          metadata: Record<string, unknown>;
        }>("/workspace/clients", {
          method: "POST",
          body: JSON.stringify(data),
        });
      },
      update: async (
        clientId: string,
        data: {
          name?: string;
          gstin?: string;
          metadata?: Record<string, unknown>;
        }
      ) => {
        return fetchApi<{
          id: string;
          name: string;
          gstin?: string;
          createdAt: string;
          updatedAt: string;
          metadata: Record<string, unknown>;
        }>(`/workspace/clients/${clientId}`, {
          method: "PUT",
          body: JSON.stringify(data),
        });
      },
      delete: async (clientId: string) => {
        return fetchApi<{ message: string }>(`/workspace/clients/${clientId}`, {
          method: "DELETE",
        });
      },
    },
  },
};
