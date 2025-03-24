import { parseDocument } from "yaml";
import { getCurrentPath } from "../yaml-utils";

const yaml = `
workflow:
  steps:
    - name: step1
      provider:
        type: test
`;

describe("getCurrentPath", () => {
  const doc = parseDocument(yaml);

  it("should get nested path at provider.type field", () => {
    // workflow:
    //   steps:
    //     - name: step1
    //       provider:
    //         type: t<cursor here>est
    const path = getCurrentPath(doc, 69);
    expect(path).toEqual(["workflow", "steps", 0, "provider", "type"]);
  });

  it("should get root path", () => {
    // w<cursor here>orkflow:
    //   steps:
    //     - name: step1
    //       provider:
    //         type: test
    const path = getCurrentPath(doc, 1);
    expect(path).toEqual(["workflow"]);
  });

  it("should get nested path, at name field", () => {
    // workflow:
    //   steps:
    //     - name<cursor here>: step1
    //       provider:
    //         type: test
    const path = getCurrentPath(doc, 30);
    expect(path).toEqual(["workflow", "steps", 0, "name"]);
  });
});
