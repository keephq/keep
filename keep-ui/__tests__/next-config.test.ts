import { withSentryConfig } from "@sentry/nextjs";

jest.mock("@sentry/nextjs", () => ({
  withSentryConfig: jest.fn((config) => config),
}));

describe("production source maps", () => {
  const originalEnv = process.env;

  afterEach(() => {
    process.env = originalEnv;
    jest.clearAllMocks();
  });

  it.each(["true", "false"])(
    "serves debug source maps with SENTRY_DISABLED=%s",
    async (sentryDisabled) => {
      process.env = {
        ...originalEnv,
        NODE_ENV: "production",
        KEEP_INCLUDE_SOURCES: "true",
        SENTRY_DISABLED: sentryDisabled,
      };
      let config: any;
      jest.isolateModules(() => {
        config = require("../next.config");
      });

      expect(config.productionBrowserSourceMaps).toBe(true);
      expect(config.compiler.removeConsole).toBe(false);
      expect(await config.rewrites()).toEqual([]);
      if (sentryDisabled === "false") {
        expect(withSentryConfig).toHaveBeenCalledWith(
          expect.anything(),
          expect.objectContaining({
            sourcemaps: { deleteSourcemapsAfterUpload: false },
          })
        );
      }
    }
  );

  it.each([undefined, "false"])(
    "blocks production source maps with KEEP_INCLUDE_SOURCES=%s",
    async (includeSources) => {
      process.env = {
        ...originalEnv,
        NODE_ENV: "production",
        SENTRY_DISABLED: "false",
      };
      if (includeSources === undefined) {
        delete process.env.KEEP_INCLUDE_SOURCES;
      } else {
        process.env.KEEP_INCLUDE_SOURCES = includeSources;
      }
      let config: any;
      jest.isolateModules(() => {
        config = require("../next.config");
      });

      expect(config.compiler.removeConsole).toBe(true);
      expect(await config.rewrites()).toEqual({
        beforeFiles: [{ source: "/:path*.map", destination: "/404" }],
      });
      expect(withSentryConfig).toHaveBeenCalledWith(
        expect.anything(),
        expect.objectContaining({
          sourcemaps: { deleteSourcemapsAfterUpload: true },
        })
      );
    }
  );
});
