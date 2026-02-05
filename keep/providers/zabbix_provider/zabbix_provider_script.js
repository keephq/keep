try {
  var result = { tags: {} },
    params = JSON.parse(value),
    req = new HttpRequest(),
    resp = "";

  if (typeof params.HTTPProxy === "string" && params.HTTPProxy.trim() !== "") {
    req.setProxy(params.HTTPProxy);
  }

  keepApiUrl = params["keepApiUrl"];
  if (
    !keepApiUrl ||
    (typeof keepApiUrl === "string" && keepApiUrl.trim() === "")
  ) {
    throw 'incorrect value for variable "keepApiUrl". The value must be a non-empty URL.';
  }

  keepApiKey = params["keepApiKey"];
  if (
    !keepApiKey ||
    (typeof keepApiKey === "string" && keepApiKey.trim() === "")
  ) {
    throw 'incorrect value for variable "keepApiKey". The value must be a non-empty API key.';
  }

  delete params["keepApiUrl"];
  delete params["keepApiKey"];
  delete params["HTTPProxy"];

  var incidentKey = "zabbix-" + params["EVENT.ID"];

  req.addHeader("Accept: application/json");
  req.addHeader("Content-Type: application/json");
  req.addHeader("X-API-KEY: " + keepApiKey);

  Zabbix.log(4, "[Keep Webhook] keepApiUrl:" + keepApiUrl);
  Zabbix.log(4, "[Keep Webhook] keepApiKey:" + keepApiKey);
  Zabbix.log(4, "[Keep Webhook] Sending request:" + JSON.stringify(params));

  resp = req.post(keepApiUrl, JSON.stringify(params));
  Zabbix.log(4, "[Keep Webhook] Received response: HTTP " + req.getStatus());

  if (req.getStatus() != 202) {
    throw "Response code not 202";
  } else {
    return resp;
  }
} catch (error) {
  Zabbix.log(3, "[Keep Webhook] Notification failed : " + error);
  throw "Keep notification failed : " + error;
}
