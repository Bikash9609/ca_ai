import { useWorkspaceStore } from "../store/workspace";

export function useWorkspace() {
  const { workspace, currentClient, setWorkspace, setCurrentClient } =
    useWorkspaceStore();

  return {
    workspace,
    currentClient,
    setWorkspace,
    setCurrentClient,
  };
}
