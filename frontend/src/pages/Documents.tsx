import { useState, useEffect, useRef } from "react";
import { useWorkspace } from "../hooks/useWorkspace";

interface Document {
  id: string;
  client_id: string;
  period: string;
  doc_type: string;
  category: string;
  status: string;
  upload_date: string;
  name?: string;
}

interface UploadFileState {
  file: File;
  status: "uploading" | "success" | "error";
  errorMessage?: string;
}

export default function Documents() {
  const { currentClient } = useWorkspace();
  const [documents, setDocuments] = useState<Document[]>([]);
  const [loading, setLoading] = useState(false);
  const [searchTerm, setSearchTerm] = useState("");
  const [filterType, setFilterType] = useState<string>("all");
  const [filterPeriod, setFilterPeriod] = useState<string>("all");
  const [dragActive, setDragActive] = useState(false);
  const [uploadStates, setUploadStates] = useState<
    Map<string, UploadFileState>
  >(new Map());
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (currentClient) {
      loadDocuments();
    }
  }, [currentClient]);

  const loadDocuments = async () => {
    if (!currentClient) return;
    setLoading(true);
    try {
      const response = await fetch(
        `http://localhost:8000/api/documents?client_id=${currentClient.id}`
      );
      if (response.ok) {
        const data = await response.json();
        setDocuments(data.documents || []);
      }
    } catch (error) {
      console.error("Failed to load documents:", error);
    } finally {
      setLoading(false);
    }
  };

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const handleDrop = async (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);

    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      await handleFiles(Array.from(e.dataTransfer.files));
    }
  };

  const handleFileInput = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      await handleFiles(Array.from(e.target.files));
    }
  };

  const handleFiles = async (files: File[]) => {
    if (!currentClient) return;

    // Initialize upload states for all files
    const newUploadStates = new Map(uploadStates);
    files.forEach((file) => {
      newUploadStates.set(file.name, {
        file,
        status: "uploading",
      });
    });
    setUploadStates(newUploadStates);

    // Upload each file individually to track per-file status
    for (const file of files) {
      const formData = new FormData();
      formData.append("files", file);
      formData.append("client_id", currentClient.id);

      try {
        const response = await fetch(
          "http://localhost:8000/api/documents/upload",
          {
            method: "POST",
            body: formData,
          }
        );

        if (response.ok) {
          setUploadStates((prev) => {
            const updated = new Map(prev);
            updated.set(file.name, {
              file,
              status: "success",
            });
            return updated;
          });
          loadDocuments();
        } else {
          let errorText = response.statusText || "Upload failed";
          try {
            const errorData = await response.json();
            errorText = errorData.detail || errorData.message || errorText;
          } catch {
            // If JSON parsing fails, use statusText
          }
          setUploadStates((prev) => {
            const updated = new Map(prev);
            updated.set(file.name, {
              file,
              status: "error",
              errorMessage: errorText,
            });
            return updated;
          });
        }
      } catch (error) {
        const errorMessage =
          error instanceof Error ? error.message : "Network error";
        setUploadStates((prev) => {
          const updated = new Map(prev);
          updated.set(file.name, {
            file,
            status: "error",
            errorMessage,
          });
          return updated;
        });
      }
    }
  };

  const retryUpload = async (fileName: string) => {
    const uploadState = uploadStates.get(fileName);
    if (!uploadState) return;

    await handleFiles([uploadState.file]);
  };

  const clearUploadState = (fileName: string) => {
    setUploadStates((prev) => {
      const updated = new Map(prev);
      updated.delete(fileName);
      return updated;
    });
  };

  const filteredDocuments = documents.filter((doc) => {
    const matchesSearch =
      !searchTerm ||
      doc.doc_type.toLowerCase().includes(searchTerm.toLowerCase()) ||
      doc.category.toLowerCase().includes(searchTerm.toLowerCase()) ||
      (doc.name && doc.name.toLowerCase().includes(searchTerm.toLowerCase())) ||
      doc.id.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesType = filterType === "all" || doc.doc_type === filterType;
    const matchesPeriod = filterPeriod === "all" || doc.period === filterPeriod;
    return matchesSearch && matchesType && matchesPeriod;
  });

  if (!currentClient) {
    return (
      <div className="p-6">
        <div className="text-center text-gray-500">
          Please select a client to view documents
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-bold">Document Management</h1>

      {/* Upload Area */}
      <div
        onDragEnter={handleDrag}
        onDragLeave={handleDrag}
        onDragOver={handleDrag}
        onDrop={handleDrop}
        className={`border-2 border-dashed rounded-lg p-8 text-center ${
          dragActive
            ? "border-blue-500 bg-blue-50"
            : "border-gray-300 bg-gray-50"
        }`}
      >
        <input
          ref={fileInputRef}
          type="file"
          multiple
          onChange={handleFileInput}
          className="hidden"
          accept=".pdf,.jpg,.jpeg,.png,.xlsx,.xls"
        />
        <div className="space-y-4">
          <div className="text-4xl">📄</div>
          <div>
            <p className="text-lg font-medium">
              Drag and drop files here, or{" "}
              <button
                onClick={() => fileInputRef.current?.click()}
                className="text-blue-600 hover:text-blue-800 underline"
              >
                browse
              </button>
            </p>
            <p className="text-sm text-gray-500 mt-2">
              Supports PDF, Images, Excel files
            </p>
          </div>
        </div>
      </div>

      {/* Upload Status */}
      {uploadStates.size > 0 && (
        <div className="bg-white rounded-lg shadow p-4 space-y-2">
          <h3 className="text-sm font-semibold text-gray-700 mb-3">
            Upload Status
          </h3>
          {Array.from(uploadStates.entries()).map(([fileName, uploadState]) => (
            <div
              key={fileName}
              className="flex items-center justify-between p-3 border rounded-lg"
            >
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium text-gray-900 truncate">
                    {fileName}
                  </span>
                  {uploadState.status === "uploading" && (
                    <span className="text-xs text-blue-600">Uploading...</span>
                  )}
                  {uploadState.status === "success" && (
                    <span className="text-xs text-green-600">✓ Uploaded</span>
                  )}
                  {uploadState.status === "error" && (
                    <span className="text-xs text-red-600">✗ Failed</span>
                  )}
                </div>
                {uploadState.status === "error" && uploadState.errorMessage && (
                  <div className="mt-1 text-xs text-red-600">
                    {uploadState.errorMessage}
                  </div>
                )}
              </div>
              <div className="flex items-center gap-2 ml-4">
                {uploadState.status === "error" && (
                  <button
                    onClick={() => retryUpload(fileName)}
                    className="px-3 py-1 text-xs font-medium text-blue-600 hover:text-blue-800 hover:bg-blue-50 rounded"
                  >
                    Retry
                  </button>
                )}
                {(uploadState.status === "success" ||
                  uploadState.status === "error") && (
                  <button
                    onClick={() => clearUploadState(fileName)}
                    className="px-3 py-1 text-xs font-medium text-gray-600 hover:text-gray-800 hover:bg-gray-50 rounded"
                  >
                    Dismiss
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Filters */}
      <div className="bg-white rounded-lg shadow p-4">
        <div className="flex gap-4 items-end">
          <div className="flex-1">
            <label className="block text-sm font-medium mb-1">Search</label>
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="Search documents..."
              className="w-full px-3 py-2 border rounded"
            />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">Type</label>
            <select
              value={filterType}
              onChange={(e) => setFilterType(e.target.value)}
              className="px-3 py-2 border rounded"
            >
              <option value="all">All Types</option>
              <option value="invoice">Invoice</option>
              <option value="statement">Statement</option>
              <option value="notice">Notice</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">Period</label>
            <select
              value={filterPeriod}
              onChange={(e) => setFilterPeriod(e.target.value)}
              className="px-3 py-2 border rounded"
            >
              <option value="all">All Periods</option>
              <option value="2024-01">Jan 2024</option>
              <option value="2024-02">Feb 2024</option>
            </select>
          </div>
        </div>
      </div>

      {/* Document List */}
      <div className="bg-white rounded-lg shadow overflow-hidden">
        <table className="w-full">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                Name
              </th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                Type
              </th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                Category
              </th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                Period
              </th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                Status
              </th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                Actions
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200">
            {filteredDocuments.map((doc) => (
              <tr key={doc.id} className="hover:bg-gray-50">
                <td className="px-4 py-3">
                  <div className="flex flex-col">
                    <span className="font-medium text-gray-900">
                      {doc.name || doc.id}
                    </span>
                    <span className="text-xs text-gray-500 mt-1">
                      ID: {doc.id}
                    </span>
                  </div>
                </td>
                <td className="px-4 py-3">
                  <span className="px-2 py-1 text-xs rounded bg-blue-100 text-blue-800">
                    {doc.doc_type}
                  </span>
                </td>
                <td className="px-4 py-3">{doc.category}</td>
                <td className="px-4 py-3">{doc.period}</td>
                <td className="px-4 py-3">
                  <span
                    className={`px-2 py-1 text-xs rounded ${
                      doc.status === "indexed"
                        ? "bg-green-100 text-green-800"
                        : "bg-yellow-100 text-yellow-800"
                    }`}
                  >
                    {doc.status}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <button className="text-blue-600 hover:text-blue-800 text-sm">
                    View
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {filteredDocuments.length === 0 && (
          <div className="text-center py-8 text-gray-500">
            No documents found
          </div>
        )}
      </div>
    </div>
  );
}
