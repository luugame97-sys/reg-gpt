"""Session-scoped, authenticated loopback HTTP bridge to SOCKS5 (RFC 1928/1929)."""
from __future__ import annotations

import asyncio
import base64
import ipaddress
import secrets
from urllib.parse import urlsplit

from .runtime import parse_proxy


class Socks5BrowserBridge:
    """Keep SOCKS credentials upstream; browsers use temporary HTTP credentials."""

    def __init__(self, proxy_url: str) -> None:
        proxy = parse_proxy(proxy_url)
        if not proxy or not proxy["server"].startswith(("socks5://", "socks5h://")):
            raise ValueError("Cầu nối yêu cầu proxy SOCKS5 hợp lệ")
        self.proxy = proxy
        self._server = None
        self._tasks: set[asyncio.Task] = set()
        self.browser_proxy: dict[str, str] = {}
        self._authorization = ""

    async def start(self) -> dict[str, str]:
        username, password = secrets.token_hex(12), secrets.token_hex(24)
        self._authorization = "Basic " + base64.b64encode(f"{username}:{password}".encode()).decode()
        self._server = await asyncio.start_server(self._handle, "127.0.0.1", 0, limit=65536)
        port = self._server.sockets[0].getsockname()[1]
        self.browser_proxy = {"server": f"http://127.0.0.1:{port}",
                              "username": username, "password": password}
        return dict(self.browser_proxy)

    async def close(self) -> None:
        server, self._server = self._server, None
        if server:
            server.close()
        tasks = list(self._tasks)
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        if server:
            await server.wait_closed()

    async def _connect(self, host: str, port: int):
        upstream = urlsplit(self.proxy["server"])
        reader, writer = await asyncio.open_connection(upstream.hostname, upstream.port or 1080)
        try:
            authenticated = "username" in self.proxy
            method = b"\x02" if authenticated else b"\x00"
            writer.write(b"\x05\x01" + method)
            await writer.drain()
            if await reader.readexactly(2) != b"\x05" + method:
                raise OSError("SOCKS5 negotiation rejected")
            if authenticated:
                username = self.proxy["username"].encode("utf-8")
                password = self.proxy.get("password", "").encode("utf-8")
                if not (1 <= len(username) <= 255 and 1 <= len(password) <= 255):
                    raise ValueError("SOCKS5 username/password phải dài 1–255 byte")
                writer.write(b"\x01" + bytes([len(username)]) + username + bytes([len(password)]) + password)
                await writer.drain()
                if await reader.readexactly(2) != b"\x01\x00":
                    raise OSError("SOCKS5 authentication rejected")
            try:
                address = ipaddress.ip_address(host)
            except ValueError:
                if upstream.scheme == "socks5":
                    infos = await asyncio.get_running_loop().getaddrinfo(host, port, type=1)
                    address = ipaddress.ip_address(infos[0][4][0])
                else:
                    address = None
            if address is not None:
                target = (b"\x01" if address.version == 4 else b"\x04") + address.packed
            else:
                domain = host.encode("idna")
                if not 1 <= len(domain) <= 255:
                    raise ValueError("Invalid SOCKS5 target")
                target = b"\x03" + bytes([len(domain)]) + domain
            writer.write(b"\x05\x01\x00" + target + port.to_bytes(2, "big"))
            await writer.drain()
            response = await reader.readexactly(4)
            if response[:3] != b"\x05\x00\x00":
                raise OSError("SOCKS5 connection rejected")
            if response[3] == 1:
                length = 4
            elif response[3] == 4:
                length = 16
            elif response[3] == 3:
                length = (await reader.readexactly(1))[0]
            else:
                raise OSError("Invalid SOCKS5 reply")
            await reader.readexactly(length + 2)
            return reader, writer
        except BaseException:
            writer.close()
            await writer.wait_closed()
            raise

    @staticmethod
    async def _relay(reader, writer) -> None:
        while data := await reader.read(65536):
            writer.write(data)
            await writer.drain()
        if writer.can_write_eof():
            writer.write_eof()

    async def _handle(self, reader, writer) -> None:
        task = asyncio.current_task()
        self._tasks.add(task)
        upstream_writer = None
        pumps = []
        started = False
        try:
            header = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), 30)
            lines = header.decode("iso-8859-1").split("\r\n")
            method, target, version = lines[0].split(" ", 2)
            headers = [line.split(":", 1) for line in lines[1:] if line]
            authorization = next((v.strip() for k, v in headers if k.lower() == "proxy-authorization"), "")
            if not secrets.compare_digest(authorization, self._authorization):
                writer.write(b'HTTP/1.1 407 Proxy Authentication Required\r\nProxy-Authenticate: Basic realm="ToolGPT"\r\nContent-Length: 0\r\nConnection: close\r\n\r\n')
                await writer.drain()
                return
            tunnel = method.upper() == "CONNECT"
            parsed = urlsplit("//" + target if tunnel else target)
            if not tunnel and parsed.scheme != "http":
                raise ValueError("HTTP proxy requires HTTP or CONNECT")
            host, port = parsed.hostname, parsed.port or (443 if tunnel else 80)
            if not host or not 1 <= port <= 65535 or parsed.username is not None:
                raise ValueError("Invalid proxy target")
            upstream_reader, upstream_writer = await asyncio.wait_for(self._connect(host, port), 30)
            if tunnel:
                writer.write(b"HTTP/1.1 200 Connection Established\r\n\r\n")
                await writer.drain()
            else:
                path = parsed.path or "/"
                if parsed.query:
                    path += "?" + parsed.query
                forwarded = [f"{method} {path} {version}"]
                forwarded.extend(f"{k}:{v}" for k, v in headers
                                 if k.lower() not in {"proxy-authorization", "proxy-connection", "connection"})
                forwarded.extend(["Connection: close", "", ""])
                upstream_writer.write("\r\n".join(forwarded).encode("iso-8859-1"))
                await upstream_writer.drain()
            started = True
            pumps = [asyncio.create_task(self._relay(reader, upstream_writer)),
                     asyncio.create_task(self._relay(upstream_reader, writer))]
            # A response may end while the browser keeps its request side open.
            done, pending = await asyncio.wait(pumps, return_when=asyncio.FIRST_COMPLETED)
            for completed in done:
                completed.result()
            if pumps[0] in done and pumps[1] in pending:
                await asyncio.wait_for(pumps[1], 300)
        except (OSError, ValueError, UnicodeError, asyncio.IncompleteReadError,
                asyncio.LimitOverrunError, TimeoutError):
            if not started:
                writer.write(b"HTTP/1.1 502 Bad Gateway\r\nContent-Length: 0\r\nConnection: close\r\n\r\n")
                try:
                    await writer.drain()
                except OSError:
                    pass
        finally:
            # Close both transports before any await, including cancellation
            # arriving while an otherwise completed handler is cleaning up.
            for stream in (upstream_writer, writer):
                if stream:
                    stream.close()
            for pump in pumps:
                if not pump.done():
                    pump.cancel()
            try:
                await asyncio.gather(*pumps, return_exceptions=True)
                for stream in (upstream_writer, writer):
                    if stream:
                        try:
                            await stream.wait_closed()
                        except OSError:
                            pass
            finally:
                self._tasks.discard(task)
