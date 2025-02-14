import asyncio
from http import HTTPMethod

from typing import Dict, Callable, Optional, Union
import logging

# Sets up default basic config
logging.basicConfig()
logger = logging.getLogger(__name__)

logger.setLevel(logging.INFO)

RESPONSE = b"""HTTP/1.1 200 OK
Connection: close
Content-Type: text/html; charset=utf8
Content-Length: 5
Cache-Control: no-cache, no-store, must-revalidate

Hello"""

TEXT_TYPE = "text/html; charset=utf8"
IMAGE_TYPE = "image/png"
NOTFOUND_MESSAGE = "Not Found"

BIRTHDAY_FORM = """<html>
<body>
<form method="post" action="/birthday">
<label for="year">Year:</label>
<input type="number" name="year"><br>
<label for="month">Month:</label>
<input type="number" name="month"><br>
<label for="day">Day:</label>
<input type="number" name="day"><br>
<input type="submit" value="submit">
</form>
</body>
</html>"""


class CutomResponseParams:
    def __init__(
        self,
        status_code: int,
        http_response_text: str,
        content_type: str,
        content: Union[str, bytes],
    ):
        self.status_code = status_code
        self.http_response_text = http_response_text
        self.content_type = content_type
        self.content = content

    def create_response(self) -> bytes:
        n_bytes = (
            len(self.content.encode())
            if isinstance(self.content, str)
            else len(self.content)
        )
        response = bytearray(
            f"""HTTP/1.1 {self.status_code} {self.http_response_text}
Connection: close
Content-Type: {self.content_type}
Content-Length: {n_bytes}
Cache-Control: no-cache, no-store

""".encode()
        )
        content = (
            bytearray(self.content.encode())
            if isinstance(self.content, str)
            else bytearray(self.content)
        )
        response.extend(content)
        return response


files = {19: "9.png", 20: "11.png", 21: "10.png"}


def index_route(_: bytearray) -> bytes:
    return CutomResponseParams(200, "OK", TEXT_TYPE, BIRTHDAY_FORM).create_response()


def birthday_route(birthday: bytearray) -> bytes:
    dob = {"year": None, "month": None, "day": None}
    for rec in birthday.split(b"&"):
        identifier, value = rec.split(b"=")
        if not value:
            return CutomResponseParams(
                400, "Bad Request", TEXT_TYPE, "Date / Month / Day is empty"
            ).create_response()
        dob[identifier.decode()] = int(value)
    if dob["day"] < 1 or dob["day"] > 31:
        return CutomResponseParams(
            400,
            "Bad Request",
            TEXT_TYPE,
            f"Day is not between 1 and 31, received: {dob['day']}",
        ).create_response()
    if dob["month"] < 1 or dob["month"] > 12:
        return CutomResponseParams(
            400,
            "Bad Request",
            TEXT_TYPE,
            f"Month is not between 1 and 12, received: {dob['month']}",
        ).create_response()
    if dob["year"] < 1000 or dob["year"] > 9999:
        return CutomResponseParams(
            400,
            "Bad Request",
            TEXT_TYPE,
            f"Year is not between 1000 and 9999, received: {dob['year']}",
        ).create_response()
    y1 = dob["year"] // 100
    y2 = dob["year"] % 100
    total = dob["day"] + dob["month"] + y1 + y2
    while True:
        total = total // 10 + total % 10
        if total < 1:
            return CutomResponseParams(
                500,
                "Internal Server Error",
                TEXT_TYPE,
                f"Received total>1:{total}\n For the date: {dob['year']}/{dob['month']}/{dob['day']}",
            ).create_response()
        file = files.get(total)
        if file is not None:
            break
        if total < 10:
            file = f"{total - 1}.png"
            break
    with open(f"resources/tarots/{file}", "rb") as file_obj:
        return CutomResponseParams(
            200, "OK", IMAGE_TYPE, file_obj.read()
        ).create_response()


def parse_top_line(x: bytearray):
    request_type, path, _ = x.split(b" ")
    return (HTTPMethod(request_type.decode()), path.decode())


class Router:
    def __init__(self):
        self.routes: Dict[str, Callable] = dict()

    def register_route(self, path: str, func: Callable):
        self.routes[path] = func

    async def callback(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ):
        data = await reader.read(4 * 1024)
        if not data:
            logger.debug("Closing Connection as there's no data")
            writer.close()
            await writer.wait_closed()
            return None
        metainfo_bytes, body = bytearray(data).split(b"\r\n\r\n")
        metainfo = metainfo_bytes.split(b"\r\n")
        _, path = parse_top_line(metainfo[0])
        callable: Optional[Callable[[bytearray], bytes]] = self.routes.get(path)
        if not callable:
            response = CutomResponseParams(
                404, "NOTFOUND", TEXT_TYPE, NOTFOUND_MESSAGE
            ).create_response()

        else:
            response = callable(body)
        writer.write(response)
        await writer.drain()
        writer.close()
        await writer.wait_closed()


async def main():
    logger.info("Initializing Router")
    router = Router()
    logger.info("Registering Routes")
    router.register_route("/", index_route)
    router.register_route("/birthday", birthday_route)
    logger.info("Starting Server on port 8080, http://127.0.0.1:8080")
    server = await asyncio.start_server(
        router.callback,
        host="127.0.0.1",
        port=8080,
        reuse_address=True,
        reuse_port=True,
    )
    await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(main())
