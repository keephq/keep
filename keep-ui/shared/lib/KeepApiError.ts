// Custom Error Class

export class KeepApiError extends Error {
  url: string;
  proposedResolution: string;
  statusCode: number | undefined;

  constructor(
    message: string,
    url: string,
    proposedResolution: string,
    statusCode?: number
  ) {
    super(message);
    this.name = "KeepApiError";
    this.url = url;
    this.proposedResolution = proposedResolution;
    this.statusCode = statusCode;
  }

  toString() {
    return `${this.name}: ${this.message} - ${this.url} - ${this.proposedResolution} - ${this.statusCode}`;
  }
}
