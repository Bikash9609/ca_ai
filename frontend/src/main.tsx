import React from "react";
import ReactDOM from "react-dom/client";
import { HeroUIProvider } from "@heroui/react";
import { BrowserRouter, useNavigate, useHref } from "react-router-dom";
import App from "./App";
import "./App.css";

function AppWithRouter() {
  const navigate = useNavigate();
  const href = useHref;

  return (
    <HeroUIProvider navigate={navigate} useHref={href}>
      <App />
    </HeroUIProvider>
  );
}

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <BrowserRouter>
      <AppWithRouter />
    </BrowserRouter>
  </React.StrictMode>
);
