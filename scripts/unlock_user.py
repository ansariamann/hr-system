import sys
import os
import asyncio

# Add src to path
sys.path.append(os.path.join(os.getcwd(), "src"))

from ats_backend.core.redis import redis_manager, get_redis

async def unlock_user(email):
    print(f"Initializing Redis...")
    try:
        await redis_manager.initialize()
    except Exception as e:
        print(f"Failed to initialize Redis: {e}")
        return

    print(f"Unlocking user: {email}")
    try:
        redis = await get_redis()
        
        # Flush all keys to ensure we catch IP-based rate limits too
        print("Flushing all Redis keys...")
        await redis.flushall()
        print("Redis flushed.")
            
    except Exception as e:
        print(f"Error: {e}")
    finally:
        await redis_manager.close()

if __name__ == "__main__":
    asyncio.run(unlock_user("admin@acmecorp.com"))
