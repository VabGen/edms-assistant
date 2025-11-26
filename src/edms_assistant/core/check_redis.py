import asyncio
from redis.asyncio import Redis

async def main():
    redis = Redis.from_url("redis://127.0.0.1:6379/0", decode_responses=True)
    keys = await redis.keys("chat:session:*")
    print("Найдены сессии:", keys)

    for key in keys:
        value = await redis.get(key)
        print(f"\n{key}:\n{value}")

    await redis.aclose()

if __name__ == "__main__":
    asyncio.run(main())