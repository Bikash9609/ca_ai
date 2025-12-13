"""
Tool implementations for LLM - All tools go through Context Firewall
These tools provide safe, filtered access to document data and rules
"""

import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from database.connection import DatabaseManager
from services.search import HybridSearch
from services.embedding import EmbeddingGenerator
import httpx

logger = logging.getLogger(__name__)


class ToolExecutor:
    """Executes tools with access to backend services"""
    
    def __init__(
        self,
        db_manager: DatabaseManager,
        client_id: str,
        rules_server_url: Optional[str] = None
    ):
        """
        Initialize tool executor
        
        Args:
            db_manager: Database manager instance
            client_id: Current client ID
            rules_server_url: Optional rules server URL
        """
        self.db = db_manager
        self.client_id = client_id
        self.rules_server_url = rules_server_url or "http://localhost:8001"
        
        # Initialize services
        self.embedding_gen = EmbeddingGenerator()
        self.search = HybridSearch(db_manager)
    
    async def search_documents(
        self,
        query: str,
        doc_type: Optional[str] = None,
        period: Optional[str] = None,
        limit: int = 20
    ) -> Dict[str, Any]:
        """
        Search documents using hybrid search
        
        Returns summary information only (no raw file paths or content)
        """
        try:
            # Generate query embedding
            query_embedding = self.embedding_gen.generate(query)
            
            # Build filters
            filters = {"client_id": self.client_id}
            if doc_type:
                filters["doc_type"] = doc_type
            if period:
                filters["period"] = period
            
            # Perform search
            results = await self.search.search(
                query=query,
                query_embedding=query_embedding,
                limit=limit,
                filters=filters
            )
            
            # Format results (summary only - no file paths)
            formatted_results = []
            for result in results:
                # Truncate text preview
                text_preview = result.get("text", "")[:500]
                
                formatted_results.append({
                    "document_id": result.get("document_id"),
                    "doc_type": result.get("doc_type"),
                    "period": result.get("period"),
                    "category": result.get("category"),
                    "text_preview": text_preview,
                    "similarity": result.get("combined_score", 0.0),
                    "chunk_index": result.get("chunk_index")
                })
            
            return {
                "count": len(formatted_results),
                "results": formatted_results,
                "query": query
            }
        except Exception as e:
            logger.error(f"Error in search_documents: {e}")
            return {
                "count": 0,
                "results": [],
                "error": str(e)
            }
    
    async def get_invoice(
        self,
        invoice_number: Optional[str] = None,
        vendor_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get structured invoice data
        
        Returns only allowed fields (no file paths, no raw content)
        """
        try:
            # Build query
            query = """
                SELECT 
                    id, client_id, period, doc_type, category,
                    metadata
                FROM documents
                WHERE client_id = ? AND doc_type = 'invoice'
            """
            params = [self.client_id]
            
            conditions = []
            if invoice_number:
                conditions.append("json_extract(metadata, '$.invoice_number') = ?")
                params.append(invoice_number)
            
            if vendor_name:
                conditions.append("json_extract(metadata, '$.vendor_name') = ?")
                params.append(vendor_name)
            
            if conditions:
                query += " AND " + " AND ".join(conditions)
            
            query += " LIMIT 1"
            
            rows = await self.db.fetchall(query, tuple(params))
            
            if not rows:
                return {
                    "found": False,
                    "invoice_number": invoice_number
                }
            
            row = rows[0]
            metadata = json.loads(row[4]) if row[4] else {}
            
            # Return only allowed structured fields
            return {
                "found": True,
                "invoice_number": metadata.get("invoice_number"),
                "date": metadata.get("date"),
                "vendor_name": metadata.get("vendor_name"),
                "amount": metadata.get("amount"),
                "taxable_value": metadata.get("taxable_value"),
                "cgst": metadata.get("cgst"),
                "sgst": metadata.get("sgst"),
                "igst": metadata.get("igst"),
                "total": metadata.get("total"),
                "gstin": metadata.get("gstin"),
                "period": row[2],
                "category": row[4]
            }
        except Exception as e:
            logger.error(f"Error in get_invoice: {e}")
            return {
                "found": False,
                "error": str(e)
            }
    
    async def get_summary(
        self,
        summary_type: str,
        period: Optional[str] = None,
        category: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get aggregated summary data
        
        Returns only summary statistics (no individual invoice details)
        """
        try:
            # Build base query
            query = """
                SELECT 
                    doc_type,
                    category,
                    period,
                    COUNT(*) as count,
                    SUM(CAST(json_extract(metadata, '$.amount') AS REAL)) as total_amount,
                    SUM(CAST(json_extract(metadata, '$.taxable_value') AS REAL)) as total_taxable,
                    SUM(CAST(json_extract(metadata, '$.cgst') AS REAL)) as total_cgst,
                    SUM(CAST(json_extract(metadata, '$.sgst') AS REAL)) as total_sgst,
                    SUM(CAST(json_extract(metadata, '$.igst') AS REAL)) as total_igst
                FROM documents
                WHERE client_id = ?
            """
            params = [self.client_id]
            
            conditions = []
            if period:
                conditions.append("period = ?")
                params.append(period)
            
            if category:
                conditions.append("category = ?")
                params.append(category)
            
            if conditions:
                query += " AND " + " AND ".join(conditions)
            
            # Add filters based on summary type
            if summary_type == "sales_total":
                query += " AND doc_type = 'invoice' AND category = 'sales'"
            elif summary_type == "purchase_total":
                query += " AND doc_type = 'invoice' AND category = 'purchase'"
            elif summary_type == "gst_liability":
                query += " AND doc_type = 'invoice' AND category = 'sales'"
            elif summary_type == "itc_summary":
                query += " AND doc_type = 'invoice' AND category = 'purchase'"
            
            query += " GROUP BY doc_type, category, period"
            
            rows = await self.db.fetchall(query, tuple(params))
            
            # Aggregate results
            if summary_type == "sales_total":
                total = sum(row[4] or 0 for row in rows if row[1] == "sales")
                return {
                    "summary_type": "sales_total",
                    "period": period,
                    "total_amount": total,
                    "count": sum(row[3] for row in rows if row[1] == "sales")
                }
            
            elif summary_type == "purchase_total":
                total = sum(row[4] or 0 for row in rows if row[1] == "purchase")
                return {
                    "summary_type": "purchase_total",
                    "period": period,
                    "total_amount": total,
                    "count": sum(row[3] for row in rows if row[1] == "purchase")
                }
            
            elif summary_type == "gst_liability":
                total_cgst = sum(row[6] or 0 for row in rows if row[1] == "sales")
                total_sgst = sum(row[7] or 0 for row in rows if row[1] == "sales")
                total_igst = sum(row[8] or 0 for row in rows if row[1] == "sales")
                return {
                    "summary_type": "gst_liability",
                    "period": period,
                    "cgst": total_cgst,
                    "sgst": total_sgst,
                    "igst": total_igst,
                    "total": total_cgst + total_sgst + total_igst
                }
            
            elif summary_type == "itc_summary":
                total_cgst = sum(row[6] or 0 for row in rows if row[1] == "purchase")
                total_sgst = sum(row[7] or 0 for row in rows if row[1] == "purchase")
                total_igst = sum(row[8] or 0 for row in rows if row[1] == "purchase")
                return {
                    "summary_type": "itc_summary",
                    "period": period,
                    "cgst": total_cgst,
                    "sgst": total_sgst,
                    "igst": total_igst,
                    "total": total_cgst + total_sgst + total_igst
                }
            
            elif summary_type == "vendor_count":
                # Count unique vendors
                vendor_query = """
                    SELECT COUNT(DISTINCT json_extract(metadata, '$.vendor_name'))
                    FROM documents
                    WHERE client_id = ? AND doc_type = 'invoice'
                """
                vendor_params = [self.client_id]
                if period:
                    vendor_query += " AND period = ?"
                    vendor_params.append(period)
                
                vendor_rows = await self.db.fetchall(vendor_query, tuple(vendor_params))
                count = vendor_rows[0][0] if vendor_rows else 0
                
                return {
                    "summary_type": "vendor_count",
                    "period": period,
                    "count": count
                }
            
            return {
                "summary_type": summary_type,
                "period": period,
                "data": [{
                    "doc_type": row[0],
                    "category": row[1],
                    "period": row[2],
                    "count": row[3],
                    "total_amount": row[4] or 0
                } for row in rows]
            }
        except Exception as e:
            logger.error(f"Error in get_summary: {e}")
            return {
                "summary_type": summary_type,
                "error": str(e)
            }
    
    async def get_reconciliation(
        self,
        source1: str,
        source2: str,
        period: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get reconciliation data between two sources
        
        Returns structured comparison data (no raw file content)
        """
        try:
            # For now, return a basic structure
            # Full implementation would compare books vs GSTR-2B vs bank statements
            
            query = """
                SELECT 
                    json_extract(metadata, '$.invoice_number') as invoice_number,
                    json_extract(metadata, '$.amount') as amount,
                    json_extract(metadata, '$.vendor_name') as vendor_name,
                    json_extract(metadata, '$.date') as date
                FROM documents
                WHERE client_id = ? AND doc_type = 'invoice'
            """
            params = [self.client_id]
            
            if period:
                query += " AND period = ?"
                params.append(period)
            
            rows = await self.db.fetchall(query, tuple(params))
            
            # Basic reconciliation structure
            return {
                "source1": source1,
                "source2": source2,
                "period": period,
                "matched_count": len(rows),  # Placeholder
                "unmatched_items": [],  # Placeholder
                "differences": {
                    "amount_difference": 0.0,
                    "missing_in_source1": [],
                    "missing_in_source2": []
                }
            }
        except Exception as e:
            logger.error(f"Error in get_reconciliation: {e}")
            return {
                "source1": source1,
                "source2": source2,
                "error": str(e)
            }
    
    async def search_gst_rules(
        self,
        query: str,
        category: Optional[str] = None,
        limit: int = 10
    ) -> Dict[str, Any]:
        """
        Search GST rules from rules server
        
        Returns rule summaries (not full case law text)
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.rules_server_url}/api/rules/search",
                    json={
                        "query": query,
                        "category": category,
                        "limit": limit,
                        "use_vector_search": True
                    },
                    timeout=10.0
                )
                
                if response.status_code != 200:
                    return {
                        "count": 0,
                        "results": [],
                        "error": f"Rules server error: {response.status_code}"
                    }
                
                data = response.json()
                
                # Format results (summary only)
                formatted_results = []
                for rule in data:
                    # Truncate rule text to summary
                    rule_text = rule.get("rule_text", "")
                    summary = rule_text[:500] if len(rule_text) > 500 else rule_text
                    
                    formatted_results.append({
                        "rule_id": rule.get("rule_id"),
                        "name": rule.get("name"),
                        "summary": summary,
                        "citation": rule.get("citation"),
                        "category": rule.get("category"),
                        "similarity": rule.get("similarity_score")
                    })
                
                return {
                    "count": len(formatted_results),
                    "results": formatted_results,
                    "query": query
                }
        except Exception as e:
            logger.error(f"Error in search_gst_rules: {e}")
            return {
                "count": 0,
                "results": [],
                "error": str(e)
            }
    
    async def explain_rule(
        self,
        rule_type: str,
        scenario: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Explain a GST rule
        
        Returns rule explanation (summary format)
        """
        try:
            # Get rule from rules server
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.rules_server_url}/api/rules/{rule_type}",
                    timeout=10.0
                )
                
                if response.status_code != 200:
                    return {
                        "rule_id": rule_type,
                        "found": False,
                        "error": "Rule not found"
                    }
                
                rule = response.json()
                
                # Format explanation
                explanation = {
                    "rule_id": rule.get("rule_id"),
                    "name": rule.get("name"),
                    "explanation": rule.get("rule_text", "")[:1000],  # Truncate to 1000 chars
                    "citation": rule.get("citation"),
                    "category": rule.get("category"),
                    "scenario": scenario
                }
                
                return explanation
        except Exception as e:
            logger.error(f"Error in explain_rule: {e}")
            return {
                "rule_id": rule_type,
                "found": False,
                "error": str(e)
            }
    
    async def get_tds_certificate(
        self,
        certificate_number: Optional[str] = None,
        deductor_name: Optional[str] = None,
        period: Optional[str] = None,
        form_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get structured TDS certificate data
        
        Returns only allowed fields (no file paths, no raw content)
        """
        try:
            query = """
                SELECT 
                    id, client_id, period, doc_type, category,
                    metadata
                FROM documents
                WHERE client_id = ? AND doc_type = 'tds_certificate'
            """
            params = [self.client_id]
            
            conditions = []
            if certificate_number:
                conditions.append("json_extract(metadata, '$.certificate_number') = ?")
                params.append(certificate_number)
            
            if deductor_name:
                conditions.append("json_extract(metadata, '$.deductor_name') = ?")
                params.append(deductor_name)
            
            if period:
                conditions.append("period = ?")
                params.append(period)
            
            if form_type:
                conditions.append("json_extract(metadata, '$.form_type') = ?")
                params.append(form_type)
            
            if conditions:
                query += " AND " + " AND ".join(conditions)
            
            query += " LIMIT 1"
            
            rows = await self.db.fetchall(query, tuple(params))
            
            if not rows:
                return {
                    "found": False,
                    "certificate_number": certificate_number
                }
            
            row = rows[0]
            metadata = json.loads(row[4]) if row[4] else {}
            
            return {
                "found": True,
                "certificate_number": metadata.get("certificate_number"),
                "form_type": metadata.get("form_type"),
                "deductor_tan": metadata.get("deductor_tan"),
                "deductor_name": metadata.get("deductor_name"),
                "deductee_pan": metadata.get("deductee_pan"),
                "deductee_name": metadata.get("deductee_name"),
                "period": row[2],
                "sections": metadata.get("sections", []),
                "tds_amounts": metadata.get("tds_amounts", {}),
                "total_tds": metadata.get("total_tds", 0.0)
            }
        except Exception as e:
            logger.error(f"Error in get_tds_certificate: {e}")
            return {
                "found": False,
                "error": str(e)
            }
    
    async def get_tds_summary(
        self,
        summary_type: str,
        period: Optional[str] = None,
        section: Optional[str] = None,
        deductee_pan: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get aggregated TDS summary data
        
        Returns only summary statistics (no individual certificate details)
        """
        try:
            query = """
                SELECT 
                    doc_type,
                    category,
                    period,
                    COUNT(*) as count,
                    json_extract(metadata, '$.total_tds') as total_tds,
                    json_extract(metadata, '$.sections') as sections,
                    json_extract(metadata, '$.tds_amounts') as tds_amounts
                FROM documents
                WHERE client_id = ? AND doc_type = 'tds_certificate'
            """
            params = [self.client_id]
            
            conditions = []
            if period:
                conditions.append("period = ?")
                params.append(period)
            
            if deductee_pan:
                conditions.append("json_extract(metadata, '$.deductee_pan') = ?")
                params.append(deductee_pan)
            
            if conditions:
                query += " AND " + " AND ".join(conditions)
            
            query += " GROUP BY doc_type, category, period"
            
            rows = await self.db.fetchall(query, tuple(params))
            
            if summary_type == "deducted_total":
                total = sum(float(row[4] or 0) for row in rows)
                return {
                    "summary_type": "deducted_total",
                    "period": period,
                    "total_tds": total,
                    "count": sum(row[3] for row in rows)
                }
            
            elif summary_type == "deposited_total":
                # Query challans for deposited amount
                challan_query = """
                    SELECT 
                        SUM(CAST(json_extract(metadata, '$.deposit_amount') AS REAL)) as total_deposited
                    FROM documents
                    WHERE client_id = ? AND doc_type = 'tds_challan'
                """
                challan_params = [self.client_id]
                if period:
                    challan_query += " AND period = ?"
                    challan_params.append(period)
                
                challan_rows = await self.db.fetchall(challan_query, tuple(challan_params))
                total_deposited = challan_rows[0][0] if challan_rows and challan_rows[0][0] else 0.0
                
                return {
                    "summary_type": "deposited_total",
                    "period": period,
                    "total_deposited": total_deposited
                }
            
            elif summary_type == "certificate_count":
                return {
                    "summary_type": "certificate_count",
                    "period": period,
                    "count": sum(row[3] for row in rows)
                }
            
            elif summary_type == "section_wise":
                # Aggregate by section
                section_totals = {}
                section_counts = {}
                
                for row in rows:
                    sections_json = row[5]
                    amounts_json = row[6]
                    
                    if sections_json:
                        try:
                            sections = json.loads(sections_json) if isinstance(sections_json, str) else sections_json
                            amounts = json.loads(amounts_json) if isinstance(amounts_json, str) else amounts_json
                            
                            if isinstance(sections, list):
                                for sec in sections:
                                    if section and sec != section:
                                        continue
                                    section_totals[sec] = section_totals.get(sec, 0.0) + float(amounts.get(sec, 0.0) if isinstance(amounts, dict) else 0.0)
                                    section_counts[sec] = section_counts.get(sec, 0) + 1
                        except (json.JSONDecodeError, TypeError):
                            pass
                
                return {
                    "summary_type": "section_wise",
                    "period": period,
                    "section": section,
                    "section_totals": section_totals,
                    "section_counts": section_counts
                }
            
            elif summary_type == "return_status":
                # Query returns for status
                return_query = """
                    SELECT 
                        json_extract(metadata, '$.return_type') as return_type,
                        json_extract(metadata, '$.filing_status') as filing_status,
                        json_extract(metadata, '$.filing_date') as filing_date,
                        json_extract(metadata, '$.quarter') as quarter
                    FROM documents
                    WHERE client_id = ? AND doc_type = 'tds_return'
                """
                return_params = [self.client_id]
                if period:
                    return_query += " AND period = ?"
                    return_params.append(period)
                
                return_rows = await self.db.fetchall(return_query, tuple(return_params))
                
                status_summary = {}
                for row in return_rows:
                    return_type = row[0]
                    status = row[1] or "pending"
                    if return_type:
                        if return_type not in status_summary:
                            status_summary[return_type] = {"filed": 0, "pending": 0}
                        if status == "filed":
                            status_summary[return_type]["filed"] += 1
                        else:
                            status_summary[return_type]["pending"] += 1
                
                return {
                    "summary_type": "return_status",
                    "period": period,
                    "status": status_summary
                }
            
            return {
                "summary_type": summary_type,
                "period": period,
                "data": [{
                    "doc_type": row[0],
                    "category": row[1],
                    "period": row[2],
                    "count": row[3]
                } for row in rows]
            }
        except Exception as e:
            logger.error(f"Error in get_tds_summary: {e}")
            return {
                "summary_type": summary_type,
                "error": str(e)
            }
    
    async def get_tds_reconciliation(
        self,
        source1: str,
        source2: str,
        period: Optional[str] = None,
        form_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Reconcile TDS data between two sources
        
        Returns structured comparison data (no raw file content)
        """
        try:
            # Get data from source1
            source1_query = """
                SELECT 
                    json_extract(metadata, '$.certificate_number') as certificate_number,
                    json_extract(metadata, '$.total_tds') as total_tds,
                    json_extract(metadata, '$.deductee_pan') as deductee_pan,
                    json_extract(metadata, '$.period') as period
                FROM documents
                WHERE client_id = ? AND doc_type = ?
            """
            source1_params = [self.client_id]
            
            if source1 == "certificates":
                source1_params.append("tds_certificate")
            elif source1 == "returns":
                source1_params.append("tds_return")
            elif source1 == "challans":
                source1_params.append("tds_challan")
            else:
                source1_params.append("tds_certificate")  # Default
            
            if period:
                source1_query += " AND period = ?"
                source1_params.append(period)
            
            source1_rows = await self.db.fetchall(source1_query, tuple(source1_params))
            
            # Get data from source2
            source2_query = """
                SELECT 
                    json_extract(metadata, '$.certificate_number') as certificate_number,
                    json_extract(metadata, '$.total_tds') as total_tds,
                    json_extract(metadata, '$.deductee_pan') as deductee_pan,
                    json_extract(metadata, '$.period') as period
                FROM documents
                WHERE client_id = ? AND doc_type = ?
            """
            source2_params = [self.client_id]
            
            if source2 == "returns":
                source2_params.append("tds_return")
            elif source2 == "challans":
                source2_params.append("tds_challan")
            elif source2 == "certificates":
                source2_params.append("tds_certificate")
            else:
                source2_params.append("tds_return")  # Default
            
            if period:
                source2_query += " AND period = ?"
                source2_params.append(period)
            
            source2_rows = await self.db.fetchall(source2_query, tuple(source2_params))
            
            # Simple matching logic (can be enhanced)
            source1_dict = {}
            for row in source1_rows:
                key = f"{row[0]}_{row[2]}" if row[0] and row[2] else str(row[0] or row[2] or len(source1_dict))
                source1_dict[key] = float(row[1] or 0)
            
            source2_dict = {}
            for row in source2_rows:
                key = f"{row[0]}_{row[2]}" if row[0] and row[2] else str(row[0] or row[2] or len(source2_dict))
                source2_dict[key] = float(row[1] or 0)
            
            matched = []
            missing_in_source1 = []
            missing_in_source2 = []
            differences = []
            
            for key, amount1 in source1_dict.items():
                if key in source2_dict:
                    amount2 = source2_dict[key]
                    if abs(amount1 - amount2) > 0.01:  # Allow small rounding differences
                        differences.append({
                            "key": key,
                            "source1_amount": amount1,
                            "source2_amount": amount2,
                            "difference": amount1 - amount2
                        })
                    else:
                        matched.append({"key": key, "amount": amount1})
                else:
                    missing_in_source2.append({"key": key, "amount": amount1})
            
            for key, amount2 in source2_dict.items():
                if key not in source1_dict:
                    missing_in_source1.append({"key": key, "amount": amount2})
            
            return {
                "source1": source1,
                "source2": source2,
                "period": period,
                "form_type": form_type,
                "matched_count": len(matched),
                "matched_items": matched[:10],  # Limit to 10 for summary
                "unmatched_items": {
                    "missing_in_source1": missing_in_source1[:10],
                    "missing_in_source2": missing_in_source2[:10]
                },
                "differences": differences[:10],
                "total_difference": sum(d["difference"] for d in differences)
            }
        except Exception as e:
            logger.error(f"Error in get_tds_reconciliation: {e}")
            return {
                "source1": source1,
                "source2": source2,
                "error": str(e)
            }
    
    async def search_tds_rules(
        self,
        query: str,
        section: Optional[str] = None,
        category: Optional[str] = None,
        limit: int = 10
    ) -> Dict[str, Any]:
        """
        Search TDS rules from rules server
        
        Returns rule summaries (not full case law text)
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.rules_server_url}/api/rules/search",
                    json={
                        "query": query,
                        "category": category or "tds",
                        "section": section,
                        "limit": limit,
                        "use_vector_search": True
                    },
                    timeout=10.0
                )
                
                if response.status_code != 200:
                    return {
                        "count": 0,
                        "results": [],
                        "error": f"Rules server error: {response.status_code}"
                    }
                
                data = response.json()
                
                # Format results (summary only)
                formatted_results = []
                for rule in data:
                    rule_text = rule.get("rule_text", "")
                    summary = rule_text[:500] if len(rule_text) > 500 else rule_text
                    
                    formatted_results.append({
                        "rule_id": rule.get("rule_id"),
                        "name": rule.get("name"),
                        "summary": summary,
                        "citation": rule.get("citation"),
                        "category": rule.get("category"),
                        "section": rule.get("section"),
                        "similarity": rule.get("similarity_score")
                    })
                
                return {
                    "count": len(formatted_results),
                    "results": formatted_results,
                    "query": query
                }
        except Exception as e:
            logger.error(f"Error in search_tds_rules: {e}")
            return {
                "count": 0,
                "results": [],
                "error": str(e)
            }
    
    async def explain_tds_rule(
        self,
        section: str,
        scenario: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Explain a TDS section and its applicability
        
        Returns rule explanation (summary format)
        """
        try:
            # Get rule from rules server
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.rules_server_url}/api/rules/tds/{section}",
                    timeout=10.0
                )
                
                if response.status_code != 200:
                    return {
                        "section": section,
                        "found": False,
                        "error": "Rule not found"
                    }
                
                rule = response.json()
                
                # Format explanation
                explanation = {
                    "section": section,
                    "name": rule.get("name"),
                    "explanation": rule.get("rule_text", "")[:1000],  # Truncate to 1000 chars
                    "citation": rule.get("citation"),
                    "category": rule.get("category"),
                    "rate": rule.get("rate"),
                    "threshold": rule.get("threshold"),
                    "exemptions": rule.get("exemptions", []),
                    "scenario": scenario
                }
                
                return explanation
        except Exception as e:
            logger.error(f"Error in explain_tds_rule: {e}")
            return {
                "section": section,
                "found": False,
                "error": str(e)
            }
    
    async def get_tds_return_status(
        self,
        return_type: str,
        period: Optional[str] = None,
        quarter: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get TDS return filing status from locally uploaded documents
        
        Returns filing status, due dates, pending items
        """
        try:
            query = """
                SELECT 
                    id, period, metadata
                FROM documents
                WHERE client_id = ? AND doc_type = 'tds_return'
                AND json_extract(metadata, '$.return_type') = ?
            """
            params = [self.client_id, return_type]
            
            if period:
                query += " AND period = ?"
                params.append(period)
            
            if quarter:
                query += " AND json_extract(metadata, '$.quarter') = ?"
                params.append(quarter)
            
            rows = await self.db.fetchall(query, tuple(params))
            
            if not rows:
                return {
                    "return_type": return_type,
                    "period": period,
                    "quarter": quarter,
                    "found": False,
                    "status": "not_found",
                    "message": "No return documents found for the specified criteria"
                }
            
            # Get the most recent return
            row = rows[0]
            metadata = json.loads(row[2]) if row[2] else {}
            
            filing_status = metadata.get("filing_status", "pending")
            filing_date = metadata.get("filing_date")
            acknowledgment_number = metadata.get("acknowledgment_number")
            
            # Calculate due date (simplified - would need proper quarter logic)
            due_date = metadata.get("due_date")
            
            return {
                "return_type": return_type,
                "period": period or row[1],
                "quarter": quarter or metadata.get("quarter"),
                "found": True,
                "status": filing_status,
                "filing_date": filing_date,
                "acknowledgment_number": acknowledgment_number,
                "due_date": due_date,
                "is_overdue": filing_status == "pending" and due_date and due_date < datetime.now().isoformat() if due_date else False
            }
        except Exception as e:
            logger.error(f"Error in get_tds_return_status: {e}")
            return {
                "return_type": return_type,
                "found": False,
                "error": str(e)
            }
