// CELMonacoEditor.tsx
import { useEffect } from "react";
import * as monaco from "monaco-editor";

// Call this once before rendering
export const setupCustomCellanguage = () => {
  console.log("IHOR SET UP");
  monaco.languages.register({ id: "cel" });

  monaco.languages.setMonarchTokensProvider("cel", {
    tokenizer: {
      root: [
        [/\b(true|false|null)\b/, "keyword"],
        [/\b([a-zA-Z_]\w*)\b/, "identifier"],
        [/\d+/, "number"],
        [/".*?"/, "string"],
        [/[+\-*/=<>!]+/, "operator"],
        [/[(){}[\],.]/, "delimiter"],
      ],
    },
  });

  monaco.languages.setLanguageConfiguration("cel", {
    comments: {
      lineComment: "//",
    },
    brackets: [
      ["{", "}"],
      ["[", "]"],
      ["(", ")"],
    ],
    autoClosingPairs: [
      { open: '"', close: '"' },
      { open: "{", close: "}" },
      { open: "[", close: "]" },
      { open: "(", close: ")" },
    ],
  });
};
