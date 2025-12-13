import { useState, useEffect } from "react";
import { useWorkspace } from "../hooks/useWorkspace";

export default function Dashboard() {
  const { workspace, currentClient, fetchWorkspace } = useWorkspace();
  const [stats, setStats] = useState({
    totalClients: 0,
    documentsProcessed: 0,
    timeSaved: 0,
  });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const loadWorkspace = async () => {
      setLoading(true);
      await fetchWorkspace();
      setLoading(false);
    };
    loadWorkspace();
  }, [fetchWorkspace]);

  useEffect(() => {
    if (workspace) {
      setStats({
        totalClients: workspace.clients.length,
        documentsProcessed: 0, // TODO: Fetch from API
        timeSaved: 0, // TODO: Calculate from activity
      });
    }
  }, [workspace]);

  if (loading) {
    return (
      <div className="p-6">
        <div className="text-center">Loading workspace...</div>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-bold">Dashboard</h1>

      {/* Statistics */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-white rounded-lg shadow p-6">
          <div className="text-sm text-gray-500 mb-1">Total Clients</div>
          <div className="text-3xl font-bold">{stats.totalClients}</div>
        </div>
        <div className="bg-white rounded-lg shadow p-6">
          <div className="text-sm text-gray-500 mb-1">Documents Processed</div>
          <div className="text-3xl font-bold">{stats.documentsProcessed}</div>
        </div>
        <div className="bg-white rounded-lg shadow p-6">
          <div className="text-sm text-gray-500 mb-1">Time Saved</div>
          <div className="text-3xl font-bold">{stats.timeSaved} hrs</div>
        </div>
      </div>

      {/* Recent Activity */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Recent Documents */}
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-lg font-semibold mb-4">Recent Documents</h2>
          <div className="space-y-2">
            <div className="text-sm text-gray-500 text-center py-4">
              No recent documents
            </div>
          </div>
        </div>

        {/* Recent Conversations */}
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-lg font-semibold mb-4">Recent Conversations</h2>
          <div className="space-y-2">
            <div className="text-sm text-gray-500 text-center py-4">
              No recent conversations
            </div>
          </div>
        </div>
      </div>

      {/* Quick Actions */}
      {currentClient && (
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-lg font-semibold mb-4">Quick Actions</h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <button className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700">
              Upload Documents
            </button>
            <button className="px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700">
              Start Chat
            </button>
            <button className="px-4 py-2 bg-purple-600 text-white rounded hover:bg-purple-700">
              GST Filing
            </button>
            <button className="px-4 py-2 bg-orange-600 text-white rounded hover:bg-orange-700">
              View Reports
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
