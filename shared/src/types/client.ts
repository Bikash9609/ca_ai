/**
 * Client types and interfaces
 */

export interface Client {
  id: string;
  name: string;
  gstin?: string;
  createdAt: string; // ISO string
  updatedAt: string; // ISO string
  metadata?: Record<string, unknown>;
}

export interface Workspace {
  path: string;
  clients: Client[];
  createdAt: string; // ISO string
}
