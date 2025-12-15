import { Link, useLocation } from "react-router-dom";
import { useWorkspace } from "../hooks/useWorkspace";

export default function Navigation() {
  const location = useLocation();
  const { currentClient } = useWorkspace();

  const navItems = [
    { path: "/", label: "Dashboard" },
    { path: "/clients", label: "Clients" },
    { path: "/documents", label: "Documents" },
    { path: "/chat", label: "Chat" },
  ];

  return (
    <nav className="w-56 bg-background border-r border-default-200 h-screen fixed left-0 top-0 flex flex-col">
      <div className="p-4 border-b border-default-200">
        <h1 className="text-xl font-bold text-foreground">CA AI</h1>
      </div>

      <div className="flex-1 overflow-y-auto p-2">
        <ul className="space-y-1">
          {navItems.map((item) => (
            <li key={item.path}>
              <Link
                to={item.path}
                className={`flex items-center gap-3 px-3 py-2 rounded-lg transition-colors ${
                  location.pathname === item.path
                    ? "bg-primary text-primary-foreground font-medium"
                    : "text-foreground hover:bg-default-100"
                }`}
              >
                <span>{item.label}</span>
              </Link>
            </li>
          ))}
        </ul>
      </div>

      {currentClient && (
        <div className="p-4 border-t border-default-200">
          <div className="text-xs text-default-500 mb-1">Current Client</div>
          <div className="font-medium text-sm text-foreground truncate">
            {currentClient.name}
          </div>
        </div>
      )}
    </nav>
  );
}
