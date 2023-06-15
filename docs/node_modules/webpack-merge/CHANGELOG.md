# Changelog

## 5.8.0 / 2021-06-07

- Docs - Update `env` example to be webpack 5 compatible. #177, #180
- Feat - Support strings as rules for TypeScript, not just enums. #179, #185

## 5.7.3 / 2020-12-22

- Fix - Don't merge strings with objects in `mergeWithRules`. #172

## 5.7.2 / 2020-12-16

- Fix - If there's no match when using `merge` operation with `mergeWithRules`, use default merge behavior as a fallback. #167

## 5.7.1 / 2020-12-16

- Fix - Fix a merge failure for `mergeWithRules` when non-array matches are merged. #166

## 5.7.0 / 2020-12-12

- Feat - Throw a `TypeError` if trying to use `mergeWithRules` with invalid configuration types for `append`/`prepend`/`merge` operations.

## 5.6.1 / 2020-12-11

- Fix - Drop extraneous logging.

## 5.6.0 / 2020-12-11

- Feat - Support `merge` (`CustomizeRule.Merge`) for objects at `mergeWithRules`. This is useful for merging loader options for example. #163

## 5.5.0 / 2020-12-10

- Feat - Allow `mergeWithRules` to merge based on rules without a match. #151 #159

## 5.4.1 / 2020-12-08

- Fix - Allow `mergeUnique` to work with arbitrary order. #161

## 5.4.0 / 2020-10-30

- Fix - Fall back correctly in `mergeWithRules` for cases that aren't matched. #157 #158
- Fix - Don't throw if using `mergeWithRules` without a rule #151
- Feat - Throw if `undefined` is passed to `merge` as a structure to merge

## 5.3.0 / 2020-10-30

- Fix - Expose `Configuration` type through a generic to TypeScript to support both webpack 4 and 5 #141 #154

In case you use webpack 4, please change your typing as instructed in the readme as the default type is loose but non-breaking.

## 5.2.0 / 2020-10-07

- Feature - Support advanced merging cases through `mergeWithRules` #146 #149

## 5.1.4 / 2020-09-09

- Fix - Expose `CustomizeRule` for TypeScript users #147

## 5.1.3 / 2020-08-30

- Fix - Allow merging a `RegExp` to itself #145

## 5.1.2 / 2020-08-18

- Fix - Allow overriding an object field with `null` #144

## 5.1.1 / 2020-08-04

- Fix - Drop `<reference types="webpack-dev-server" />` from **index.d.ts** #143

## 5.1.0 / 2020-08-03

- Feature - Expose `merge` as `default` for backwards-compatibility with TypeScript. Now `import merge from "webpack-merge";` works there. In CommonJS, the default alias is exposed through `default` property due to technical constraints.

## 5.0.9 / 2020-07-09

- Fix - Don't crash on `merge()` and `merge([])`. Now `{}` is returned in these corner cases.

## 5.0.8 / 2020-07-07

- Fix - Support Node 10 #138

## 5.0.7 / 2020-07-06

- Fix - Drop tslib dependency by setting `"importHelpers": false,`

## 5.0.6 / 2020-07-06

- Fix - Add tslib to dependencies

## 5.0.5 / 2020-07-06

- Tech - Optimize build size (UMD isn't needed)

## 5.0.4 / 2020-07-06

- Documentation - Use CommonJS imports at the examples. #137

## 5.0.3 / 2020-07-06

- Feature - Support TypeScript out of the box. #84 #86 #95 #110 #112
- Deprecation - `merge.smart` has been dropped as it's tricky to support all the corner cases. Instead, it's better to use the provided utilities to put together a `merge` that fits your case.
- Deprecation - `mergeStrategy` has been dropped in favor of using `mergeWithCustomize` with `customizeArray` and `customizeObject`.
- Deprecation - `merge.multiple` has been dropped as the functionality was too specific and it's better to implement in the user space if needed.
- Breaking - `merge` has been moved as a regular import (i.e. `import { merge } from 'webpack-merge'`).
- Breaking - Merge customization has been moved behind `mergeWithCustomize`.
- Breaking - Bump supported Node version to 12
- Feature - `customizeArray` supports wildcards now. Example: `'entry.*': 'prepend'`. #45 #99
- Feature - Throw an error in case a `Promise` is being merged. It's better to wrap configuration within a `Promise` and merge inside it. #81
- Fix - Drop lodash in favor of simpler dependencies. #134
- Fix - Make `unique` merge from right to left to match behavior elsewhere. #119
- Fix - Make sure `unique` doesn't lose non-unique items to merge. #125

Special thanks to Google and Addy Osmani for supporting the work financially as it allowed me to complete the work required by the new major release.

## 4.2.2 / 2019-08-27

- Fix - Update minimum version of lodash to 4.17.15 in order to avoid `npm audit warning`. #116
- Docs - Improve `merge.unique` documentation. #103
- Docs - Add clear note about precedence. #115

## 4.2.1 / 2019-01-04

- Feature - Support `oneOf` at `merge.smart`. #111
- Fix - If there's only single array to merge, clone it. #106

## 4.1.4 / 2018-08-01

- Maintenance - Remove bitHound from the README as it closed down. #102

## 4.1.3 / 2018-06-14

- Fix - Smart merge respects the existing loader order #79, #101

## 4.1.2 / 2017-02-22

- Maintenance - Update lodash, #97, #98

## 4.1.1 / 2017-11-01

- Docs - Add `customizeArray` and `customizeObject` examples. #93

## 4.1.0 / 2017-03-16

- Feature - `merge.multiple` to allow working with webpack multi-compiler mode. It accepts multiple objects and returns an array you can push to webpack. #74

## 4.0.0 / 2017-03-06

- Breaking feature - `merge.smart` allows re-ordering loaders like below. #70

```javascript
merge.smart(
  {
    loaders: [
      {
        test: /\.js$/,
        loaders: ["babel"],
      },
    ],
  },
  {
    loaders: [
      {
        test: /\.js$/,
        loaders: ["react-hot", "babel"],
      },
    ],
  }
);
// will become
{
  loaders: [
    {
      test: /\.js$/,
      // order of second argument is respected
      loaders: ["react-hot", "babel"],
    },
  ];
}
```

## 3.0.0 / 2017-02-19

- Breaking fix - `merge.smart` should not merge a child missing `include`/`exclude` to a parent that has either. This is safer and more predictable behavior than the old one. #69

## 2.6.1 / 2017-01-29

- Bug fix - `merge.smart` should not merge rules that have differing `enforce` fields. #65

## 2.6.0 / 2017-01-27

- Bug fix - Support `replace` mode for `merge.smartStrategy`. #63

## 2.5.0 / 2017-01-26

- Bug fix - Make sure `merge.smartStrategy` works with higher level nesting like `'module.rules.use': 'prepend'`. #64

## 2.4.0 / 2017-01-12

- Feature - Add `merge.unique` helper that plugs into `customizeArray`. This allows you to force only one plugin of a type to the end result. #58

## 2.3.1 / 2017-01-06

- Bug fix - Clear up `CopyWebpackPlugin` handling. #56

## 2.3.0 / 2017-01-06

- Refactor - Depend only on `lodash` instead of individual packages as latter has been discontinued. #52

## 2.2.0 / 2017-01-05

- Bug fix - Drop `merge.smartStrategy(rules, plugins)` as that caused other issues (prototype copying for complex cases). That needs a better approach. #55

## 2.1.1 / 2017-01-05

- Bug fix - Avoid recursion at `merge.smart`. #53

## 2.1.0 / 2017-01-05

- Feature - Allow `merge.smartStrategy` to merge plugin contents. API: `merge.smartStrategy(rules, plugins)`. #44. Example:

```javascript
const output = merge.smartStrategy(
  {
    entry: 'prepend', // or 'replace'
    'module.loaders': 'prepend'
  },
  ['LoaderOptionsPlugin']
)(object1, object2, object3, ...);
```

## 2.0.0 / 2016-12-22

- Breaking - Disallow overriding configuration with empty arrays/objects (#48). If you want to override, use `merge.strategy`. Example:

```javascript
const a = {
  entry: ["foo"],
};
const b = {
  entry: [],
};

merge(a, b); // Yields a result, not b like before.
```

## 1.1.2 / 2016-12-18

- Bug fix - `merge({ entry: {} })` should return the same result as input instead of a function.

## 1.1.1 / 2016-12-11

- Bug fix - Support previously undocumented, yet used, `merge([<object>])` format. This works with all available functions. #46

## 1.1.0 / 2016-12-09

- Feature - Allow `merge` behavior to be customized with overrides. Example:

```javascript
var output = merge({
  customizeArray(a, b, key) { return [...a, ...b]; },
  customizeObject(a, b, key) { return mergeWith(a, b); }
})(object1, object2, object3, ...);
```

This allows you to guarantee array uniqueness and so on.

## 1.0.2 / 2016-11-29

- Bug fix - `merge` should not mutate inputs with mismatched keys.

## 1.0.0 / 2016-11-28

- Feature: Support merging Webpack 2 Rule.use. #38
- Bug fix - Don't concat loaders if the first matching entry's include/exclude doesn't match. #39

## 0.20.0 / 2016-11-27

- Feature: Add support for merging functions. This feature has been designed `postcss` in mind. It executes the functions, picks their results, and packs them again.

## 0.19.0 / 2016-11-26

- Feature: Add support for 'replace' option at `merge.strategy`. It literally replaces the old field value with the newer one. #40

## 0.18.0 / 2016-11-24

- Feature: Add support for recursive definitions at `merge.strategy`. Example:

```javascript
var output = merge.strategy({
  entry: 'prepend',
  'module.loaders': 'prepend'
})(object1, object2, object3, ...);
```

- Feature: Add `merge.smartStrategy`. This combines the ideas of `merge.smart` and `merge.strategy` into one. Example:

```javascript
var output = merge.smartStrategy({
  entry: 'prepend',
  'module.loaders': 'prepend'
})(object1, object2, object3, ...);
```

## 0.17.0 / 2016-11-16

- Feature: Add support for `merge.strategy`. Now you can customize merging behavior per root level configuration field. Example: `merge.strategy({ entry: 'prepend' })(object1, object2, object3, ...);`. #17

## 0.16.0 / 2016-11-14

- Feature: Add support for webpack 2 at `merge.smart`. It should pick up `module.rules` as you might expect now. #35

## 0.15.0 / 2016-10-18

- Breaking: Rework `merge.smart` so that it **appends** loaders instead of **prepending** them. This is the logical thing to do as it allows you to specify behavior better as you `merge`. #32

## 0.14.1 / 2016-07-25

- Docs: Improve package description. #23.
- Bug fix - Let `merge.smart` merge loaders based on their full name instead of first letter. Thanks to @choffmeister. #26.

## 0.14.0 / 2016-06-05

- Feature: Allow `merge.smart` to merge `loaders` if `exclude` is the same. Thanks to @mshwery. #21.

## 0.13.0 / 2016-05-24

- Bug fix: Allow `merge.smart` to merge configuration if `include` is defined. Thanks to @blackrabbit99. #20.

## 0.12.0 / 2016-04-19

- Feature: Support `include/exclude` at `merge.smart` for `loader` definition too. Thanks to @Whoaa512. #16.

## 0.11.0 / 2016-04-18

- Feature: Support `include/exclude` at `merge.smart` when its set only in a parent. #15.

## 0.10.0 / 2016-04-10

- Feature: Support `include/exclude` at `merge.smart`. Thanks to @siready. #14.

## 0.9.0 / 2016-04-08

- Feature: Allow existing objects/arrays to be emptied with an empty object/array later in merge. This overriding behavior is useful for example emptying your `entry` configuration.

## 0.8.4 / 2016-03-17

- Bug fix: _webpack-merge_ should not mutate inputs. #12

## 0.8.3 / 2016-03-02

- Bug fix: Drop `files` field from _package.json_ as it wasn't including the dist correctly.

## 0.8.0 / 2016-03-02

- Breaking: Change merging behavior so that only loaders get prepended. The rest follow appending logic. This makes `entry` array merging behavior logical. Prepend makes sense only for loaders after all. #10

## 0.7.3 / 2016-01-11

- Bug fix: Do not error when there are no matching loaders. Thanks @GreenGremlin!

## 0.7.2 / 2016-01-08

- Regenerate tarball. The problem was that there were some old dependencies included. Closes #7.

## 0.7.1 / 2016-01-03

- Improve performance by defaulting to `concat` and by dropping a redundant check. Thanks @davegomez!

## 0.7.0 / 2015-12-31

- Bug fix: Arrays get merged within nested structures correctly now. Array items are prepended (reverse order compared to earlier). This is related to the change made in _0.6.0_. Incidentally this change affects normal merge as well.
- Smart merge: If a loader contains either `include` or `exclude`, it will generate separate entries instead of merging. Without this the configuration might change in an unpredictable manner.

## 0.6.0 / 2015-12-30

- Support `preLoaders` and `postLoaders`. Previously only `loaders` were supported.
- Breaking: Change smart merging behavior for `loaders` field so that it prepends loaders instead of appending them. The benefit of this is that now it's possible to specialize loader setup in a predictable manner. For example you can have a linter set up at the root and expect it to become evaluated first always.

## 0.5.1 / 2015-12-26

- Fix `merge` object/array case (missing `bind`). The behavior should be correct now.

## 0.5.0 / 2015-12-26

- Breaking: Push smart merging behind `merge.smart`. Now `merge` behaves exactly as in _0.3.0_ series.

## 0.4.0 / 2015-12-23

- Dropped changelog generator. It's better to write these by hand.
- Breaking: Added smart merging (@GreenGremlin)

## 0.3.2 / 2015-11-23

- Tweaked changelog generator process.

## 0.3.1 / 2015-11-23

- Added changelog generator.

## 0.3.0 / 2015-11-13

- Improved formatting
- Allowed an arbitrary amount of objects to be merged

## 0.2.0 / 2015-08-30

- Only require lodash modules used by the package (@montogeek)
- Removed lodash.isarray dependency, use Array.isArray standard object

## 0.1.3 / 2015-08-10

- Improved README example

## 0.1.2 / 2015-07-01

- Simplified example

## 0.1.1 / 2015-06-26

- Fixed travis link

## 0.1.0 / 2015-06-26

- Initial implementation
