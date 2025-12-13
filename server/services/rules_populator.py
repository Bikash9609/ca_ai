"""
Service to populate initial GST rules into the database
"""

import json
import logging
from typing import List, Dict, Any
from datetime import date
from server.database.connection import DatabasePool
from server.services.rules_data import INITIAL_RULES
from server.services.embedding import RulesEmbeddingGenerator

logger = logging.getLogger(__name__)


class RulesPopulator:
    """Populate initial rules into the database"""
    
    def __init__(self, db_pool: DatabasePool):
        """
        Initialize rules populator
        
        Args:
            db_pool: Database connection pool
        """
        self.db_pool = db_pool
        self.embedding_generator = None
    
    async def populate_initial_rules(self, version: str = "1.0.0", force: bool = False) -> int:
        """
        Populate initial GST rules
        
        Args:
            version: Version string for the rules
            force: If True, delete existing rules before populating
            
        Returns:
            Number of rules populated
        """
        try:
            # Check if rules already exist
            existing_count = await self.db_pool.fetchval(
                "SELECT COUNT(*) FROM gst_rules WHERE version = $1",
                version
            )
            
            if existing_count > 0 and not force:
                logger.info(f"Rules version {version} already exists. Use force=True to overwrite.")
                return existing_count
            
            if force:
                # Delete existing rules for this version
                await self.db_pool.execute(
                    "DELETE FROM gst_rule_logic WHERE rule_id IN (SELECT rule_id FROM gst_rules WHERE version = $1)",
                    version
                )
                await self.db_pool.execute(
                    "DELETE FROM gst_rule_embeddings WHERE rule_id IN (SELECT id FROM gst_rules WHERE version = $1)",
                    version
                )
                await self.db_pool.execute(
                    "DELETE FROM gst_rules WHERE version = $1",
                    version
                )
                logger.info(f"Deleted existing rules for version {version}")
            
            # Insert rules
            count = 0
            for rule_data in INITIAL_RULES:
                rule_id = rule_data["rule_id"]
                
                # Insert into gst_rules
                rule_db_id = await self.db_pool.fetchval(
                    """
                    INSERT INTO gst_rules (
                        rule_id, name, rule_text, citation, circular_number,
                        effective_from, effective_to, category, version, is_active
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                    ON CONFLICT (rule_id) DO UPDATE SET
                        name = EXCLUDED.name,
                        rule_text = EXCLUDED.rule_text,
                        citation = EXCLUDED.citation,
                        circular_number = EXCLUDED.circular_number,
                        effective_from = EXCLUDED.effective_from,
                        effective_to = EXCLUDED.effective_to,
                        category = EXCLUDED.category,
                        version = EXCLUDED.version,
                        updated_at = NOW()
                    RETURNING id
                    """,
                    rule_data["rule_id"],
                    rule_data["name"],
                    rule_data["rule_text"],
                    rule_data.get("citation"),
                    rule_data.get("circular_number"),
                    rule_data.get("effective_from"),
                    rule_data.get("effective_to"),
                    rule_data.get("category"),
                    version,
                    True
                )
                
                # Insert rule logic if present
                if rule_data.get("rule_logic"):
                    logic = rule_data["rule_logic"]
                    await self.db_pool.execute(
                        """
                        INSERT INTO gst_rule_logic (
                            rule_id, condition_type, condition_logic, action_type,
                            action_percentage, action_amount_formula, priority, is_active
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                        ON CONFLICT DO NOTHING
                        """,
                        rule_id,
                        logic["condition_type"],
                        json.dumps(logic["condition_logic"]),
                        logic["action_type"],
                        logic.get("action_percentage"),
                        logic.get("action_amount_formula"),
                        logic.get("priority", 0),
                        True
                    )
                
                count += 1
                logger.debug(f"Inserted rule: {rule_id}")
            
            # Create version entry
            await self.db_pool.execute(
                """
                INSERT INTO gst_rule_versions (version, changelog, rules_count)
                VALUES ($1, $2, $3)
                ON CONFLICT (version) DO UPDATE SET
                    changelog = EXCLUDED.changelog,
                    rules_count = EXCLUDED.rules_count,
                    released_at = NOW()
                """,
                version,
                f"Initial rules population - {count} rules",
                count
            )
            
            logger.info(f"Populated {count} rules for version {version}")
            return count
            
        except Exception as e:
            logger.error(f"Error populating rules: {e}")
            raise
    
    async def vectorize_rules(self, version: str = "1.0.0") -> int:
        """
        Generate embeddings and store them for all rules
        
        Args:
            version: Version string for the rules
            
        Returns:
            Number of rules vectorized
        """
        try:
            if self.embedding_generator is None:
                self.embedding_generator = RulesEmbeddingGenerator()
            
            # Get all rules for this version
            rules = await self.db_pool.fetch(
                "SELECT id, rule_id, rule_text, name FROM gst_rules WHERE version = $1 AND is_active = TRUE",
                version
            )
            
            if not rules:
                logger.warning(f"No rules found for version {version}")
                return 0
            
            # Delete existing embeddings for this version
            await self.db_pool.execute(
                "DELETE FROM gst_rule_embeddings WHERE rule_id IN (SELECT id FROM gst_rules WHERE version = $1)",
                version
            )
            
            # Generate embeddings
            texts_to_embed = []
            rule_ids = []
            
            for rule in rules:
                # Combine name and rule_text for better semantic search
                combined_text = f"{rule['name']}\n\n{rule['rule_text']}"
                texts_to_embed.append(combined_text)
                rule_ids.append(rule['id'])
            
            # Generate embeddings in batch
            embeddings = self.embedding_generator.generate_batch(texts_to_embed)
            
            # Insert embeddings
            count = 0
            for rule_id, embedding, text in zip(rule_ids, embeddings, texts_to_embed):
                # Convert list to PostgreSQL vector format
                embedding_str = "[" + ",".join(map(str, embedding)) + "]"
                
                await self.db_pool.execute(
                    """
                    INSERT INTO gst_rule_embeddings (rule_id, embedding, chunk_text)
                    VALUES ($1, $2::vector, $3)
                    """,
                    rule_id,
                    embedding_str,
                    text[:1000]  # Store first 1000 chars as chunk_text
                )
                count += 1
            
            logger.info(f"Vectorized {count} rules for version {version}")
            return count
            
        except Exception as e:
            logger.error(f"Error vectorizing rules: {e}")
            raise
    
    async def populate_and_vectorize(self, version: str = "1.0.0", force: bool = False) -> Dict[str, int]:
        """
        Populate rules and vectorize them in one operation
        
        Args:
            version: Version string for the rules
            force: If True, delete existing rules before populating
            
        Returns:
            Dictionary with counts of rules populated and vectorized
        """
        rules_count = await self.populate_initial_rules(version, force)
        embeddings_count = await self.vectorize_rules(version)
        
        return {
            "rules_populated": rules_count,
            "embeddings_created": embeddings_count
        }
