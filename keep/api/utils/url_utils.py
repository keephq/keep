import urllib.parse

def encode_url(url):
    parsed = urllib.parse.urlparse(url)
    valid_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
    if parsed.query:
        query_pairs = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
        for key, value in query_pairs:
            encoded_key = urllib.parse.quote(key, safe="")
            encoded_value = urllib.parse.quote(value, safe="")
            valid_url += f"?{encoded_key}={encoded_value}"
    if parsed.fragment:
        encoded_fragment = urllib.parse.quote(parsed.fragment, safe="")
        valid_url += f"#{encoded_fragment}"
    return valid_url
