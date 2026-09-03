"""Exercise FileResponse through real loopback HTTP, without recordings or a browser.

Run in an isolated environment with starlette==1.6.0, uvicorn==0.52.4,
httptools==0.7.1, and anyio==4.15.0. JSON goes to stdout.
The disconnect listener is a diagnostic intervention, not a production patch.
"""

import asyncio
import hashlib
import importlib.metadata
import json
import os
import socket
import tempfile
import time
from pathlib import Path

import anyio
import uvicorn
from starlette.responses import FileResponse

MIB = 1024 * 1024


async def exercise(path, size, name, limit, abort, listen):
    done = asyncio.Event()
    client_closed = False
    stats = {
        "condition": name,
        "fixtureBytes": size,
        "requestedRange": f"bytes=0-{limit - 1}" if limit else "bytes=0-",
        "readTargetBytes": 3 * MIB,
        "asgiBodyBytes": 0,
        "asgiBodyCalls": 0,
        "bytesSubmittedAfterClientClose": 0,
        "disconnectReceivedByListener": False,
    }

    async def app(scope, receive, send):
        stats["asgiSpecVersion"] = scope["asgi"]["spec_version"]

        async def observed_send(message):
            if message["type"] == "http.response.body":
                length = len(message.get("body", b""))
                stats["asgiBodyBytes"] += length
                stats["asgiBodyCalls"] += 1
                if client_closed:
                    stats["bytesSubmittedAfterClientClose"] += length
            await send(message)
            # Give the real client and transport callbacks a scheduling turn;
            # no synthetic time delay or replacement of Uvicorn.send is used.
            await asyncio.sleep(0)

        response = FileResponse(path)
        try:
            if listen:
                async with anyio.create_task_group() as group:
                    async def serve():
                        await response(scope, receive, observed_send)
                        group.cancel_scope.cancel()

                    group.start_soon(serve)
                    while True:
                        if (await receive())["type"] == "http.disconnect":
                            stats["disconnectReceivedByListener"] = True
                            group.cancel_scope.cancel()
                            break
            else:
                await response(scope, receive, observed_send)
        finally:
            done.set()

    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    config = uvicorn.Config(
        app, http="httptools", lifespan="off", log_level="error", access_log=False
    )
    server = uvicorn.Server(config)
    task = asyncio.create_task(server.serve(sockets=[sock]))
    writer = None
    try:
        async with asyncio.timeout(10):
            while not server.started:
                if task.done():
                    await task
                    raise RuntimeError("Server exited before listening")
                await asyncio.sleep(0.001)
            reader, writer = await asyncio.open_connection("127.0.0.1", port)
            writer.write(
                (
                    "GET /fixture HTTP/1.1\r\nHost: localhost\r\n"
                    f"Range: {stats['requestedRange']}\r\nConnection: close\r\n\r\n"
                ).encode()
            )
            await writer.drain()
            headers = (await reader.readuntil(b"\r\n\r\n")).decode()
            stats["statusLine"] = headers.split("\r\n")[0]
            body = await reader.readexactly(stats["readTargetBytes"])
            stats["clientBodyBytes"] = len(body)
            if not abort:
                stats["clientBodyBytes"] += len(await reader.read())
            started = time.monotonic()
            client_closed = True
            writer.close()
            await writer.wait_closed()
            await done.wait()
            stats["completionAfterCloseMs"] = (time.monotonic() - started) * 1000
    finally:
        if writer is not None:
            writer.close()
            await writer.wait_closed()
        server.should_exit = True
        try:
            await asyncio.wait_for(task, 10)
        finally:
            sock.close()
    stats["cleanup"] = {"serverStopped": task.done(), "socketClosed": sock.fileno() == -1}
    return stats


async def main():
    conditions = [
        ("unbounded-abort", None, True, False),
        ("bounded-complete", 3 * MIB, False, False),
        ("bounded-abort", 4 * MIB, True, False),
        ("unbounded-disconnect-listener", None, True, True),
    ]
    results = []
    with tempfile.TemporaryDirectory(prefix="file-response-disconnect-") as directory:
        path = os.path.join(directory, "fixture.bin")
        size = 16 * MIB
        with open(path, "wb") as fixture:
            fixture.truncate(size)
        for condition in conditions:
            results.append(await exercise(path, size, *condition))

    print(json.dumps({
        "schemaVersion": 1,
        "scriptSha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "versions": {
            package: importlib.metadata.version(package)
            for package in ("starlette", "uvicorn", "httptools", "anyio")
        },
        "scope": "Linux loopback HTTP with a generated zero-filled file; ASGI body bytes are not disk I/O or bytes delivered to the client. No playback latency claim.",
        "observer": "Count actual ASGI body messages before delegating to Uvicorn.send; yield once after each send without a timed delay.",
        "listenerScope": "Diagnostic cancellation around FileResponse.__call__, with no background task, pathsend, multipart, or WebSocket coverage; not a production-ready patch.",
        "temporaryFixtureRemoved": not os.path.exists(directory),
        "results": results,
    }, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
