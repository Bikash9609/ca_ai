import { useWorkspace } from "../hooks/useWorkspace";

export default function Dashboard() {
  const { workspace, currentClient } = useWorkspace();

  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold mb-4">Dashboard</h1>
      {workspace ? (
        <div>
          <p>Workspace: {workspace.path}</p>
          <p>Clients: {workspace.clients.length}</p>
        </div>
      ) : (
        <p>No workspace selected</p>
      )}
    </div>
  );
}
