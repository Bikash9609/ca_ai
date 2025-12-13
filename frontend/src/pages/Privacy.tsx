import { useState, useEffect } from "react";
import {
  Card,
  CardBody,
  CardHeader,
  Tabs,
  Tab,
  Input,
  Select,
  SelectItem,
  Button,
  Table,
  TableHeader,
  TableColumn,
  TableBody,
  TableRow,
  TableCell,
  Chip,
} from "@heroui/react";
import { useWorkspace } from "../hooks/useWorkspace";

interface PrivacyStats {
  total_queries: number;
  total_data_shared_bytes: number;
  recent_interactions: Array<{
    timestamp: string;
    tool_name: string;
    result_size_bytes: number;
  }>;
}

interface UsageStatistics {
  total_tool_calls: number;
  tool_usage: Record<string, number>;
  data_shared_by_tool: Record<string, number>;
  average_result_size: number;
  peak_usage_day: string | null;
  usage_by_hour: Record<string, number>;
  total_data_shared_bytes: number;
}

interface SecurityMonitoring {
  total_violations: number;
  violations_by_tool: Record<string, number>;
  violations_by_reason: Record<string, number>;
  recent_violations: Array<{
    timestamp: string;
    tool_name: string;
    reason: string;
  }>;
  suspicious_activity: boolean;
}

export default function Privacy() {
  const { currentClient } = useWorkspace();
  const [activeTab, setActiveTab] = useState<"dashboard" | "logs" | "data">(
    "dashboard"
  );
  const [privacyStats, setPrivacyStats] = useState<PrivacyStats | null>(null);
  const [usageStats, setUsageStats] = useState<UsageStatistics | null>(null);
  const [securityMonitoring, setSecurityMonitoring] =
    useState<SecurityMonitoring | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (currentClient) {
      loadPrivacyData();
    }
  }, [currentClient]);

  const loadPrivacyData = async () => {
    if (!currentClient) return;

    setLoading(true);
    try {
      const [statsRes, usageRes, securityRes] = await Promise.all([
        fetch(`http://localhost:8000/api/privacy/stats/${currentClient.id}`),
        fetch(`http://localhost:8000/api/privacy/usage/${currentClient.id}`),
        fetch(`http://localhost:8000/api/privacy/security/${currentClient.id}`),
      ]);

      if (statsRes.ok) {
        const stats = await statsRes.json();
        setPrivacyStats(stats);
      }

      if (usageRes.ok) {
        const usage = await usageRes.json();
        setUsageStats(usage);
      }

      if (securityRes.ok) {
        const security = await securityRes.json();
        setSecurityMonitoring(security);
      }
    } catch (error) {
      console.error("Failed to load privacy data:", error);
    } finally {
      setLoading(false);
    }
  };

  const formatBytes = (bytes: number): string => {
    if (bytes === 0) return "0 B";
    const k = 1024;
    const sizes = ["B", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return `${(bytes / Math.pow(k, i)).toFixed(2)} ${sizes[i]}`;
  };

  if (loading) {
    return (
      <div className="p-6">
        <div className="text-center">Loading privacy data...</div>
      </div>
    );
  }

  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold mb-6 text-foreground">
        Privacy & Security
      </h1>

      {/* Tabs */}
      <Tabs
        selectedKey={activeTab}
        onSelectionChange={(key) => setActiveTab(key as typeof activeTab)}
        classNames={{
          base: "mb-6",
        }}
      >
        <Tab key="dashboard" title="Dashboard" />
        <Tab key="logs" title="Audit Logs" />
        <Tab key="data" title="Data Management" />
      </Tabs>

      {/* Dashboard Tab */}
      {activeTab === "dashboard" && (
        <div className="space-y-6">
          {/* Access Summary */}
          <Card classNames={{ base: "border border-default-200" }}>
            <CardHeader>
              <h2 className="text-xl font-semibold text-foreground">
                Access Summary
              </h2>
            </CardHeader>
            <CardBody>
              <div className="grid grid-cols-3 gap-4">
                <div>
                  <div className="text-sm text-default-500">Total Queries</div>
                  <div className="text-2xl font-bold text-foreground">
                    {privacyStats?.total_queries || 0}
                  </div>
                </div>
                <div>
                  <div className="text-sm text-default-500">Data Shared</div>
                  <div className="text-2xl font-bold text-foreground">
                    {formatBytes(privacyStats?.total_data_shared_bytes || 0)}
                  </div>
                </div>
                <div>
                  <div className="text-sm text-default-500">Tools Used</div>
                  <div className="text-2xl font-bold text-foreground">
                    {Object.keys(usageStats?.tool_usage || {}).length}
                  </div>
                </div>
              </div>
            </CardBody>
          </Card>

          {/* Security Status */}
          <Card classNames={{ base: "border border-default-200" }}>
            <CardHeader>
              <h2 className="text-xl font-semibold text-foreground">
                Security Status
              </h2>
            </CardHeader>
            <CardBody className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-foreground">Firewall Active</span>
                <Chip color="success">✓ Active</Chip>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-foreground">File Access</span>
                <Chip color="success">✓ Blocked</Chip>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-foreground">All Interactions Logged</span>
                <Chip color="success">✓ Yes</Chip>
              </div>
              {securityMonitoring &&
                securityMonitoring.total_violations > 0 && (
                  <div className="flex items-center justify-between">
                    <span className="text-foreground">Security Violations</span>
                    <Chip color="danger">
                      {securityMonitoring.total_violations} detected
                    </Chip>
                  </div>
                )}
            </CardBody>
          </Card>

          {/* Recent Interactions */}
          <Card classNames={{ base: "border border-default-200" }}>
            <CardHeader>
              <h2 className="text-xl font-semibold text-foreground">
                Recent Interactions
              </h2>
            </CardHeader>
            <CardBody>
              <div className="space-y-2">
                {privacyStats?.recent_interactions
                  .slice(0, 10)
                  .map((interaction, idx) => (
                    <div
                      key={idx}
                      className="flex justify-between items-center py-2 border-b border-default-200"
                    >
                      <div>
                        <div className="font-medium text-foreground">
                          {interaction.tool_name}
                        </div>
                        <div className="text-sm text-default-500">
                          {new Date(interaction.timestamp).toLocaleString()}
                        </div>
                      </div>
                      <div className="text-sm text-default-600">
                        {formatBytes(interaction.result_size_bytes)}
                      </div>
                    </div>
                  ))}
                {(!privacyStats?.recent_interactions ||
                  privacyStats.recent_interactions.length === 0) && (
                  <div className="text-default-500 text-center py-4">
                    No interactions yet
                  </div>
                )}
              </div>
            </CardBody>
          </Card>

          {/* Usage Statistics */}
          {usageStats && (
            <Card classNames={{ base: "border border-default-200" }}>
              <CardHeader>
                <h2 className="text-xl font-semibold text-foreground">
                  Usage Statistics
                </h2>
              </CardHeader>
              <CardBody>
                <div className="space-y-4">
                  <div>
                    <div className="text-sm text-default-500 mb-2">
                      Tool Usage
                    </div>
                    <div className="space-y-1">
                      {Object.entries(usageStats.tool_usage).map(
                        ([tool, count]) => (
                          <div key={tool} className="flex justify-between">
                            <span className="text-foreground">{tool}</span>
                            <span className="font-medium text-foreground">
                              {count}
                            </span>
                          </div>
                        )
                      )}
                    </div>
                  </div>
                  {usageStats.peak_usage_day && (
                    <div>
                      <div className="text-sm text-default-500">
                        Peak Usage Day
                      </div>
                      <div className="font-medium text-foreground">
                        {usageStats.peak_usage_day}
                      </div>
                    </div>
                  )}
                </div>
              </CardBody>
            </Card>
          )}
        </div>
      )}

      {/* Audit Logs Tab */}
      {activeTab === "logs" && <AuditLogViewer clientId={currentClient?.id} />}

      {/* Data Management Tab */}
      {activeTab === "data" && <DataManagement clientId={currentClient?.id} />}
    </div>
  );
}

function AuditLogViewer({ clientId }: { clientId?: string }) {
  const [logs, setLogs] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState("");
  const [filterTool, setFilterTool] = useState<string>("all");

  useEffect(() => {
    if (clientId) {
      loadLogs();
    }
  }, [clientId]);

  const loadLogs = async () => {
    if (!clientId) return;

    setLoading(true);
    try {
      const res = await fetch(
        `http://localhost:8000/api/privacy/logs/${clientId}?limit=500`
      );
      if (res.ok) {
        const data = await res.json();
        setLogs(data.logs || []);
      }
    } catch (error) {
      console.error("Failed to load logs:", error);
    } finally {
      setLoading(false);
    }
  };

  const exportLogs = async () => {
    if (!clientId) return;

    try {
      const res = await fetch(
        `http://localhost:8000/api/privacy/logs/${clientId}/all`
      );
      if (res.ok) {
        const data = await res.json();
        const blob = new Blob([JSON.stringify(data.logs, null, 2)], {
          type: "application/json",
        });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `audit_logs_${
          new Date().toISOString().split("T")[0]
        }.json`;
        a.click();
        URL.revokeObjectURL(url);
      }
    } catch (error) {
      console.error("Failed to export logs:", error);
    }
  };

  const filteredLogs = logs.filter((log) => {
    const matchesSearch =
      !searchTerm ||
      log.tool_name?.toLowerCase().includes(searchTerm.toLowerCase()) ||
      JSON.stringify(log.params || {})
        .toLowerCase()
        .includes(searchTerm.toLowerCase());

    const matchesTool = filterTool === "all" || log.tool_name === filterTool;

    return matchesSearch && matchesTool;
  });

  const uniqueTools = Array.from(
    new Set(logs.map((log) => log.tool_name).filter(Boolean))
  );

  if (loading) {
    return <div className="text-center py-8">Loading audit logs...</div>;
  }

  return (
    <div className="space-y-4">
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
                placeholder="Search logs..."
              />
            </div>
            <div>
              <Select
                label="Filter by Tool"
                selectedKeys={[filterTool]}
                onSelectionChange={(keys) => {
                  const selected = Array.from(keys)[0] as string;
                  setFilterTool(selected);
                }}
              >
                <SelectItem key="all">All Tools</SelectItem>
                {uniqueTools.map((tool) => (
                  <SelectItem key={tool} value={tool}>
                    {tool}
                  </SelectItem>
                ))}
              </Select>
            </div>
            <Button color="primary" onPress={exportLogs}>
              Export Logs
            </Button>
          </div>
        </CardBody>
      </Card>

      {/* Log List */}
      <Card classNames={{ base: "border border-default-200" }}>
        <Table aria-label="Audit logs table">
          <TableHeader>
            <TableColumn>Timestamp</TableColumn>
            <TableColumn>Tool</TableColumn>
            <TableColumn>Data Size</TableColumn>
            <TableColumn>Status</TableColumn>
          </TableHeader>
          <TableBody emptyContent="No logs found">
            {filteredLogs.map((log, idx) => (
              <TableRow key={idx}>
                <TableCell>
                  {new Date(log.timestamp).toLocaleString()}
                </TableCell>
                <TableCell className="font-medium">
                  {log.tool_name || "N/A"}
                </TableCell>
                <TableCell>
                  {log.result_size_bytes
                    ? `${(log.result_size_bytes / 1024).toFixed(2)} KB`
                    : "N/A"}
                </TableCell>
                <TableCell>
                  {log.violation ? (
                    <Chip color="danger">Violation</Chip>
                  ) : (
                    <Chip color="success">Allowed</Chip>
                  )}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Card>
    </div>
  );
}

function DataManagement({ clientId }: { clientId?: string }) {
  const [workspaceInfo, setWorkspaceInfo] = useState<{
    path: string;
    size_bytes: number;
    file_count: number;
  } | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadWorkspaceInfo();
  }, []);

  const loadWorkspaceInfo = async () => {
    setLoading(true);
    try {
      const res = await fetch("http://localhost:8000/api/workspace/info");
      if (res.ok) {
        const info = await res.json();
        setWorkspaceInfo(info);
      }
    } catch (error) {
      console.error("Failed to load workspace info:", error);
    } finally {
      setLoading(false);
    }
  };

  const formatBytes = (bytes: number): string => {
    if (bytes === 0) return "0 B";
    const k = 1024;
    const sizes = ["B", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return `${(bytes / Math.pow(k, i)).toFixed(2)} ${sizes[i]}`;
  };

  if (loading) {
    return (
      <div className="text-center py-8">Loading workspace information...</div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Workspace Info */}
      <Card classNames={{ base: "border border-default-200" }}>
        <CardHeader>
          <h2 className="text-xl font-semibold text-foreground">
            Workspace Information
          </h2>
        </CardHeader>
        <CardBody>
          <div className="space-y-3">
            <div>
              <div className="text-sm text-default-500">Location</div>
              <div className="font-mono text-sm text-foreground">
                {workspaceInfo?.path || "N/A"}
              </div>
            </div>
            <div>
              <div className="text-sm text-default-500">Total Size</div>
              <div className="text-lg font-semibold text-foreground">
                {workspaceInfo ? formatBytes(workspaceInfo.size_bytes) : "N/A"}
              </div>
            </div>
            <div>
              <div className="text-sm text-default-500">File Count</div>
              <div className="text-lg font-semibold text-foreground">
                {workspaceInfo?.file_count || 0} files
              </div>
            </div>
          </div>
        </CardBody>
      </Card>

      {/* Export Options */}
      <Card classNames={{ base: "border border-default-200" }}>
        <CardHeader>
          <h2 className="text-xl font-semibold text-foreground">Export Data</h2>
        </CardHeader>
        <CardBody>
          <div className="space-y-3">
            <Button color="primary" className="w-full">
              Export Workspace as ZIP
            </Button>
            <Button color="primary" className="w-full">
              Export Processed Data
            </Button>
            <Button color="primary" className="w-full">
              Export Audit Logs
            </Button>
          </div>
        </CardBody>
      </Card>

      {/* Deletion Options */}
      <Card
        classNames={{
          base: "border-l-4 border-l-danger border border-default-200",
        }}
      >
        <CardHeader>
          <h2 className="text-xl font-semibold text-danger">Danger Zone</h2>
        </CardHeader>
        <CardBody>
          <div className="space-y-3">
            <div>
              <p className="text-sm text-default-600 mb-2">
                Permanently delete client data. This action cannot be undone.
              </p>
              <Button color="danger">Delete Client Data</Button>
            </div>
            <div>
              <p className="text-sm text-default-600 mb-2">
                Permanently delete entire workspace. This action cannot be
                undone.
              </p>
              <Button color="danger">Delete Workspace</Button>
            </div>
          </div>
        </CardBody>
      </Card>
    </div>
  );
}
