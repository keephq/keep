const { HttpsProxyAgent } = require("https-proxy-agent");
const nodeFetch = require("node-fetch");
const proxyUrl = process.env.HTTP_PROXY || process.env.http_proxy;
const apiUrl = process.env.API_URL;

if (proxyUrl) {
  const proxyAgent = new HttpsProxyAgent(proxyUrl);
  global.fetch = (url, options = {}) => {
    // Whitelist API_URL for direct access
    if (apiUrl && url.startsWith(apiUrl)) {
      return nodeFetch(url, options);
    }
    return nodeFetch(url, { ...options, agent: proxyAgent });
  };
}
