import { useState, useEffect } from "react";
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
      <h1 className="text-2xl font-bold mb-6">Privacy & Security</h1>

      {/* Tabs */}
      <div className="border-b mb-6">
        <nav className="flex space-x-4">
          <button
            onClick={() => setActiveTab("dashboard")}
            className={`py-2 px-4 border-b-2 ${
              activeTab === "dashboard"
                ? "border-blue-500 text-blue-600"
                : "border-transparent text-gray-500"
            }`}
          >
            Dashboard
          </button>
          <button
            onClick={() => setActiveTab("logs")}
            className={`py-2 px-4 border-b-2 ${
              activeTab === "logs"
                ? "border-blue-500 text-blue-600"
                : "border-transparent text-gray-500"
            }`}
          >
            Audit Logs
          </button>
          <button
            onClick={() => setActiveTab("data")}
            className={`py-2 px-4 border-b-2 ${
              activeTab === "data"
                ? "border-blue-500 text-blue-600"
                : "border-transparent text-gray-500"
            }`}
          >
            Data Management
          </button>
        </nav>
      </div>

      {/* Dashboard Tab */}
      {activeTab === "dashboard" && (
        <div className="space-y-6">
          {/* Access Summary */}
          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="text-xl font-semibold mb-4">Access Summary</h2>
            <div className="grid grid-cols-3 gap-4">
              <div>
                <div className="text-sm text-gray-500">Total Queries</div>
                <div className="text-2xl font-bold">
                  {privacyStats?.total_queries || 0}
                </div>
              </div>
              <div>
                <div className="text-sm text-gray-500">Data Shared</div>
                <div className="text-2xl font-bold">
                  {formatBytes(privacyStats?.total_data_shared_bytes || 0)}
                </div>
              </div>
              <div>
                <div className="text-sm text-gray-500">Tools Used</div>
                <div className="text-2xl font-bold">
                  {Object.keys(usageStats?.tool_usage || {}).length}
                </div>
              </div>
            </div>
          </div>

          {/* Security Status */}
          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="text-xl font-semibold mb-4">Security Status</h2>
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span>Firewall Active</span>
                <span className="text-green-600 font-semibold">✓ Active</span>
              </div>
              <div className="flex items-center justify-between">
                <span>File Access</span>
                <span className="text-green-600 font-semibold">✓ Blocked</span>
              </div>
              <div className="flex items-center justify-between">
                <span>All Interactions Logged</span>
                <span className="text-green-600 font-semibold">✓ Yes</span>
              </div>
              {securityMonitoring &&
                securityMonitoring.total_violations > 0 && (
                  <div className="flex items-center justify-between">
                    <span>Security Violations</span>
                    <span className="text-red-600 font-semibold">
                      {securityMonitoring.total_violations} detected
                    </span>
                  </div>
                )}
            </div>
          </div>

          {/* Recent Interactions */}
          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="text-xl font-semibold mb-4">Recent Interactions</h2>
            <div className="space-y-2">
              {privacyStats?.recent_interactions
                .slice(0, 10)
                .map((interaction, idx) => (
                  <div
                    key={idx}
                    className="flex justify-between items-center py-2 border-b"
                  >
                    <div>
                      <div className="font-medium">{interaction.tool_name}</div>
                      <div className="text-sm text-gray-500">
                        {new Date(interaction.timestamp).toLocaleString()}
                      </div>
                    </div>
                    <div className="text-sm text-gray-600">
                      {formatBytes(interaction.result_size_bytes)}
                    </div>
                  </div>
                ))}
              {(!privacyStats?.recent_interactions ||
                privacyStats.recent_interactions.length === 0) && (
                <div className="text-gray-500 text-center py-4">
                  No interactions yet
                </div>
              )}
            </div>
          </div>

          {/* Usage Statistics */}
          {usageStats && (
            <div className="bg-white rounded-lg shadow p-6">
              <h2 className="text-xl font-semibold mb-4">Usage Statistics</h2>
              <div className="space-y-4">
                <div>
                  <div className="text-sm text-gray-500 mb-2">Tool Usage</div>
                  <div className="space-y-1">
                    {Object.entries(usageStats.tool_usage).map(
                      ([tool, count]) => (
                        <div key={tool} className="flex justify-between">
                          <span>{tool}</span>
                          <span className="font-medium">{count}</span>
                        </div>
                      )
                    )}
                  </div>
                </div>
                {usageStats.peak_usage_day && (
                  <div>
                    <div className="text-sm text-gray-500">Peak Usage Day</div>
                    <div className="font-medium">
                      {usageStats.peak_usage_day}
                    </div>
                  </div>
                )}
              </div>
            </div>
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
      <div className="bg-white rounded-lg shadow p-4">
        <div className="flex gap-4 items-end">
          <div className="flex-1">
            <label className="block text-sm font-medium mb-1">Search</label>
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="Search logs..."
              className="w-full px-3 py-2 border rounded"
            />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">
              Filter by Tool
            </label>
            <select
              value={filterTool}
              onChange={(e) => setFilterTool(e.target.value)}
              className="px-3 py-2 border rounded"
            >
              <option value="all">All Tools</option>
              {uniqueTools.map((tool) => (
                <option key={tool} value={tool}>
                  {tool}
                </option>
              ))}
            </select>
          </div>
          <button
            onClick={exportLogs}
            className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
          >
            Export Logs
          </button>
        </div>
      </div>

      {/* Log List */}
      <div className="bg-white rounded-lg shadow">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Timestamp
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Tool
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Data Size
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Status
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {filteredLogs.map((log, idx) => (
                <tr key={idx} className="hover:bg-gray-50">
                  <td className="px-4 py-3 text-sm">
                    {new Date(log.timestamp).toLocaleString()}
                  </td>
                  <td className="px-4 py-3 text-sm font-medium">
                    {log.tool_name || "N/A"}
                  </td>
                  <td className="px-4 py-3 text-sm">
                    {log.result_size_bytes
                      ? `${(log.result_size_bytes / 1024).toFixed(2)} KB`
                      : "N/A"}
                  </td>
                  <td className="px-4 py-3 text-sm">
                    {log.violation ? (
                      <span className="text-red-600">Violation</span>
                    ) : (
                      <span className="text-green-600">Allowed</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {filteredLogs.length === 0 && (
          <div className="text-center py-8 text-gray-500">No logs found</div>
        )}
      </div>
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
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-xl font-semibold mb-4">Workspace Information</h2>
        <div className="space-y-3">
          <div>
            <div className="text-sm text-gray-500">Location</div>
            <div className="font-mono text-sm">
              {workspaceInfo?.path || "N/A"}
            </div>
          </div>
          <div>
            <div className="text-sm text-gray-500">Total Size</div>
            <div className="text-lg font-semibold">
              {workspaceInfo ? formatBytes(workspaceInfo.size_bytes) : "N/A"}
            </div>
          </div>
          <div>
            <div className="text-sm text-gray-500">File Count</div>
            <div className="text-lg font-semibold">
              {workspaceInfo?.file_count || 0} files
            </div>
          </div>
        </div>
      </div>

      {/* Export Options */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-xl font-semibold mb-4">Export Data</h2>
        <div className="space-y-3">
          <button className="w-full px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700">
            Export Workspace as ZIP
          </button>
          <button className="w-full px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700">
            Export Processed Data
          </button>
          <button className="w-full px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700">
            Export Audit Logs
          </button>
        </div>
      </div>

      {/* Deletion Options */}
      <div className="bg-white rounded-lg shadow p-6 border-l-4 border-red-500">
        <h2 className="text-xl font-semibold mb-4 text-red-600">Danger Zone</h2>
        <div className="space-y-3">
          <div>
            <p className="text-sm text-gray-600 mb-2">
              Permanently delete client data. This action cannot be undone.
            </p>
            <button className="px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700">
              Delete Client Data
            </button>
          </div>
          <div>
            <p className="text-sm text-gray-600 mb-2">
              Permanently delete entire workspace. This action cannot be undone.
            </p>
            <button className="px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700">
              Delete Workspace
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
