from dataclasses import dataclass
from redis.client import Redis
from vehicle_data import settings


# @dataclass
# class KeyStore:
#     host: str = settings.REDIS_HOST
#     redis_client: Redis = Redis(host=host, port=settings.REDIS_PORT)
