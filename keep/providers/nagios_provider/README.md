## Nagios Webhook Payload Notes

Configure Nagios notifications to POST Nagios macros to the Keep webhook endpoint.

Recommended fields:

- `NOTIFICATIONTYPE`
- `HOSTNAME`
- `HOSTSTATE` or `SERVICESTATE`
- `HOSTOUTPUT` or `SERVICEOUTPUT`
- `LONGDATETIME` or `SHORTDATETIME`
- `HOSTPROBLEMID` / `SERVICEPROBLEMID`
- `SERVICEDESC` (for service notifications)

The provider accepts common lowercase/underscore variants as well.
