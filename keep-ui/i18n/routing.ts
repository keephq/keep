import { defineRouting } from 'next-intl/routing';
import { createNavigation } from 'next-intl/navigation';
import { locales, defaultLocale } from './config';

// 不使用 URL 前缀，通过 cookie 存储语言偏好
export const routing = defineRouting({
  locales,
  defaultLocale,
  localePrefix: 'never', // 不在 URL 中显示语言前缀
});

// 创建导航助手
export const { Link, redirect, usePathname, useRouter, getPathname } =
  createNavigation(routing);
