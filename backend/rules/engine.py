"""
Rules Engine - Deterministic GST rule evaluation
Loads rule logic from database and applies it to invoices
"""

import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
import httpx

logger = logging.getLogger(__name__)


class RuleLogicLoader:
    """Loads rule logic from rules server database"""
    
    def __init__(self, rules_server_url: str = "http://localhost:8001"):
        self.rules_server_url = rules_server_url
        self.rules_cache: Dict[str, Any] = {}
    
    async def load_rule_logic(self, rule_id: str) -> Optional[Dict[str, Any]]:
        """Load rule logic for a specific rule"""
        if rule_id in self.rules_cache:
            return self.rules_cache[rule_id]
        
        try:
            async with httpx.AsyncClient() as client:
                # Get rule details
                rule_response = await client.get(
                    f"{self.rules_server_url}/api/rules/{rule_id}",
                    timeout=10.0
                )
                
                if rule_response.status_code != 200:
                    return None
                
                rule = rule_response.json()
                
                # Get rule logic (would need a new endpoint or include in rule response)
                # For now, we'll parse from the rule data structure
                rule_logic = {
                    "rule_id": rule.get("rule_id"),
                    "name": rule.get("name"),
                    "citation": rule.get("citation"),
                    "category": rule.get("category"),
                }
                
                self.rules_cache[rule_id] = rule_logic
                return rule_logic
        except Exception as e:
            logger.error(f"Error loading rule logic for {rule_id}: {e}")
            return None
    
    async def load_all_active_rules(self) -> List[Dict[str, Any]]:
        """Load all active rules with their logic"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.rules_server_url}/api/rules?is_active=true",
                    timeout=10.0
                )
                
                if response.status_code != 200:
                    return []
                
                rules = response.json()
                return rules
        except Exception as e:
            logger.error(f"Error loading all rules: {e}")
            return []
    
    def parse_condition_logic(self, condition_logic: Dict[str, Any]) -> Dict[str, Any]:
        """Parse condition logic JSON into evaluable structure"""
        return condition_logic


class ConditionEvaluator:
    """Evaluates conditions for rule matching"""
    
    @staticmethod
    def evaluate_vendor_in_gstr2b(
        vendor_gstin: str,
        gstr2b_data: Dict[str, Any]
    ) -> bool:
        """Check if vendor GSTIN exists in GSTR-2B data"""
        if not gstr2b_data:
            return False
        
        vendors = gstr2b_data.get("vendors", [])
        if isinstance(vendors, list):
            return vendor_gstin in vendors
        
        # If vendors is a dict with GSTIN as keys
        if isinstance(vendors, dict):
            return vendor_gstin in vendors
        
        return False
    
    @staticmethod
    def evaluate_recipient_registration(
        recipient_gstin: str,
        registration_data: Dict[str, Any]
    ) -> bool:
        """Check if recipient is registered"""
        if not registration_data:
            return False
        
        registered_gstins = registration_data.get("registered", [])
        return recipient_gstin in registered_gstins
    
    @staticmethod
    def evaluate_blocked_category(
        invoice: Dict[str, Any],
        blocked_categories: List[str]
    ) -> bool:
        """Check if invoice category is blocked"""
        invoice_category = invoice.get("category", "")
        hsn_code = invoice.get("hsn_code", "")
        
        # Check category
        if invoice_category in blocked_categories:
            return True
        
        # Check HSN code for blocked items (e.g., liquor, petrol)
        blocked_hsn_prefixes = ["2203", "2710"]  # Example: liquor, petrol
        for prefix in blocked_hsn_prefixes:
            if hsn_code.startswith(prefix):
                return True
        
        return False
    
    @staticmethod
    def evaluate_amount_mismatch(
        invoice_amount: float,
        gstr2b_amount: float,
        tolerance: float = 0.01
    ) -> Dict[str, Any]:
        """Check if amounts match within tolerance"""
        difference = abs(invoice_amount - gstr2b_amount)
        match = difference <= tolerance
        
        return {
            "match": match,
            "difference": difference,
            "invoice_amount": invoice_amount,
            "gstr2b_amount": gstr2b_amount,
            "excess": max(0, invoice_amount - gstr2b_amount)
        }
    
    def evaluate_condition(
        self,
        condition_type: str,
        condition_logic: Dict[str, Any],
        context: Dict[str, Any]
    ) -> bool:
        """Evaluate a condition based on type and logic"""
        if condition_type == "vendor_not_in_gstr2b":
            vendor_gstin = context.get("vendor_gstin", "")
            gstr2b_data = context.get("gstr2b_data", {})
            return not self.evaluate_vendor_in_gstr2b(vendor_gstin, gstr2b_data)
        
        elif condition_type == "recipient_not_registered":
            recipient_gstin = context.get("recipient_gstin", "")
            registration_data = context.get("registration_data", {})
            return not self.evaluate_recipient_registration(recipient_gstin, registration_data)
        
        elif condition_type == "blocked_category":
            invoice = context.get("invoice", {})
            blocked_categories = condition_logic.get("categories", [])
            return self.evaluate_blocked_category(invoice, blocked_categories)
        
        elif condition_type == "amount_mismatch":
            invoice = context.get("invoice", {})
            gstr2b_data = context.get("gstr2b_data", {})
            
            invoice_amount = invoice.get("tax_amount", 0.0)
            gstr2b_amount = gstr2b_data.get("amount", 0.0)
            
            result = self.evaluate_amount_mismatch(invoice_amount, gstr2b_amount)
            return not result["match"]
        
        return False


class ActionExecutor:
    """Executes actions based on rule evaluation"""
    
    @staticmethod
    def block_itc(
        invoice: Dict[str, Any],
        action_percentage: float = 100.0,
        action_amount_formula: Optional[str] = None
    ) -> Dict[str, Any]:
        """Block ITC based on rule"""
        tax_amount = invoice.get("tax_amount", 0.0)
        taxable_value = invoice.get("taxable_value", 0.0)
        
        if action_amount_formula:
            # Evaluate formula (simplified - would need proper expression evaluator)
            if action_amount_formula == "invoice_tax_amount":
                blocked_amount = tax_amount * (action_percentage / 100.0)
            elif action_amount_formula.startswith("invoice_amount -"):
                # Parse formula like "invoice_amount - gstr2b_amount"
                blocked_amount = tax_amount * (action_percentage / 100.0)
            else:
                blocked_amount = tax_amount * (action_percentage / 100.0)
        else:
            blocked_amount = tax_amount * (action_percentage / 100.0)
        
        return {
            "action": "block_itc",
            "blocked_amount": blocked_amount,
            "percentage": action_percentage,
            "eligible_amount": tax_amount - blocked_amount
        }
    
    @staticmethod
    def reverse_itc(
        invoice: Dict[str, Any],
        action_percentage: float = 100.0
    ) -> Dict[str, Any]:
        """Reverse ITC based on rule"""
        tax_amount = invoice.get("tax_amount", 0.0)
        reversed_amount = tax_amount * (action_percentage / 100.0)
        
        return {
            "action": "reverse_itc",
            "reversed_amount": reversed_amount,
            "percentage": action_percentage
        }
    
    @staticmethod
    def partial_itc(
        invoice: Dict[str, Any],
        eligible_percentage: float
    ) -> Dict[str, Any]:
        """Allow partial ITC"""
        tax_amount = invoice.get("tax_amount", 0.0)
        eligible_amount = tax_amount * (eligible_percentage / 100.0)
        blocked_amount = tax_amount - eligible_amount
        
        return {
            "action": "partial_itc",
            "eligible_amount": eligible_amount,
            "blocked_amount": blocked_amount,
            "percentage": eligible_percentage
        }
    
    def execute_action(
        self,
        action_type: str,
        invoice: Dict[str, Any],
        action_percentage: float = 100.0,
        action_amount_formula: Optional[str] = None
    ) -> Dict[str, Any]:
        """Execute action based on type"""
        if action_type == "block_itc":
            return self.block_itc(invoice, action_percentage, action_amount_formula)
        elif action_type == "reverse_itc":
            return self.reverse_itc(invoice, action_percentage)
        elif action_type == "partial_itc":
            return self.partial_itc(invoice, action_percentage)
        else:
            return {
                "action": "none",
                "eligible_amount": invoice.get("tax_amount", 0.0)
            }


class RulesEngine:
    """Main rules engine for GST compliance"""
    
    def __init__(self, rules_server_url: str = "http://localhost:8001"):
        self.loader = RuleLogicLoader(rules_server_url)
        self.evaluator = ConditionEvaluator()
        self.executor = ActionExecutor()
        self.rules: List[Dict[str, Any]] = []
    
    async def initialize(self):
        """Initialize engine by loading rules"""
        self.rules = await self.loader.load_all_active_rules()
        logger.info(f"Loaded {len(self.rules)} rules")
    
    async def evaluate_invoice(
        self,
        invoice: Dict[str, Any],
        gstr2b_data: Optional[Dict[str, Any]] = None,
        registration_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Evaluate a single invoice against all rules
        
        Returns:
            {
                "eligible": bool,
                "eligible_amount": float,
                "blocked_amount": float,
                "rules_applied": List[Dict],
                "explanation": str
            }
        """
        if not self.rules:
            await self.initialize()
        
        context = {
            "invoice": invoice,
            "gstr2b_data": gstr2b_data or {},
            "registration_data": registration_data or {},
            "vendor_gstin": invoice.get("vendor_gstin", ""),
            "recipient_gstin": invoice.get("recipient_gstin", ""),
        }
        
        total_blocked = 0.0
        rules_applied = []
        explanations = []
        
        # Sort rules by priority (higher priority first)
        sorted_rules = sorted(
            self.rules,
            key=lambda r: r.get("priority", 0),
            reverse=True
        )
        
        for rule in sorted_rules:
            rule_id = rule.get("rule_id", "")
            rule_logic = rule.get("rule_logic")
            
            if not rule_logic or not rule_logic.get("is_active", True):
                continue
            
            condition_type = rule_logic.get("condition_type")
            condition_logic = rule_logic.get("condition_logic", {})
            
            # Evaluate condition
            condition_met = self.evaluator.evaluate_condition(
                condition_type,
                condition_logic,
                context
            )
            
            if condition_met:
                # Execute action
                action_type = rule_logic.get("action_type")
                action_percentage = rule_logic.get("action_percentage", 100.0)
                action_amount_formula = rule_logic.get("action_amount_formula")
                
                action_result = self.executor.execute_action(
                    action_type,
                    invoice,
                    action_percentage,
                    action_amount_formula
                )
                
                blocked = action_result.get("blocked_amount", 0.0)
                total_blocked += blocked
                
                rules_applied.append({
                    "rule_id": rule_id,
                    "rule_name": rule.get("name"),
                    "citation": rule.get("citation"),
                    "action": action_result,
                })
                
                explanations.append(
                    f"{rule.get('name')} ({rule.get('citation', '')}): "
                    f"{action_result.get('action', '')} - "
                    f"Blocked: ₹{blocked:.2f}"
                )
        
        tax_amount = invoice.get("tax_amount", 0.0)
        eligible_amount = tax_amount - total_blocked
        
        return {
            "eligible": eligible_amount > 0,
            "eligible_amount": eligible_amount,
            "blocked_amount": total_blocked,
            "total_tax": tax_amount,
            "rules_applied": rules_applied,
            "explanation": "; ".join(explanations) if explanations else "No rules applied",
            "invoice_number": invoice.get("invoice_number"),
            "vendor_gstin": invoice.get("vendor_gstin"),
        }
    
    async def evaluate_batch(
        self,
        invoices: List[Dict[str, Any]],
        gstr2b_data: Optional[Dict[str, Any]] = None,
        registration_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Evaluate multiple invoices"""
        results = []
        total_eligible = 0.0
        total_blocked = 0.0
        
        for invoice in invoices:
            result = await self.evaluate_invoice(invoice, gstr2b_data, registration_data)
            results.append(result)
            total_eligible += result["eligible_amount"]
            total_blocked += result["blocked_amount"]
        
        return {
            "total_invoices": len(invoices),
            "total_eligible_itc": total_eligible,
            "total_blocked_itc": total_blocked,
            "results": results,
            "summary": {
                "eligible_count": sum(1 for r in results if r["eligible"]),
                "blocked_count": sum(1 for r in results if r["blocked_amount"] > 0),
            }
        }
