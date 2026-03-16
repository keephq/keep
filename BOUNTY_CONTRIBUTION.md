# Bounty Contribution

This addresses issue #6097: feat(provider): Add SNMP webhook support for receiving traps (Issue #2112)

## Description
## Summary
- Add SNMP webhook support for receiving SNMP traps/events into Keep as alerts (Issue #2112)
- Claiming bounty: /claim #2112

## Changes

### SNMP Provider Enhancements

- Added webhook support to receive SNMP traps from external systems (Zabbix, Nagios, etc.)
- Implemented webhook_description and webhook_template class attributes
- Added parse_event_raw_body() static method for parsing JSON payloads
- Added _format_alert() static method to convert traps to AlertDto
- Added WEBHOOK_IN

## Payment
0x4F666e7b4F63637223625FD4e9Ace6055fD6a847
