import {
  editor,
  Token,
  languages,
  Position,
  CancellationToken,
} from "monaco-editor";

enum CompletionItemKind {
  Property = 9,
}

export function handleCompletions(
  model: editor.ITextModel,
  position: Position,
  context: languages.CompletionContext,
  token: CancellationToken
): languages.ProviderResult<languages.CompletionList> {
  const fieldsForSuggestions: string[] | undefined =
    (model as any).___fieldsForSuggestions___ || [];

  const word = model.getWordUntilPosition(position);
  const range = {
    startLineNumber: position.lineNumber,
    endLineNumber: position.lineNumber,
    startColumn: word.startColumn,
    endColumn: word.endColumn,
  };

  const textUntilPosition = model.getValueInRange({
    startLineNumber: position.lineNumber,
    startColumn: 1,
    endLineNumber: position.lineNumber,
    endColumn: position.column,
  });

  const match = textUntilPosition.match(
    /([a-zA-Z_][\w]*(?:\.[a-zA-Z_][\w]*)*)\.?$/
  );

  let pathPrefix = match?.[1] ?? ""; // e.g. "gcp.tags"
  pathPrefix = `${pathPrefix}.`;

  let suggestions = fieldsForSuggestions
    ?.filter((x) => x !== pathPrefix && x.startsWith(pathPrefix))
    .map((x) => x.replace(pathPrefix, ""))
    .map((x) => (x.startsWith(".") ? x.slice(1) : x))
    .filter((x) => x.length > 0)
    .map((label) => ({
      label,
      kind: CompletionItemKind.Property,
      insertText: label,
      range,
    }));

  suggestions = suggestions?.concat([
    {
      label: "contains",
      kind: 1, // languages.CompletionItemKind.Function,
      insertText: "contains('${1:arg}')",
      insertTextRules: 4, // languages.CompletionItemInsertTextRule.InsertAsSnippet,
      documentation: "Check if value contains a substring.",
      range,
    },
    {
      label: "startsWith",
      kind: 1, // languages.CompletionItemKind.Function,
      insertText: "startsWith('${1:arg}')",
      insertTextRules: 4, // languages.CompletionItemInsertTextRule.InsertAsSnippet,
      documentation: "When value starts with a substring.",
      range,
    },
    {
      label: "endsWith",
      kind: 1, // languages.CompletionItemKind.Function,
      insertText: "endsWith('${1:arg}')",
      insertTextRules: 4, // languages.CompletionItemInsertTextRule.InsertAsSnippet,
      documentation: "When value ends with a substring.",
      range,
    },
  ] as any);

  // console.log("Ihor", {
  //   pathPrefix,
  //   suggestions,
  //   fieldsForSuggestions: fieldsForSuggestions?.toSorted(),
  // });

  return { suggestions: suggestions || [] };
}
