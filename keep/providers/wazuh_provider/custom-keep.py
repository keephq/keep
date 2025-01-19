import json
import os
import sys
from datetime import datetime, timedelta, timezone

# Exit error codes
ERR_NO_REQUEST_MODULE = 1
ERR_BAD_ARGUMENTS = 2
ERR_FILE_NOT_FOUND = 6
ERR_INVALID_JSON = 7

try:
    import requests
except Exception:
    print("No module 'requests' found. Install: pip install requests")
    sys.exit(ERR_NO_REQUEST_MODULE)

# Global vars
debug_enabled = False
pwd = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
json_alert = {}
json_options = {}

# Log path
LOG_FILE = f'{pwd}/logs/integrations.log'

# Constants
ALERT_INDEX = 1
API_KEY_INDEX = 2
WEBHOOK_INDEX = 3


def main(args):
    global debug_enabled
    try:
        # Read arguments
        bad_arguments: bool = False
        if len(args) >= 4:
            msg = '{0} {1} {2} {3} {4}'.format(
                args[1], args[2], args[3], args[4] if len(args) > 4 else '', args[5] if len(args) > 5 else ''
            )
            debug_enabled = len(args) > 4 and args[4] == 'debug'
        else:
            msg = '# ERROR: Wrong arguments'
            bad_arguments = True

        # Logging the call
        with open(LOG_FILE, 'a') as f:
            f.write(msg + '\n')

        if bad_arguments:
            debug('# ERROR: Exiting, bad arguments. Inputted: %s' % args)
            sys.exit(ERR_BAD_ARGUMENTS)

        # Core function
        process_args(args)

    except Exception as e:
        debug(str(e))
        raise


def process_args(args) -> None:
    debug('# Running Custom Keep script')

    # Read args
    alert_file_location: str = args[ALERT_INDEX]
    webhook: str = args[WEBHOOK_INDEX]
    api_key: str = args[API_KEY_INDEX]
    options_file_location: str = ''

    # Look for options file location
    for idx in range(4, len(args)):
        if args[idx][-7:] == 'options':
            options_file_location = args[idx]
            break

    # Load options. Parse JSON object.
    json_options = get_json_options(options_file_location)
    debug(f"# Opening options file at '{options_file_location}' with '{json_options}'")

    # Load alert. Parse JSON object.
    json_alert = get_json_alert(alert_file_location)
    debug(f"# Opening alert file at '{alert_file_location}' with '{json_alert}'")

    debug('# Generating message')
    msg: any = generate_msg(json_alert, json_options)

    if not len(msg):
        debug('# ERROR: Empty message')
        raise Exception

    debug(f'# Sending message {msg} to Keep server')
    send_msg(msg, webhook, api_key)


def debug(msg: str) -> None:
    if debug_enabled:
        print(msg)
        with open(LOG_FILE, 'a') as f:
            f.write(msg + '\n')


def generate_msg(alert: any, options: any) -> any:
    level = alert['rule']['level']
    description = alert['rule']['description'] if 'description' in alert['rule'] else 'N/A'
    rule_id = alert['rule']['id']

    severity = 'low'
    if level > 14:
        severity = 'critical'
    elif level > 11:
        severity = 'high'
    elif level > 6:
        severity = 'info'
    
    created_at = datetime.now(timezone.utc).astimezone()
    
    print(json.dumps(alert))

    return json.dumps({
        'description': description,
        'severity': severity,
        'message': f'Rule ID {rule_id}\nLevel {level}',
        'created_at': created_at
    })


def send_msg(msg: str, url: str, api_key: str) -> None:
    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'X-API-KEY': api_key
    }
    res = requests.post(url, data=msg, headers=headers, timeout=10)
    debug('# Response received: %s' % res.json)


def get_json_alert(file_location: str) -> any:
    try:
        with open(file_location) as alert_file:
            return json.load(alert_file)
    except FileNotFoundError:
        debug("# JSON file for alert %s doesn't exist" % file_location)
        sys.exit(ERR_FILE_NOT_FOUND)
    except json.decoder.JSONDecodeError as e:
        debug('Failed getting JSON alert. Error: %s' % e)
        sys.exit(ERR_INVALID_JSON)


def get_json_options(file_location: str) -> any:
    try:
        with open(file_location) as options_file:
            return json.load(options_file)
    except FileNotFoundError:
        debug("# JSON file for options %s doesn't exist" % file_location)
    except BaseException as e:
        debug('Failed getting JSON options. Error: %s' % e)
        sys.exit(ERR_INVALID_JSON)


if __name__ == '__main__':
    main(sys.argv)