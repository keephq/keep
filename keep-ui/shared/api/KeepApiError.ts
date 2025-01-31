// Custom Error
export class KeepApiError extends Error {
  url: string;
  proposedResolution: string;
  statusCode: number | undefined;
  responseJson: any;
  constructor(
    message: string,
    url: string,
    proposedResolution: string,
    responseJson: any,
    statusCode?: number
  ) {
    super(message);
    this.name = "KeepApiError";
    this.url = url;
    this.proposedResolution = proposedResolution;
    this.statusCode = statusCode;
    this.responseJson = responseJson;
  }

  toString() {
    return `${this.name}: ${this.message} - ${this.url} - ${this.proposedResolution} - ${this.statusCode}`;
  }
}

export class KeepApiReadOnlyError extends KeepApiError {
  constructor(
    message: string,
    url: string,
    proposedResolution: string,
    responseJson: any,
    statusCode?: number
  ) {
    super(message, url, proposedResolution, responseJson, statusCode);
    this.name = "KeepReadOnlyError";
  }
}

export class KeepApiHealthError extends KeepApiError {
  constructor(message: string = "API server is not available") {
    const proposedResolution =
      "Check if the Keep backend is running and API_URL is correct.";
    super(message, "", proposedResolution, {}, 503);
    this.name = "KeepApiHealthError";
    this.message = message;
  }

  toString() {
    return `${this.name}: ${this.message} - ${this.proposedResolution}`;
  }
}
