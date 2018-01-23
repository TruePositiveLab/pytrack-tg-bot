import asyncio
import logging
from functools import partial

from youtrack.connection import Connection as ConnectionSync


class Connection(ConnectionSync):

    def __init__(self, url,
                 login=None, password=None,
                 proxy_info=None, api_key=None,
                 loop=None):
        self.loop = loop or asyncio.get_event_loop()
        self.semaphore = asyncio.Semaphore(1)
        self.logger = logging.getLogger("youtrack")

        super().__init__(url, login, password, proxy_info, api_key)

    def __getattribute__(self, name):
        if name[0] != '_':
            fun = getattr(super(), name, None)
            if fun is not None and callable(fun):
                return partial(self._async, fun)
        return super().__getattribute__(name)

    async def _async(self, fun, *args, **kwargs):
        try:
            await self.semaphore.acquire()
            return await self.loop.run_in_executor(None,
                                                   partial(fun, *args, **kwargs))
        finally:
            self.semaphore.release()
