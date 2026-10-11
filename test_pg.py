import asyncio
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

async def main():
    try:
        async with AsyncPostgresSaver.from_conn_string("postgresql://postgres:postgres@localhost:5432/cold_email") as memory:
            print(memory)
    except Exception as e:
        print("Error:", e)
    
asyncio.run(main())
