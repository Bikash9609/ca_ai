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
