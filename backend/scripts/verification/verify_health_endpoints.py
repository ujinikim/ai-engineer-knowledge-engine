import asyncio
from pathlib import Path
import sys

from httpx import ASGITransport, AsyncClient

sys.path.append(str(Path(__file__).resolve().parents[2]))

from app.main import app


async def verify() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://health-test") as client:
        live_response = await client.get("/health/live")
        ready_response = await client.get("/health/ready")

    if live_response.status_code != 200 or live_response.json() != {"status": "alive"}:
        raise RuntimeError("The liveness endpoint did not report an alive API process.")
    if ready_response.status_code != 200 or ready_response.json().get("status") != "ready":
        raise RuntimeError(
            f"The readiness endpoint did not accept the migrated CI database: "
            f"{ready_response.json()}"
        )

    print(
        f"Liveness and database readiness checks passed: "
        f"live={live_response.json()}, ready={ready_response.json()}"
    )


def main() -> None:
    asyncio.run(verify())


if __name__ == "__main__":
    main()
