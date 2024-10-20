from pydantic import HttpUrl, conint


class HttpsUrl(HttpUrl):
    scheme = {'https'}

    @staticmethod
    def get_default_parts(parts):
        return {'port': '443'}

UrlPort = conint(ge=1, le=65_535)
