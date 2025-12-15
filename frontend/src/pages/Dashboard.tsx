import { useState, useEffect } from "react";
import { Card, CardBody, Button } from "@heroui/react";
import { useNavigate } from "react-router-dom";
import { useWorkspace } from "../hooks/useWorkspace";

export default function Dashboard() {
  const { workspace, currentClient, fetchWorkspace } = useWorkspace();
  const navigate = useNavigate();
  const [stats, setStats] = useState({
    totalClients: 0,
    documentsProcessed: 0,
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
      });
    }
  }, [workspace]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-center text-default-500">Loading workspace...</div>
      </div>
    );
  }

  return (
    <div className="p-8 max-w-6xl mx-auto">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-foreground mb-2">Dashboard</h1>
        <p className="text-default-600">Welcome to your CA Assistant</p>
      </div>

      {/* Statistics */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
        <Card classNames={{ base: "border border-default-200" }}>
          <CardBody className="p-6">
            <div className="text-sm text-default-500 mb-2">Total Clients</div>
            <div className="text-4xl font-bold text-foreground mb-4">
              {stats.totalClients}
            </div>
            <Button
              color="primary"
              variant="flat"
              size="sm"
              onPress={() => navigate("/clients")}
            >
              Manage Clients
            </Button>
          </CardBody>
        </Card>
        <Card classNames={{ base: "border border-default-200" }}>
          <CardBody className="p-6">
            <div className="text-sm text-default-500 mb-2">
              Documents Processed
            </div>
            <div className="text-4xl font-bold text-foreground mb-4">
              {stats.documentsProcessed}
            </div>
            <Button
              color="primary"
              variant="flat"
              size="sm"
              onPress={() => navigate("/documents")}
            >
              View Documents
            </Button>
          </CardBody>
        </Card>
      </div>

      {/* Quick Actions */}
      {currentClient ? (
        <Card classNames={{ base: "border border-default-200" }}>
          <CardBody className="p-6">
            <h2 className="text-xl font-semibold text-foreground mb-4">
              Quick Actions for {currentClient.name}
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <Button
                color="primary"
                className="w-full"
                onPress={() => navigate("/documents")}
              >
                Upload Documents
              </Button>
              <Button
                color="primary"
                variant="flat"
                className="w-full"
                onPress={() => navigate("/chat")}
              >
                Start Chat
              </Button>
              <Button
                color="primary"
                variant="flat"
                className="w-full"
                onPress={() => navigate("/clients")}
              >
                Switch Client
              </Button>
            </div>
          </CardBody>
        </Card>
      ) : (
        <Card classNames={{ base: "border border-default-200" }}>
          <CardBody className="p-6 text-center">
            <h2 className="text-xl font-semibold text-foreground mb-4">
              Get Started
            </h2>
            <p className="text-default-600 mb-6">
              Create your first client to start managing documents and chatting
            </p>
            <Button
              color="primary"
              size="lg"
              onPress={() => navigate("/clients")}
            >
              Create Client
            </Button>
          </CardBody>
        </Card>
      )}
    </div>
  );
}
