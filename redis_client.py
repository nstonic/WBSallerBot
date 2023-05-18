from redis.client import Redis


class RedisClient:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, **kwargs):
        if kwargs:
            self.client = Redis(
                host=kwargs['host'],
                port=kwargs['port'],
                password=kwargs['password']
            )
