module.exports = {
  editor: {
    create: jest.fn(),
    defineTheme: jest.fn(),
    setTheme: jest.fn(),
    getModel: jest.fn(),
    setModelMarkers: jest.fn(),
  },
  languages: {
    register: jest.fn(),
    setMonarchTokensProvider: jest.fn(),
    setLanguageConfiguration: jest.fn(),
    registerCompletionItemProvider: jest.fn(),
  },
  MarkerSeverity: {
    Error: 8,
    Warning: 4,
    Info: 2,
    Hint: 1,
  },
};