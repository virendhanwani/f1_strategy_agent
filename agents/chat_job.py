"""Run one chat independently of Streamlit's interruptible render thread."""
import asyncio
import logging
from queue import Queue
from threading import Event, Lock, Thread

logger = logging.getLogger(__name__)


class ChatJob:
    def __init__(self, stream, question, history):
        self.events = Queue()
        self.done = Event()
        self.result = None
        self._lock = Lock()
        self._cancelled = False
        self._loop = None
        self._task = None
        self._thread = Thread(target=self._run, args=(stream, question, list(history)), daemon=True)
        self._thread.start()

    def cancel(self):
        with self._lock:
            self._cancelled = True
            if self._loop is not None and self._task is not None:
                try:
                    self._loop.call_soon_threadsafe(self._task.cancel)
                except RuntimeError:
                    # asyncio.run may have just closed the loop after completion.
                    if not self._loop.is_closed():
                        raise

    def _run(self, stream, question, history):
        async def consume():
            with self._lock:
                self._loop = asyncio.get_running_loop()
                self._task = asyncio.current_task()
                cancelled = self._cancelled
            if cancelled:
                raise asyncio.CancelledError
            async for event in stream(question, history):
                if event['type'] in ('complete', 'error'):
                    self.result = event
                else:
                    self.events.put(event)

        try:
            asyncio.run(consume())
            if self.result is None:
                self.result = {'type': 'error', 'message': 'The response ended before an answer was ready.'}
        except asyncio.CancelledError:
            self.result = {'type': 'error', 'message': 'The request was cancelled. Please send the question again.'}
        except Exception:
            logger.exception('Background chat request failed')
            self.result = {'type': 'error', 'message': 'The request could not be completed. Please try again later.'}
        finally:
            with self._lock:
                self._loop = None
                self._task = None
            self.done.set()
