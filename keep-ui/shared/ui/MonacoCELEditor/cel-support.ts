import { handleCompletions } from "./handle-completions";

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

  monaco.languages.setLanguageConfiguration("cel", {
    brackets: [
      ["[", "]"],
      ["(", ")"],
    ],
    autoClosingPairs: [
      { open: '"', close: '"' },
      { open: "'", close: "'" },
      { open: "[", close: "]" },
      { open: "(", close: ")" },
    ],
  });

  monaco.languages.registerCompletionItemProvider("cel", {
    triggerCharacters: ["."],

    provideCompletionItems: (
      model: any,
      position: any,
      context: any,
      cancellationToken: any
    ) => handleCompletions(model, position, context, cancellationToken),
  });
};
