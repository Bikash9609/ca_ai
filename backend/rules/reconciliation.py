"""
GSTR-2B Reconciliation - Match invoices with GSTR-2B data
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)


class InvoiceMatcher:
    """Matches invoices with GSTR-2B data"""
    
    @staticmethod
    def match_by_invoice_number(
        invoice_number: str,
        gstr2b_invoices: List[Dict[str, Any]],
        exact_match: bool = True
    ) -> Optional[Dict[str, Any]]:
        """Match invoice by invoice number"""
        for gstr2b_inv in gstr2b_invoices:
            gstr2b_number = gstr2b_inv.get("invoice_number", "")
            
            if exact_match:
                if invoice_number == gstr2b_number:
                    return gstr2b_inv
            else:
                # Case-insensitive match
                if invoice_number.lower() == gstr2b_number.lower():
                    return gstr2b_inv
        
        return None
    
    @staticmethod
    def match_by_amount(
        invoice_amount: float,
        gstr2b_invoices: List[Dict[str, Any]],
        tolerance: float = 0.01
    ) -> List[Dict[str, Any]]:
        """Match invoices by amount within tolerance"""
        matches = []
        
        for gstr2b_inv in gstr2b_invoices:
            gstr2b_amount = gstr2b_inv.get("taxable_value", 0.0) + gstr2b_inv.get("tax_amount", 0.0)
            difference = abs(invoice_amount - gstr2b_amount)
            
            if difference <= tolerance:
                matches.append(gstr2b_inv)
        
        return matches
    
    @staticmethod
    def fuzzy_match(
        invoice: Dict[str, Any],
        gstr2b_invoices: List[Dict[str, Any]],
        threshold: float = 0.8
    ) -> Optional[Tuple[Dict[str, Any], float]]:
        """
        Fuzzy match invoice using multiple fields
        Returns: (matched_invoice, similarity_score) or None
        """
        invoice_number = str(invoice.get("invoice_number", ""))
        invoice_amount = invoice.get("taxable_value", 0.0) + invoice.get("tax_amount", 0.0)
        vendor_gstin = invoice.get("vendor_gstin", "")
        invoice_date = invoice.get("invoice_date", "")
        
        best_match = None
        best_score = 0.0
        
        for gstr2b_inv in gstr2b_invoices:
            gstr2b_number = str(gstr2b_inv.get("invoice_number", ""))
            gstr2b_amount = gstr2b_inv.get("taxable_value", 0.0) + gstr2b_inv.get("tax_amount", 0.0)
            gstr2b_vendor = gstr2b_inv.get("vendor_gstin", "")
            gstr2b_date = gstr2b_inv.get("invoice_date", "")
            
            # Calculate similarity scores
            number_similarity = SequenceMatcher(None, invoice_number.lower(), gstr2b_number.lower()).ratio()
            
            # Amount match (within 1% tolerance = 1.0, otherwise 0)
            amount_match = 1.0 if abs(invoice_amount - gstr2b_amount) / max(invoice_amount, 1.0) < 0.01 else 0.0
            
            # Vendor match
            vendor_match = 1.0 if vendor_gstin == gstr2b_vendor else 0.0
            
            # Date match (exact = 1.0, same month = 0.5, otherwise 0)
            date_match = 0.0
            if invoice_date and gstr2b_date:
                if invoice_date == gstr2b_date:
                    date_match = 1.0
                elif invoice_date[:7] == gstr2b_date[:7]:  # Same month
                    date_match = 0.5
            
            # Weighted average
            total_score = (
                number_similarity * 0.4 +
                amount_match * 0.3 +
                vendor_match * 0.2 +
                date_match * 0.1
            )
            
            if total_score > best_score and total_score >= threshold:
                best_score = total_score
                best_match = gstr2b_inv
        
        if best_match:
            return (best_match, best_score)
        return None


class ReconciliationEngine:
    """Main reconciliation engine"""
    
    def __init__(self):
        self.matcher = InvoiceMatcher()
    
    def reconcile_invoices(
        self,
        purchase_invoices: List[Dict[str, Any]],
        gstr2b_data: List[Dict[str, Any]],
        use_fuzzy_matching: bool = True
    ) -> Dict[str, Any]:
        """
        Reconcile purchase invoices with GSTR-2B data
        
        Returns:
            {
                "matched_items": List[Dict],
                "unmatched_invoices": List[Dict],
                "unmatched_gstr2b": List[Dict],
                "differences": List[Dict],
                "summary": Dict
            }
        """
        matched_items = []
        unmatched_invoices = []
        unmatched_gstr2b = gstr2b_data.copy()
        differences = []
        
        for invoice in purchase_invoices:
            invoice_number = invoice.get("invoice_number", "")
            invoice_amount = invoice.get("taxable_value", 0.0) + invoice.get("tax_amount", 0.0)
            
            # Try exact match first
            matched = self.matcher.match_by_invoice_number(
                invoice_number,
                unmatched_gstr2b,
                exact_match=True
            )
            
            # Try fuzzy match if exact match fails
            if not matched and use_fuzzy_matching:
                fuzzy_result = self.matcher.fuzzy_match(invoice, unmatched_gstr2b)
                if fuzzy_result:
                    matched, similarity = fuzzy_result
                    if similarity >= 0.8:
                        # Use fuzzy match
                        pass
                    else:
                        matched = None
            
            if matched:
                # Check for amount differences
                gstr2b_amount = matched.get("taxable_value", 0.0) + matched.get("tax_amount", 0.0)
                amount_diff = abs(invoice_amount - gstr2b_amount)
                
                if amount_diff > 0.01:
                    differences.append({
                        "invoice_number": invoice_number,
                        "invoice_amount": invoice_amount,
                        "gstr2b_amount": gstr2b_amount,
                        "difference": amount_diff,
                        "type": "amount_mismatch"
                    })
                
                matched_items.append({
                    "invoice": invoice,
                    "gstr2b": matched,
                    "matched_by": "invoice_number" if matched.get("invoice_number") == invoice_number else "fuzzy",
                    "amount_difference": amount_diff
                })
                
                # Remove from unmatched list
                unmatched_gstr2b = [inv for inv in unmatched_gstr2b if inv.get("invoice_number") != matched.get("invoice_number")]
            else:
                unmatched_invoices.append(invoice)
        
        # Summary
        total_invoices = len(purchase_invoices)
        matched_count = len(matched_items)
        unmatched_count = len(unmatched_invoices)
        difference_count = len(differences)
        
        return {
            "matched_items": matched_items,
            "unmatched_invoices": unmatched_invoices,
            "unmatched_gstr2b": unmatched_gstr2b,
            "differences": differences,
            "summary": {
                "total_invoices": total_invoices,
                "matched_count": matched_count,
                "unmatched_count": unmatched_count,
                "match_percentage": (matched_count / total_invoices * 100) if total_invoices > 0 else 0,
                "difference_count": difference_count,
                "total_amount_difference": sum(d.get("difference", 0.0) for d in differences)
            }
        }
    
    def generate_reconciliation_report(
        self,
        reconciliation_result: Dict[str, Any],
        period: str,
        client_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """Generate reconciliation report"""
        return {
            "period": period,
            "client_name": client_name,
            "reconciliation_date": datetime.utcnow().isoformat(),
            "summary": reconciliation_result.get("summary", {}),
            "matched_items": [
                {
                    "invoice_number": item["invoice"].get("invoice_number"),
                    "vendor_gstin": item["invoice"].get("vendor_gstin"),
                    "invoice_amount": item["invoice"].get("taxable_value", 0.0) + item["invoice"].get("tax_amount", 0.0),
                    "gstr2b_amount": item["gstr2b"].get("taxable_value", 0.0) + item["gstr2b"].get("tax_amount", 0.0),
                    "amount_difference": item.get("amount_difference", 0.0),
                    "matched_by": item.get("matched_by", "unknown")
                }
                for item in reconciliation_result.get("matched_items", [])
            ],
            "unmatched_invoices": [
                {
                    "invoice_number": inv.get("invoice_number"),
                    "vendor_gstin": inv.get("vendor_gstin"),
                    "invoice_date": inv.get("invoice_date"),
                    "amount": inv.get("taxable_value", 0.0) + inv.get("tax_amount", 0.0)
                }
                for inv in reconciliation_result.get("unmatched_invoices", [])
            ],
            "unmatched_gstr2b": [
                {
                    "invoice_number": inv.get("invoice_number"),
                    "vendor_gstin": inv.get("vendor_gstin"),
                    "invoice_date": inv.get("invoice_date"),
                    "amount": inv.get("taxable_value", 0.0) + inv.get("tax_amount", 0.0)
                }
                for inv in reconciliation_result.get("unmatched_gstr2b", [])
            ],
            "differences": reconciliation_result.get("differences", []),
            "action_items": [
                {
                    "type": "missing_in_gstr2b",
                    "description": f"Invoice {inv.get('invoice_number')} not found in GSTR-2B",
                    "invoice_number": inv.get("invoice_number"),
                    "vendor_gstin": inv.get("vendor_gstin"),
                    "recommendation": "Contact vendor to ensure GSTR-1 is filed"
                }
                for inv in reconciliation_result.get("unmatched_invoices", [])
            ] + [
                {
                    "type": "amount_mismatch",
                    "description": f"Amount mismatch for invoice {diff.get('invoice_number')}",
                    "invoice_number": diff.get("invoice_number"),
                    "difference": diff.get("difference", 0.0),
                    "recommendation": "Verify invoice amount and GSTR-2B data"
                }
                for diff in reconciliation_result.get("differences", [])
            ]
        }
