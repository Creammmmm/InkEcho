"""Qt event-loop ownership of Python asynchronous generator cleanup."""

import sys

from qasync import QEventLoop


class ManagedQtEventLoop(QEventLoop):
    """Keep CPython async-generator hooks active while Qt runs Python tasks.

    qasync 0.28 overrides run_forever without CPython's hook setup. HTTPX's
    nested streaming generators can then be synchronously finalized despite
    needing asynchronous cleanup. Delegate to this loop's standard CPython
    hooks here, rather than changing thread-local hooks around an HTTP request.
    The two private hook methods are intentionally confined to this adapter.
    """

    def run_forever(self):
        previous = sys.get_asyncgen_hooks()
        sys.set_asyncgen_hooks(
            firstiter=self._asyncgen_firstiter_hook,
            finalizer=self._asyncgen_finalizer_hook,
        )
        try:
            return super().run_forever()
        finally:
            sys.set_asyncgen_hooks(*previous)

    def __exit__(self, *args):
        try:
            if not self.is_closed():
                self.run_until_complete(self.shutdown_asyncgens())
        finally:
            super().__exit__(*args)
