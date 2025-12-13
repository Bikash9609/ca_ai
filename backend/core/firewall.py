"""
Context Firewall - Privacy enforcement layer
Ensures LLM only sees summaries, never raw documents
"""

from typing import Any, Dict, List, Optional
from enum import Enum


class AccessLevel(Enum):
    """Access levels for tools"""
    SUMMARY_ONLY = "summary_only"
    STRUCTURED_DATA = "structured_data"
    NO_ACCESS = "no_access"


class ToolRegistry:
    """Registry of allowed tools with their access levels"""
    
    ALLOWED_TOOLS = {
        "search_documents": AccessLevel.SUMMARY_ONLY,
        "get_invoice": AccessLevel.STRUCTURED_DATA,
        "get_summary": AccessLevel.SUMMARY_ONLY,
        "get_reconciliation": AccessLevel.STRUCTURED_DATA,
        "search_gst_rules": AccessLevel.SUMMARY_ONLY,
        "explain_rule": AccessLevel.SUMMARY_ONLY,
    }
    
    @classmethod
    def is_allowed(cls, tool_name: str) -> bool:
        """Check if a tool is allowed"""
        return tool_name in cls.ALLOWED_TOOLS
    
    @classmethod
    def get_access_level(cls, tool_name: str) -> Optional[AccessLevel]:
        """Get access level for a tool"""
        return cls.ALLOWED_TOOLS.get(tool_name)


class ParameterValidator:
    """Validates tool parameters for security"""
    
    @staticmethod
    def validate(tool_name: str, params: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """
        Validate tool parameters
        Returns: (is_valid, error_message)
        """
        # Prevent path traversal
        for key, value in params.items():
            if isinstance(value, str) and (".." in value or value.startswith("/")):
                if "path" in key.lower() or "file" in key.lower():
                    return False, f"Path traversal detected in {key}"
        
        # Validate parameter types
        if tool_name == "search_documents":
            if "query" not in params:
                return False, "Missing required parameter: query"
            if not isinstance(params["query"], str):
                return False, "Parameter 'query' must be a string"
        
        return True, None


class ResultFilter:
    """Filters results based on access level"""
    
    @staticmethod
    def filter_result(
        tool_name: str,
        result: Any,
        access_level: AccessLevel
    ) -> Any:
        """Filter result based on access level"""
        if access_level == AccessLevel.SUMMARY_ONLY:
            return ResultFilter._extract_summary(result)
        elif access_level == AccessLevel.STRUCTURED_DATA:
            return ResultFilter._extract_structured_data(result)
        else:
            return None
    
    @staticmethod
    def _extract_summary(result: Any) -> Dict[str, Any]:
        """Extract summary from result"""
        if isinstance(result, dict):
            # Return only summary fields
            return {
                "summary": result.get("summary", ""),
                "count": result.get("count", 0),
                "metadata": {
                    "type": result.get("type"),
                    "date": result.get("date"),
                }
            }
        return {"summary": str(result)[:500]}  # Truncate to 500 chars
    
    @staticmethod
    def _extract_structured_data(result: Any) -> Dict[str, Any]:
        """Extract structured data (allowed fields only)"""
        if isinstance(result, dict):
            allowed_fields = [
                "id", "invoice_number", "date", "amount", "gstin",
                "vendor_name", "taxable_value", "cgst", "sgst", "igst"
            ]
            return {
                k: v for k, v in result.items()
                if k in allowed_fields
            }
        return result


class ContextFirewall:
    """Main context firewall class"""
    
    def __init__(self):
        self.registry = ToolRegistry()
        self.validator = ParameterValidator()
        self.filter = ResultFilter()
    
    def process_tool_call(
        self,
        tool_name: str,
        params: Dict[str, Any],
        execute_func: callable
    ) -> tuple[bool, Optional[Any], Optional[str]]:
        """
        Process a tool call through the firewall
        Returns: (success, result, error_message)
        """
        # Check if tool is allowed
        if not self.registry.is_allowed(tool_name):
            return False, None, f"Tool '{tool_name}' is not allowed"
        
        # Validate parameters
        is_valid, error = self.validator.validate(tool_name, params)
        if not is_valid:
            return False, None, error
        
        # Get access level
        access_level = self.registry.get_access_level(tool_name)
        if not access_level:
            return False, None, f"Unknown access level for tool '{tool_name}'"
        
        # Execute tool
        try:
            result = execute_func()
        except Exception as e:
            return False, None, f"Tool execution failed: {str(e)}"
        
        # Filter result
        filtered_result = self.filter.filter_result(tool_name, result, access_level)
        
        return True, filtered_result, None
