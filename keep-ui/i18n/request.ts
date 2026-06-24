import { getRequestConfig } from "next-intl/server";
import { cookies } from "next/headers";
import { defaultLocale, isValidLocale, type Locale } from "./config";

export default getRequestConfig(async () => {
  const cookieStore = await cookies();
  const cookieLocale = cookieStore.get("NEXT_LOCALE")?.value;

  let locale: Locale = defaultLocale;
  if (cookieLocale && isValidLocale(cookieLocale)) {
    locale = cookieLocale;
  }

  const messages = (await import(`./messages/${locale}/index.json`)).default;

  return {
    locale,
    messages,
  };
});
