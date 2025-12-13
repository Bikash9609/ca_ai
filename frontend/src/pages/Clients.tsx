import { useState, useEffect } from "react";
import {
  Modal,
  ModalContent,
  ModalHeader,
  ModalBody,
  ModalFooter,
  Input,
  Button,
  Table,
  TableHeader,
  TableColumn,
  TableBody,
  TableRow,
  TableCell,
  Card,
  CardBody,
  Tabs,
  Tab,
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
        <h1 className="text-2xl font-bold text-foreground">Clients</h1>
        <Button color="primary" onPress={() => setShowCreateDialog(true)}>
          Add Client
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

      {/* Search and View Controls */}
      <div className="flex gap-4 mb-6">
        <Input
          type="text"
          placeholder="Search clients..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          className="flex-1"
          classNames={{
            base: "flex-1",
          }}
        />
        <Tabs
          selectedKey={viewMode}
          onSelectionChange={(key) => setViewMode(key as "grid" | "list")}
          classNames={{
            base: "border border-default-200 rounded-lg",
            tabList: "gap-0 p-1",
            tab: "min-w-20",
          }}
        >
          <Tab key="grid" title="Grid" />
          <Tab key="list" title="List" />
        </Tabs>
      </div>

      {filteredClients.length === 0 ? (
        <div className="text-center py-12">
          <p className="text-default-500 mb-4">
            {searchTerm ? "No clients found" : "No clients found"}
          </p>
          {!searchTerm && (
            <Button color="primary" onPress={() => setShowCreateDialog(true)}>
              Create Your First Client
            </Button>
          )}
        </div>
      ) : viewMode === "grid" ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredClients.map((client) => (
            <Card
              key={client.id}
              isPressable
              onPress={() => setCurrentClient(client)}
              classNames={{
                base: "border border-default-200 hover:border-primary",
              }}
            >
              <CardBody>
                <h3 className="font-semibold text-lg mb-2 text-foreground">
                  {client.name}
                </h3>
                {client.gstin && (
                  <p className="text-sm text-default-600 mb-2">
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
      ) : (
        <Card classNames={{ base: "border border-default-200" }}>
          <Table aria-label="Clients table">
            <TableHeader>
              <TableColumn>Name</TableColumn>
              <TableColumn>GSTIN</TableColumn>
              <TableColumn>Created</TableColumn>
              <TableColumn>Actions</TableColumn>
            </TableHeader>
            <TableBody>
              {filteredClients.map((client) => (
                <TableRow
                  key={client.id}
                  className="cursor-pointer"
                  onClick={() => setCurrentClient(client)}
                >
                  <TableCell>{client.name}</TableCell>
                  <TableCell>{client.gstin || "N/A"}</TableCell>
                  <TableCell>
                    {new Date(client.createdAt).toLocaleDateString()}
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
      )}
    </div>
  );
}
