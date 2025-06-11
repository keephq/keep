const React = require('react');

module.exports = {
  Editor: () => React.createElement('div', { 'data-testid': 'monaco-editor' }),
  DiffEditor: () => React.createElement('div', { 'data-testid': 'monaco-diff-editor' }),
  loader: {
    config: jest.fn(),
    init: jest.fn(() => Promise.resolve({
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
    })),
  },
};