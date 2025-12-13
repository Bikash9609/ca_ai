/**
 * Client types and interfaces
 */

export interface Client {
  id: string;
  name: string;
  gstin?: string;
  createdAt: Date;
  updatedAt: Date;
  metadata?: Record<string, unknown>;
}

export interface Workspace {
  path: string;
  clients: Client[];
}

