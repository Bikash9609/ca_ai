import { useState, useEffect, useRef } from "react";
import {
  Card,
  CardBody,
  CardHeader,
  Input,
  Select,
  SelectItem,
  Table,
  TableHeader,
  TableColumn,
  TableBody,
  TableRow,
  TableCell,
  Button,
  Chip,
} from "@heroui/react";
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
    // Reset input value to allow selecting the same file again
    if (e.target) {
      e.target.value = "";
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
        <div className="text-center text-default-500">
          Please select a client to view documents
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-bold text-foreground">
        Document Management
      </h1>

      {/* Upload Area */}
      <Card
        onDragEnter={handleDrag}
        onDragLeave={handleDrag}
        onDragOver={handleDrag}
        onDrop={handleDrop}
        classNames={{
          base: `border-2 border-dashed p-8 text-center ${
            dragActive
              ? "border-primary bg-primary-50"
              : "border-default-300 bg-default-50"
          }`,
        }}
      >
        <CardBody>
          <input
            ref={fileInputRef}
            type="file"
            multiple
            onChange={handleFileInput}
            className="hidden"
            accept=".pdf,.jpg,.jpeg,.png,.xlsx,.xls"
            style={{ display: "none" }}
          />
          <div className="space-y-4">
            <div className="text-4xl">📄</div>
            <div>
              <p className="text-lg font-medium text-foreground">
                Drag and drop files here, or{" "}
                <button
                  type="button"
                  onClick={(e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    if (fileInputRef.current) {
                      fileInputRef.current.click();
                    }
                  }}
                  className="underline text-primary hover:text-primary-600 cursor-pointer bg-transparent border-none p-0 font-medium"
                >
                  browse
                </button>
              </p>
              <p className="text-sm text-default-500 mt-2">
                Supports PDF, Images, Excel files
              </p>
            </div>
          </div>
        </CardBody>
      </Card>

      {/* Upload Status */}
      {uploadStates.size > 0 && (
        <Card classNames={{ base: "border border-default-200" }}>
          <CardHeader>
            <h3 className="text-sm font-semibold text-foreground">
              Upload Status
            </h3>
          </CardHeader>
          <CardBody className="space-y-2">
            {Array.from(uploadStates.entries()).map(
              ([fileName, uploadState]) => (
                <Card
                  key={fileName}
                  classNames={{ base: "border border-default-200" }}
                >
                  <CardBody>
                    <div className="flex items-center justify-between">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-medium text-foreground truncate">
                            {fileName}
                          </span>
                          {uploadState.status === "uploading" && (
                            <Chip size="sm" color="primary">
                              Uploading...
                            </Chip>
                          )}
                          {uploadState.status === "success" && (
                            <Chip size="sm" color="success">
                              ✓ Uploaded
                            </Chip>
                          )}
                          {uploadState.status === "error" && (
                            <Chip size="sm" color="danger">
                              ✗ Failed
                            </Chip>
                          )}
                        </div>
                        {uploadState.status === "error" &&
                          uploadState.errorMessage && (
                            <div className="mt-1 text-xs text-danger">
                              {uploadState.errorMessage}
                            </div>
                          )}
                      </div>
                      <div className="flex items-center gap-2 ml-4">
                        {uploadState.status === "error" && (
                          <Button
                            size="sm"
                            variant="light"
                            color="primary"
                            onPress={() => retryUpload(fileName)}
                          >
                            Retry
                          </Button>
                        )}
                        {(uploadState.status === "success" ||
                          uploadState.status === "error") && (
                          <Button
                            size="sm"
                            variant="light"
                            onPress={() => clearUploadState(fileName)}
                          >
                            Dismiss
                          </Button>
                        )}
                      </div>
                    </div>
                  </CardBody>
                </Card>
              )
            )}
          </CardBody>
        </Card>
      )}

      {/* Filters */}
      <Card classNames={{ base: "border border-default-200" }}>
        <CardBody>
          <div className="flex gap-4 items-end">
            <div className="flex-1">
              <Input
                type="text"
                label="Search"
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                placeholder="Search documents..."
              />
            </div>
            <div>
              <Select
                label="Type"
                selectedKeys={[filterType]}
                onSelectionChange={(keys) => {
                  const selected = Array.from(keys)[0] as string;
                  setFilterType(selected);
                }}
              >
                <SelectItem key="all">All Types</SelectItem>
                <SelectItem key="invoice">Invoice</SelectItem>
                <SelectItem key="statement">Statement</SelectItem>
                <SelectItem key="notice">Notice</SelectItem>
              </Select>
            </div>
            <div>
              <Select
                label="Period"
                selectedKeys={[filterPeriod]}
                onSelectionChange={(keys) => {
                  const selected = Array.from(keys)[0] as string;
                  setFilterPeriod(selected);
                }}
              >
                <SelectItem key="all">All Periods</SelectItem>
                <SelectItem key="2024-01">Jan 2024</SelectItem>
                <SelectItem key="2024-02">Feb 2024</SelectItem>
              </Select>
            </div>
          </div>
        </CardBody>
      </Card>

      {/* Document List */}
      <Card classNames={{ base: "border border-default-200" }}>
        <Table aria-label="Documents table">
          <TableHeader>
            <TableColumn>Name</TableColumn>
            <TableColumn>Type</TableColumn>
            <TableColumn>Category</TableColumn>
            <TableColumn>Period</TableColumn>
            <TableColumn>Status</TableColumn>
            <TableColumn>Actions</TableColumn>
          </TableHeader>
          <TableBody emptyContent="No documents found">
            {filteredDocuments.map((doc) => (
              <TableRow key={doc.id}>
                <TableCell>
                  <div className="flex flex-col">
                    <span className="font-medium text-foreground">
                      {doc.name || doc.id}
                    </span>
                    <span className="text-xs text-default-500 mt-1">
                      ID: {doc.id}
                    </span>
                  </div>
                </TableCell>
                <TableCell>
                  <Chip size="sm" color="primary">
                    {doc.doc_type}
                  </Chip>
                </TableCell>
                <TableCell>{doc.category}</TableCell>
                <TableCell>{doc.period}</TableCell>
                <TableCell>
                  <Chip
                    size="sm"
                    color={doc.status === "indexed" ? "success" : "warning"}
                  >
                    {doc.status}
                  </Chip>
                </TableCell>
                <TableCell>
                  <Button size="sm" variant="light" color="primary">
                    View
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Card>
    </div>
  );
}
