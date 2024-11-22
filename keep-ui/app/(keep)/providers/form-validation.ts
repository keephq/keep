import { z } from "zod";
import { Provider } from "./providers";

type URLOptions = {
  protocols: string[];
  requireTld: boolean;
  requireProtocol: boolean;
  requirePort: boolean;
  validateLength: boolean;
  maxLength: number;
};

type ValidatorRes = { success: true } | { success: false; msg: string };

const defaultURLOptions: URLOptions = {
  protocols: [],
  requireTld: false,
  requireProtocol: true,
  requirePort: false,
  validateLength: true,
  maxLength: 2 ** 16,
};

function mergeOptions<T extends Record<string, unknown>>(
  defaults: T,
  opts?: Partial<T>
): T {
  if (!opts) return defaults;
  return { ...defaults, ...opts };
}

const error = (msg: string) => ({ success: false, msg });
const urlError = error("Please provide a valid URL");
const protocolError = error("A valid URL protocol is required");
const relProtocolError = error("A protocol-relavie URL is not allowed");
const missingPortError = error("A URL with a port number is required");
const portError = error("Invalid port number");
const hostError = error("Invalid URL host");
const hostWildcardError = error("Wildcard in URL host is not allowed");
const tldError = error(
  "URL must contain a valid TLD e.g .com, .io, .dev, .net"
);

function getProtocolError(opts: URLOptions["protocols"]) {
  if (opts.length === 1)
    return error(`A URL with \`${opts[0]}\` protocol is required`);
  if (opts.length === 2)
    return error(
      `A URL with \`${opts[0]}\` or \`${opts[1]}\` protocol is required`
    );
  const lst = opts.length - 1;
  const wrap = (acc: string, p: string) => acc + `\`${p}\``;
  const optsStr = opts.reduce(
    (acc, p, i) =>
      i === lst
        ? wrap(acc, p)
        : i === lst - 1
          ? wrap(acc, p) + " or "
          : wrap(acc, p) + ", ",
    ""
  );
  return error(`A URL with one of ${optsStr} protocols is required`);
}

function isFQDN(str: string, options?: Partial<URLOptions>): ValidatorRes {
  const opts = mergeOptions(defaultURLOptions, options);

  if (str[str.length - 1] === ".") return hostError; // trailing dot not allowed
  if (str.indexOf("*.") === 0) return hostWildcardError; // wildcard not allowed

  const parts = str.split(".");
  const tld = parts[parts.length - 1];
  const tldRegex =
    /^([a-z\u00A1-\u00A8\u00AA-\uD7FF\uF900-\uFDCF\uFDF0-\uFFEF]{2,}|xn[a-z0-9-]{2,})$/i;

  if (
    opts.requireTld &&
    (parts.length < 2 || !tldRegex.test(tld) || /\s/.test(tld))
  )
    return tldError;

  const partsValid = parts.every((part) => {
    if (!/^[a-z_\u00a1-\uffff0-9-]+$/i.test(part)) {
      return false;
    }

    // disallow full-width chars
    if (/[\uff01-\uff5e]/.test(part)) {
      return false;
    }

    // disallow parts starting or ending with hyphen
    if (/^-|-$/.test(part)) {
      return false;
    }

    return true;
  });

  return partsValid ? { success: true } : hostError;
}

function isIP(str: string) {
  const validation = z.string().ip().safeParse(str);
  return validation.success;
}

function isURL(str: string, options?: Partial<URLOptions>): ValidatorRes {
  const opts = mergeOptions(defaultURLOptions, options);

  if (str.length === 0 || /[\s<>]/.test(str)) return urlError;
  if (opts.validateLength && str.length > opts.maxLength) {
    return error(`Invalid url length, max of ${opts.maxLength} expected.`);
  }

  let url = str;
  let host: string;
  let port: number;
  let portStr: string = "";
  let split: string[];

  split = url.split("#");
  url = split.shift() ?? "";

  split = url.split("?");
  url = split.shift() ?? "";

  if (url.slice(0, 2) === "//") return relProtocolError;

  // extract protocol & validate
  split = url.split("://");
  if (split.length > 1) {
    const protocol = split?.shift()?.toLowerCase() ?? "";
    if (opts.protocols.length && opts.protocols.indexOf(protocol) === -1)
      return getProtocolError(opts.protocols);
  } else if (opts.requireProtocol && opts.protocols.length) {
    return getProtocolError(opts.protocols);
  } else if (split.length > 2 || opts.requireProtocol) return protocolError;
  url = split.join("://");

  split = url.split("/");
  url = split.shift() ?? "";
  if (!url.length) return urlError;

  // extract auth details & validate
  split = url.split("@");
  if (split.length > 1 && !split[0]) return urlError;
  if (split.length > 1) {
    const auth = split.shift() ?? "";
    if (auth.split(":").length > 2) return urlError;
    const [user, pass] = auth.split(":");
    if (!user && !pass) return urlError;
  }
  const hostname = split.join("@");

  // extract ipv6 & port
  const wrapped_ipv6 = /^\[([^\]]+)\](?::([0-9]+))?$/;
  const ipv6Match = hostname.match(wrapped_ipv6);
  if (ipv6Match) {
    host = ipv6Match[1];
    portStr = ipv6Match[2];
  } else {
    split = hostname.split(":");
    host = split.shift() ?? "";
    if (split.length) portStr = split.join(":");
  }

  if (portStr.length) {
    port = parseInt(portStr, 10);
    if (Number.isNaN(port)) return urlError;
    if (port <= 0 || port > 65_535) return portError;
  } else if (opts.requirePort) return missingPortError;

  if (!host) return hostError;
  if (isIP(host)) return { success: true };
  return isFQDN(host, opts);
}

const required_error = "This field is required";

function getBaseUrlSchema(options?: Partial<URLOptions>) {
  const urlStr = z.string({ required_error });
  const schema = urlStr.superRefine((url, ctx) => {
    const valdn = isURL(url, options);
    if (valdn.success) return;
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      message: valdn.msg,
    });
  });
  return schema;
}

export function getZodSchema(fields: Provider["config"], installed: boolean) {
  const portError = "Invalid port number";

  const kvPairs = Object.entries(fields).map(([field, config]) => {
    if (config.type === "form") {
      const baseSchema = z.record(z.string(), z.string()).array();
      const schema = config.required
        ? baseSchema.nonempty({
            message: "At least one key-value entry should be provided.",
          })
        : baseSchema.optional();
      return [field, schema];
    }

    if (config.type === "file") {
      const baseSchema = z
        .instanceof(File, { message: "Please upload a file here." })
        .or(z.string())
        .refine(
          (file) => {
            if (config.file_type == undefined) return true;
            if (config.file_type.length <= 1) return true;
            if (typeof file === "string" && installed) return true;
            return (
              typeof file !== "string" && config.file_type.includes(file.type)
            );
          },
          {
            message:
              config.file_type && config.file_type?.split(",").length > 1
                ? `File type should be one of ${config.file_type}.`
                : `File should be of type ${config.file_type}.`,
          }
        );
      const schema = config.required ? baseSchema : baseSchema.optional();
      return [field, schema];
    }

    if (config.type === "switch") {
      const schema = config.required ? z.boolean() : z.boolean().optional();
      return [field, schema];
    }

    if (config.validation === "any_url") {
      const baseSchema = getBaseUrlSchema();
      const schema = config.required ? baseSchema : baseSchema.optional();
      return [field, schema];
    }

    if (config.validation === "any_http_url") {
      const baseSchema = getBaseUrlSchema({ protocols: ["http", "https"] });
      const schema = config.required ? baseSchema : baseSchema.optional();
      return [field, schema];
    }

    if (config.validation === "https_url") {
      const baseSchema = getBaseUrlSchema({
        protocols: ["https"],
        requireTld: true,
        maxLength: 2083,
      });
      const schema = config.required ? baseSchema : baseSchema.optional();
      return [field, schema];
    }

    if (config.validation === "no_scheme_url") {
      const baseSchema = getBaseUrlSchema({ requireProtocol: false });
      const schema = config.required ? baseSchema : baseSchema.optional();
      return [field, schema];
    }

    if (config.validation === "tld") {
      const baseSchema = z
        .string({ required_error })
        .regex(new RegExp(/\.[a-z]{2,63}$/), {
          message: "Please provide a valid TLD e.g .com, .io, .dev, .net",
        });
      const schema = config.required ? baseSchema : baseSchema.optional();
      return [field, schema];
    }

    if (config.validation === "port") {
      const baseSchema = z
        .string({ required_error })
        .pipe(
          z.coerce
            .number({ invalid_type_error: portError })
            .min(1, { message: portError })
            .max(65_535, { message: portError })
        );
      const schema = config.required ? baseSchema : baseSchema.optional();
      return [field, schema];
    }
    return [
      field,
      config.required
        ? z
            .string({ required_error })
            .trim()
            .min(1, { message: required_error })
        : z.string().optional(),
    ];
  });
  return z.object({
    provider_name: z
      .string({ required_error })
      .trim()
      .min(1, { message: required_error }),
    ...Object.fromEntries(kvPairs),
  });
}
