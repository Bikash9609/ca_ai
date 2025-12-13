import { useState, useEffect, useRef } from "react";
import { useWorkspace } from "../hooks/useWorkspace";

interface Message {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  timestamp: Date;
  toolCalls?: Array<{
    tool: string;
    input: any;
    result?: any;
  }>;
  error?: string;
}

export default function Chat() {
  const { currentClient } = useWorkspace();
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [provider, setProvider] = useState<
    "claude" | "ollama" | "gemini" | "groq" | "openrouter"
  >("claude");
  const [apiKey, setApiKey] = useState("");
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  const handleSend = async () => {
    if (!input.trim() || !currentClient || loading) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      role: "user",
      content: input,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setLoading(true);
    setError(null);

    // Create abort controller for cancellation
    abortControllerRef.current = new AbortController();

    try {
      const response = await fetch("http://localhost:8000/api/chat/stream", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          query: input,
          client_id: currentClient.id,
          provider: provider,
          api_key: apiKey || undefined,
        }),
        signal: abortControllerRef.current.signal,
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();

      let assistantMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: "assistant",
        content: "",
        timestamp: new Date(),
        toolCalls: [],
      };

      setMessages((prev) => [...prev, assistantMessage]);

      let buffer = "";
      let currentToolCall: any = null;

      while (true) {
        const { done, value } = await reader!.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (line.startsWith("data: ")) {
            const data = line.slice(6);
            if (data === "[DONE]") continue;

            try {
              const chunk = JSON.parse(data);

              if (chunk.type === "text") {
                setMessages((prev) => {
                  const updated = [...prev];
                  const lastMsg = updated[updated.length - 1];
                  if (lastMsg.role === "assistant") {
                    lastMsg.content += chunk.content;
                  }
                  return updated;
                });
              } else if (chunk.type === "tool_call") {
                currentToolCall = {
                  tool: chunk.content.tool,
                  input: chunk.content.input,
                };
                setMessages((prev) => {
                  const updated = [...prev];
                  const lastMsg = updated[updated.length - 1];
                  if (lastMsg.role === "assistant") {
                    if (!lastMsg.toolCalls) lastMsg.toolCalls = [];
                    lastMsg.toolCalls.push(currentToolCall);
                  }
                  return updated;
                });
              } else if (chunk.type === "tool_result") {
                if (currentToolCall) {
                  currentToolCall.result = chunk.content.result;
                  setMessages((prev) => {
                    const updated = [...prev];
                    return updated;
                  });
                }
              } else if (chunk.type === "error") {
                setError(chunk.content);
                setMessages((prev) => {
                  const updated = [...prev];
                  const lastMsg = updated[updated.length - 1];
                  if (lastMsg.role === "assistant") {
                    lastMsg.error = chunk.content;
                  }
                  return updated;
                });
              }
            } catch (e) {
              // Skip invalid JSON
            }
          }
        }
      }
    } catch (err: any) {
      if (err.name === "AbortError") {
        return; // User cancelled
      }
      setError(err.message || "Failed to send message");
      setMessages((prev) => {
        const updated = [...prev];
        const lastMsg = updated[updated.length - 1];
        if (lastMsg.role === "assistant") {
          lastMsg.error = err.message || "Failed to send message";
        }
        return updated;
      });
    } finally {
      setLoading(false);
      abortControllerRef.current = null;
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleCancel = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      setLoading(false);
    }
  };

  const clearHistory = async () => {
    if (!currentClient) return;
    try {
      await fetch("http://localhost:8000/api/chat/history/clear", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          client_id: currentClient.id,
          provider: provider,
        }),
      });
      setMessages([]);
    } catch (err) {
      console.error("Failed to clear history:", err);
    }
  };

  const exportConversation = () => {
    const data = {
      messages: messages,
      exported_at: new Date().toISOString(),
    };
    const blob = new Blob([JSON.stringify(data, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `conversation_${new Date().toISOString().split("T")[0]}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  if (!currentClient) {
    return (
      <div className="p-6">
        <div className="text-center text-gray-500">
          Please select a client to start chatting
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-screen">
      {/* Header */}
      <div className="border-b bg-white p-4">
        <div className="flex items-center justify-between">
          <h1 className="text-xl font-semibold">Chat Assistant</h1>
          <div className="flex items-center gap-4">
            <select
              value={provider}
              onChange={(e) =>
                setProvider(
                  e.target.value as
                    | "claude"
                    | "ollama"
                    | "gemini"
                    | "groq"
                    | "openrouter"
                )
              }
              className="px-3 py-1 border rounded"
            >
              <option value="claude">Claude</option>
              <option value="ollama">Ollama</option>
              <option value="gemini">Gemini</option>
              <option value="groq">Groq</option>
              <option value="openrouter">OpenRouter</option>
            </select>
            {provider !== "ollama" && (
              <input
                type="password"
                placeholder={`API Key${
                  provider === "claude" ? " (optional)" : ""
                }`}
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                className="px-3 py-1 border rounded w-48"
              />
            )}
            <button
              onClick={clearHistory}
              className="px-3 py-1 text-sm border rounded hover:bg-gray-50"
            >
              Clear
            </button>
            <button
              onClick={exportConversation}
              className="px-3 py-1 text-sm border rounded hover:bg-gray-50"
            >
              Export
            </button>
          </div>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 && (
          <div className="text-center text-gray-500 mt-8">
            Start a conversation by asking a question about GST compliance
          </div>
        )}
        {messages.map((message) => (
          <MessageBubble key={message.id} message={message} />
        ))}
        {loading && (
          <div className="flex items-center gap-2 text-gray-500">
            <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-blue-600"></div>
            <span>Thinking...</span>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Error Display */}
      {error && (
        <div className="bg-red-50 border-l-4 border-red-500 p-4 mx-4 mb-2">
          <div className="flex items-center justify-between">
            <div className="text-red-700">{error}</div>
            <button
              onClick={() => setError(null)}
              className="text-red-500 hover:text-red-700"
            >
              ×
            </button>
          </div>
        </div>
      )}

      {/* Input Area */}
      <div className="border-t bg-white p-4">
        <div className="flex gap-2">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder="Ask a question about GST compliance..."
            className="flex-1 px-4 py-2 border rounded-lg resize-none focus:outline-none focus:ring-2 focus:ring-blue-500"
            rows={3}
            disabled={loading}
          />
          <div className="flex flex-col gap-2">
            {loading ? (
              <button
                onClick={handleCancel}
                className="px-6 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700"
              >
                Cancel
              </button>
            ) : (
              <button
                onClick={handleSend}
                disabled={!input.trim() || loading}
                className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Send
              </button>
            )}
          </div>
        </div>
        <div className="text-xs text-gray-500 mt-2">
          Press Enter to send, Shift+Enter for new line
        </div>
      </div>
    </div>
  );
}

function MessageBubble({ message }: { message: Message }) {
  const isUser = message.role === "user";

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-3xl rounded-lg p-4 ${
          isUser ? "bg-blue-600 text-white" : "bg-gray-100 text-gray-900"
        }`}
      >
        {message.toolCalls && message.toolCalls.length > 0 && (
          <div className="mb-2 space-y-1">
            {message.toolCalls.map((toolCall, idx) => (
              <div
                key={idx}
                className="text-xs bg-white bg-opacity-20 rounded px-2 py-1"
              >
                🔧 {toolCall.tool}
              </div>
            ))}
          </div>
        )}
        <div className="whitespace-pre-wrap">
          <MarkdownRenderer content={message.content} />
        </div>
        {message.error && (
          <div className="mt-2 text-red-300 text-sm">
            Error: {message.error}
          </div>
        )}
        <div className="text-xs opacity-70 mt-2">
          {message.timestamp.toLocaleTimeString()}
        </div>
      </div>
    </div>
  );
}

function MarkdownRenderer({ content }: { content: string }) {
  // Simple markdown rendering (can be enhanced with react-markdown)
  const lines = content.split("\n");
  const elements: JSX.Element[] = [];
  let inCodeBlock = false;
  let codeBlockContent: string[] = [];

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];

    if (line.startsWith("```")) {
      if (inCodeBlock) {
        // End code block
        elements.push(
          <pre
            key={i}
            className="bg-gray-800 text-gray-100 p-2 rounded my-2 overflow-x-auto"
          >
            <code>{codeBlockContent.join("\n")}</code>
          </pre>
        );
        codeBlockContent = [];
        inCodeBlock = false;
      } else {
        // Start code block
        inCodeBlock = true;
      }
      continue;
    }

    if (inCodeBlock) {
      codeBlockContent.push(line);
      continue;
    }

    // Headers
    if (line.startsWith("# ")) {
      elements.push(
        <h1 key={i} className="text-2xl font-bold my-2">
          {line.slice(2)}
        </h1>
      );
    } else if (line.startsWith("## ")) {
      elements.push(
        <h2 key={i} className="text-xl font-semibold my-2">
          {line.slice(3)}
        </h2>
      );
    } else if (line.startsWith("### ")) {
      elements.push(
        <h3 key={i} className="text-lg font-medium my-1">
          {line.slice(4)}
        </h3>
      );
    } else if (line.trim() === "") {
      elements.push(<br key={i} />);
    } else {
      // Regular text with basic formatting
      const formatted = line
        .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
        .replace(/\*(.+?)\*/g, "<em>$1</em>")
        .replace(
          /`(.+?)`/g,
          "<code class='bg-gray-200 px-1 rounded'>$1</code>"
        );
      elements.push(
        <p
          key={i}
          className="my-1"
          dangerouslySetInnerHTML={{ __html: formatted }}
        />
      );
    }
  }

  if (inCodeBlock && codeBlockContent.length > 0) {
    elements.push(
      <pre
        key="final-code"
        className="bg-gray-800 text-gray-100 p-2 rounded my-2 overflow-x-auto"
      >
        <code>{codeBlockContent.join("\n")}</code>
      </pre>
    );
  }

  return <div>{elements}</div>;
}
