import { parseDocument } from "yaml";
import { getCurrentPath } from "../MonacoEditorWithValidation";

const yaml = `
workflow:
  steps:
    - name: step1
      provider:
        type: test
`;

describe("getCurrentPath", () => {
  const doc = parseDocument(yaml);

  it("should get nested path", () => {
    const path = getCurrentPath(doc, 69);
    expect(path).toEqual(["workflow", "steps", 0, "provider", "type"]);
  });

  it("should get root path", () => {
    const path = getCurrentPath(doc, 1);
    expect(path).toEqual(["workflow"]);
  });

  it("should get nested path, at 30", () => {
    const path = getCurrentPath(doc, 30);
    expect(path).toEqual(["workflow", "steps", 0, "name"]);
  });
});
