import { create } from "zustand";
import type { Workspace, Client } from "../types";

interface WorkspaceState {
  workspace: Workspace | null;
  currentClient: Client | null;
  setWorkspace: (workspace: Workspace | null) => void;
  setCurrentClient: (client: Client | null) => void;
}

export const useWorkspaceStore = create<WorkspaceState>((set) => ({
  workspace: null,
  currentClient: null,
  setWorkspace: (workspace) => set({ workspace }),
  setCurrentClient: (client) => set({ currentClient: client }),
}));
