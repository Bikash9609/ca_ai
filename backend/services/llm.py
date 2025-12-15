"""
LLM Service - Unified multi-provider LLM integration with context firewall using LiteLLM
"""

import os
# Disable model source connectivity check for Google Generative AI
# Must be set before importing google.genai to prevent connectivity checks
os.environ["DISABLE_MODEL_SOURCE_CHECK"] = "True"

import json
import logging
from typing import Dict, Any, List, Optional, AsyncGenerator
from enum import Enum

try:
    import litellm
    LITELLM_AVAILABLE = True
except ImportError:
    LITELLM_AVAILABLE = False
    litellm = None

from core.firewall import ContextFirewall
from core.tools import ToolExecutor
from core.privacy import AuditLogger
from services.context_packer import ContextPacker
from services.qa_tracking import QATracker
from services.conversation import get_conversation_manager
from database.connection import DatabaseManager

logger = logging.getLogger(__name__)


class LLMProvider(Enum):
    """Supported LLM providers"""
    CLAUDE = "claude"
    OLLAMA = "ollama"
    GEMINI = "gemini"
    GROQ = "groq"
    OPENROUTER = "openrouter"
    NONE = "none"


class LLMService:
    """Main LLM service with context firewall integration using LiteLLM"""
    
    def __init__(
        self,
        firewall: ContextFirewall,
        tool_executor: ToolExecutor,
        audit_logger: Optional[AuditLogger] = None,
        api_key: Optional[str] = None,
        provider: LLMProvider = LLMProvider.CLAUDE,
        db_manager: Optional[DatabaseManager] = None,
        client_id: Optional[str] = None
    ):
        """
        Initialize LLM service
        
        Args:
            firewall: Context firewall instance
            tool_executor: Tool executor instance
            audit_logger: Optional audit logger
            api_key: API key (provider-specific, or from env)
            provider: LLM provider to use
            db_manager: Database manager for Q&A tracking
            client_id: Client ID for Q&A tracking
        """
        if not LITELLM_AVAILABLE:
            raise ImportError("litellm is required. Install with: uv pip install litellm")
        
        self.firewall = firewall
        self.tool_executor = tool_executor
        self.audit_logger = audit_logger
        self.provider = provider
        self.client_id = client_id
        
        # Get provider-specific API key and model name
        self.api_key = api_key or self._get_api_key_for_provider()
        self.model_name = self._get_litellm_model_name()
        self.ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434") if provider == LLMProvider.OLLAMA else None
        
        # Conversation history
        self.conversation_history: List[Dict[str, Any]] = []
        
        # Context packer and Q&A tracking
        self.context_packer = ContextPacker()
        self.qa_tracker = QATracker(db_manager) if db_manager else None
        self.conversation_manager = get_conversation_manager()
        
        # Store last search chunks for context packing
        self._last_search_chunks: List[Dict[str, Any]] = []
        self._last_question: Optional[str] = None
        
        # System prompt
        self.system_prompt = self._build_system_prompt()
    
    def _get_api_key_for_provider(self) -> Optional[str]:
        """Get API key for the current provider from environment"""
        if self.provider == LLMProvider.CLAUDE:
            return os.getenv("ANTHROPIC_API_KEY")
        elif self.provider == LLMProvider.GEMINI:
            return os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        elif self.provider == LLMProvider.GROQ:
            return os.getenv("GROQ_API_KEY")
        elif self.provider == LLMProvider.OPENROUTER:
            return os.getenv("OPENROUTER_API_KEY")
        elif self.provider == LLMProvider.OLLAMA:
            return None  # Ollama doesn't need API key
        return None
    
    def _get_litellm_model_name(self) -> str:
        """Map provider to LiteLLM model name"""
        if self.provider == LLMProvider.CLAUDE:
            return os.getenv("CLAUDE_MODEL", "claude-3-5-sonnet-20241022")
        elif self.provider == LLMProvider.GEMINI:
            model = os.getenv("GEMINI_MODEL", "gemini-1.5-flash-002")
            # Normalize older aliases to supported Vertex names
            if model == "gemini-1.5-flash":
                model = "gemini-1.5-flash-002"
            return f"gemini/{model}"
        elif self.provider == LLMProvider.GROQ:
            model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
            return f"groq/{model}"
        elif self.provider == LLMProvider.OPENROUTER:
            model = os.getenv("OPENROUTER_MODEL", "openai/gpt-4o")
            return f"openrouter/{model}"
        elif self.provider == LLMProvider.OLLAMA:
            model = os.getenv("OLLAMA_MODEL", "llama2")
            return f"ollama/{model}"
        else:
            return "gpt-3.5-turbo"  # Default fallback
    
    def _build_system_prompt(self) -> str:
        """Build system prompt for CA assistant with safety measures"""
        return """You are a CA's AI assistant for GST and TDS compliance and financial analysis.

CORE PROTOCOL:
1. MANDATORY: Use ONLY the provided context. Never assume facts not in context.
2. ADVISORY ONLY: This is assistance, not professional advice. CA must approve all actions.
3. UNCERTAINTY: If information is missing or unclear, state that explicitly.
4. SOURCE CITATION: Reference page numbers and document types when possible.
5. NO AUTO-DECISIONS: Never auto-file or auto-decide — always require CA approval.

WHEN ANSWERING:
- Cite page numbers: "Based on AWS invoices on pages 3–5..."
- Mention uncertainty: "PAN not found in uploaded docs — please confirm"
- Reference sources: "See chunk from document XYZ, page 3"
- Highlight assumptions: "Assuming this refers to FY 2024-25 based on context"

TOOLS (GST):
- search_documents(query, doc_type, period) -> Returns relevant chunks with page references
- get_invoice(invoice_number, vendor_name)
- get_summary(summary_type, period, category) -> PRIMARY for GST calc
- get_reconciliation(source1, source2, period)
- search_gst_rules(query, category, limit)
- explain_rule(rule_type, scenario)

TOOLS (TDS):
- get_tds_certificate(certificate_number, deductor_name, period, form_type)
- get_tds_summary(summary_type, period, section, deductee_pan) -> PRIMARY for TDS calc
- get_tds_reconciliation(source1, source2, period, form_type)
- search_tds_rules(query, section, category, limit)
- explain_tds_rule(section, scenario)
- get_tds_return_status(return_type, period, quarter)

CONTEXT (INDIAN GST):
- ITC requires GSTR-1 filing (Rule 36(4) blocks ITC if missing from GSTR-2B).
- Sec 17(5) defines blocked credits.
- Deadlines: GSTR-1 (11th), GSTR-3B (20th).

CONTEXT (INDIAN TDS):
- Common sections: 194A (Interest), 194C (Contractors), 194H (Commission), 194I (Rent), 194J (Professional fees), 194LA (Immovable property).
- TDS deposit deadline: 7th of next month.
- TDS return filing: 24Q (Salary), 26Q (Non-Salary), 27Q (NRI), 27EQ (TCS).
- Certificate deadlines: Form 16 (15th May), Form 16A (15 days from request).
- Rates vary by section and threshold amounts.

EXAMPLE FLOWS:
GST: User: "Why is ITC blocked?"
     Action: Call `get_summary("itc_summary", ...)`
     Result: See Rule 36(4) flag.
     Reply: "Blocked due to vendor non-filing (Rule 36(4)). See page 12 of GSTR-2B document."

TDS: User: "What is TDS deducted under section 194A for Q1 2024?"
     Action: Call `get_tds_summary(summary_type="section_wise", period="2024-Q1", section="194A")`
     Result: Returns aggregated TDS data.
     Reply: "Total TDS deducted under section 194A for Q1 2024 is ₹X from Y certificates. See Form 16A documents, pages 3-5."
"""
    
    def _get_tool_definitions(self) -> List[Dict[str, Any]]:
        """Get tool definitions in OpenAI format (LiteLLM standard)"""
        return [
            {
                "type": "function",
                "function": {
                    "name": "search_documents",
                    "description": "Search documents using semantic and keyword search",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Search query"
                            },
                            "doc_type": {
                                "type": "string",
                                "description": "Document type filter (optional)"
                            },
                            "period": {
                                "type": "string",
                                "description": "Period filter (optional, format: YYYY-MM)"
                            },
                            "limit": {
                                "type": "integer",
                                "description": "Maximum number of results",
                                "default": 20
                            }
                        },
                        "required": ["query"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_invoice",
                    "description": "Get structured invoice data by invoice number or vendor",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "invoice_number": {
                                "type": "string",
                                "description": "Invoice number (optional)"
                            },
                            "vendor_name": {
                                "type": "string",
                                "description": "Vendor name (optional)"
                            }
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_summary",
                    "description": "Get aggregated summary statistics",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "summary_type": {
                                "type": "string",
                                "enum": ["sales_total", "purchase_total", "gst_liability", "itc_summary", "vendor_count"],
                                "description": "Type of summary to retrieve"
                            },
                            "period": {
                                "type": "string",
                                "description": "Period (format: YYYY-MM)"
                            },
                            "category": {
                                "type": "string",
                                "description": "Category filter (optional)"
                            }
                        },
                        "required": ["summary_type"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_reconciliation",
                    "description": "Get reconciliation data between two sources",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "source1": {
                                "type": "string",
                                "description": "First source (e.g., 'books', 'gstr2b')"
                            },
                            "source2": {
                                "type": "string",
                                "description": "Second source (e.g., 'gstr2b', 'bank_statements')"
                            },
                            "period": {
                                "type": "string",
                                "description": "Period (format: YYYY-MM)"
                            }
                        },
                        "required": ["source1", "source2"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "search_gst_rules",
                    "description": "Search GST rules from rules database",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Search query"
                            },
                            "category": {
                                "type": "string",
                                "description": "Rule category filter (optional)"
                            },
                            "limit": {
                                "type": "integer",
                                "description": "Maximum number of results",
                                "default": 10
                            }
                        },
                        "required": ["query"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "explain_rule",
                    "description": "Explain a specific GST rule",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "rule_type": {
                                "type": "string",
                                "description": "Rule ID (e.g., 'itc_36_4', 'itc_42')"
                            },
                            "scenario": {
                                "type": "string",
                                "description": "Optional scenario description"
                            }
                        },
                        "required": ["rule_type"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_tds_certificate",
                    "description": "Get structured TDS certificate data (Form 16, 16A, 16B, 16C)",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "certificate_number": {
                                "type": "string",
                                "description": "TDS certificate number (optional)"
                            },
                            "deductor_name": {
                                "type": "string",
                                "description": "Deductor name (optional)"
                            },
                            "period": {
                                "type": "string",
                                "description": "Period filter (optional, format: YYYY-MM)"
                            },
                            "form_type": {
                                "type": "string",
                                "enum": ["16", "16A", "16B", "16C"],
                                "description": "Form type (16, 16A, 16B, 16C)"
                            }
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_tds_summary",
                    "description": "Get aggregated TDS summary statistics - PRIMARY tool for TDS calculations",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "summary_type": {
                                "type": "string",
                                "enum": ["deducted_total", "deposited_total", "certificate_count", "return_status", "section_wise"],
                                "description": "Type of TDS summary to retrieve"
                            },
                            "period": {
                                "type": "string",
                                "description": "Period filter (optional, format: YYYY-MM or YYYY-Q1/Q2/Q3/Q4)"
                            },
                            "section": {
                                "type": "string",
                                "description": "TDS section filter (optional, e.g., '194A', '194C')"
                            },
                            "deductee_pan": {
                                "type": "string",
                                "description": "Deductee PAN filter (optional)"
                            }
                        },
                        "required": ["summary_type"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_tds_reconciliation",
                    "description": "Reconcile TDS data between two sources (certificates vs returns, returns vs challans, books vs certificates)",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "source1": {
                                "type": "string",
                                "description": "First source (e.g., 'certificates', 'returns', 'books')"
                            },
                            "source2": {
                                "type": "string",
                                "description": "Second source (e.g., 'returns', 'challans', 'books')"
                            },
                            "period": {
                                "type": "string",
                                "description": "Period filter (optional, format: YYYY-MM)"
                            },
                            "form_type": {
                                "type": "string",
                                "description": "Form type filter (optional, e.g., '16', '16A', '24Q', '26Q')"
                            }
                        },
                        "required": ["source1", "source2"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "search_tds_rules",
                    "description": "Search TDS rules from rules database",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Search query"
                            },
                            "section": {
                                "type": "string",
                                "description": "TDS section filter (optional, e.g., '194A', '194C')"
                            },
                            "category": {
                                "type": "string",
                                "description": "Rule category filter (optional: 'deduction', 'deposit', 'return', 'compliance')"
                            },
                            "limit": {
                                "type": "integer",
                                "description": "Maximum number of results",
                                "default": 10
                            }
                        },
                        "required": ["query"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "explain_tds_rule",
                    "description": "Explain a specific TDS section and its applicability",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "section": {
                                "type": "string",
                                "description": "TDS section (e.g., '194A', '194C', '194H', '194I', '194J')"
                            },
                            "scenario": {
                                "type": "string",
                                "description": "Optional scenario description"
                            }
                        },
                        "required": ["section"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_tds_return_status",
                    "description": "Get TDS return filing status from locally uploaded documents",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "return_type": {
                                "type": "string",
                                "enum": ["24Q", "26Q", "27Q", "27EQ"],
                                "description": "TDS return type (24Q: Salary, 26Q: Non-Salary, 27Q: NRI, 27EQ: TCS)"
                            },
                            "period": {
                                "type": "string",
                                "description": "Period (format: YYYY-MM)"
                            },
                            "quarter": {
                                "type": "string",
                                "enum": ["Q1", "Q2", "Q3", "Q4"],
                                "description": "Quarter (Q1, Q2, Q3, Q4)"
                            }
                        },
                        "required": ["return_type"]
                    }
                }
            }
        ]
    
    async def process_query(
        self,
        query: str,
        user_id: Optional[str] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Process a user query with tool calling using LiteLLM
        
        Yields:
            {
                "type": "text" | "tool_call" | "tool_result" | "error",
                "content": str | Dict
            }
        """
        # Store question for Q&A tracking
        self._last_question = query
        
        # Add user message to history
        self.conversation_history.append({
            "role": "user",
            "content": query
        })
        
        try:
            # Build messages for LiteLLM
            messages = self._build_messages()
            tools = self._get_tool_definitions()
            
            # Prepare LiteLLM call parameters
            litellm_params = {
                "model": self.model_name,
                "messages": messages,
                "tools": tools,
                "stream": True,
                "temperature": 0.7,
                "max_tokens": 4096,
            }
            
            # Add API key if provided
            if self.api_key:
                litellm_params["api_key"] = self.api_key
            
            # Handle Ollama special case (local URL)
            if self.provider == LLMProvider.OLLAMA:
                litellm_params["api_base"] = self.ollama_url
            
            # Call LiteLLM
            response = await litellm.acompletion(**litellm_params)
            
            # Process streaming response
            current_text = ""
            tool_calls = {}
            
            async for chunk in response:
                if not hasattr(chunk, 'choices') or not chunk.choices:
                    continue
                
                delta = chunk.choices[0].delta
                
                # Handle text content
                if hasattr(delta, 'content') and delta.content:
                    current_text += delta.content
                    yield {
                        "type": "text",
                        "content": delta.content
                    }
                
                # Handle tool calls
                if hasattr(delta, 'tool_calls') and delta.tool_calls:
                    for tool_call_delta in delta.tool_calls:
                        if tool_call_delta.index is not None:
                            idx = tool_call_delta.index
                            
                            # Initialize tool call if needed
                            if idx not in tool_calls:
                                tool_calls[idx] = {
                                    "id": tool_call_delta.id or f"call_{idx}",
                                    "name": "",
                                    "arguments": ""
                                }
                            
                            # Update tool call
                            if hasattr(tool_call_delta, 'function') and tool_call_delta.function:
                                if tool_call_delta.function.name:
                                    tool_calls[idx]["name"] = tool_call_delta.function.name
                                if tool_call_delta.function.arguments:
                                    tool_calls[idx]["arguments"] += tool_call_delta.function.arguments
                
                # Check if finished with tool calls
                if hasattr(chunk.choices[0], 'finish_reason') and chunk.choices[0].finish_reason == "tool_calls":
                    # Execute tool calls
                    for idx in sorted(tool_calls.keys()):
                        tool_call = tool_calls[idx]
                        if not tool_call or not tool_call["name"]:
                            continue
                        
                        try:
                            args = json.loads(tool_call["arguments"]) if tool_call["arguments"] else {}
                        except json.JSONDecodeError:
                            logger.warning(f"Failed to parse tool arguments: {tool_call['arguments']}")
                            args = {}
                        
                        yield {
                            "type": "tool_call",
                            "content": {
                                "tool": tool_call["name"],
                                "input": args
                            }
                        }
                        
                        # Execute through firewall
                        tool_name = tool_call["name"]
                        success, result, error = await self.firewall.process_tool_call(
                            tool_name=tool_name,
                            params=args,
                            execute_func=lambda: self._execute_tool(tool_name, args)
                        )
                        
                        if success:
                            yield {
                                "type": "tool_result",
                                "content": {
                                    "tool": tool_call["name"],
                                    "result": result
                                }
                            }
                            
                            # Add tool call and result to history
                            self.conversation_history.append({
                                "role": "assistant",
                                "content": None,
                                "tool_calls": [{
                                    "id": tool_call["id"],
                                    "type": "function",
                                    "function": {
                                        "name": tool_call["name"],
                                        "arguments": tool_call["arguments"]
                                    }
                                }]
                            })
                            self.conversation_history.append({
                                "role": "tool",
                                "content": str(result),
                                "tool_call_id": tool_call["id"]
                            })
                            
                            # Get follow-up response with tool results
                            follow_up_messages = self._build_messages()
                            follow_up_params = {
                                "model": self.model_name,
                                "messages": follow_up_messages,
                                "tools": tools,
                                "stream": True,
                                "temperature": 0.7,
                                "max_tokens": 4096,
                            }
                            
                            if self.api_key:
                                follow_up_params["api_key"] = self.api_key
                            if self.provider == LLMProvider.OLLAMA:
                                follow_up_params["api_base"] = self.ollama_url
                            
                            follow_up_response = await litellm.acompletion(**follow_up_params)
                            
                            follow_up_text = ""
                            async for follow_up_chunk in follow_up_response:
                                if hasattr(follow_up_chunk, 'choices') and follow_up_chunk.choices:
                                    delta = follow_up_chunk.choices[0].delta
                                    if hasattr(delta, 'content') and delta.content:
                                        follow_up_text += delta.content
                                        yield {
                                            "type": "text",
                                            "content": delta.content
                                        }
                            
                            # Ensure assistant message is recorded even if no further text streamed
                            if follow_up_text:
                                self.conversation_history.append({
                                    "role": "assistant",
                                    "content": follow_up_text
                                })
                            else:
                                yield {
                                    "type": "text",
                                    "content": "No relevant TDS findings were returned from the documents."
                                }
                        else:
                            yield {
                                "type": "error",
                                "content": f"Tool execution failed: {error}"
                            }
            
            # Add final assistant response to history
            if current_text:
                self.conversation_history.append({
                    "role": "assistant",
                    "content": current_text
                })
                
                # Track Q&A if tracker available
                if self.qa_tracker and self.client_id and self._last_search_chunks:
                    chunk_ids = [chunk.get("chunk_id") for chunk in self._last_search_chunks if chunk.get("chunk_id")]
                    if chunk_ids:
                        try:
                            await self.qa_tracker.store_qa(
                                client_id=self.client_id,
                                question=self._last_question or query,
                                answer=current_text,
                                chunk_ids=chunk_ids,
                                model_version=self.model_name
                            )
                        except Exception as e:
                            logger.warning(f"Could not store Q&A: {e}")
                
                # Update conversation context
                if self.client_id and self._last_search_chunks:
                    conv_context = self.conversation_manager.get_context(self.client_id)
                    conv_context.add_question(
                        question=self._last_question or query,
                        context_chunks=self._last_search_chunks,
                        answer=current_text
                    )
        
        except Exception as e:
            logger.error(f"Error processing query: {e}", exc_info=True)
            yield {
                "type": "error",
                "content": f"Error: {str(e)}"
            }
        finally:
            # Clear temporary state
            self._last_question = None
    
    def _build_messages(self) -> List[Dict[str, Any]]:
        """Build messages list from conversation history for LiteLLM"""
        messages = []
        
        # Add system message
        messages.append({
            "role": "system",
            "content": self.system_prompt
        })
        
        # Add conversation history (last 10 messages for context)
        for msg in self.conversation_history[-10:]:
            if msg["role"] == "user":
                messages.append({
                    "role": "user",
                    "content": msg.get("content", "")
                })
            elif msg["role"] == "assistant":
                # Handle assistant messages with or without tool calls
                if msg.get("tool_calls"):
                    # Message with tool calls
                    messages.append({
                        "role": "assistant",
                        "content": msg.get("content"),
                        "tool_calls": msg["tool_calls"]
                    })
                else:
                    # Regular text message
                    content = msg.get("content", "")
                    if isinstance(content, list):
                        # Handle Claude-style content list
                        text_content = ""
                        for item in content:
                            if isinstance(item, dict) and item.get("type") == "text":
                                text_content += item.get("text", "")
                            elif isinstance(item, str):
                                text_content += item
                        messages.append({
                            "role": "assistant",
                            "content": text_content or None
                        })
                    else:
                        messages.append({
                            "role": "assistant",
                            "content": content
                        })
            elif msg["role"] == "tool":
                # Tool result message
                messages.append({
                    "role": "tool",
                    "content": str(msg.get("content", "")),
                    "tool_call_id": msg.get("tool_call_id") or msg.get("tool_use_id", "")
                })
        
        return messages
    
    async def _execute_tool(self, tool_name: str, params: Dict[str, Any]) -> Any:
        """Execute a tool (called through firewall)"""
        if tool_name == "search_documents":
            result = await self.tool_executor.search_documents(
                query=params.get("query", ""),
                doc_type=params.get("doc_type"),
                period=params.get("period"),
                limit=params.get("limit", 20),
                use_multi_pass=True
            )
            # Store chunks for context packing
            self._last_search_chunks = result.get("chunks", [])
            return result
        elif tool_name == "get_invoice":
            return await self.tool_executor.get_invoice(
                invoice_number=params.get("invoice_number"),
                vendor_name=params.get("vendor_name")
            )
        elif tool_name == "get_summary":
            return await self.tool_executor.get_summary(
                summary_type=params.get("summary_type"),
                period=params.get("period"),
                category=params.get("category")
            )
        elif tool_name == "get_reconciliation":
            return await self.tool_executor.get_reconciliation(
                source1=params.get("source1"),
                source2=params.get("source2"),
                period=params.get("period")
            )
        elif tool_name == "search_gst_rules":
            return await self.tool_executor.search_gst_rules(
                query=params.get("query", ""),
                category=params.get("category"),
                limit=params.get("limit", 10)
            )
        elif tool_name == "explain_rule":
            return await self.tool_executor.explain_rule(
                rule_type=params.get("rule_type", ""),
                scenario=params.get("scenario")
            )
        elif tool_name == "get_tds_certificate":
            return await self.tool_executor.get_tds_certificate(
                certificate_number=params.get("certificate_number"),
                deductor_name=params.get("deductor_name"),
                period=params.get("period"),
                form_type=params.get("form_type")
            )
        elif tool_name == "get_tds_summary":
            return await self.tool_executor.get_tds_summary(
                summary_type=params.get("summary_type"),
                period=params.get("period"),
                section=params.get("section"),
                deductee_pan=params.get("deductee_pan")
            )
        elif tool_name == "get_tds_reconciliation":
            return await self.tool_executor.get_tds_reconciliation(
                source1=params.get("source1"),
                source2=params.get("source2"),
                period=params.get("period"),
                form_type=params.get("form_type")
            )
        elif tool_name == "search_tds_rules":
            return await self.tool_executor.search_tds_rules(
                query=params.get("query", ""),
                section=params.get("section"),
                category=params.get("category"),
                limit=params.get("limit", 10)
            )
        elif tool_name == "explain_tds_rule":
            return await self.tool_executor.explain_tds_rule(
                section=params.get("section", ""),
                scenario=params.get("scenario")
            )
        elif tool_name == "get_tds_return_status":
            return await self.tool_executor.get_tds_return_status(
                return_type=params.get("return_type"),
                period=params.get("period"),
                quarter=params.get("quarter")
            )
        else:
            raise ValueError(f"Unknown tool: {tool_name}")
    
    def clear_history(self):
        """Clear conversation history"""
        self.conversation_history = []
    
    def get_history(self) -> List[Dict[str, Any]]:
        """Get conversation history"""
        return self.conversation_history.copy()
    
    def estimate_tokens(self, text: str) -> int:
        """Estimate token count (rough approximation)"""
        # Rough estimate: 1 token ≈ 4 characters
        return len(text) // 4
