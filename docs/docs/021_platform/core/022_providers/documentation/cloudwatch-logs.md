---
sidebar_label: CloudWatch Logs
---

# AWS CloudWatch Logs

:::note Brief Description
CloudWatch Logs Provider is a provider used to query AWS CloudWatch Logs
:::

## Inputs
The `query` function takes the following parameters as inputs:
- `log_group`: Required. The name of the log group to query.
- `query`: Required. A query string to use to filter the log events to be returned.
- `hours`: Optional. An integer representing the number of hours to query the logs for. Defaults to 24.

## Outputs
The function returns a list or tuple of the query results.

## Authentication Parameters
The `query` function requires an `access_key` and `access_key_secret` to authenticate with AWS. These can be obtained by creating an AWS IAM user with the necessary permissions to query CloudWatch logs.

## Connecting with the Provider
To obtain the `access_key` and `access_key_secret` from AWS, you will need to create an AWS IAM user with the necessary permissions to query CloudWatch logs. You can do this by following these steps:
1. Log in to the AWS Management Console.
2. Navigate to the IAM service.
3. Click on the "Users" option in the left-side menu.
4. Click on the "Add user" button.
5. Enter a user name and select "Programmatic access" as the access type.
6. Click on the "Next: Permissions" button.
7. Attach the "CloudWatchLogsReadOnlyAccess" policy to the user.
8. Click on the "Next: Review" button.
9. Review the user details and click on the "Create user" button.
10. Copy the `access_key` and `access_key_secret` displayed on the next screen and use them when creating an instance of the `CloudwatchLogsProvider` provider.

## Notes
*No information yet, feel free to contribute it using the "Edit this page" link the buttom of the page*

## Useful Links
*No information yet, feel free to contribute it using the "Edit this page" link the buttom of the page*
