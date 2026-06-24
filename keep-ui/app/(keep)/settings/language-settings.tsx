"use client";

import { Card, Subtitle, Text } from "@tremor/react";
import { useLocale } from "next-intl";
import { useRouter } from "next/navigation";
import { GlobeAltIcon } from "@heroicons/react/24/outline";

const languages = [
  { code: "en", label: "English", flag: "🇺🇸" },
  { code: "zh", label: "中文", flag: "🇨🇳" },
];

export default function LanguageSettings() {
  const locale = useLocale();
  const router = useRouter();

  const handleSwitch = (newLocale: string) => {
    document.cookie = `NEXT_LOCALE=${newLocale};path=/;max-age=${365 * 24 * 60 * 60}`;
    router.refresh();
  };

  return (
    <Card className="p-6">
      <div className="flex items-center gap-2 mb-4">
        <GlobeAltIcon className="h-5 w-5 text-gray-500" />
        <Subtitle>Language / 语言</Subtitle>
      </div>
      <Text className="mb-4 text-gray-500">
        Select your preferred language for the interface.
      </Text>
      <div className="grid grid-cols-2 gap-3">
        {languages.map((lang) => (
          <button
            key={lang.code}
            onClick={() => handleSwitch(lang.code)}
            className={`flex items-center gap-3 p-4 rounded-lg border-2 transition-all ${
              lang.code === locale
                ? "border-orange-500 bg-orange-50"
                : "border-gray-200 hover:border-gray-300 hover:bg-gray-50"
            }`}
          >
            <span className="text-2xl">{lang.flag}</span>
            <div className="text-left">
              <div className="font-medium">{lang.label}</div>
              <div className="text-xs text-gray-500">
                {lang.code === "en" ? "English" : "简体中文"}
              </div>
            </div>
            {lang.code === locale && (
              <div className="ml-auto">
                <div className="w-4 h-4 rounded-full bg-orange-500 flex items-center justify-center">
                  <svg
                    className="w-3 h-3 text-white"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M5 13l4 4L19 7"
                    />
                  </svg>
                </div>
              </div>
            )}
          </button>
        ))}
      </div>
    </Card>
  );
}
