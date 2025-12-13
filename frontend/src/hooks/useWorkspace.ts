import { useCallback } from "react";
import { useWorkspaceStore } from "../store/workspace";
import { api } from "../services/api";

export function useWorkspace() {
  const { workspace, currentClient, setWorkspace, setCurrentClient } =
    useWorkspaceStore();

  const fetchWorkspace = useCallback(async () => {
    try {
      const response = await api.workspace.get();
      if (response.data) {
        setWorkspace(response.data);
      } else if (response.error) {
        console.error("Failed to fetch workspace:", response.error);
      }
    } catch (error) {
      console.error("Failed to fetch workspace:", error);
    }
  }, [setWorkspace]);

  return {
    workspace,
    currentClient,
    setWorkspace,
    setCurrentClient,
    fetchWorkspace,
  };
}
