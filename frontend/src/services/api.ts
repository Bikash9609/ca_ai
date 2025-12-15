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
  chat: {
    conversations: {
      list: async (
        clientId: string,
        limit: number = 50,
        offset: number = 0
      ) => {
        return fetchApi<{
          conversations: Array<{
            id: string;
            title: string;
            provider: string;
            created_at: string;
            updated_at: string;
            metadata: Record<string, unknown>;
          }>;
        }>(
          `/chat/conversations?client_id=${clientId}&limit=${limit}&offset=${offset}`
        );
      },
      create: async (data: {
        client_id: string;
        title?: string;
        provider?: string;
      }) => {
        return fetchApi<{
          id: string;
          title: string;
          provider: string;
          created_at: string;
          updated_at: string;
          metadata: Record<string, unknown>;
        }>("/chat/conversations", {
          method: "POST",
          body: JSON.stringify(data),
        });
      },
      get: async (conversationId: string, clientId: string) => {
        return fetchApi<{
          id: string;
          title: string;
          provider: string;
          created_at: string;
          updated_at: string;
          metadata: Record<string, unknown>;
          messages: Array<{
            id: string;
            role: string;
            content: string;
            tool_calls: Array<unknown>;
            created_at: string;
          }>;
        }>(`/chat/conversations/${conversationId}?client_id=${clientId}`);
      },
      updateTitle: async (
        conversationId: string,
        clientId: string,
        title: string
      ) => {
        return fetchApi<{ status: string; title: string }>(
          `/chat/conversations/${conversationId}/title?client_id=${clientId}`,
          {
            method: "PUT",
            body: JSON.stringify({ title }),
          }
        );
      },
      delete: async (conversationId: string, clientId: string) => {
        return fetchApi<{ status: string }>(
          `/chat/conversations/${conversationId}?client_id=${clientId}`,
          {
            method: "DELETE",
          }
        );
      },
    },
  },
  documents: {
    list: async (
      clientId: string,
      params?: {
        doc_type?: string;
        period?: string;
        status?: string;
        limit?: number;
        offset?: number;
      }
    ) => {
      const queryParams = new URLSearchParams({
        client_id: clientId,
        ...(params?.doc_type && { doc_type: params.doc_type }),
        ...(params?.period && { period: params.period }),
        ...(params?.status && { status: params.status }),
        ...(params?.limit && { limit: params.limit.toString() }),
        ...(params?.offset && { offset: params.offset.toString() }),
      });
      return fetchApi<{
        documents: Array<{
          id: string;
          client_id: string;
          period: string;
          doc_type: string;
          category: string;
          status: string;
          upload_date: string;
          name?: string;
          metadata?: Record<string, unknown>;
        }>;
        total: number;
      }>(`/documents?${queryParams}`);
    },
    delete: async (documentId: string, clientId: string) => {
      return fetchApi<{ status: string; document_id: string }>(
        `/documents/${documentId}?client_id=${clientId}`,
        {
          method: "DELETE",
        }
      );
    },
  },
};
