// Shared types for the frontend application

export interface Client {
  id: string;
  name: string;
  gstin?: string;
  createdAt: string;
  updatedAt: string;
}

export interface Workspace {
  path: string;
  clients: Client[];
  createdAt: string;
}

export interface Document {
  id: string;
  clientId: string;
  period: string;
  docType: string;
  category: string;
  filePath: string;
  uploadDate: string;
  status: string;
  metadata?: Record<string, unknown>;
}
