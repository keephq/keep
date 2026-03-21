import { getRequestConfig } from 'next-intl/server';
import { cookies } from 'next/headers';
import { locales, defaultLocale, localeCookieName, type Locale } from './config';

export default getRequestConfig(async () => {
  // 从 cookie 获取语言偏好
  const cookieStore = await cookies();
  const localeCookie = cookieStore.get(localeCookieName)?.value as Locale | undefined;

  // 验证 cookie 中的语言是否有效
  const locale: Locale = localeCookie && locales.includes(localeCookie)
    ? localeCookie
    : defaultLocale;

  return {
    locale,
    messages: (await import(`./messages/${locale}.json`)).default,
  };
});
