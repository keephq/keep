---
sidebar_label: MySQL
---

# MySQL

:::note Brief Description
MySQL Provider is a provider used to query MySQL databases
:::

## Inputs
The `query` function of `MysqlProvider` takes the following arguments:
* `query` (str): A string containing the query to be executed against the MySQL database.
* `single_row` (bool, optional): If `True`, the function will return only the first result.

## Outputs
The `query` function returns either a `list` or a `tuple` of results, depending on whether `single_row` was set to `True` or not. If `single_row` was `True`, then the function returns a single result.

## Authentication Parameters
The following authentication parameters are used to connect to the MySQL database:
* `username` (str): The MySQL username.
* `password` (str): The MySQL password.
* `host` (str): The MySQL hostname.
* `database` (str, optional): The name of the MySQL database.

## Connecting with the Provider
In order to connect to the MySQL database, you will need to create a new user with the required permissions. Here's how you can do this:
1. Connect to the MySQL server as a user with sufficient privileges to create a new user.
2. Run the following command to create a new user:
`CREATE USER '<username>'@'<host>' IDENTIFIED BY '<password>'`;
1. Grant the necessary permissions to the new user by running the following command:
`GRANT ALL PRIVILEGES ON <database>.* TO '<username>'@'<host>'`;

## Notes

## Useful Links
* [MySQL Documentation](https://dev.mysql.com/doc/refman/8.0/en/)
