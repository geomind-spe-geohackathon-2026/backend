import asyncio
import logging

from src.core.logging.logger import DisconnectFilter


def record_with(error: BaseException) -> logging.LogRecord:
    return logging.LogRecord(
        "sqlalchemy.pool.impl.AsyncAdaptedQueuePool",
        logging.ERROR,
        __file__,
        1,
        "Exception terminating connection",
        None,
        (type(error), error, None),
    )


def test_a_client_that_disconnects_leaves_no_traceback() -> None:
    assert not DisconnectFilter().filter(record_with(asyncio.CancelledError()))


def test_other_failures_of_the_pool_are_still_logged() -> None:
    assert DisconnectFilter().filter(record_with(RuntimeError("broken")))
