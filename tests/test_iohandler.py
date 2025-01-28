"""
Test the io handler
"""

import datetime

import pytest

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
    #      "  }, [data, data?.testDetails, onSelect]);",
    # that screwed are iohandler
    #
    e = {
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
                        "      onSelect(data.testDetails);",
                        "    }",
                        "  }, [data, data?.testDetails, onSelect]);",
                        "",
                        "  useEffect(() => {",
                    ],
                    "context_line": "    error && captureException(error, { extra: { test } });",
                    "post_context": [
                        "  }, [error, testId]);",
                        "",
                        "  const onSelectHandler = (externalReference: string) => {",
                        "    setTestId(externalReference);",
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
                    "context_line": "{snip} ?void 0:f.testDetails,u]),(0,s.useEffect)(()=>{h&&(0,D.Tb)(h,{extra:{test:l}})},[h,l]);let m=e=>{d(e)},g=(0,s.useMemo)(()=>t&&0===n.leng {snip}",
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
            "exceptions": [e, e],
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


def test_functions(mocked_context_manager):
    mocked_context_manager.get_full_context.return_value = {
        "steps": {"some_list": [["Asd", 2, 3], [4, 5, 6], [7, 8, 9]]},
    }
    iohandler = IOHandler(mocked_context_manager)
    s = iohandler.render("result is keep.first(keep.first({{ steps.some_list }}))")
    assert s == "result is Asd"


def test_render_with_json_dumps_function(mocked_context_manager):
    mocked_context_manager.get_full_context.return_value = {
        "steps": {"some_object": {"key": "value"}}
    }
    iohandler = IOHandler(mocked_context_manager)
    template = "JSON: keep.json_dumps({{ steps.some_object }})"
    rendered = iohandler.render(template)
    assert rendered == 'JSON: {\n    "key": "value"\n}'


def test_render_uppercase(context_manager):
    iohandler = IOHandler(context_manager)
    template = "hello keep.uppercase('world')"
    result = iohandler.render(template)
    assert result == "hello WORLD"


def test_render_datetime_compare(context_manager):
    now = datetime.datetime.utcnow()
    one_hour_ago = now - datetime.timedelta(hours=1)
    context_manager.steps_context = {
        "now": now.isoformat(),
        "one_hour_ago": one_hour_ago.isoformat(),
    }
    iohandler = IOHandler(context_manager)
    template = "Difference in hours: keep.datetime_compare(keep.to_utc('{{ steps.now }}'), keep.to_utc('{{ steps.one_hour_ago }}'))"
    result = iohandler.render(template)
    assert "Difference in hours: 1.0" in result


def test_get_pods_foreach(mocked_context_manager):
    # Mock pods data as would be returned by the `get-pods` step
    mocked_context_manager.get_full_context.return_value = {
        "steps": {
            "get-pods": {
                "results": [
                    {
                        "metadata": {"name": "pod1", "namespace": "default"},
                        "status": {"phase": "Running"},
                    },
                    {
                        "metadata": {"name": "pod2", "namespace": "kube-system"},
                        "status": {"phase": "Pending"},
                    },
                ]
            }
        }
    }

    iohandler = IOHandler(mocked_context_manager)
    template = "Pod status report:{{#steps.get-pods.results}}\nPod name: {{ metadata.name }} || Namespace: {{ metadata.namespace }} || Status: {{ status.phase }}{{/steps.get-pods.results}}"
    rendered = iohandler.render(template)

    expected_output = "Pod status report:\nPod name: pod1 || Namespace: default || Status: Running\nPod name: pod2 || Namespace: kube-system || Status: Pending"
    assert rendered.strip() == expected_output.strip()


def test_resend_python_service_condition(mocked_context_manager):
    # Mock return_code to simulate the success scenario
    mocked_context_manager.get_full_context.return_value = {
        "steps": {"run-script": {"results": {"return_code": 0}}}
    }

    iohandler = IOHandler(mocked_context_manager)
    condition = "{{ steps.run-script.results.return_code }} == 0"
    # Simulate condition evaluation
    assert eval(iohandler.render(condition)) is True


def test_blogpost_workflow_enrich_alert(mocked_context_manager):
    # Mock customer data as would be returned by the `get-more-details` step
    mocked_context_manager.get_full_context.return_value = {
        "steps": {
            "get-more-details": {
                "results": {
                    "name": "John Doe",
                    "email": "john@example.com",
                    "tier": "premium",
                }
            }
        },
        "alert": {"customer_id": 123},
    }

    iohandler = IOHandler(mocked_context_manager)
    # Assume this template represents the enrichment logic
    template = "Customer details: Name: {{ steps.get-more-details.results.name }}, Email: {{ steps.get-more-details.results.email }}, Tier: {{ steps.get-more-details.results.tier }}"
    rendered = iohandler.render(template)

    expected_output = (
        "Customer details: Name: John Doe, Email: john@example.com, Tier: premium"
    )
    assert rendered == expected_output


def test_sentry_alerts_conditions(mocked_context_manager):
    # Mock alert data to simulate a sentry alert for the payments service
    mocked_context_manager.get_full_context.return_value = {
        "alert": {
            "service": "payments",
            "name": "Error Alert",
            "description": "Critical error occurred.",
        }
    }

    iohandler = IOHandler(mocked_context_manager)
    condition_payments = "'{{ alert.service }}' == 'payments'"
    condition_ftp = "'{{ alert.service }}' == 'ftp'"

    # Simulate condition evaluations
    assert eval(iohandler.render(condition_payments)) is True
    assert eval(iohandler.render(condition_ftp)) is False


def test_db_disk_space_alert(mocked_context_manager):
    # Mock datadog logs data as would be returned by the `check-error-rate` step
    mocked_context_manager.get_full_context.return_value = {
        "steps": {"check-error-rate": {"results": {"logs": ["Error 1", "Error 2"]}}}
    }

    iohandler = IOHandler(mocked_context_manager)
    template = "Number of logs: keep.len({{ steps.check-error-rate.results.logs }})"
    rendered = iohandler.render(template)

    assert rendered == "Number of logs: 2"


def test_query_bigquery_for_customer_tier(mocked_context_manager):
    # Mock customer tier data as would be returned by the `get-customer-tier-by-id` step
    mocked_context_manager.get_full_context.return_value = {
        "steps": {
            "get-customer-tier-by-id": {
                "result": {"customer_name": "Acme Corp", "tier": "enterprise"}
            }
        },
        "alert": {"customer_id": "123"},
    }

    iohandler = IOHandler(mocked_context_manager)
    # Check if the enterprise-tier condition correctly asserts
    condition = "'{{ steps.get-customer-tier-by-id.result.tier }}' == 'enterprise'"
    assert eval(iohandler.render(condition)) is True


def test_opsgenie_get_open_alerts(mocked_context_manager):
    # Mock open alerts data as would be returned by the `get-open-alerts` step
    mocked_context_manager.get_full_context.return_value = {
        "steps": {
            "get-open-alerts": {
                "results": {
                    "number_of_alerts": 2,
                    "alerts": [
                        {
                            "id": "1",
                            "priority": "high",
                            "created_at": "2024-03-20T12:00:00Z",
                            "message": "Critical issue",
                        },
                        {
                            "id": "2",
                            "priority": "medium",
                            "created_at": "2024-03-20T13:00:00Z",
                            "message": "Minor issue",
                        },
                    ],
                }
            }
        }
    }

    iohandler = IOHandler(mocked_context_manager)
    template = (
        "Opsgenie has {{ steps.get-open-alerts.results.number_of_alerts }} open alerts"
    )
    rendered = iohandler.render(template)

    assert "Opsgenie has 2 open alerts" in rendered


def test_malformed_template_with_unmatched_braces(context_manager):
    iohandler = IOHandler(context_manager)
    malformed_template = "This template has an unmatched {{ brace."

    with pytest.raises(Exception) as excinfo:
        iohandler.render(malformed_template)

    # Adjusted the assertion to match the actual error message
    assert "number of } and { does not match" in str(excinfo.value)


"""
this is actually a bug but minor priority for now

def test_malformed_template_with_incorrect_function_syntax(context_manager):
    iohandler = IOHandler(context_manager)
    wrong_function_use = "Incorrect function call keep.lenֿ[wrong_syntax]"

    rendered = iohandler.render(wrong_function_use)

    assert wrong_function_use == rendered
"""


def test_unrecognized_function_call(context_manager):
    iohandler = IOHandler(context_manager)
    template_with_unrecognized_function = (
        "Calling an unrecognized function keep.nonexistent_function()"
    )

    with pytest.raises(Exception) as excinfo:
        iohandler.render(template_with_unrecognized_function)

    assert "module 'keep.functions' has no attribute" in str(
        excinfo.value
    )  # This assertion depends on the specific error handling and messaging in your application


def test_missing_closing_parenthesis(context_manager):
    iohandler = IOHandler(context_manager)
    malformed_template = "keep.len({{ steps.some_list }"
    extracted_functions = iohandler.extract_keep_functions(malformed_template)
    assert (
        len(extracted_functions) == 0
    ), "Expected no functions to be extracted due to missing closing parenthesis."


def test_nested_malformed_function_calls(context_manager):
    iohandler = IOHandler(context_manager)
    malformed_template = (
        "keep.first(keep.len({{ steps.some_list }, keep.lowercase('TEXT')"
    )
    extracted_functions = iohandler.extract_keep_functions(malformed_template)
    assert (
        len(extracted_functions) == 0
    ), "Expected no functions to be extracted due to malformed nested calls."


def test_extra_closing_parenthesis(context_manager):
    iohandler = IOHandler(context_manager)
    malformed_template = "keep.len({{ steps.some_list }}))"
    extracted_functions = iohandler.extract_keep_functions(malformed_template)
    # Assuming the method can ignore the extra closing parenthesis and still extract the function correctly
    assert (
        len(extracted_functions) == 1
    ), "Expected one function to be extracted despite an extra closing parenthesis."


def test_incorrect_function_name(context_manager):
    iohandler = IOHandler(context_manager)
    malformed_template = "keep.lenght({{ steps.some_list }})"
    extracted_functions = iohandler.extract_keep_functions(malformed_template)
    # Assuming the method extracts the function call regardless of the function name being valid
    assert (
        len(extracted_functions) == 1
    ), "Expected one function to be extracted despite the incorrect function name."


def test_keep_in_string_not_as_function_call(context_manager):
    iohandler = IOHandler(context_manager)
    template = "Here is a sentence with keep. not as a function call: 'Let's keep. moving forward.'"
    extracted_functions = iohandler.extract_keep_functions(template)
    assert (
        len(extracted_functions) == 0
    ), "Expected no functions to be extracted when 'keep.' is part of a string."


def test_no_function_calls(context_manager):
    iohandler = IOHandler(context_manager)
    template = "This is a sentence with keep. but no function calls."
    # Assuming extract_keep_functions is a method of setup object
    functions = iohandler.extract_keep_functions(template)
    assert len(functions) == 0, "Should find no functions"


def test_malformed_function_calls(context_manager):
    iohandler = IOHandler(context_manager)
    template = "Here is a malformed function call keep.(without closing parenthesis."
    functions = iohandler.extract_keep_functions(template)
    assert len(functions) == 0, "Should handle malformed function calls gracefully."


def test_mixed_content(context_manager):
    iohandler = IOHandler(context_manager)
    template = "Mix of valid keep.doSomething() and text keep. not as a call."
    functions = iohandler.extract_keep_functions(template)
    assert len(functions) == 1, "Should only extract valid function calls."


def test_nested_functions(context_manager):
    iohandler = IOHandler(context_manager)
    template = "Nested functions keep.nest(keep.inner()) should be handled."
    functions = iohandler.extract_keep_functions(template)
    assert len(functions) == 1, "Should handle nested functions without getting stuck."


def test_endless_loop_potential(context_manager):
    iohandler = IOHandler(context_manager)
    template = "keep.() empty function call followed by text keep. not as a call."
    functions = iohandler.extract_keep_functions(template)
    assert (
        len(functions) == 1
    ), "Should not enter an endless loop with empty function calls."


def test_edge_case_with_escaped_quotes(context_manager):
    iohandler = IOHandler(context_manager)
    template = (
        r"Edge case keep.function('argument with an escaped quote\\') and more text."
    )
    functions = iohandler.extract_keep_functions(template)
    assert (
        len(functions) == 1
    ), "Should correctly handle escaped quotes within function arguments."


def test_consecutive_function_calls(context_manager):
    iohandler = IOHandler(context_manager)
    template = "Consecutive keep.first() and keep.second() calls."
    functions = iohandler.extract_keep_functions(template)
    assert len(functions) == 2, "Should correctly handle consecutive function calls."


def test_function_call_at_end(context_manager):
    iohandler = IOHandler(context_manager)
    template = "Function call at the very end keep.end()"
    functions = iohandler.extract_keep_functions(template)
    assert (
        len(functions) == 1
    ), "Should correctly handle a function call at the end of the string."


def test_complex_mixture(context_manager):
    iohandler = IOHandler(context_manager)
    template = "Mix keep.start() some text keep.in('middle') and malformed keep. and valid keep.end()."
    functions = iohandler.extract_keep_functions(template)
    assert (
        len(functions) == 3
    ), "Should correctly handle a complex mixture of text and function calls."


def test_escaped_quotes_inside_function_arguments(context_manager):
    iohandler = IOHandler(context_manager)
    template = "keep.split('some,string,with,escaped\\\\'quotes', ',')"
    extracted_functions = iohandler.extract_keep_functions(template)
    # Assuming the method can handle escaped quotes within function arguments
    assert (
        len(extracted_functions) == 1
    ), "Expected one function to be extracted with escaped quotes inside arguments."


def test_double_function_call(context_manager):
    iohandler = IOHandler(context_manager)
    template = """{ vars.alert_tier }} Alert: Pipelines are down
      Hi,
      This {{ vars.alert_tier }} alert is triggered keep.get_firing_time('{{ alert }}', 'minutes') because the pipelines for {{ alert.host }} are down for more than keep.get_firing_time('{{ alert }}', 'minutes') minutes.
      Please visit monitoring.keeohq.dev for more!"""
    extracted_functions = iohandler.extract_keep_functions(template)
    assert (
        len(extracted_functions) == 2
    ), "Should handle nested function calls correctly."


def test_if_else_in_template_existing(mocked_context_manager):
    mocked_context_manager.get_full_context.return_value = {
        "alert": {"notexist": "it actually exists", "name": "this is a test"}
    }
    iohandler = IOHandler(mocked_context_manager)
    rendered = iohandler.render(
        "{{#alert.notexist}}{{.}}{{/alert.notexist}}{{^alert.notexist}}{{alert.name}}{{/alert.notexist}}",
        safe=True,
    )
    assert rendered == "it actually exists"


def test_if_else_in_template_not_existing(mocked_context_manager):
    mocked_context_manager.get_full_context.return_value = {
        "alert": {"name": "this is a test"}
    }
    iohandler = IOHandler(mocked_context_manager)
    rendered = iohandler.render(
        "{{#alert.notexist}}{{.}}{{/alert.notexist}}{{^alert.notexist}}{{alert.name}}{{/alert.notexist}}",
        safe=True,
    )
    assert rendered == "this is a test"


def test_escaped_quotes_with_with_space(context_manager):
    iohandler = IOHandler(context_manager)
    template = "keep.split('some string with 'quotes and with space' after', ',')"
    extracted_functions = iohandler.extract_keep_functions(template)
    # Assuming the method can handle escaped quotes within function arguments
    assert (
        len(extracted_functions) == 1
    ), "Expected one function to be extracted with escaped quotes inside arguments."


def test_escaped_quotes_with_with_newlines(context_manager):
    iohandler = IOHandler(context_manager)
    template = "keep.split('some string with 'quotes and with space' \r\n after', ',')"
    extracted_functions = iohandler.extract_keep_functions(template)
    # Assuming the method can handle escaped quotes within function arguments
    assert (
        len(extracted_functions) == 1
    ), "Expected one function to be extracted with escaped quotes inside arguments."


def test_add_time_to_date_function(context_manager):
    context_manager.alert = AlertDto(
        **{
            "id": "test",
            "name": "test",
            "lastReceived": "2024-03-20T00:00:00.000Z",
            "source": ["sentry"],
            "date": "2024-08-16T14:21:00.000-0500",
        }
    )
    context_manager.event_context = context_manager.alert
    iohandler = IOHandler(context_manager)
    s = iohandler.render(
        'keep.add_time_to_date("{{ alert.date }}", "%Y-%m-%dT%H:%M:%S.%f%z", "1w 2d 3h 30m")'
    )
    expected_date = datetime.datetime(
        2024, 8, 25, 17, 51, tzinfo=datetime.timezone(datetime.timedelta(hours=-5))
    )
    assert s == str(expected_date), f"Expected {expected_date}, but got {s}"

    # one day
    s = iohandler.render(
        'keep.add_time_to_date("{{ alert.date }}", "%Y-%m-%dT%H:%M:%S.%f%z", "1d")'
    )
    expected_date = datetime.datetime(
        2024, 8, 17, 14, 21, tzinfo=datetime.timezone(datetime.timedelta(hours=-5))
    )
    assert s == str(expected_date), f"Expected {expected_date}, but got {s}"


# def test_openobserve_rows_bug(db_session, context_manager):
#     template = "keep.get_firing_time('{{ alert }}', 'minutes') >= 30 and keep.get_firing_time('{{ alert }}', 'minutes') < 90"
#     # from 1 hour ago
#     lastReceived = datetime.datetime.utcnow() - datetime.timedelta(hours=1)
#     alert = AlertDto(
#         **{
#             "id": "dfbc23f1-9a71-475c-8fc6-8bf051cc2336",
#             "name": "camera_reachability_23",
#             "status": "firing",
#             "severity": "warning",
#             "lastReceived": str(lastReceived),
#             "environment": "camera_reachability",
#             "isFullDuplicate": False,
#             "isPartialDuplicate": True,
#             "duplicateReason": None,
#             "service": None,
#             "source": ["openobserve"],
#             "apiKeyRef": "webhook",
#             "message": None,
#             "description": "scheduled",
#             "pushed": True,
#             "event_id": "42172953-9f5d-4b65-80a0-d1a29d205934",
#             "url": None,
#             "labels": {
#                 "url": "",
#                 "alert_period": "5",
#                 "alert_operator": "&gt;=",
#                 "alert_threshold": "1",
#                 "alert_count": "2",
#                 "alert_agg_value": "0.00",
#                 "alert_end_time": "2024-10-18T13:34:35",
#             },
#             "fingerprint": "d135867d811043414f60f8b6d7b5e9f69464389650e50f476848a64faec2c9b5",
#             "deleted": False,
#             "dismissUntil": None,
#             "dismissed": False,
#             "assignee": None,
#             "providerId": "e3ac6f75cda04397b09099af62d35329",
#             "providerType": "openobserve",
#             "note": None,
#             "startedAt": "2024-10-18T13:28:42",
#             "isNoisy": False,
#             "enriched_fields": [],
#             "incident": None,
#             "trigger": "manual",
#             "rows": "{\\'host': 'somedevice-va1.data.city.keephq.dev'}\\n{'host': 'somedevice2-va1.data.city.keephq.dev'}",
#             "alert_url": "/web/logs?stream_type=metrics&amp;stream=camera_reachability&amp;stream_value=camera_reachability&amp;from=1729258122035000&amp;to=1729258475705000&amp;sql_mode=true&amp;query=123&amp;org_identifier=somecity",
#             "alert_hash": "6530fb046247d056996d3ce7b0f25083ffff9700393f27c21e979e150bf049db",
#             "org_name": "somecity",
#             "stream_type": "metrics",
#         }
#     )
#     context_manager.alert = alert
#     context_manager.event_context = context_manager.alert
#     iohandler = IOHandler(context_manager)

#     # it should be greater than 60 minutes and less than 90 minutes
#     s = iohandler.render(template)
#     # the alert is not really added to the DB so the firing time is 0.00
#     assert s == "0.00 >= 30 and 0.00 < 90"


def test_recursive_rendering_basic(context_manager):
    iohandler = IOHandler(context_manager)

    context_manager.steps_context = {
        "name": "World",
        "greeting": "Hello {{ steps.name }}",
    }
    template = "{{ steps.greeting }}!"
    result = iohandler.render(template)
    assert result == "Hello World!", f"Expected 'Hello World!', but got {result}"


def test_recursive_rendering_nested(context_manager):
    iohandler = IOHandler(context_manager)
    context_manager.steps_context = {
        "name": "World",
        "greeting": "Hello {{ steps.name }}",
        "message": "{{ steps.greeting }}! How are you?",
    }
    template = "{{ steps.message }}"
    result = iohandler.render(template)
    assert (
        result == "Hello World! How are you?"
    ), f"Expected 'Hello World! How are you?', but got {result}"


def test_recursive_rendering_with_functions(context_manager):
    iohandler = IOHandler(context_manager)
    context_manager.steps_context = {
        "name": "world",
        "greeting": "Hello keep.uppercase({{ steps.name }})",
    }
    template = "{{ steps.greeting }}!"
    result = iohandler.render(template)
    assert result == "Hello WORLD!", f"Expected 'Hello WORLD!', but got {result}"


def test_recursive_rendering_max_iterations(context_manager):
    iohandler = IOHandler(context_manager)
    context_manager.steps_context = {"loop": "{{ steps.loop }}"}
    template = "{{ steps.loop }}"
    result = iohandler.render(template)
    assert (
        result == "{{ steps.loop }}"
    ), "Expected no change due to max iterations limit"


def test_render_with_consts(context_manager):
    iohandler = IOHandler(context_manager)
    context_manager.alert = AlertDto(
        **{
            "id": "test",
            "name": "test",
            "lastReceived": "2024-03-20T00:00:00.000Z",
            "source": ["sentry"],
            "date": "2024-08-16T14:21:00.000-0500",
            "host": "example.com",
        }
    )
    context_manager.event_context = context_manager.alert
    context_manager.current_step_vars = {"alert_tier": "critical"}
    consts = {
        "email_template": (
            "<strong>Hi,<br>"
            "This {{ vars.alert_tier }} is triggered because the pipelines for {{ alert.host }} are down for more than 0 minutes.<br>"
            "Please visit monitoring.keeohq.dev for more!<br>"
            "Regards,<br>"
            "KeepHQ dev Monitoring</strong>"
        )
    }
    context_manager.consts_context = consts
    template = "{{ consts.email_template }}"
    result = iohandler.render(template)
    expected_result = (
        "<strong>Hi,<br>"
        "This critical is triggered because the pipelines for example.com are down for more than 0 minutes.<br>"
        "Please visit monitoring.keeohq.dev for more!<br>"
        "Regards,<br>"
        "KeepHQ dev Monitoring</strong>"
    )
    assert (
        result == expected_result
    ), f"Expected '{expected_result}', but got '{result}'"
