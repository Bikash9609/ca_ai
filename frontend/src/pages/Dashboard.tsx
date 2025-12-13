import { useState, useEffect } from "react";
import { Card, CardBody, CardHeader, Button } from "@heroui/react";
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
      <h1 className="text-2xl font-bold text-foreground">Dashboard</h1>

      {/* Statistics */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card classNames={{ base: "border border-default-200" }}>
          <CardBody>
            <div className="text-sm text-default-500 mb-1">Total Clients</div>
            <div className="text-3xl font-bold text-foreground">
              {stats.totalClients}
            </div>
          </CardBody>
        </Card>
        <Card classNames={{ base: "border border-default-200" }}>
          <CardBody>
            <div className="text-sm text-default-500 mb-1">
              Documents Processed
            </div>
            <div className="text-3xl font-bold text-foreground">
              {stats.documentsProcessed}
            </div>
          </CardBody>
        </Card>
        <Card classNames={{ base: "border border-default-200" }}>
          <CardBody>
            <div className="text-sm text-default-500 mb-1">Time Saved</div>
            <div className="text-3xl font-bold text-foreground">
              {stats.timeSaved} hrs
            </div>
          </CardBody>
        </Card>
      </div>

      {/* Recent Activity */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Recent Documents */}
        <Card classNames={{ base: "border border-default-200" }}>
          <CardHeader>
            <h2 className="text-lg font-semibold text-foreground">
              Recent Documents
            </h2>
          </CardHeader>
          <CardBody>
            <div className="text-sm text-default-500 text-center py-4">
              No recent documents
            </div>
          </CardBody>
        </Card>

        {/* Recent Conversations */}
        <Card classNames={{ base: "border border-default-200" }}>
          <CardHeader>
            <h2 className="text-lg font-semibold text-foreground">
              Recent Conversations
            </h2>
          </CardHeader>
          <CardBody>
            <div className="text-sm text-default-500 text-center py-4">
              No recent conversations
            </div>
          </CardBody>
        </Card>
      </div>

      {/* Quick Actions */}
      {currentClient && (
        <Card classNames={{ base: "border border-default-200" }}>
          <CardHeader>
            <h2 className="text-lg font-semibold text-foreground">
              Quick Actions
            </h2>
          </CardHeader>
          <CardBody>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <Button color="primary" className="w-full">
                Upload Documents
              </Button>
              <Button color="success" className="w-full">
                Start Chat
              </Button>
              <Button color="secondary" className="w-full">
                GST Filing
              </Button>
              <Button color="warning" className="w-full">
                View Reports
              </Button>
            </div>
          </CardBody>
        </Card>
      )}
    </div>
  );
}
