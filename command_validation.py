import ipaddress
import re


HEX_KEY = re.compile(r'^[0-9A-Fa-f]{32}$')
PROCEDURE = re.compile(r'^[A-Za-z][A-Za-z0-9-]*$')
APN = re.compile(r'^[A-Za-z0-9.-]{1,100}$')
RUN_ID = re.compile(r'^[0-9a-f]{32}$')
RESULT_SOCKET = re.compile(r'^/tmp/enb-load-[A-Za-z0-9-]+\.sock$')
USER_PROCEDURES = {
    'attach', 'detach', 'idle', 'tau', 'tau-p', 'service-request', 'data',
}


def validate_command(command):
    if not isinstance(command, dict):
        raise TypeError('command must be a dictionary')
    procedure = command.get('procedure')
    if not isinstance(procedure, str) or not PROCEDURE.fullmatch(procedure):
        raise ValueError('invalid or missing procedure')

    for field in ('enb_ip', 'mme_ip', 'gtpu_ip'):
        if command.get(field):
            ipaddress.IPv4Address(command[field])
    if command.get('external_gtpu') not in (None, False, True):
        raise ValueError('external_gtpu must be a boolean')
    bearer_events = command.get('bearer_events')
    if bearer_events and ('\n' in bearer_events or '\r' in bearer_events):
        raise ValueError('invalid bearer event destination')
    if command.get('imsi'):
        validate_imsi(command['imsi'])
    for field in ('ki', 'opc'):
        if command.get(field) and not HEX_KEY.fullmatch(command[field]):
            raise ValueError(f'{field} must contain 32 hexadecimal characters')
    if command.get('mcc') and (
            len(command['mcc']) != 3 or not command['mcc'].isdigit()):
        raise ValueError('MCC must contain 3 digits')
    if command.get('mnc') and (
            len(command['mnc']) not in (2, 3) or not command['mnc'].isdigit()):
        raise ValueError('MNC must contain 2 or 3 digits')
    if command.get('apn') and not APN.fullmatch(command['apn']):
        raise ValueError('APN contains invalid characters')
    if command.get('pdp_type') and command['pdp_type'] not in ('1', '2', '3', '5'):
        raise ValueError('pdn_type must be 1, 2, 3, or 5')
    if command.get('load_run_id') and not RUN_ID.fullmatch(command['load_run_id']):
        raise ValueError('invalid load test run ID')
    if command.get('load_result_socket') and not RESULT_SOCKET.fullmatch(
            command['load_result_socket']):
        raise ValueError('invalid load test result socket')
    _validate_integer(command, 'tac1', 0, 65535)
    _validate_integer(command, 'tac2', 0, 65535)
    _validate_integer(command, 'enb_id', 0, 1048575)
    _validate_integer(command, 's1_port', 1, 65535)

    if procedure == 'start-simulator':
        _require(command, 'enb_ip', 'mme_ip')
    elif procedure == 'attach':
        _require(command, 'imsi', 'ki', 'opc', 'mcc', 'mnc')
    elif procedure in USER_PROCEDURES:
        _require(command, 'imsi')
    return command


def validate_imsi(imsi):
    if len(imsi) != 15 or not imsi.isdigit():
        raise ValueError('IMSI must contain 15 digits')


def _require(command, *fields):
    missing = [field for field in fields if not command.get(field)]
    if missing:
        raise ValueError(f"missing required fields: {', '.join(missing)}")


def _validate_integer(command, field, minimum, maximum):
    value = command.get(field)
    if value is None:
        return
    try:
        number = int(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f'{field} must be an integer') from error
    if not minimum <= number <= maximum:
        raise ValueError(f'{field} must be between {minimum} and {maximum}')
