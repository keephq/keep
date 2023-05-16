# Changelog

## [5.1.0](https://github.com/googleapis/gaxios/compare/v5.0.2...v5.1.0) (2023-03-06)


### Features

* Add support for custom backoff ([#498](https://github.com/googleapis/gaxios/issues/498)) ([4a34467](https://github.com/googleapis/gaxios/commit/4a344678110864d97818a8272ebcc5e1c4921b52))

## [5.0.2](https://github.com/googleapis/gaxios/compare/v5.0.1...v5.0.2) (2022-09-09)


### Bug Fixes

* Do not import the whole google-gax from proto JS ([#1553](https://github.com/googleapis/gaxios/issues/1553)) ([#501](https://github.com/googleapis/gaxios/issues/501)) ([6f58d1e](https://github.com/googleapis/gaxios/commit/6f58d1e80ce6b196d17fbc75dc47d8d20804920a))
* use google-gax v3.3.0 ([6f58d1e](https://github.com/googleapis/gaxios/commit/6f58d1e80ce6b196d17fbc75dc47d8d20804920a))

## [5.0.1](https://github.com/googleapis/gaxios/compare/v5.0.0...v5.0.1) (2022-07-04)


### Bug Fixes

* **types:** loosen AbortSignal type ([5a379ca](https://github.com/googleapis/gaxios/commit/5a379ca123f08f286c4774711a7a3293bffc1ea6))

## [5.0.0](https://github.com/googleapis/gaxios/compare/v4.3.3...v5.0.0) (2022-04-20)


### ⚠ BREAKING CHANGES

* drop node 10 from engines list, update typescript to 4.6.3 (#477)

### Features

* handling missing process global ([c30395b](https://github.com/googleapis/gaxios/commit/c30395bbf34d889e75c7c72a7dff701dc7a98244))


### Build System

* drop node 10 from engines list, update typescript to 4.6.3 ([#477](https://github.com/googleapis/gaxios/issues/477)) ([a926962](https://github.com/googleapis/gaxios/commit/a9269624a70aa6305599cc0af079d0225ed6af50))

### [4.3.3](https://github.com/googleapis/gaxios/compare/v4.3.2...v4.3.3) (2022-04-08)


### Bug Fixes

* do not stringify form data ([#475](https://github.com/googleapis/gaxios/issues/475)) ([17370dc](https://github.com/googleapis/gaxios/commit/17370dcdfd4568d7f3f0855961030d238166836a))

### [4.3.2](https://www.github.com/googleapis/gaxios/compare/v4.3.1...v4.3.2) (2021-09-14)


### Bug Fixes

* address codeql warning with hostname matches ([#415](https://www.github.com/googleapis/gaxios/issues/415)) ([5a4d060](https://www.github.com/googleapis/gaxios/commit/5a4d06019343aa08e1bcf8e05108e22ac3b12636))

### [4.3.1](https://www.github.com/googleapis/gaxios/compare/v4.3.0...v4.3.1) (2021-09-02)


### Bug Fixes

* **build:** switch primary branch to main ([#427](https://www.github.com/googleapis/gaxios/issues/427)) ([819219e](https://www.github.com/googleapis/gaxios/commit/819219ed742814259c525bdf5721b28234019c08))

## [4.3.0](https://www.github.com/googleapis/gaxios/compare/v4.2.1...v4.3.0) (2021-05-26)


### Features

* allow cert and key to be provided for mTLS ([#399](https://www.github.com/googleapis/gaxios/issues/399)) ([d74ab91](https://www.github.com/googleapis/gaxios/commit/d74ab9125d581e46d655614729872e79317c740d))

### [4.2.1](https://www.github.com/googleapis/gaxios/compare/v4.2.0...v4.2.1) (2021-04-20)


### Bug Fixes

* **deps:** upgrade webpack and karma-webpack ([#379](https://www.github.com/googleapis/gaxios/issues/379)) ([75c9013](https://www.github.com/googleapis/gaxios/commit/75c90132e99c2f960c01e0faf0f8e947c920aa73))

## [4.2.0](https://www.github.com/googleapis/gaxios/compare/v4.1.0...v4.2.0) (2021-03-01)


### Features

* handle application/x-www-form-urlencoded/Buffer ([#374](https://www.github.com/googleapis/gaxios/issues/374)) ([ce21e9c](https://www.github.com/googleapis/gaxios/commit/ce21e9ccd228578a9f90bb2fddff797cec4a9402))

## [4.1.0](https://www.github.com/googleapis/gaxios/compare/v4.0.1...v4.1.0) (2020-12-08)


### Features

* add an option to configure the fetch impl ([#342](https://www.github.com/googleapis/gaxios/issues/342)) ([2e081ef](https://www.github.com/googleapis/gaxios/commit/2e081ef161d84aa435788e8d525d393dc7964117))
* add no_proxy env variable ([#361](https://www.github.com/googleapis/gaxios/issues/361)) ([efe72a7](https://www.github.com/googleapis/gaxios/commit/efe72a71de81d466160dde5da551f7a41acc3ac4))

### [4.0.1](https://www.github.com/googleapis/gaxios/compare/v4.0.0...v4.0.1) (2020-10-27)


### Bug Fixes

* prevent bonus ? with empty qs params ([#357](https://www.github.com/googleapis/gaxios/issues/357)) ([b155f76](https://www.github.com/googleapis/gaxios/commit/b155f76cbc4c234da1d99c26691296702342c205))

## [4.0.0](https://www.github.com/googleapis/gaxios/compare/v3.2.0...v4.0.0) (2020-10-21)


### ⚠ BREAKING CHANGES

* parameters in `url` and parameters provided via params will now be combined.

### Bug Fixes

* drop requirement on URL/combine url and params ([#338](https://www.github.com/googleapis/gaxios/issues/338)) ([e166bc6](https://www.github.com/googleapis/gaxios/commit/e166bc6721fd979070ab3d9c69b71ffe9ee061c7))

## [3.2.0](https://www.github.com/googleapis/gaxios/compare/v3.1.0...v3.2.0) (2020-09-14)


### Features

* add initial retry delay, and set default to 100ms ([#336](https://www.github.com/googleapis/gaxios/issues/336)) ([870326b](https://www.github.com/googleapis/gaxios/commit/870326b8245f16fafde0b0c32cfd2f277946e3a1))

## [3.1.0](https://www.github.com/googleapis/gaxios/compare/v3.0.4...v3.1.0) (2020-07-30)


### Features

* pass default adapter to adapter option ([#319](https://www.github.com/googleapis/gaxios/issues/319)) ([cf06bd9](https://www.github.com/googleapis/gaxios/commit/cf06bd9f51cbe707ed5973e390d31a091d4537c1))

### [3.0.4](https://www.github.com/googleapis/gaxios/compare/v3.0.3...v3.0.4) (2020-07-09)


### Bug Fixes

* typeo in nodejs .gitattribute ([#306](https://www.github.com/googleapis/gaxios/issues/306)) ([8514672](https://www.github.com/googleapis/gaxios/commit/8514672f9d56bc6f077dcbab050b3342d4e343c6))

### [3.0.3](https://www.github.com/googleapis/gaxios/compare/v3.0.2...v3.0.3) (2020-04-20)


### Bug Fixes

* apache license URL ([#468](https://www.github.com/googleapis/gaxios/issues/468)) ([#272](https://www.github.com/googleapis/gaxios/issues/272)) ([cf1b7cb](https://www.github.com/googleapis/gaxios/commit/cf1b7cb66e4c98405236834e63349931b4f35b90))

### [3.0.2](https://www.github.com/googleapis/gaxios/compare/v3.0.1...v3.0.2) (2020-03-24)


### Bug Fixes

* continue replacing application/x-www-form-urlencoded with application/json ([#263](https://www.github.com/googleapis/gaxios/issues/263)) ([dca176d](https://www.github.com/googleapis/gaxios/commit/dca176df0990f2c22255f9764405c496ea07ada2))

### [3.0.1](https://www.github.com/googleapis/gaxios/compare/v3.0.0...v3.0.1) (2020-03-23)


### Bug Fixes

* allow an alternate JSON content-type to be set ([#257](https://www.github.com/googleapis/gaxios/issues/257)) ([698a29f](https://www.github.com/googleapis/gaxios/commit/698a29ff3b22f30ea99ad190c4592940bef88f1f))

## [3.0.0](https://www.github.com/googleapis/gaxios/compare/v2.3.2...v3.0.0) (2020-03-19)


### ⚠ BREAKING CHANGES

* **deps:** TypeScript introduced breaking changes in generated code in 3.7.x
* drop Node 8 from engines field (#254)

### Features

* drop Node 8 from engines field ([#254](https://www.github.com/googleapis/gaxios/issues/254)) ([8c9fff7](https://www.github.com/googleapis/gaxios/commit/8c9fff7f92f70f029292c906c62d194c1d58827d))
* **deps:** updates to latest TypeScript ([#253](https://www.github.com/googleapis/gaxios/issues/253)) ([054267b](https://www.github.com/googleapis/gaxios/commit/054267bf12e1801c134e3b5cae92dcc5ea041fab))

### [2.3.2](https://www.github.com/googleapis/gaxios/compare/v2.3.1...v2.3.2) (2020-02-28)


### Bug Fixes

* update github repo in package ([#239](https://www.github.com/googleapis/gaxios/issues/239)) ([7e750cb](https://www.github.com/googleapis/gaxios/commit/7e750cbaaa59812817d725c74fb9d364c4b71096))

### [2.3.1](https://www.github.com/googleapis/gaxios/compare/v2.3.0...v2.3.1) (2020-02-13)


### Bug Fixes

* **deps:** update dependency https-proxy-agent to v5 ([#233](https://www.github.com/googleapis/gaxios/issues/233)) ([56de0a8](https://www.github.com/googleapis/gaxios/commit/56de0a824a2f9622e3e4d4bdd41adccd812a30b4))

## [2.3.0](https://www.github.com/googleapis/gaxios/compare/v2.2.2...v2.3.0) (2020-01-31)


### Features

* add promise support for onRetryAttempt and shouldRetry ([#223](https://www.github.com/googleapis/gaxios/issues/223)) ([061afa3](https://www.github.com/googleapis/gaxios/commit/061afa381a51d39823e63accf3dacd16e191f3b9))

### [2.2.2](https://www.github.com/googleapis/gaxios/compare/v2.2.1...v2.2.2) (2020-01-08)


### Bug Fixes

* **build:** add publication configuration ([#218](https://www.github.com/googleapis/gaxios/issues/218)) ([43e581f](https://www.github.com/googleapis/gaxios/commit/43e581ff4ed5e79d72f6f29748a5eebb6bff1229))

### [2.2.1](https://www.github.com/googleapis/gaxios/compare/v2.2.0...v2.2.1) (2020-01-04)


### Bug Fixes

* **deps:** update dependency https-proxy-agent to v4 ([#201](https://www.github.com/googleapis/gaxios/issues/201)) ([5cdeef2](https://www.github.com/googleapis/gaxios/commit/5cdeef288a0c5c544c0dc2659aafbb2215d06c4b))
* remove retryDelay option ([#203](https://www.github.com/googleapis/gaxios/issues/203)) ([d21e08d](https://www.github.com/googleapis/gaxios/commit/d21e08d2aada980d39bc5ca7093d54452be2d646))

## [2.2.0](https://www.github.com/googleapis/gaxios/compare/v2.1.1...v2.2.0) (2019-12-05)


### Features

* populate GaxiosResponse with raw response information (res.url) ([#189](https://www.github.com/googleapis/gaxios/issues/189)) ([53a7f54](https://www.github.com/googleapis/gaxios/commit/53a7f54cc0f20320d7a6a21a9a9f36050cec2eec))


### Bug Fixes

* don't retry a request that is aborted intentionally ([#190](https://www.github.com/googleapis/gaxios/issues/190)) ([ba9777b](https://www.github.com/googleapis/gaxios/commit/ba9777b15b5262f8288a8bb3cca49a1de8427d8e))
* **deps:** pin TypeScript below 3.7.0 ([5373f07](https://www.github.com/googleapis/gaxios/commit/5373f0793a765965a8221ecad2f99257ed1b7444))

### [2.1.1](https://www.github.com/googleapis/gaxios/compare/v2.1.0...v2.1.1) (2019-11-15)


### Bug Fixes

* **docs:** snippets are now replaced in jsdoc comments ([#183](https://www.github.com/googleapis/gaxios/issues/183)) ([8dd1324](https://www.github.com/googleapis/gaxios/commit/8dd1324256590bd2f2e9015c813950e1cd8cb330))

## [2.1.0](https://www.github.com/googleapis/gaxios/compare/v2.0.3...v2.1.0) (2019-10-09)


### Bug Fixes

* **deps:** update dependency https-proxy-agent to v3 ([#172](https://www.github.com/googleapis/gaxios/issues/172)) ([4a38f35](https://www.github.com/googleapis/gaxios/commit/4a38f35))


### Features

* **TypeScript:** agent can now be passed as builder method, rather than agent instance ([c84ddd6](https://www.github.com/googleapis/gaxios/commit/c84ddd6))

### [2.0.3](https://www.github.com/googleapis/gaxios/compare/v2.0.2...v2.0.3) (2019-09-11)


### Bug Fixes

* do not override content-type if its given ([#158](https://www.github.com/googleapis/gaxios/issues/158)) ([f49e0e6](https://www.github.com/googleapis/gaxios/commit/f49e0e6))
* improve stream detection logic ([6c41537](https://www.github.com/googleapis/gaxios/commit/6c41537))
* revert header change ([#161](https://www.github.com/googleapis/gaxios/issues/161)) ([b0f6a8b](https://www.github.com/googleapis/gaxios/commit/b0f6a8b))

### [2.0.2](https://www.github.com/googleapis/gaxios/compare/v2.0.1...v2.0.2) (2019-07-23)


### Bug Fixes

* check for existence of fetch before using it ([#138](https://www.github.com/googleapis/gaxios/issues/138)) ([79eb58d](https://www.github.com/googleapis/gaxios/commit/79eb58d))
* **docs:** make anchors work in jsdoc ([#139](https://www.github.com/googleapis/gaxios/issues/139)) ([85103bb](https://www.github.com/googleapis/gaxios/commit/85103bb))
* prevent double option processing ([#142](https://www.github.com/googleapis/gaxios/issues/142)) ([19b4b3c](https://www.github.com/googleapis/gaxios/commit/19b4b3c))
