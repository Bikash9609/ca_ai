"""
Script to populate initial GST rules into the database
"""

import asyncio
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from server.database.connection import DatabasePool
from server.services.rules_populator import RulesPopulator


async def main():
    """Main function to populate rules"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Populate GST rules into database")
    parser.add_argument("--version", default="1.0.0", help="Version string for rules")
    parser.add_argument("--force", action="store_true", help="Force overwrite existing rules")
    parser.add_argument("--vectorize", action="store_true", default=True, help="Generate embeddings (default: True)")
    parser.add_argument("--host", default=os.getenv("DB_HOST", "localhost"), help="Database host")
    parser.add_argument("--port", type=int, default=int(os.getenv("DB_PORT", "5432")), help="Database port")
    parser.add_argument("--database", default=os.getenv("DB_NAME", "gst_rules_db"), help="Database name")
    parser.add_argument("--user", default=os.getenv("DB_USER", "postgres"), help="Database user")
    parser.add_argument("--password", default=os.getenv("DB_PASSWORD", "postgres"), help="Database password")
    
    args = parser.parse_args()
    
    # Create database pool
    db_pool = DatabasePool(
        host=args.host,
        port=args.port,
        database=args.database,
        user=args.user,
        password=args.password,
    )
    
    try:
        await db_pool.create_pool()
        print(f"Connected to database: {args.database}")
        
        # Create populator
        populator = RulesPopulator(db_pool)
        
        if args.vectorize:
            # Populate and vectorize
            result = await populator.populate_and_vectorize(args.version, args.force)
            print(f"✓ Populated {result['rules_populated']} rules")
            print(f"✓ Created {result['embeddings_created']} embeddings")
        else:
            # Populate only
            count = await populator.populate_initial_rules(args.version, args.force)
            print(f"✓ Populated {count} rules")
        
        print(f"\nRules version {args.version} ready!")
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        await db_pool.close_pool()


if __name__ == "__main__":
    asyncio.run(main())
