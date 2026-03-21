import { getRequestConfig } from "next-intl/server";
import { cookies, headers } from "next/headers";
import {
  locales,
  defaultLocale,
  localeCookieName,
  type Locale,
} from "./config";

function getPreferredLocale(acceptLanguage: string | null): Locale {
  if (!acceptLanguage) {
    return defaultLocale;
  }

  const parsedLanguages = acceptLanguage
    .split(",")
    .map((entry) => {
      const [languagePart, qualityPart] = entry.trim().split(";q=");
      return {
        language: languagePart.toLowerCase(),
        quality: qualityPart ? Number(qualityPart) : 1,
      };
    })
    .sort((first, second) => second.quality - first.quality);

  for (const { language } of parsedLanguages) {
    if (language === "zh-cn" || language.startsWith("zh")) {
      return "zh-CN";
    }

    if (language.startsWith("en")) {
      return "en";
    }
  }

  return defaultLocale;
}

export default getRequestConfig(async () => {
  // 从 cookie 获取语言偏好
  const cookieStore = await cookies();
  const headerStore = await headers();
  const localeCookie = cookieStore.get(localeCookieName)?.value as
    | Locale
    | undefined;

  // 验证 cookie 中的语言是否有效
  const locale: Locale =
    localeCookie && locales.includes(localeCookie)
      ? localeCookie
      : getPreferredLocale(headerStore.get("accept-language"));

  return {
    locale,
    messages: (await import(`./messages/${locale}.json`)).default,
  };
});
