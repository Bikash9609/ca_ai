import { useState, useEffect } from "react";
import {
  Modal,
  ModalContent,
  ModalHeader,
  ModalBody,
  ModalFooter,
  Input,
  Button,
  Card,
  CardBody,
} from "@heroui/react";
import { useWorkspace } from "../hooks/useWorkspace";
import type { Client } from "../types";
import { api } from "../services/api";

export default function Clients() {
  const { setCurrentClient, setWorkspace } = useWorkspace();
  const [clients, setClients] = useState<Client[]>([]);
  const [filteredClients, setFilteredClients] = useState<Client[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState("");
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
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-center text-default-500">Loading clients...</div>
      </div>
    );
  }

  return (
    <div className="p-8 max-w-7xl mx-auto">
      <div className="flex justify-between items-center mb-6">
        <div>
          <h1 className="text-3xl font-bold text-foreground mb-2">Clients</h1>
          <p className="text-default-600">Manage your client list</p>
        </div>
        <Button
          color="primary"
          size="lg"
          onPress={() => setShowCreateDialog(true)}
        >
          + Add Client
        </Button>
      </div>

      {/* Create Client Dialog */}
      <Modal
        isOpen={showCreateDialog}
        onClose={() => {
          setShowCreateDialog(false);
          setCreateForm({ name: "", gstin: "" });
        }}
        classNames={{
          base: "border border-default-200",
        }}
      >
        <ModalContent>
          {(onClose) => (
            <>
              <ModalHeader className="flex flex-col gap-1">
                Create New Client
              </ModalHeader>
              <ModalBody>
                <Input
                  label="Client Name"
                  placeholder="Enter client name"
                  value={createForm.name}
                  onChange={(e) =>
                    setCreateForm({ ...createForm, name: e.target.value })
                  }
                  isRequired
                  autoFocus
                />
                <Input
                  label="GSTIN (Optional)"
                  placeholder="Enter GSTIN"
                  value={createForm.gstin}
                  onChange={(e) =>
                    setCreateForm({ ...createForm, gstin: e.target.value })
                  }
                />
              </ModalBody>
              <ModalFooter>
                <Button color="danger" variant="light" onPress={onClose}>
                  Cancel
                </Button>
                <Button
                  color="primary"
                  onPress={handleCreateClient}
                  isLoading={creating}
                  isDisabled={!createForm.name.trim()}
                >
                  {creating ? "Creating..." : "Create"}
                </Button>
              </ModalFooter>
            </>
          )}
        </ModalContent>
      </Modal>

      {/* Search */}
      <div className="mb-6">
        <Input
          type="text"
          placeholder="Search clients by name or GSTIN..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          className="max-w-md"
          classNames={{
            base: "max-w-md",
          }}
        />
      </div>

      {/* Client Grid */}
      {filteredClients.length === 0 ? (
        <Card classNames={{ base: "border border-default-200" }}>
          <CardBody className="p-12 text-center">
            <p className="text-default-500 mb-4 text-lg">
              {searchTerm ? "No clients found" : "No clients yet"}
            </p>
            {!searchTerm && (
              <Button color="primary" onPress={() => setShowCreateDialog(true)}>
                Create Your First Client
              </Button>
            )}
          </CardBody>
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredClients.map((client) => (
            <Card
              key={client.id}
              isPressable
              onPress={() => setCurrentClient(client)}
              classNames={{
                base: "border border-default-200 hover:border-primary transition-colors cursor-pointer",
              }}
            >
              <CardBody className="p-6">
                <h3 className="font-semibold text-lg mb-2 text-foreground">
                  {client.name}
                </h3>
                {client.gstin && (
                  <p className="text-sm text-default-600 mb-3">
                    GSTIN: {client.gstin}
                  </p>
                )}
                <p className="text-xs text-default-400">
                  Created: {new Date(client.createdAt).toLocaleDateString()}
                </p>
              </CardBody>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
