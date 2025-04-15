// Call this once before rendering
const languageName = "cel";

export const setupCustomCellanguage = (monaco: any) => {
  if (
    monaco.languages
      .getLanguages()
      .some((lang: any) => lang.id === languageName)
  )
    return;
  monaco.languages.register({ id: languageName });

  monaco.languages.setMonarchTokensProvider(languageName, {
    tokenizer: {
      root: [
        // Whitespace
        [/[ \t\r\n]+/, "white"],

        // Comments
        [/\/\/.*$/, "comment"],

        // Strings
        [
          /"/,
          { token: "string.quote", bracket: "@open", next: "@string_double" },
        ],
        [
          /'/,
          { token: "string.quote", bracket: "@open", next: "@string_single" },
        ],

        // Numbers (with optional decimal)
        [/\d+(\.\d+)?/, "number"],

        // Operators (longest match first)
        [/(==|!=|<=|>=)/, "operator"],
        [/[\+\-\*\/%<>=!]/, "operator"],

        // Keywords
        [/\b(true|false|null)\b/, "keyword"],

        // Identifiers
        [/[a-zA-Z_][\w$]*/, "identifier"],

        // Delimiters
        [/[()[\]{}.,]/, "delimiter"],
      ],

      string_double: [
        [/[^\\"]+/, "string"],
        [/\\./, "string.escape"],
        [/"/, { token: "string.quote", bracket: "@close", next: "@pop" }],
      ],

      string_single: [
        [/[^\\']+/, "string"],
        [/\\./, "string.escape"],
        [/'/, { token: "string.quote", bracket: "@close", next: "@pop" }],
      ],
    },
  });

  monaco.editor.defineTheme(`${languageName}-dark`, {
    base: "vs-dark",
    inherit: true,
    rules: [
      { token: "keyword", foreground: "C586C0" }, // purple
      { token: "identifier", foreground: "9CDCFE" }, // light blue
      { token: "number", foreground: "FF0000" }, // red
      { token: "string", foreground: "CE9178" }, // salmon
      { token: "operator", foreground: "D4D4D4" }, // light gray
      { token: "delimiter", foreground: "D4D4D4" }, // same as operator
    ],
    colors: {
      "editor.background": "#1E1E1E",
    },
  });

  monaco.languages.setLanguageConfiguration(languageName, {
    // comments: {
    //   lineComment: "//",
    // },
    brackets: [
      // ["{", "}"],
      ["[", "]"],
      ["(", ")"],
    ],
    autoClosingPairs: [
      { open: '"', close: '"' },
      { open: "'", close: "'" },
      // { open: "{", close: "}" },
      { open: "[", close: "]" },
      { open: "(", close: ")" },
    ],
  });

  console.log(
    "Ihor",
    monaco.languages
      .getLanguages()
      .some((lang: any) => lang.id === languageName)
  );
};
