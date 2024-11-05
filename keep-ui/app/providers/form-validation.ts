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
const urlError = error("Please provide a valid URL.");
const protocolError = error("A valid URL protocol is required.");
const relProtocolError = error("A protocol-relavie URL is not allowed.");
const missingPortError = error("A URL with a port number is required.");
const portError = error("Invalid port number.");
const hostError = error("Invalid URL host.");
const hostWildcardError = error("Wildcard in URL host is not allowed");
const tldError = error(
  "URL must contain a valid TLD e.g .com, .io, .dev, .net"
);

function getProtocolError(opts: URLOptions["protocols"]) {
  if (opts.length === 0) return protocolError;
  if (opts.length === 1)
    return error(`A URL with \`${opts[0]}\` protocol is required.`);
  if (opts.length === 2)
    return error(
      `A URL with \`${opts[0]}\` or \`${opts[1]}\` protocol is required.`
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
  return error(`A URL with one of ${optsStr} protocols is required.`);
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

  split = url.split("://");
  const protocol = split?.shift()?.toLowerCase() ?? "";
  if (opts.requireProtocol && opts.protocols.indexOf(protocol) === -1)
    return getProtocolError(opts.protocols);
  url = split.join("://");

  split = url.split("/");
  url = split.shift() ?? "";
  if (!url.length) return urlError;

  split = url.split("@");
  if (split.length > 1 && !split[0]) return urlError;
  if (split.length > 1) {
    const auth = split.shift() ?? "";
    if (auth.split(":").length > 2) return urlError;
    const [user, pass] = auth.split(":");
    if (!user && !pass) return urlError;
  }

  const hostname = split.join("@");
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
    if (Number.isNaN(port)) return missingPortError;
    if (port <= 0 || port > 65_535) return portError;
  } else if (opts.requirePort) return missingPortError;

  if (!host) return hostError;
  if (isIP(host)) return { success: true };
  return isFQDN(host, opts);
}

function addZodErr(valdn: ValidatorRes, ctx: z.RefinementCtx) {
  if (valdn.success) return;
  ctx.addIssue({
    code: z.ZodIssueCode.custom,
    message: valdn.msg,
  });
}

export function getZodSchema(fields: Provider["config"]) {
  const required_error = "This field is required";
  const portError = "Invalid port number";
  const emptyStringToNull = z
    .string()
    .optional()
    .transform((val) => (val?.length === 0 ? null : val));

  const kvPairs = Object.entries(fields).map(([field, config]) => {
    if (config.type === "form") {
      const baseFormSchema = z.record(z.string(), z.string()).array();
      const formSchema = config.required
        ? baseFormSchema.nonempty({
            message: "At least one key-value entry should be provided.",
          })
        : baseFormSchema.optional();
      return [field, formSchema];
    }

    if (config.type === "file") {
      const baseFileSchema = z
        .instanceof(File, { message: "Please upload a file here." })
        .refine(
          (file) => {
            if (config.file_type == undefined) return true;
            if (config.file_type.length <= 1) return true;
            return config.file_type.includes(file.type);
          },
          {
            message:
              config.file_type && config.file_type?.split(",").length > 1
                ? `File type should be one of ${config.file_type}.`
                : `File should be of type ${config.file_type}.`,
          }
        );
      const fileSchema = config.required
        ? baseFileSchema
        : baseFileSchema.optional();
      return [field, fileSchema];
    }

    if (config.type === "switch") {
      const switchSchema = config.required
        ? z.boolean()
        : z.boolean().optional();
      return [field, switchSchema];
    }

    const urlStr = z.string({ required_error });

    if (config.validation === "any_url") {
      const urlSchema = urlStr.superRefine((url, ctx) => {
        const valdn = isURL(url);
        addZodErr(valdn, ctx);
      });
      const anyUrlSchema = config.required
        ? urlSchema
        : emptyStringToNull.pipe(urlSchema.nullish());
      return [field, anyUrlSchema];
    }

    if (config.validation === "any_http_url") {
      const baseAnyHttpSchema = urlStr.superRefine((url, ctx) => {
        const valdn = isURL(url, { protocols: ["http", "https"] });
        addZodErr(valdn, ctx);
      });
      const anyHttpSchema = config.required
        ? baseAnyHttpSchema
        : emptyStringToNull.pipe(baseAnyHttpSchema.nullish());
      return [field, anyHttpSchema];
    }

    if (config.validation === "https_url") {
      const baseHttpsSchema = urlStr.superRefine((url, ctx) => {
        const valdn = isURL(url, { requireTld: true, protocols: ["https"] });
        addZodErr(valdn, ctx);
      });
      const httpsSchema = config.required
        ? baseHttpsSchema
        : emptyStringToNull.pipe(baseHttpsSchema.nullish());
      return [field, httpsSchema];
    }

    if (config.validation === "no_scheme_url") {
      const baseNoSchemeSchema = urlStr.superRefine((url, ctx) => {
        const valdn = isURL(url, { requireProtocol: false });
        addZodErr(valdn, ctx);
      });
      const noSchemeSchema = config.required
        ? baseNoSchemeSchema
        : emptyStringToNull.pipe(baseNoSchemeSchema.nullish());
      return [field, noSchemeSchema];
    }

    if (config.validation === "tld") {
      const baseTldSchema = z
        .string({ required_error })
        .regex(new RegExp(/\.[a-z]{2,63}$/), {
          message: "Please provide a valid TLD e.g .com, .io, .dev, .net",
        });
      const tldSchema = config.required
        ? baseTldSchema
        : baseTldSchema.optional();
      return [field, tldSchema];
    }

    if (config.validation === "port") {
      const basePortSchema = z.coerce
        .number({ required_error, invalid_type_error: portError })
        .min(1, { message: portError })
        .max(65_535, { message: portError });
      const portSchema = config.required
        ? basePortSchema
        : emptyStringToNull.pipe(basePortSchema.nullish());
      return [field, portSchema];
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
