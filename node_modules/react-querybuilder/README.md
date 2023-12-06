# react-querybuilder

_The Query Builder component for React_

**React Query Builder** is a fully customizable query builder component for React, along with a collection of utility functions for [importing from](#import), and [exporting to](#export), various query languages like SQL, MongoDB, and more.

![Screenshot](../../_assets/screenshot.png)

## Documentation

Complete documentation is available at [https://react-querybuilder.js.org].

## Demo

[Click here to see a live, interactive demo](https://react-querybuilder.js.org/demo).

Custom components are not limited to the following libraries, but these have first-class support through their respective compatibility packages:

| Library                                            | Compatibility package                                                                        | Demo                                                     | Example                                                                                                               |
| -------------------------------------------------- | -------------------------------------------------------------------------------------------- | -------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------- |
| [Ant Design](https://ant.design/)                  | [@react-querybuilder/antd](https://www.npmjs.com/package/@react-querybuilder/antd)           | [demo](https://react-querybuilder.js.org/demo/antd)      | [example](https://codesandbox.io/p/sandbox/github/react-querybuilder/react-querybuilder/tree/main/examples/antd)      |
| [Bootstrap](https://getbootstrap.com/)             | [@react-querybuilder/bootstrap](https://www.npmjs.com/package/@react-querybuilder/bootstrap) | [demo](https://react-querybuilder.js.org/demo/bootstrap) | [example](https://codesandbox.io/p/sandbox/github/react-querybuilder/react-querybuilder/tree/main/examples/bootstrap) |
| [Bulma](https://bulma.io/)                         | [@react-querybuilder/bulma](https://www.npmjs.com/package/@react-querybuilder/bulma)         | [demo](https://react-querybuilder.js.org/demo/bulma)     | [example](https://codesandbox.io/p/sandbox/github/react-querybuilder/react-querybuilder/tree/main/examples/bulma)     |
| [Chakra UI](https://chakra-ui.com/)                | [@react-querybuilder/chakra](https://www.npmjs.com/package/@react-querybuilder/chakra)       | [demo](https://react-querybuilder.js.org/demo/chakra)    | [example](https://codesandbox.io/p/sandbox/github/react-querybuilder/react-querybuilder/tree/main/examples/chakra)    |
| [Fluent UI](https://github.com/microsoft/fluentui) | [@react-querybuilder/fluent](https://www.npmjs.com/package/@react-querybuilder/fluent)       | [demo](https://react-querybuilder.js.org/demo/fluent)    | [example](https://codesandbox.io/p/sandbox/github/react-querybuilder/react-querybuilder/tree/main/examples/fluent)    |
| [Mantine](https://mantine.dev/)                    | [@react-querybuilder/mantine](https://www.npmjs.com/package/@react-querybuilder/mantine)     | [demo](https://react-querybuilder.js.org/demo/mantine)   | [example](https://codesandbox.io/p/sandbox/github/react-querybuilder/react-querybuilder/tree/main/examples/mantine)   |
| [MUI](https://mui.com/)                            | [@react-querybuilder/material](https://www.npmjs.com/package/@react-querybuilder/material)   | [demo](https://react-querybuilder.js.org/demo/material)  | [example](https://codesandbox.io/p/sandbox/github/react-querybuilder/react-querybuilder/tree/main/examples/material)  |
| [React Native](https://reactnative.dev/)           | [@react-querybuilder/native](https://www.npmjs.com/package/@react-querybuilder/native)       |                                                          |                                                                                                                       |

## Basic usage

```bash
npm i react-querybuilder
# OR yarn add / pnpm add / bun add
```

```tsx
import { useState } from 'react';
import { Field, QueryBuilder, RuleGroupType } from 'react-querybuilder';
import 'react-querybuilder/dist/query-builder.css';

const fields: Field[] = [
  { name: 'firstName', label: 'First Name' },
  { name: 'lastName', label: 'Last Name' },
  { name: 'age', label: 'Age', inputType: 'number' },
  { name: 'address', label: 'Address' },
  { name: 'phone', label: 'Phone' },
  { name: 'email', label: 'Email', validator: ({ value }) => /^[^@]+@[^@]+/.test(value) },
  { name: 'twitter', label: 'Twitter' },
  { name: 'isDev', label: 'Is a Developer?', valueEditorType: 'checkbox', defaultValue: false },
];

const initialQuery: RuleGroupType = {
  combinator: 'and',
  rules: [],
};

export const App = () => {
  const [query, setQuery] = useState(initialQuery);

  return <QueryBuilder fields={fields} query={query} onQueryChange={q => setQuery(q)} />;
};
```

To enable drag-and-drop, install the [`@react-querybuilder/dnd` package](https://www.npmjs.com/package/@react-querybuilder/dnd) and nest `<QueryBuilder />` under `<QueryBuilderDnD />`.

## Export

To [export queries](https://react-querybuilder.js.org/docs/utils/export) as SQL, MongoDB, or one of several other formats, use the `formatQuery` function.

```ts
const query = {
  combinator: 'and',
  rules: [
    {
      field: 'first_name',
      operator: 'beginsWith',
      value: 'Stev',
    },
    {
      field: 'last_name',
      operator: 'in',
      value: 'Vai, Vaughan',
    },
  ],
};
const sqlWhere = formatQuery(query, 'sql');
console.log(sqlWhere);
// `(first_name like 'Stev%' and last_name in ('Vai', 'Vaughan'))`
```

## Import

To [import queries](https://react-querybuilder.js.org/docs/utils/import) use `parseSQL`, `parseCEL`, `parseJsonLogic`, or `parseMongoDB` depending on the source.

**Tip:** `parseSQL` will accept a full `SELECT` statement or the `WHERE` clause by itself (everything but the expressions in the `WHERE` clause will be ignored). Trailing semicolon is optional.

```ts
const query = parseSQL(
  `SELECT * FROM my_table WHERE first_name LIKE 'Stev%' AND last_name in ('Vai', 'Vaughan')`
);
console.log(query);
/*
{
  "combinator": "and",
  "rules": [
    {
      "field": "first_name",
      "operator": "beginsWith",
      "value": "Stev",
    },
    {
      "field": "last_name",
      "operator": "in",
      "value": "Vai, Vaughan",
    },
  ],
}
*/
```

Note: `formatQuery`, `transformQuery`, and the `parse*` functions can be used without importing React (e.g., on the server) like this:

```js
import { formatQuery } from 'react-querybuilder/formatQuery';
import { parseCEL } from 'react-querybuilder/parseCEL';
import { parseJsonLogic } from 'react-querybuilder/parseJsonLogic';
import { parseMongoDB } from 'react-querybuilder/parseMongoDB';
import { parseSQL } from 'react-querybuilder/parseSQL';
import { transformQuery } from 'react-querybuilder/transformQuery';
```
