import { z } from "zod";
import { Provider } from "./providers";

type UrlOptions = {
  protocols: string[];
  requireTld: boolean;
  requireProtocol: boolean;
  requirePort: boolean;
  validateLength: boolean;
  maxLength: number;
};

type ValidatorRes = { success: true } | { success: false; msg: string };

const defaultUrlOptions: UrlOptions = {
  protocols: [],
  requireTld: false,
  requireProtocol: true,
  requirePort: false,
  validateLength: true,
  maxLength: 2 ** 16,
};

function mergeOptions<T extends Record<string, unknown>>(
  defaults: T,
  opts?: T
) {
  if (!opts) return defaults;
  for (const key in defaults) {
    if (typeof opts[key] === "undefined") {
      opts[key] = defaults[key];
    }
  }
  return opts;
}

const error = (msg: string) => ({ success: false, msg });
const urlError = { success: false, msg: "Please provide a valid URL." };
const protocolError = {
  success: false,
  msg: "A valid URL protocol is required.",
};
const relProtocolError = {
  success: false,
  msg: "A protocol-relavie URL is not allowed.",
};

function getProtocolError(opts: UrlOptions["protocols"]) {
  if (opts.length === 0) return protocolError;
  if (opts.length === 1) return error(`A URL with \`${opts[0]}\` is required.`);
  if (opts.length === 2)
    return error(`A URL with \`${opts[0]}\` or \`${opts[1]}\` is required.`);
  const lst = opts.length - 1;
  const wrap = (x: string, y: string) => `\`${x} + ${y}\``;
  const optsStr = opts.reduce(
    (acc, p, i) =>
      i === 0
        ? wrap(acc, p)
        : i === lst
          ? wrap(acc, `or ${p}`)
          : wrap(acc, `, ${p}`),
    ""
  );
  return error(`A URL with one of ${optsStr} is required.`);
}

function isUrl(url: string, options?: UrlOptions): ValidatorRes {
  const opts = mergeOptions(defaultUrlOptions, options);

  if (url.length === 0 || /[\s<>]/.test(url)) return urlError;
  if (opts.validateLength && url.length > opts.maxLength) {
    return {
      success: false,
      msg: `Invalid url length, max of ${opts.maxLength} expected.`,
    };
  }

  let _url = url;
  let protocol: string;
  let host: string;
  let hostname: string;
  let port: number;
  let portStr: string | null;
  let split: string[];
  let ipv6: string | null;

  split = url.split("#");
  _url = split.shift() ?? "";

  split = url.split("?");
  _url = split.shift() ?? "";

  if (_url.slice(0, 2) === "//") return relProtocolError;

  split = url.split("://");
  protocol = split?.shift()?.toLowerCase() ?? "";
  if (opts.requireProtocol && opts.protocols.indexOf(protocol) === -1)
    return getProtocolError(opts.protocols);

  return { success: true };
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

    const urlSchema = z.string({ required_error }).url({
      message:
        "Please provide a valid url, with a scheme & hostname as required.",
    });
    const urlTldSchema = z.string().regex(new RegExp(/\.[a-z]{2,63}$/), {
      message: "Url must contain a valid TLD e.g .com, .io, .dev, .net",
    });
    const baseAnyHttpSchema = urlSchema.refine(
      (url) => url.startsWith("http://") || url.startsWith("https://"),
      { message: "A url with `http` or `https` protocol is reuquired." }
    );
    const baseHttpSchema = baseAnyHttpSchema.and(urlTldSchema);
    const baseHttpsSchema = urlSchema
      .refine((url) => url.startsWith("https://"), {
        message: "A url with `https` protocol is required.",
      })
      .and(urlTldSchema);

    if (config.validation === "any_url") {
      const anyUrlSchema = config.required
        ? urlSchema
        : emptyStringToNull.pipe(urlSchema.nullish());
      return [field, anyUrlSchema];
    }

    if (config.validation === "any_http_url") {
      const anyHttpSchema = config.required
        ? baseAnyHttpSchema
        : emptyStringToNull.pipe(baseAnyHttpSchema.nullish());
      return [field, anyHttpSchema];
    }

    if (config.validation === "http_url") {
      const httpSchema = config.required
        ? baseHttpSchema
        : emptyStringToNull.pipe(baseHttpSchema.nullish());
      return [field, httpSchema];
    }
    if (config.validation === "https_url") {
      const httpsSchema = config.required
        ? baseHttpsSchema
        : emptyStringToNull.pipe(baseHttpsSchema.nullish());
      return [field, httpsSchema];
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
