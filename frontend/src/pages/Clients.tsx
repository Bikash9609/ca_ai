import { useState, useEffect } from "react";
import { useWorkspace } from "../hooks/useWorkspace";
import Button from "../components/Button";
import type { Client } from "../types";
import { api } from "../services/api";

export default function Clients() {
  const { setCurrentClient, setWorkspace } = useWorkspace();
  const [clients, setClients] = useState<Client[]>([]);
  const [filteredClients, setFilteredClients] = useState<Client[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState("");
  const [viewMode, setViewMode] = useState<"grid" | "list">("grid");
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [createForm, setCreateForm] = useState({
    name: "",
    gstin: "",
  });
  const [creating, setCreating] = useState(false);

  const loadClients = async () => {
    setLoading(true);
    try {
      const response = await api.workspace.clients.list();
      if (response.data) {
        setClients(response.data);
        setFilteredClients(response.data);
      } else if (response.error) {
        console.error("Failed to load clients:", response.error);
      }
    } catch (error) {
      console.error("Failed to load clients:", error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadClients();
  }, []);

  const handleCreateClient = async () => {
    if (!createForm.name.trim()) {
      alert("Client name is required");
      return;
    }

    setCreating(true);
    try {
      const response = await api.workspace.clients.create({
        name: createForm.name.trim(),
        gstin: createForm.gstin.trim() || undefined,
      });

      if (response.data) {
        setShowCreateDialog(false);
        setCreateForm({ name: "", gstin: "" });
        await loadClients();
        // Refresh workspace data
        const workspaceResponse = await api.workspace.get();
        if (workspaceResponse.data) {
          setWorkspace(workspaceResponse.data);
        }
      } else if (response.error) {
        alert(`Failed to create client: ${response.error}`);
      }
    } catch (error) {
      console.error("Failed to create client:", error);
      alert("Failed to create client");
    } finally {
      setCreating(false);
    }
  };

  useEffect(() => {
    if (searchTerm) {
      const filtered = clients.filter(
        (client) =>
          client.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
          client.gstin?.toLowerCase().includes(searchTerm.toLowerCase())
      );
      setFilteredClients(filtered);
    } else {
      setFilteredClients(clients);
    }
  }, [searchTerm, clients]);

  if (loading) {
    return <div className="p-6">Loading clients...</div>;
  }

  return (
    <div className="p-6">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold">Clients</h1>
        <Button onClick={() => setShowCreateDialog(true)}>Add Client</Button>
      </div>

      {/* Create Client Dialog */}
      {showCreateDialog && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 w-full max-w-md">
            <h2 className="text-xl font-bold mb-4">Create New Client</h2>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Client Name *
                </label>
                <input
                  type="text"
                  value={createForm.name}
                  onChange={(e) =>
                    setCreateForm({ ...createForm, name: e.target.value })
                  }
                  placeholder="Enter client name"
                  className="w-full px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                  autoFocus
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  GSTIN (Optional)
                </label>
                <input
                  type="text"
                  value={createForm.gstin}
                  onChange={(e) =>
                    setCreateForm({ ...createForm, gstin: e.target.value })
                  }
                  placeholder="Enter GSTIN"
                  className="w-full px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
            </div>
            <div className="flex gap-3 mt-6">
              <Button
                onClick={handleCreateClient}
                disabled={creating || !createForm.name.trim()}
                className="flex-1"
              >
                {creating ? "Creating..." : "Create"}
              </Button>
              <Button
                variant="outline"
                onClick={() => {
                  setShowCreateDialog(false);
                  setCreateForm({ name: "", gstin: "" });
                }}
                disabled={creating}
                className="flex-1"
              >
                Cancel
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Search and View Controls */}
      <div className="flex gap-4 mb-6">
        <input
          type="text"
          placeholder="Search clients..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          className="flex-1 px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
        <div className="flex gap-2 border rounded-lg p-1">
          <button
            onClick={() => setViewMode("grid")}
            className={`px-3 py-1 rounded ${
              viewMode === "grid" ? "bg-blue-600 text-white" : "text-gray-600"
            }`}
          >
            Grid
          </button>
          <button
            onClick={() => setViewMode("list")}
            className={`px-3 py-1 rounded ${
              viewMode === "list" ? "bg-blue-600 text-white" : "text-gray-600"
            }`}
          >
            List
          </button>
        </div>
      </div>

      {filteredClients.length === 0 ? (
        <div className="text-center py-12">
          <p className="text-gray-500 mb-4">
            {searchTerm ? "No clients found" : "No clients found"}
          </p>
          {!searchTerm && (
            <Button onClick={() => setShowCreateDialog(true)}>
              Create Your First Client
            </Button>
          )}
        </div>
      ) : viewMode === "grid" ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredClients.map((client) => (
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
      ) : (
        <div className="bg-white rounded-lg shadow overflow-hidden">
          <table className="w-full">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Name
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  GSTIN
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Created
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {filteredClients.map((client) => (
                <tr
                  key={client.id}
                  className="hover:bg-gray-50 cursor-pointer"
                  onClick={() => setCurrentClient(client)}
                >
                  <td className="px-4 py-3 font-medium">{client.name}</td>
                  <td className="px-4 py-3 text-sm text-gray-600">
                    {client.gstin || "N/A"}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-600">
                    {new Date(client.createdAt).toLocaleDateString()}
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
        </div>
      )}
    </div>
  );
}
