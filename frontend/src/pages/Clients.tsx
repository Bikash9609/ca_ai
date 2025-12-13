import { useState, useEffect } from "react";
import { useWorkspace } from "../hooks/useWorkspace";
import Button from "../components/Button";
import type { Client } from "../types";

export default function Clients() {
  const { workspace, setCurrentClient } = useWorkspace();
  const [clients, setClients] = useState<Client[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // TODO: Fetch clients from API
    // For now, use clients from workspace store
    if (workspace) {
      setClients(workspace.clients);
    }
    setLoading(false);
  }, [workspace]);

  if (loading) {
    return <div className="p-6">Loading clients...</div>;
  }

  return (
    <div className="p-6">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold">Clients</h1>
        <Button>Add Client</Button>
      </div>

      {clients.length === 0 ? (
        <div className="text-center py-12">
          <p className="text-gray-500 mb-4">No clients found</p>
          <Button>Create Your First Client</Button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {clients.map((client) => (
            <div
              key={client.id}
              className="border rounded-lg p-4 hover:shadow-md transition-shadow cursor-pointer"
              onClick={() => setCurrentClient(client)}
            >
              <h3 className="font-semibold text-lg mb-2">{client.name}</h3>
              {client.gstin && (
                <p className="text-sm text-gray-600 mb-2">
                  GSTIN: {client.gstin}
                </p>
              )}
              <p className="text-xs text-gray-400">
                Created: {new Date(client.createdAt).toLocaleDateString()}
              </p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
