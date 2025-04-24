import { extractMustacheVariables } from "../mustache";

describe("Mustache Utils", () => {
  it("should extract simple mustache variables", () => {
    const yamlString =
      "Hello {{alert.labels.severity}}, welcome to {{ place }}!";
    const variables = extractMustacheVariables(yamlString);
    expect(variables).toEqual(["alert.labels.severity", "place"]);
  });

  it("should extract variables from a more complex string", () => {
    const yamlString = `
      workflow:
        id: example-workflow
        steps:
          - name: step-1
            provider:
              type: http
              config: "{{ providers.http }}"
              with:
                url: "https://example.com/{{ steps.previous.results.id }}"
                headers:
                  Authorization: "Bearer {{ secrets.API_KEY }}"
    `;
    const variables = extractMustacheVariables(yamlString);
    expect(variables).toEqual([
      "providers.http",
      "steps.previous.results.id",
      "secrets.API_KEY",
    ]);
  });

  it("should handle variables with different spacing", () => {
    const yamlString = "Testing {{no_space}} and {{  extra_space  }} variables";
    const variables = extractMustacheVariables(yamlString);
    expect(variables).toEqual(["no_space", "extra_space"]);
  });

  it("should return an empty array when no variables are present", () => {
    const yamlString = "This string has no mustache variables";
    const variables = extractMustacheVariables(yamlString);
    expect(variables).toEqual([]);
  });

  it("should filter out invalid variables", () => {
    const yamlString =
      "Invalid variables: {{ }} and {{ invalid. }} but {{ valid }} is ok";
    const variables = extractMustacheVariables(yamlString);
    expect(variables).toEqual(["valid"]);
  });

  it("should extract the same variable multiple times if it appears multiple times", () => {
    const yamlString = "{{ repeated }} shows up {{ repeated }} twice";
    const variables = extractMustacheVariables(yamlString);
    expect(variables).toEqual(["repeated", "repeated"]);
  });
});
