import asyncio
import enum
import urllib.parse
import base64


class ASGICycleState(enum.Enum):
    REQUEST = enum.auto()
    RESPONSE = enum.auto()
    CLOSED = enum.auto()


class ASGIHTTPCycle:
    def __init__(self, scope):
        self.scope = scope
        self.app_queue = asyncio.Queue()
        self.state = ASGICycleState.REQUEST
        self.response = {}

    def put_message(self, message) -> None:
        if self.state is ASGICycleState.CLOSED:
            return
        self.app_queue.put_nowait(message)

    async def receive(self) -> dict:
        message = await self.app_queue.get()
        return message

    async def send(self, message) -> None:
        message_type = message["type"]

        if self.state is ASGICycleState.REQUEST:
            if message_type != "http.response.start":
                raise RuntimeError(
                    f"Expected 'http.response.start', received: {message_type}"
                )

            status_code = message["status"]
            headers = message.get("headers", [])

            self.response["statusCode"] = message["status"]
            self.response["isBase64Encoded"] = False
            self.response["headers"] = {
                k.decode("utf-8"): v.decode("utf-8") for k, v in headers
            }
            self.state = ASGICycleState.RESPONSE

        elif self.state is ASGICycleState.RESPONSE:
            if message_type != "http.response.body":
                raise RuntimeError(
                    f"Expected 'http.response.body', received: {message_type}"
                )

            body = message["body"]
            if isinstance(body, bytes):
                body = body.decode("utf-8")
            self.response["body"] = body

            # TODO: Currently only handle sending a single body response, so this will
            # always be closed.
            # more_body = message.get("more_body")
            # if not more_body:
            #     self.state = ASGICycleState.CLOSED

            self.state = ASGICycleState.CLOSED

        if self.state is ASGICycleState.CLOSED:
            self.put_message({"type": "http.disconnect"})


class ASGIWebSocketCycle:
    def __init__(self, scope):
        self.scope = scope
        self.app_queue = asyncio.Queue()
        self.state = ASGICycleState.REQUEST
        self.response = {}

    def put_message(self, message) -> None:
        if self.state is ASGICycleState.CLOSED:
            return
        self.app_queue.put_nowait(message)

    async def receive(self) -> dict:
        message = await self.app_queue.get()
        return message

    async def send(self, message) -> None:
        message_type = message["type"]

        if self.state is ASGICycleState.CLOSED:
            raise RuntimeError(f"Unexpected message, ASGIConnection is closed.")

        if self.state == ASGICycleState.REQUEST:
            # subprotocol = message.get("subprotocol", None)
            # if subprotocol is not None:
            #     self.handshake_headers.append(
            #         (b"Sec-WebSocket-Protocol", subprotocol.encode("utf-8"))
            #     )

            accept = message_type == "websocket.accept"
            close = message_type == "websocket.close"

            if accept or close:
                # accept()
                self.state = ASGICycleState.RESPONSE
            else:
                # reject()
                self.state = ASGICycleState.CLOSED

        if self.state is ASGICycleState.RESPONSE:
            print("do a thing")

        if message_type == "websocket.close":
            code = message.get("code", 1000)
            self.state = ASGICycleState.CLOSED