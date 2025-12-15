import { useState, useEffect, useRef } from "react";
import {
  Button,
  Spinner,
  Modal,
  ModalContent,
  ModalHeader,
  ModalBody,
  ModalFooter,
  Input,
  Select,
  SelectItem,
} from "@heroui/react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { useWorkspace } from "../hooks/useWorkspace";
import { api } from "../services/api";

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

interface Conversation {
  id: string;
  title: string;
  provider: string;
  created_at: string;
  updated_at: string;
  metadata: Record<string, unknown>;
}

export default function Chat() {
  const { currentClient } = useWorkspace();
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [currentConversationId, setCurrentConversationId] = useState<
    string | null
  >(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [provider, setProvider] = useState<
    "claude" | "ollama" | "gemini" | "groq" | "openrouter"
  >("claude");
  const [apiKey, setApiKey] = useState("");
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  useEffect(() => {
    if (currentClient) {
      loadConversations();
    }
  }, [currentClient]);

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    if (currentConversationId && currentClient) {
      loadConversation(currentConversationId);
    }
  }, [currentConversationId, currentClient]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  const loadConversations = async () => {
    if (!currentClient) return;
    try {
      const response = await api.chat.conversations.list(currentClient.id);
      if (response.data) {
        setConversations(response.data.conversations);
      }
    } catch (error) {
      console.error("Failed to load conversations:", error);
    }
  };

  const loadConversation = async (conversationId: string) => {
    if (!currentClient) return;
    try {
      const response = await api.chat.conversations.get(
        conversationId,
        currentClient.id
      );
      if (response.data) {
        const loadedMessages: Message[] = response.data.messages.map(
          (msg: any) => ({
            id: msg.id,
            role: msg.role as "user" | "assistant" | "system",
            content: msg.content,
            timestamp: new Date(msg.created_at),
            toolCalls: msg.tool_calls || [],
          })
        );
        setMessages(loadedMessages);
      }
    } catch (error) {
      console.error("Failed to load conversation:", error);
    }
  };

  const createNewConversation = async () => {
    if (!currentClient) return;
    try {
      const response = await api.chat.conversations.create({
        client_id: currentClient.id,
        provider: provider,
      });
      if (response.data) {
        setCurrentConversationId(response.data.id);
        setMessages([]);
        await loadConversations();
      }
    } catch (error) {
      console.error("Failed to create conversation:", error);
    }
  };

  const deleteConversation = async (conversationId: string) => {
    if (!currentClient) return;
    try {
      await api.chat.conversations.delete(conversationId, currentClient.id);
      if (currentConversationId === conversationId) {
        setCurrentConversationId(null);
        setMessages([]);
      }
      await loadConversations();
    } catch (error) {
      console.error("Failed to delete conversation:", error);
    }
  };

  const handleSend = async () => {
    if (!input.trim() || !currentClient || loading) return;

    // Create conversation if none exists
    let convId = currentConversationId;
    if (!convId) {
      const createResponse = await api.chat.conversations.create({
        client_id: currentClient.id,
        provider: provider,
      });
      if (createResponse.data) {
        convId = createResponse.data.id;
        setCurrentConversationId(convId);
        await loadConversations();
      } else {
        setError("Failed to create conversation");
        return;
      }
    }

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

      // Save messages to conversation (simplified - in production, save after each message)
      // For now, we'll rely on the backend to maintain state
    } catch (err: any) {
      if (err.name === "AbortError") {
        return;
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

  if (!currentClient) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-center text-default-500">
          <p className="text-lg mb-2">
            Please select a client to start chatting
          </p>
          <p className="text-sm">
            Go to Clients page to create or select a client
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-screen bg-background">
      {/* Conversation History Sidebar */}
      {sidebarOpen && (
        <div className="w-64 border-r border-default-200 bg-default-50 flex flex-col">
          <div className="p-4 border-b border-default-200">
            <Button
              color="primary"
              size="sm"
              className="w-full"
              onPress={createNewConversation}
            >
              + New Chat
            </Button>
          </div>
          <div className="flex-1 overflow-y-auto p-2">
            {conversations.length === 0 ? (
              <div className="text-center text-default-500 text-sm py-8">
                No conversations yet
              </div>
            ) : (
              <div className="space-y-1">
                {conversations.map((conv) => (
                  <div
                    key={conv.id}
                    className={`group relative p-3 rounded-lg cursor-pointer transition-colors ${
                      currentConversationId === conv.id
                        ? "bg-primary text-primary-foreground"
                        : "hover:bg-default-100"
                    }`}
                    onClick={() => setCurrentConversationId(conv.id)}
                  >
                    <div className="font-medium text-sm truncate">
                      {conv.title}
                    </div>
                    <div
                      className={`text-xs mt-1 ${
                        currentConversationId === conv.id
                          ? "opacity-80"
                          : "text-default-500"
                      }`}
                    >
                      {new Date(conv.updated_at).toLocaleDateString()}
                    </div>
                    {currentConversationId === conv.id && (
                      <button
                        className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 text-xs w-6 h-6 rounded hover:bg-white hover:bg-opacity-20 flex items-center justify-center transition-opacity"
                        onClick={(e) => {
                          e.stopPropagation();
                          deleteConversation(conv.id);
                        }}
                      >
                        ×
                      </button>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col">
        {/* Header */}
        <div className="border-b border-default-200 bg-background px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Button
              size="sm"
              variant="light"
              onPress={() => setSidebarOpen(!sidebarOpen)}
            >
              {sidebarOpen ? "←" : "☰"}
            </Button>
            <h1 className="text-lg font-semibold text-foreground">
              {currentClient.name}
            </h1>
          </div>
          <Button
            size="sm"
            variant="light"
            onPress={() => setSettingsOpen(true)}
          >
            Settings
          </Button>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-4 py-6">
          {messages.length === 0 && (
            <div className="flex items-center justify-center h-full">
              <div className="text-center text-default-500 max-w-md">
                <p className="text-lg mb-2">Start a conversation</p>
                <p className="text-sm">
                  Ask questions about your client's documents and GST compliance
                </p>
              </div>
            </div>
          )}
          <div className="max-w-4xl mx-auto space-y-6">
            {messages.map((message) => (
              <MessageBubble key={message.id} message={message} />
            ))}
            {loading && (
              <div className="flex items-center gap-2 text-default-500">
                <Spinner size="sm" color="primary" />
                <span>Thinking...</span>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>
        </div>

        {/* Error Display */}
        {error && (
          <div className="mx-4 mb-2 p-3 bg-danger-50 border border-danger-200 rounded-lg text-danger-700 text-sm">
            {error}
          </div>
        )}

        {/* Input Area */}
        <div className="border-t border-default-200 bg-background p-4">
          <div className="max-w-4xl mx-auto">
            <div className="flex gap-2 items-end">
              <div className="flex-1 relative">
                <textarea
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyPress={handleKeyPress}
                  placeholder="Ask a question..."
                  className="w-full px-4 py-3 pr-12 border border-default-200 rounded-lg resize-none focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent bg-background text-foreground"
                  rows={1}
                  style={{
                    minHeight: "48px",
                    maxHeight: "200px",
                  }}
                  disabled={loading}
                  onInput={(e) => {
                    const target = e.target as HTMLTextAreaElement;
                    target.style.height = "auto";
                    target.style.height = `${Math.min(
                      target.scrollHeight,
                      200
                    )}px`;
                  }}
                />
              </div>
              {loading ? (
                <Button color="danger" onPress={handleCancel} size="lg">
                  Cancel
                </Button>
              ) : (
                <Button
                  color="primary"
                  onPress={handleSend}
                  isDisabled={!input.trim() || loading}
                  size="lg"
                >
                  Send
                </Button>
              )}
            </div>
            <div className="text-xs text-default-500 mt-2 text-center">
              Press Enter to send, Shift+Enter for new line
            </div>
          </div>
        </div>
      </div>

      {/* Settings Modal */}
      <Modal isOpen={settingsOpen} onClose={() => setSettingsOpen(false)}>
        <ModalContent>
          <ModalHeader>Settings</ModalHeader>
          <ModalBody>
            <Select
              label="LLM Provider"
              selectedKeys={[provider]}
              onSelectionChange={(keys) => {
                const selected = Array.from(keys)[0] as string;
                setProvider(selected as typeof provider);
              }}
            >
              <SelectItem key="claude" value="claude">
                Claude
              </SelectItem>
              <SelectItem key="ollama" value="ollama">
                Ollama
              </SelectItem>
              <SelectItem key="gemini" value="gemini">
                Gemini
              </SelectItem>
              <SelectItem key="groq" value="groq">
                Groq
              </SelectItem>
              <SelectItem key="openrouter" value="openrouter">
                OpenRouter
              </SelectItem>
            </Select>
            {provider !== "ollama" && (
              <Input
                type="password"
                label="API Key"
                placeholder={`API Key${
                  provider === "claude" ? " (optional)" : ""
                }`}
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
              />
            )}
          </ModalBody>
          <ModalFooter>
            <Button color="primary" onPress={() => setSettingsOpen(false)}>
              Save
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>
    </div>
  );
}

function MessageBubble({ message }: { message: Message }) {
  const isUser = message.role === "user";

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[85%] rounded-lg px-4 py-3 shadow-sm ${
          isUser
            ? "bg-primary text-primary-foreground"
            : "bg-default-100 text-foreground border border-default-200"
        }`}
      >
        {message.toolCalls && message.toolCalls.length > 0 && (
          <div className="mb-2 space-y-1">
            {message.toolCalls.map((toolCall, idx) => (
              <div
                key={idx}
                className={`text-xs rounded px-2 py-1 ${
                  isUser ? "bg-white bg-opacity-20" : "bg-default-200"
                }`}
              >
                🔧 {toolCall.tool}
              </div>
            ))}
          </div>
        )}
        <div className="prose prose-sm max-w-none dark:prose-invert">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>
            {message.content}
          </ReactMarkdown>
        </div>
        {message.error && (
          <div
            className={`mt-2 text-sm ${
              isUser ? "text-red-200" : "text-danger"
            }`}
          >
            Error: {message.error}
          </div>
        )}
        <div
          className={`text-xs mt-2 ${
            isUser ? "opacity-70" : "text-default-500"
          }`}
        >
          {message.timestamp.toLocaleTimeString()}
        </div>
      </div>
    </div>
  );
}
