"""
LLM Service - Claude API integration with context firewall
"""

import os
# Disable model source connectivity check for Google Generative AI
# Must be set before importing google.genai to prevent connectivity checks
os.environ["DISABLE_MODEL_SOURCE_CHECK"] = "True"

import json
import logging
import asyncio
from typing import Dict, Any, List, Optional, AsyncGenerator
from enum import Enum

try:
    from anthropic import Anthropic, AsyncAnthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False
    AsyncAnthropic = None

try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False

try:
    from google import genai as google_genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    google_genai = None

try:
    from groq import AsyncGroq
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False
    AsyncGroq = None

try:
    from openai import AsyncOpenAI
    OPENROUTER_AVAILABLE = True
except ImportError:
    OPENROUTER_AVAILABLE = False
    AsyncOpenAI = None

from core.firewall import ContextFirewall
from core.tools import ToolExecutor
from core.privacy import AuditLogger

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
    """Main LLM service with context firewall integration"""
    
    def __init__(
        self,
        firewall: ContextFirewall,
        tool_executor: ToolExecutor,
        audit_logger: Optional[AuditLogger] = None,
        api_key: Optional[str] = None,
        provider: LLMProvider = LLMProvider.CLAUDE
    ):
        """
        Initialize LLM service
        
        Args:
            firewall: Context firewall instance
            tool_executor: Tool executor instance
            audit_logger: Optional audit logger
            api_key: API key for Claude (or from env)
            provider: LLM provider to use
        """
        self.firewall = firewall
        self.tool_executor = tool_executor
        self.audit_logger = audit_logger
        self.provider = provider
        
        # Initialize Claude client if available
        if provider == LLMProvider.CLAUDE and ANTHROPIC_AVAILABLE:
            self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
            if self.api_key:
                self.client = AsyncAnthropic(api_key=self.api_key)
            else:
                logger.warning("No Anthropic API key provided. Claude integration disabled.")
                self.client = None
        elif provider == LLMProvider.OLLAMA:
            self.ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434")
            self.ollama_model = os.getenv("OLLAMA_MODEL", "llama2")
            self.client = None  # Ollama uses HTTP directly
        elif provider == LLMProvider.GEMINI and GEMINI_AVAILABLE:
            self.api_key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
            if self.api_key:
                # Use sync client, will run in thread for async operations
                self.client = google_genai.Client(api_key=self.api_key)
                self.gemini_model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
            else:
                logger.warning("No Gemini API key provided. Gemini integration disabled.")
                self.client = None
        elif provider == LLMProvider.GROQ and GROQ_AVAILABLE:
            self.api_key = api_key or os.getenv("GROQ_API_KEY")
            if self.api_key:
                self.client = AsyncGroq(api_key=self.api_key)
                self.groq_model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
            else:
                logger.warning("No Groq API key provided. Groq integration disabled.")
                self.client = None
        elif provider == LLMProvider.OPENROUTER and OPENROUTER_AVAILABLE:
            self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")
            if self.api_key:
                self.client = AsyncOpenAI(
                    base_url="https://openrouter.ai/api/v1",
                    api_key=self.api_key
                )
                self.openrouter_model = os.getenv("OPENROUTER_MODEL", "openai/gpt-4o")
            else:
                logger.warning("No OpenRouter API key provided. OpenRouter integration disabled.")
                self.client = None
        else:
            self.client = None
        
        # Conversation history
        self.conversation_history: List[Dict[str, Any]] = []
        
        # System prompt
        self.system_prompt = self._build_system_prompt()
    
    def _build_system_prompt(self) -> str:
        """Build system prompt for CA assistant"""
        return """
        You are a CA's AI assistant for GST compliance and financial analysis.

CORE PROTOCOL:
1. MANDATORY: Call tools to retrieve data BEFORE answering. Never simulate actions.
2. NO MANUAL MATH: Use `get_summary` for all tax/ITC calculations.
3. READ-ONLY: You cannot see files, modify data, or save externally.
4. ADVISORY ONLY: CA must approve all actions.

TOOLS:
- search_documents(query, doc_type, period)
- get_invoice(invoice_number, vendor_name)
- get_summary(summary_type, period, category) -> PRIMARY for calc
- get_reconciliation(source1, source2, period)
- search_gst_rules(query, category, limit)
- explain_rule(rule_type, scenario)

CONTEXT (INDIAN GST):
- ITC requires GSTR-1 filing (Rule 36(4) blocks ITC if missing from GSTR-2B).
- Sec 17(5) defines blocked credits.
- Deadlines: GSTR-1 (11th), GSTR-3B (20th).

EXAMPLE FLOW:
User: "Why is ITC blocked?"
Action: Call `get_summary("itc_summary", ...)`
Result: See Rule 36(4) flag.
Reply: "Blocked due to vendor non-filing (Rule 36(4))." 
"""
    def _get_tool_definitions(self) -> List[Dict[str, Any]]:
        """Get tool definitions for Claude"""
        return [
            {
                "name": "search_documents",
                "description": "Search documents using semantic and keyword search",
                "input_schema": {
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
            },
            {
                "name": "get_invoice",
                "description": "Get structured invoice data by invoice number or vendor",
                "input_schema": {
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
            },
            {
                "name": "get_summary",
                "description": "Get aggregated summary statistics",
                "input_schema": {
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
            },
            {
                "name": "get_reconciliation",
                "description": "Get reconciliation data between two sources",
                "input_schema": {
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
            },
            {
                "name": "search_gst_rules",
                "description": "Search GST rules from rules database",
                "input_schema": {
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
            },
            {
                "name": "explain_rule",
                "description": "Explain a specific GST rule",
                "input_schema": {
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
        ]
    
    async def process_query(
        self,
        query: str,
        user_id: Optional[str] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Process a user query with tool calling
        
        Yields:
            {
                "type": "text" | "tool_call" | "tool_result" | "error",
                "content": str | Dict
            }
        """
        if self.provider == LLMProvider.OLLAMA:
            async for chunk in self._process_ollama_query(query):
                yield chunk
            return
        elif self.provider == LLMProvider.GEMINI:
            async for chunk in self._process_gemini_query(query):
                yield chunk
            return
        elif self.provider == LLMProvider.GROQ:
            async for chunk in self._process_groq_query(query):
                yield chunk
            return
        elif self.provider == LLMProvider.OPENROUTER:
            async for chunk in self._process_openrouter_query(query):
                yield chunk
            return
        
        if not self.client:
            yield {
                "type": "error",
                "content": "LLM service not configured. Please provide API key."
            }
            return
        
        # Add user message to history
        self.conversation_history.append({
            "role": "user",
            "content": query
        })
        
        try:
            # Create message with tools
            message = await self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=4096,
                system=self.system_prompt,
                tools=self._get_tool_definitions(),
                messages=self.conversation_history[-10:],  # Last 10 messages for context
                stream=True
            )
            
            # Process stream
            current_text = ""
            tool_calls = []
            
            async for event in message:
                if event.type == "message_start":
                    continue
                elif event.type == "content_block_start":
                    if event.content_block.type == "tool_use":
                        tool_calls.append({
                            "id": event.content_block.id,
                            "name": event.content_block.name,
                            "input": event.content_block.input
                        })
                elif event.type == "content_block_delta":
                    if event.delta.type == "text_delta":
                        current_text += event.delta.text
                        yield {
                            "type": "text",
                            "content": event.delta.text
                        }
                elif event.type == "message_delta":
                    # Token usage info
                    if hasattr(event, "usage"):
                        yield {
                            "type": "usage",
                            "content": {
                                "input_tokens": getattr(event.usage, "input_tokens", 0),
                                "output_tokens": getattr(event.usage, "output_tokens", 0)
                            }
                        }
            
            # Execute tool calls
            if tool_calls:
                for tool_call in tool_calls:
                    yield {
                        "type": "tool_call",
                        "content": {
                            "tool": tool_call["name"],
                            "input": tool_call["input"]
                        }
                    }
                    
                    # Execute through firewall
                    success, result, error = await self.firewall.process_tool_call(
                        tool_name=tool_call["name"],
                        params=tool_call["input"],
                        execute_func=lambda: self._execute_tool(tool_call["name"], tool_call["input"])
                    )
                    
                    if success:
                        yield {
                            "type": "tool_result",
                            "content": {
                                "tool": tool_call["name"],
                                "result": result
                            }
                        }
                        
                        # Add tool use and result to history
                        self.conversation_history.append({
                            "role": "assistant",
                            "content": [{
                                "type": "tool_use",
                                "id": tool_call["id"],
                                "name": tool_call["name"],
                                "input": tool_call["input"]
                            }]
                        })
                        self.conversation_history.append({
                            "role": "user",
                            "content": [{
                                "type": "tool_result",
                                "tool_use_id": tool_call["id"],
                                "content": str(result)
                            }]
                        })
                        
                        # Get LLM response to tool result
                        response = await self.client.messages.create(
                            model="claude-3-5-sonnet-20241022",
                            max_tokens=4096,
                            system=self.system_prompt,
                            messages=self.conversation_history[-5:],
                            stream=True
                        )
                        
                        async for event in response:
                            if event.type == "content_block_delta":
                                if event.delta.type == "text_delta":
                                    yield {
                                        "type": "text",
                                        "content": event.delta.text
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
        
        except Exception as e:
            logger.error(f"Error processing query: {e}")
            yield {
                "type": "error",
                "content": f"Error: {str(e)}"
            }
    
    async def _execute_tool(self, tool_name: str, params: Dict[str, Any]) -> Any:
        """Execute a tool (called through firewall)"""
        if tool_name == "search_documents":
            return await self.tool_executor.search_documents(
                query=params.get("query", ""),
                doc_type=params.get("doc_type"),
                period=params.get("period"),
                limit=params.get("limit", 20)
            )
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
        else:
            raise ValueError(f"Unknown tool: {tool_name}")
    
    def clear_history(self):
        """Clear conversation history"""
        self.conversation_history = []
    
    def get_history(self) -> List[Dict[str, Any]]:
        """Get conversation history"""
        return self.conversation_history.copy()
    
    async def _process_ollama_query(
        self,
        query: str
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Process query using Ollama (local LLM)"""
        if not HTTPX_AVAILABLE:
            yield {
                "type": "error",
                "content": "httpx not available. Install with: uv pip install httpx"
            }
            return
        
        try:
            async with httpx.AsyncClient() as client:
                # Ollama doesn't support tool calling natively, so we'll do simple chat
                response = await client.post(
                    f"{self.ollama_url}/api/generate",
                    json={
                        "model": self.ollama_model,
                        "prompt": f"{self.system_prompt}\n\nUser: {query}\nAssistant:",
                        "stream": True
                    },
                    timeout=60.0
                )
                
                async for line in response.aiter_lines():
                    if line:
                        try:
                            data = json.loads(line)
                            if "response" in data:
                                yield {
                                    "type": "text",
                                    "content": data["response"]
                                }
                            if data.get("done"):
                                break
                        except Exception:
                            continue
        except Exception as e:
            logger.error(f"Ollama error: {e}")
            yield {
                "type": "error",
                "content": f"Ollama error: {str(e)}. Make sure Ollama is running."
            }
    
    def _convert_tools_to_gemini_format(self) -> List[Dict[str, Any]]:
        """Convert tool definitions to Gemini function calling format"""
        function_declarations = []
        for tool_def in self._get_tool_definitions():
            function_declarations.append({
                "name": tool_def["name"],
                "description": tool_def.get("description", ""),
                "parameters": tool_def["input_schema"]
            })
        return function_declarations
    
    def _convert_tools_to_openai_format(self) -> List[Dict[str, Any]]:
        """Convert tool definitions to OpenAI function calling format"""
        tools = []
        for tool_def in self._get_tool_definitions():
            tools.append({
                "type": "function",
                "function": {
                    "name": tool_def["name"],
                    "description": tool_def.get("description", ""),
                    "parameters": tool_def["input_schema"]
                }
            })
        return tools
    
    async def _process_gemini_query(
        self,
        query: str
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Process query using Google Gemini with function calling support"""
        if not GEMINI_AVAILABLE:
            yield {
                "type": "error",
                "content": "google-genai not available. Install with: uv pip install google-genai"
            }
            return
        
        if not self.client:
            yield {
                "type": "error",
                "content": "Gemini service not configured. Please provide API key."
            }
            return
        
        # Add user message to history
        self.conversation_history.append({
            "role": "user",
            "content": query
        })
        
        try:
            # Convert tools to Gemini format
            tools = self._convert_tools_to_gemini_format()
            
            # Build conversation contents for Gemini
            contents = []
            for msg in self.conversation_history[-10:]:
                if msg["role"] == "user":
                    contents.append(google_genai.types.Content(
                        role="user",
                        parts=[google_genai.types.Part(text=str(msg.get("content", "")))]
                    ))
                elif msg["role"] == "assistant":
                    # Handle both text and function call responses
                    if isinstance(msg.get("content"), str):
                        contents.append(google_genai.types.Content(
                            role="model",
                            parts=[google_genai.types.Part(text=str(msg.get("content", "")))]
                        ))
                    elif isinstance(msg.get("content"), list):
                        # Handle function call format
                        parts = []
                        for part in msg.get("content", []):
                            if isinstance(part, dict):
                                if part.get("type") == "tool_use":
                                    parts.append(google_genai.types.Part(
                                        function_call=google_genai.types.FunctionCall(
                                            name=part.get("name", ""),
                                            args=part.get("input", {})
                                        )
                                    ))
                                elif part.get("type") == "tool_result":
                                    parts.append(google_genai.types.Part(
                                        function_response=google_genai.types.FunctionResponse(
                                            name=part.get("name", ""),
                                            response=part.get("result", {})
                                        )
                                    ))
                        if parts:
                            contents.append(google_genai.types.Content(
                                role="model",
                                parts=parts
                            ))
            
            # Add current user query
            contents.append(google_genai.types.Content(
                role="user",
                parts=[google_genai.types.Part(text=query)]
            ))
            
            # Generate content with function calling
            def generate_sync():
                try:
                    config = google_genai.types.GenerateContentConfig(
                        system_instruction=self.system_prompt,
                        temperature=0.7,
                        max_output_tokens=4096,
                        tools=[google_genai.types.Tool(function_declarations=tools)] if tools else None
                    )
                    return self.client.models.generate_content(
                        model=self.gemini_model,
                        contents=contents,
                        config=config
                    )
                except Exception as e:
                    logger.error(f"Gemini generation error: {e}")
                    import traceback
                    logger.error(traceback.format_exc())
                    return None
            
            # Run sync operation in thread
            response = await asyncio.to_thread(generate_sync)
            
            if response is None:
                yield {
                    "type": "error",
                    "content": "Failed to generate response from Gemini"
                }
                return
            
            # Check for function calls
            function_calls = []
            current_text = ""
            
            if response.candidates and len(response.candidates) > 0:
                candidate = response.candidates[0]
                if candidate.content and candidate.content.parts:
                    for part in candidate.content.parts:
                        if hasattr(part, "function_call") and part.function_call:
                            # Function call detected
                            try:
                                args = {}
                                if hasattr(part.function_call, "args"):
                                    if isinstance(part.function_call.args, dict):
                                        args = part.function_call.args
                                    elif hasattr(part.function_call.args, "__dict__"):
                                        args = part.function_call.args.__dict__
                                
                                function_calls.append({
                                    "name": part.function_call.name,
                                    "args": args
                                })
                            except Exception as e:
                                logger.error(f"Error parsing function call: {e}")
                                yield {
                                    "type": "error",
                                    "content": f"Error parsing function call: {str(e)}"
                                }
                        elif hasattr(part, "text") and part.text:
                            current_text += part.text
                            yield {
                                "type": "text",
                                "content": part.text
                            }
            
            # Execute function calls if any
            if function_calls:
                # Store assistant response with function calls
                assistant_content = []
                for fc in function_calls:
                    assistant_content.append({
                        "type": "tool_use",
                        "name": fc["name"],
                        "input": fc["args"]
                    })
                    
                    yield {
                        "type": "tool_call",
                        "content": {
                            "tool": fc["name"],
                            "input": fc["args"]
                        }
                    }
                    
                    # Execute through firewall
                    success, result, error = await self.firewall.process_tool_call(
                        tool_name=fc["name"],
                        params=fc["args"],
                        execute_func=lambda: self._execute_tool(fc["name"], fc["args"])
                    )
                    
                    if success:
                        yield {
                            "type": "tool_result",
                            "content": {
                                "tool": fc["name"],
                                "result": result
                            }
                        }
                        
                        # Add function response to contents for next call
                        assistant_content.append({
                            "type": "tool_result",
                            "name": fc["name"],
                            "result": result
                        })
                    else:
                        yield {
                            "type": "error",
                            "content": f"Tool execution failed: {error}"
                        }
                
                # Add assistant response with function calls to history
                self.conversation_history.append({
                    "role": "assistant",
                    "content": assistant_content
                })
                
                # Get final response with function results
                # Build contents with function response
                contents.append(google_genai.types.Content(
                    role="model",
                    parts=[google_genai.types.Part(
                        function_call=google_genai.types.FunctionCall(
                            name=function_calls[0]["name"],
                            args=function_calls[0]["args"]
                        )
                    )]
                ))
                
                # Add function response
                for fc in function_calls:
                    success, result, error = await self.firewall.process_tool_call(
                        tool_name=fc["name"],
                        params=fc["args"],
                        execute_func=lambda: self._execute_tool(fc["name"], fc["args"])
                    )
                    if success:
                        contents.append(google_genai.types.Content(
                            role="user",
                            parts=[google_genai.types.Part(
                                function_response=google_genai.types.FunctionResponse(
                                    name=fc["name"],
                                    response=result
                                )
                            )]
                        ))
                
                # Get final response
                def get_final_response():
                    try:
                        config = google_genai.types.GenerateContentConfig(
                            system_instruction=self.system_prompt,
                            temperature=0.7,
                            max_output_tokens=4096,
                        )
                        return self.client.models.generate_content(
                            model=self.gemini_model,
                            contents=contents,
                            config=config
                        )
                    except Exception as e:
                        logger.error(f"Gemini final response error: {e}")
                        return None
                
                final_response = await asyncio.to_thread(get_final_response)
                
                if final_response and final_response.candidates:
                    for candidate in final_response.candidates:
                        if candidate.content and candidate.content.parts:
                            for part in candidate.content.parts:
                                if hasattr(part, "text") and part.text:
                                    yield {
                                        "type": "text",
                                        "content": part.text
                                    }
                                    current_text += part.text
            else:
                # No function calls, just text response
                if current_text:
                    self.conversation_history.append({
                        "role": "assistant",
                        "content": current_text
                    })
        
        except Exception as e:
            logger.error(f"Gemini error: {e}")
            import traceback
            logger.error(traceback.format_exc())
            yield {
                "type": "error",
                "content": f"Gemini error: {str(e)}"
            }
    
    async def _process_groq_query(
        self,
        query: str
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Process query using Groq"""
        if not GROQ_AVAILABLE:
            yield {
                "type": "error",
                "content": "groq not available. Install with: uv pip install groq"
            }
            return
        
        if not self.client:
            yield {
                "type": "error",
                "content": "Groq service not configured. Please provide API key."
            }
            return
        
        # Add user message to history
        self.conversation_history.append({
            "role": "user",
            "content": query
        })
        
        try:
            # Convert tools to OpenAI format
            tools = self._convert_tools_to_openai_format()
            
            # Prepare messages for Groq (OpenAI-compatible)
            messages = []
            messages.append({
                "role": "system",
                "content": self.system_prompt
            })
            for msg in self.conversation_history[-10:]:
                if msg["role"] in ["user", "assistant"]:
                    messages.append({
                        "role": msg["role"],
                        "content": msg.get("content", "")
                    })
                elif msg["role"] == "tool":
                    # Convert tool messages
                    messages.append({
                        "role": "tool",
                        "content": str(msg.get("content", "")),
                        "tool_call_id": msg.get("tool_use_id", "")
                    })
            
            # Generate with streaming
            stream = await self.client.chat.completions.create(
                model=self.groq_model,
                messages=messages,
                tools=tools if tools else None,
                stream=True,
                temperature=0.7,
                max_tokens=4096
            )
            
            current_text = ""
            tool_calls = []
            current_tool_call = None
            
            async for chunk in stream:
                if chunk.choices and len(chunk.choices) > 0:
                    delta = chunk.choices[0].delta
                    
                    if delta.content:
                        current_text += delta.content
                        yield {
                            "type": "text",
                            "content": delta.content
                        }
                    
                    if delta.tool_calls:
                        for tool_call_delta in delta.tool_calls:
                            if tool_call_delta.index is not None:
                                idx = tool_call_delta.index
                                if idx >= len(tool_calls):
                                    tool_calls.extend([None] * (idx + 1 - len(tool_calls)))
                                
                                if tool_calls[idx] is None:
                                    tool_calls[idx] = {
                                        "id": tool_call_delta.id or f"call_{idx}",
                                        "name": "",
                                        "arguments": ""
                                    }
                                
                                if tool_call_delta.function:
                                    if tool_call_delta.function.name:
                                        tool_calls[idx]["name"] = tool_call_delta.function.name
                                    if tool_call_delta.function.arguments:
                                        tool_calls[idx]["arguments"] += tool_call_delta.function.arguments
                    
                    if chunk.choices[0].finish_reason == "tool_calls":
                        # Execute tool calls
                        for tool_call in tool_calls:
                            if tool_call:
                                try:
                                    import json
                                    args = json.loads(tool_call["arguments"])
                                except:
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
                                    
                                    # Add to history
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
                                    
                                    # Get follow-up response
                                    follow_up_messages = []
                                    follow_up_messages.append({
                                        "role": "system",
                                        "content": self.system_prompt
                                    })
                                    for msg in self.conversation_history[-5:]:
                                        if msg["role"] in ["user", "assistant", "tool"]:
                                            follow_up_msg = {"role": msg["role"], "content": msg.get("content", "")}
                                            if msg["role"] == "tool":
                                                follow_up_msg["tool_call_id"] = msg.get("tool_call_id", "")
                                            follow_up_messages.append(follow_up_msg)
                                    
                                    follow_up_stream = await self.client.chat.completions.create(
                                        model=self.groq_model,
                                        messages=follow_up_messages,
                                        tools=tools if tools else None,
                                        stream=True,
                                        temperature=0.7,
                                        max_tokens=4096
                                    )
                                    
                                    async for follow_up_chunk in follow_up_stream:
                                        if follow_up_chunk.choices and len(follow_up_chunk.choices) > 0:
                                            if follow_up_chunk.choices[0].delta.content:
                                                yield {
                                                    "type": "text",
                                                    "content": follow_up_chunk.choices[0].delta.content
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
        
        except Exception as e:
            logger.error(f"Groq error: {e}")
            yield {
                "type": "error",
                "content": f"Groq error: {str(e)}"
            }
    
    async def _process_openrouter_query(
        self,
        query: str
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Process query using OpenRouter"""
        if not OPENROUTER_AVAILABLE:
            yield {
                "type": "error",
                "content": "openai not available. Install with: uv pip install openai"
            }
            return
        
        if not self.client:
            yield {
                "type": "error",
                "content": "OpenRouter service not configured. Please provide API key."
            }
            return
        
        # Add user message to history
        self.conversation_history.append({
            "role": "user",
            "content": query
        })
        
        try:
            # Convert tools to OpenAI format
            tools = self._convert_tools_to_openai_format()
            
            # Prepare messages for OpenRouter (OpenAI-compatible)
            messages = []
            messages.append({
                "role": "system",
                "content": self.system_prompt
            })
            for msg in self.conversation_history[-10:]:
                if msg["role"] in ["user", "assistant"]:
                    messages.append({
                        "role": msg["role"],
                        "content": msg.get("content", "")
                    })
                elif msg["role"] == "tool":
                    messages.append({
                        "role": "tool",
                        "content": str(msg.get("content", "")),
                        "tool_call_id": msg.get("tool_use_id", "")
                    })
            
            # Generate with streaming
            stream = await self.client.chat.completions.create(
                model=self.openrouter_model,
                messages=messages,
                tools=tools if tools else None,
                stream=True,
                temperature=0.7,
                max_tokens=4096
            )
            
            current_text = ""
            tool_calls = []
            
            async for chunk in stream:
                if chunk.choices and len(chunk.choices) > 0:
                    delta = chunk.choices[0].delta
                    
                    if delta.content:
                        current_text += delta.content
                        yield {
                            "type": "text",
                            "content": delta.content
                        }
                    
                    if delta.tool_calls:
                        for tool_call_delta in delta.tool_calls:
                            if tool_call_delta.index is not None:
                                idx = tool_call_delta.index
                                if idx >= len(tool_calls):
                                    tool_calls.extend([None] * (idx + 1 - len(tool_calls)))
                                
                                if tool_calls[idx] is None:
                                    tool_calls[idx] = {
                                        "id": tool_call_delta.id or f"call_{idx}",
                                        "name": "",
                                        "arguments": ""
                                    }
                                
                                if tool_call_delta.function:
                                    if tool_call_delta.function.name:
                                        tool_calls[idx]["name"] = tool_call_delta.function.name
                                    if tool_call_delta.function.arguments:
                                        tool_calls[idx]["arguments"] += tool_call_delta.function.arguments
                    
                    if chunk.choices[0].finish_reason == "tool_calls":
                        # Execute tool calls
                        for tool_call in tool_calls:
                            if tool_call:
                                try:
                                    import json
                                    args = json.loads(tool_call["arguments"])
                                except:
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
                                    
                                    # Add to history
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
                                        "tool_use_id": tool_call["id"]
                                    })
                                    
                                    # Get follow-up response
                                    follow_up_messages = []
                                    follow_up_messages.append({
                                        "role": "system",
                                        "content": self.system_prompt
                                    })
                                    for msg in self.conversation_history[-5:]:
                                        if msg["role"] in ["user", "assistant", "tool"]:
                                            follow_up_msg = {"role": msg["role"], "content": msg.get("content", "")}
                                            if msg["role"] == "tool":
                                                follow_up_msg["tool_call_id"] = msg.get("tool_use_id", "")
                                            follow_up_messages.append(follow_up_msg)
                                    
                                    follow_up_stream = await self.client.chat.completions.create(
                                        model=self.openrouter_model,
                                        messages=follow_up_messages,
                                        tools=tools if tools else None,
                                        stream=True,
                                        temperature=0.7,
                                        max_tokens=4096
                                    )
                                    
                                    async for follow_up_chunk in follow_up_stream:
                                        if follow_up_chunk.choices and len(follow_up_chunk.choices) > 0:
                                            if follow_up_chunk.choices[0].delta.content:
                                                yield {
                                                    "type": "text",
                                                    "content": follow_up_chunk.choices[0].delta.content
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
        
        except Exception as e:
            logger.error(f"OpenRouter error: {e}")
            yield {
                "type": "error",
                "content": f"OpenRouter error: {str(e)}"
            }
    
    def estimate_tokens(self, text: str) -> int:
        """Estimate token count (rough approximation)"""
        # Rough estimate: 1 token ≈ 4 characters
        return len(text) // 4
