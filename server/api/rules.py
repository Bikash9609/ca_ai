"""
Rules API routes
"""

from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel
from typing import Optional, List
from datetime import date
from server.database.connection import DatabasePool
from server.services.embedding import RulesEmbeddingGenerator

router = APIRouter()


class RuleResponse(BaseModel):
    id: int
    rule_id: str
    name: str
    rule_text: str
    citation: Optional[str]
    circular_number: Optional[str]
    effective_from: Optional[date]
    effective_to: Optional[date]
    category: Optional[str]
    version: str
    is_active: bool


class RuleSearchRequest(BaseModel):
    query: str
    category: Optional[str] = None
    limit: int = 10
    use_vector_search: bool = True


class RuleSearchResponse(BaseModel):
    id: int
    rule_id: str
    name: str
    rule_text: str
    citation: Optional[str]
    category: Optional[str]
    version: str
    similarity_score: Optional[float] = None


def get_db_pool() -> DatabasePool:
    """Dependency to get database pool"""
    from server.main import db_pool
    if db_pool is None:
        raise HTTPException(status_code=500, detail="Database pool not initialized")
    return db_pool


@router.get("/rules", response_model=List[RuleResponse])
async def get_rules(
    category: Optional[str] = Query(None),
    version: Optional[str] = Query(None),
    is_active: bool = Query(True),
    pool: DatabasePool = Depends(get_db_pool)
):
    """Get rules with optional filtering"""
    
    query = "SELECT * FROM gst_rules WHERE is_active = $1"
    params = [is_active]
    
    if category:
        query += " AND category = $2"
        params.append(category)
    else:
        query = query.replace("$2", "$1")
    
    if version:
        query += f" AND version = ${len(params) + 1}"
        params.append(version)
    
    query += " ORDER BY created_at DESC"
    
    rows = await pool.fetch(query, *params)
    
    return [
        RuleResponse(
            id=row["id"],
            rule_id=row["rule_id"],
            name=row["name"],
            rule_text=row["rule_text"],
            citation=row["citation"],
            circular_number=row["circular_number"],
            effective_from=row["effective_from"],
            effective_to=row["effective_to"],
            category=row["category"],
            version=row["version"],
            is_active=row["is_active"],
        )
        for row in rows
    ]


@router.get("/rules/{rule_id}", response_model=RuleResponse)
async def get_rule_by_id(rule_id: str, pool: DatabasePool = Depends(get_db_pool)):
    """Get a specific rule by rule_id"""
    
    row = await pool.fetchrow(
        "SELECT * FROM gst_rules WHERE rule_id = $1",
        rule_id
    )
    
    if not row:
        raise HTTPException(status_code=404, detail="Rule not found")
    
    return RuleResponse(
        id=row["id"],
        rule_id=row["rule_id"],
        name=row["name"],
        rule_text=row["rule_text"],
        citation=row["citation"],
        circular_number=row["circular_number"],
        effective_from=row["effective_from"],
        effective_to=row["effective_to"],
        category=row["category"],
        version=row["version"],
        is_active=row["is_active"],
    )


@router.get("/rules/category/{category}", response_model=List[RuleResponse])
async def get_rules_by_category(
    category: str,
    version: Optional[str] = Query(None),
    pool: DatabasePool = Depends(get_db_pool)
):
    """Get rules by category"""
    
    query = "SELECT * FROM gst_rules WHERE category = $1 AND is_active = TRUE"
    params = [category]
    
    if version:
        query += " AND version = $2"
        params.append(version)
    
    query += " ORDER BY created_at DESC"
    
    rows = await pool.fetch(query, *params)
    
    return [
        RuleResponse(
            id=row["id"],
            rule_id=row["rule_id"],
            name=row["name"],
            rule_text=row["rule_text"],
            citation=row["citation"],
            circular_number=row["circular_number"],
            effective_from=row["effective_from"],
            effective_to=row["effective_to"],
            category=row["category"],
            version=row["version"],
            is_active=row["is_active"],
        )
        for row in rows
    ]


@router.post("/rules/search", response_model=List[RuleSearchResponse])
async def search_rules(
    request: RuleSearchRequest,
    pool: DatabasePool = Depends(get_db_pool)
):
    """Search rules using vector similarity search or full-text search"""
    
    if request.use_vector_search:
        # Try vector search first
        try:
            embedding_gen = RulesEmbeddingGenerator()
            query_embedding = embedding_gen.generate(request.query)
            embedding_str = "[" + ",".join(map(str, query_embedding)) + "]"
            
            # Vector similarity search
            vector_query = """
                SELECT 
                    r.id, r.rule_id, r.name, r.rule_text, r.citation, 
                    r.category, r.version,
                    1 - (e.embedding <=> $1::vector) as similarity_score
                FROM gst_rules r
                INNER JOIN gst_rule_embeddings e ON r.id = e.rule_id
                WHERE r.is_active = TRUE
            """
            params = [embedding_str]
            
            if request.category:
                vector_query += " AND r.category = $2"
                params.append(request.category)
            
            vector_query += f" ORDER BY e.embedding <=> $1::vector LIMIT ${len(params) + 1}"
            params.append(request.limit)
            
            rows = await pool.fetch(vector_query, *params)
            
            if rows:
                return [
                    RuleSearchResponse(
                        id=row["id"],
                        rule_id=row["rule_id"],
                        name=row["name"],
                        rule_text=row["rule_text"],
                        citation=row["citation"],
                        category=row["category"],
                        version=row["version"],
                        similarity_score=float(row["similarity_score"]) if row["similarity_score"] else None,
                    )
                    for row in rows
                ]
        except Exception as e:
            # Fall back to full-text search if vector search fails
            pass
    
    # Fallback to full-text search
    query = """
        SELECT 
            id, rule_id, name, rule_text, citation, category, version,
            ts_rank(to_tsvector('english', rule_text || ' ' || name), plainto_tsquery('english', $1)) as similarity_score
        FROM gst_rules
        WHERE is_active = TRUE
        AND to_tsvector('english', rule_text || ' ' || name) @@ plainto_tsquery('english', $1)
    """
    params = [request.query]
    
    if request.category:
        query += " AND category = $2"
        params.append(request.category)
    
    query += f" ORDER BY ts_rank(to_tsvector('english', rule_text || ' ' || name), plainto_tsquery('english', $1)) DESC LIMIT ${len(params) + 1}"
    params.append(request.limit)
    
    rows = await pool.fetch(query, *params)
    
    return [
        RuleSearchResponse(
            id=row["id"],
            rule_id=row["rule_id"],
            name=row["name"],
            rule_text=row["rule_text"],
            citation=row["citation"],
            category=row["category"],
            version=row["version"],
            similarity_score=float(row["similarity_score"]) if row.get("similarity_score") else None,
        )
        for row in rows
    ]
