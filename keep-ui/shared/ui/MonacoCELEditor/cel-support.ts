// Call this once before rendering
export const setupCustomCellanguage = (monaco: any) => {
  if (monaco.languages.getLanguages().some((lang: any) => lang.id === "cel"))
    return;
  monaco.languages.register({ id: "cel" });

  monaco.languages.setMonarchTokensProvider("cel", {
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
        [/(==|!=|<=|>=|&&|\|\||\bin\b|\bnot in\b)/, "operator"],
        [/[\+\-\*\/%<>=!]/, "operator"],

        // Keywords
        [/\b(true|false|null)\b/, "keyword"],
        // Functions — identifier followed by (
        [/[a-zA-Z_][\w$]*(?=\s*\()/, "function"],

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

  monaco.editor.defineTheme("cel-dark", {
    base: "vs-dark",
    inherit: true,
    rules: [
      { token: "keyword", foreground: "C586C0" }, // purple
      { token: "identifier", foreground: "9CDCFE" }, // light blue
      { token: "number", foreground: "B5CEA8" }, // light green
      { token: "string", foreground: "CE9178" }, // salmon
      { token: "operator", foreground: "FFFF00" }, // yellow
      { token: "delimiter", foreground: "D4D4D4" }, // same as operator
      { token: "function", foreground: "C586C0" }, // purple
    ],
    colors: {
      "editor.background": "#00000000", // Transparent background
    },
  });

  monaco.languages.setLanguageConfiguration("cel", {
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
};
