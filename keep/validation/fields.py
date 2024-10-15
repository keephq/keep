from pydantic import HttpUrl


class HttpsUrl(HttpUrl):
    scheme = {'https'}

    @staticmethod
    def get_default_parts(parts):
        return {'port': '443'}

