import { editor, languages, Position, CancellationToken } from "monaco-editor";

// NOTE: The enums below are workarounds due to inability to import from monaco-editor (turbopack related)
enum CompletionItemKind {
  Function = 1,
  Property = 9,
}

enum CompletionItemInsertTextRule {
  InsertAsSnippet = 4,
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
    ?.filter(
      (fieldSuggestion) =>
        fieldSuggestion !== pathPrefix && fieldSuggestion.startsWith(pathPrefix)
    )
    .map((fieldSuggestion) => fieldSuggestion.replace(pathPrefix, ""))
    .map((fieldSuggestion) =>
      fieldSuggestion.startsWith(".")
        ? fieldSuggestion.slice(1)
        : fieldSuggestion
    )
    .filter((fieldSuggestion) => fieldSuggestion.length > 0)
    .map((label) => ({
      label,
      kind: CompletionItemKind.Property,
      insertText: label,
      range,
    }));

  suggestions = suggestions?.concat([
    {
      label: "contains",
      kind: CompletionItemKind.Function,
      insertText: "contains('${1:arg}')",
      insertTextRules: CompletionItemInsertTextRule.InsertAsSnippet,
      documentation: "Check if value contains a substring.",
      range,
    },
    {
      label: "startsWith",
      kind: CompletionItemKind.Function,
      insertText: "startsWith('${1:arg}')",
      insertTextRules: CompletionItemInsertTextRule.InsertAsSnippet,
      documentation: "When value starts with a substring.",
      range,
    },
    {
      label: "endsWith",
      kind: CompletionItemKind.Function,
      insertText: "endsWith('${1:arg}')",
      insertTextRules: CompletionItemInsertTextRule.InsertAsSnippet,
      documentation: "When value ends with a substring.",
      range,
    },
  ] as any);

  return { suggestions: suggestions || [] };
}
