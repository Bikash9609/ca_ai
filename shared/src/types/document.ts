/**
 * Document types and interfaces
 */

export type DocumentType = "invoice" | "statement" | "notice" | "certificate" | "other";

export type DocumentCategory = "gst" | "it" | "general";

export type DocumentStatus = "uploaded" | "processing" | "indexed" | "error";

export interface Document {
  id: string;
  clientId: string;
  period: string;
  docType: DocumentType;
  category: DocumentCategory;
  filePath: string;
  fileHash: string;
  uploadDate: Date;
  status: DocumentStatus;
  metadata?: Record<string, unknown>;
}

export interface DocumentChunk {
  id: string;
  documentId: string;
  chunkIndex: number;
  text: string;
  metadata?: Record<string, unknown>;
}

