"""
Test the io handler
"""

from keep.api.models.alert import AlertDto
from keep.iohandler.iohandler import IOHandler


def test_vanilla(context_manager):
    iohandler = IOHandler(context_manager)
    s = iohandler.render("hello world")
    assert s == "hello world"


def test_with_basic_context(context_manager):
    iohandler = IOHandler(context_manager)
    context_manager.steps_context = {
        "name": "s",
    }
    context_manager.providers_context = {
        "name": "s2",
    }
    s = iohandler.render("hello {{ steps.name }}")
    s2 = iohandler.render("hello {{ providers.name }}")
    assert s == "hello s"
    assert s2 == "hello s2"


def test_with_function(context_manager):
    iohandler = IOHandler(context_manager)
    context_manager.steps_context = {
        "some_list": [1, 2, 3],
    }
    context_manager.providers_context = {
        "name": "s3",
    }
    s = iohandler.render("hello keep.len({{ steps.some_list }})")
    assert s == "hello 3"


def test_with_function_2(context_manager):
    iohandler = IOHandler(context_manager)
    context_manager.steps_context = {
        "some_list": [1, 2, 3],
    }
    context_manager.providers_context = {
        "name": "s3",
    }
    s = iohandler.render("hello keep.first({{ steps.some_list }})")
    assert s == "hello 1"


def test_with_json_dumps(context_manager):
    iohandler = IOHandler(context_manager)
    context_manager.steps_context = {
        "some_list": [1, 2, 3],
    }
    context_manager.providers_context = {
        "name": "s3",
    }
    s = iohandler.render("hello keep.json_dumps({{ steps.some_list }})")
    assert s == "hello [\n    1,\n    2,\n    3\n]"


def test_with_json_dumps_when_json_string(context_manager):
    iohandler = IOHandler(context_manager)
    context_manager.steps_context = {
        "some_list": "[1, 2, 3]",
    }
    context_manager.providers_context = {
        "name": "s3",
    }
    s = iohandler.render("hello keep.json_dumps({{ steps.some_list }})")
    assert s == "hello [\n    1,\n    2,\n    3\n]"


def test_alert_with_odd_number_of_parentheses(context_manager):
    """Tests complex alert with odd number of parentheses

    "unterminated string literal" error is raised when the alert message contains an odd number of parentheses
    """

    # this is example for sentry alert with
    #      "  }, [data, data?.storeDetails, onSelect]);",
    # that screwed are iohandler
    #
    context_manager.alert = AlertDto(
        **{
            "id": "test",
            "name": "test",
            "lastReceived": "2024-03-20T00:00:00.000Z",
            "source": ["sentry"],
            "environment": "prod",
            "service": None,
            "apiKeyRef": None,
            "message": "Object captured as exception with keys: test, test2, test3, test4, test5",
            "labels": {},
            "fingerprint": "testtesttest",
            "dismissUntil": None,
            "dismissed": False,
            "jira_component": "Test",
            "linearb_service": "Test - UI",
            "jira_component_full": "Test (UI)",
            "alert_hash": "testtesttest",
            "jira_priority": "High",
            "exceptions": [
                {
                    "type": "Error",
                    "value": "Object captured as exception with keys: test, test2, test3, test4, test5",
                    "mechanism": {
                        "type": "generic",
                        "handled": True,
                        "synthetic": True,
                    },
                    "stacktrace": {
                        "frames": [
                            {
                                "colno": 1,
                                "in_app": False,
                                "lineno": 9,
                                "module": "chunks/framework",
                                "abs_path": "app:///_next/static/chunks/framework-test.js",
                                "filename": "app:///_next/static/chunks/framework-test.js",
                            },
                            {
                                "colno": 2,
                                "in_app": False,
                                "lineno": 9,
                                "module": "chunks/framework",
                                "abs_path": "app:///_next/static/chunks/framework-test.js",
                                "filename": "app:///_next/static/chunks/framework-test.js",
                                "function": "r8",
                            },
                            {
                                "colno": 3,
                                "in_app": False,
                                "lineno": 9,
                                "module": "chunks/framework",
                                "abs_path": "app:///_next/static/chunks/framework-test.js",
                                "filename": "app:///_next/static/chunks/framework-test.js",
                                "function": "oP",
                            },
                            {
                                "colno": 4,
                                "in_app": False,
                                "lineno": 9,
                                "module": "chunks/framework",
                                "abs_path": "app:///_next/static/chunks/framework-test.js",
                                "filename": "app:///_next/static/chunks/framework-test.js",
                                "function": "oU",
                            },
                            {
                                "colno": 5,
                                "in_app": False,
                                "lineno": 9,
                                "module": "chunks/framework",
                                "abs_path": "app:///_next/static/chunks/framework-test.js",
                                "filename": "app:///_next/static/chunks/framework-test.js",
                            },
                            {
                                "colno": 6,
                                "in_app": False,
                                "lineno": 9,
                                "module": "chunks/framework",
                                "abs_path": "app:///_next/static/chunks/framework-test.js",
                                "filename": "app:///_next/static/chunks/framework-test.js",
                                "function": "oV",
                            },
                            {
                                "colno": 7,
                                "in_app": False,
                                "lineno": 9,
                                "module": "chunks/framework",
                                "abs_path": "app:///_next/static/chunks/framework-test.js",
                                "filename": "app:///_next/static/chunks/framework-test.js",
                                "function": "uU",
                            },
                            {
                                "data": {
                                    "sourcemap": "app:///_next/static/chunks/pages/_app-test.js.map",
                                    "symbolicated": True,
                                    "resolved_with": "index",
                                },
                                "colno": 14,
                                "in_app": True,
                                "lineno": 43,
                                "module": "chunks/pages/modules/shared/components/test-test-test/test-test-test",
                                "abs_path": "app:///_next/static/chunks/pages/modules/shared/components/test-test-test/test-test-test.tsx",
                                "filename": "./modules/shared/components/test-test-test/test-test-test.tsx",
                                "function": "<anonymous>",
                                "pre_context": [
                                    "      onSelect(data.storeDetails);",
                                    "    }",
                                    "  }, [data, data?.storeDetails, onSelect]);",
                                    "",
                                    "  useEffect(() => {",
                                ],
                                "context_line": "    error && captureException(error, { extra: { test } });",
                                "post_context": [
                                    "  }, [error, storeId]);",
                                    "",
                                    "  const onSelectHandler = (externalReference: string) => {",
                                    "    setStoreId(externalReference);",
                                    "  };",
                                ],
                            },
                            {
                                "data": {
                                    "sourcemap": "app:///_next/static/chunks/pages/_app-test.js.map",
                                    "symbolicated": True,
                                    "resolved_with": "index",
                                },
                                "colno": 23,
                                "in_app": False,
                                "lineno": 21,
                                "module": "chunks/pages/node_modules/@sentry/core/esm/exports",
                                "abs_path": "app:///_next/static/chunks/pages/node_modules/@sentry/core/esm/exports.js",
                                "filename": "./node_modules/@sentry/core/esm/exports.js",
                                "function": "captureException",
                                "pre_context": [
                                    "  // eslint-disable-next-line @typescript-eslint/no-explicit-any",
                                    "  exception,",
                                    "  hint,",
                                    ") {",
                                    "  // eslint-disable-next-line deprecation/deprecation",
                                ],
                                "context_line": "  return test();",
                                "post_context": [
                                    "}",
                                    "",
                                    "/**",
                                    " * Captures a message event and sends it to Sentry.",
                                    " *",
                                ],
                            },
                        ]
                    },
                    "raw_stacktrace": {
                        "frames": [
                            {
                                "colno": 1,
                                "in_app": True,
                                "lineno": 9,
                                "abs_path": "app:///_next/static/chunks/test-test.js",
                                "filename": "app:///_next/static/chunks/test-test.js",
                            },
                            {
                                "colno": 2,
                                "in_app": True,
                                "lineno": 8,
                                "abs_path": "app:///_next/static/chunks/pages/_app-test.js",
                                "filename": "app:///_next/static/chunks/pages/_app-test.js",
                                "pre_context": [
                                    " *",
                                    " * Copyright (c) Facebook, Inc. and its affiliates.",
                                    " *",
                                    " * This source code is licensed under the MIT license found in the",
                                    " * LICENSE file in the root directory of this source tree.",
                                ],
                                "context_line": "{snip} ?void 0:f.storeDetails,u]),(0,s.useEffect)(()=>{h&&(0,D.Tb)(h,{extra:{test:l}})},[h,l]);let m=e=>{d(e)},g=(0,s.useMemo)(()=>t&&0===n.leng {snip}",
                                "post_context": [
                                    "Sentry.addTracingExtensions();",
                                    "Sentry.init({...});",
                                    '{snip} y{return"SentryError"===e.exception.values[0].type}catch(e){}return!1}(t)?(x.X&&k.kg.warn(`Event dropped due to being internal Sentry Error.',
                                    "{snip} ge for event ${(0,P.jH)(e)}`),n})(t).some(e=>(0,B.U0)(e,o)))?(x.X&&k.kg.warn(`Event dropped due to being matched by \\`ignoreErrors\\` option.",
                                    "{snip} eturn!0;let n=$(e);return!n||(0,B.U0)(n,t)}(t,i.allowUrls)||(x.X&&k.kg.warn(`Event dropped due to not being matched by \\`allowUrls\\` option.",
                                ],
                            },
                            {
                                "colno": 162667,
                                "in_app": True,
                                "lineno": 8,
                                "abs_path": "app:///_next/static/chunks/pages/_app-test.js",
                                "filename": "app:///_next/static/chunks/pages/_app-test.js",
                                "function": "u",
                                "pre_context": [
                                    " *",
                                    " * Copyright (c) Facebook, Inc. and its affiliates.",
                                    " *",
                                    " * This source code is licensed under the MIT license found in the",
                                    " * LICENSE file in the root directory of this source tree.",
                                ],
                                "context_line": "{snip} 300,letterSpacing1400:t.letterSpacing1400,letterSpacing1500:t.letterSpacing1500,letterSpacing1600:t.letterSpacing1600}},8248:function(e,t,n) {snip}",
                                "post_context": [
                                    "Sentry.addTracingExtensions();",
                                    "Sentry.init({...});",
                                    '{snip} y{return"SentryError"===e.exception.values[0].type}catch(e){}return!1}(t)?(x.X&&k.kg.warn(`Event dropped due to being internal Sentry Error.',
                                    "{snip} ge for event ${(0,P.jH)(e)}`),n})(t).some(e=>(0,B.U0)(e,o)))?(x.X&&k.kg.warn(`Event dropped due to being matched by \\`ignoreErrors\\` option.",
                                    "{snip} eturn!0;let n=$(e);return!n||(0,B.U0)(n,t)}(t,i.allowUrls)||(x.X&&k.kg.warn(`Event dropped due to not being matched by \\`allowUrls\\` option.",
                                ],
                            },
                        ]
                    },
                }
            ],
            "github_repo": "https://github.com/test/test.git",
            "tags": {
                "os": "Windows >=10",
                "url": "https://test.test.keephq.dev/keep",
                "level": "error",
                "browser": "Edge 122.0.0",
                "handled": "yes",
                "os.name": "Windows",
                "release": "1234",
                "runtime": "browser",
                "mechanism": "generic",
                "transaction": "/test",
                "browser.name": "Edge",
                "service_name": "keep-test",
            },
        }
    )
    context_manager.event_context = context_manager.alert
    iohandler = IOHandler(context_manager)
    s = iohandler.render(
        "{{#alert.exceptions}}\n*{{ type }}*\n{{ value }}\n\n*Stack Trace*\n{code:json} keep.json_dumps({{{ stacktrace }}}) {code}\n{{/alert.exceptions}}\n{{^alert.exceptions}}\nNo stack trace available\n{{/alert.exceptions}}\n\n*Tags*\n{code:json} keep.json_dumps({{{ alert.tags }}}) {code}\n\nSee: {{ alert.url }}\n",
    )
    assert "test, test2, test3, test4, test5" in s
    assert "aptures a message event and sends it to Sentry" in s
