import ipaddress
import re
import subprocess


INTERFACE_NAME = re.compile(r'^[A-Za-z0-9_.-]{1,15}$')
NAMESPACE_NAME = re.compile(r'^[A-Za-z0-9_.-]{1,64}$')


class NetworkCommandError(RuntimeError):
    pass


class NetworkRuntime:
    def __init__(self, runner=subprocess.run):
        self._runner = runner

    def _run(self, *args, check=True):
        result = self._runner(
            list(args),
            capture_output=True,
            text=True,
        )
        if check and result.returncode != 0:
            detail = result.stderr.strip() or result.stdout.strip()
            raise NetworkCommandError(f"{' '.join(args)} failed: {detail}")
        return result

    def namespaces(self):
        result = self._run('ip', 'netns', 'list')
        return {
            line.split()[0]
            for line in result.stdout.splitlines()
            if line.strip()
        }

    def ensure_bridge(self, bridge_name):
        _validate_interface(bridge_name)
        result = self._run(
            'ip', '-details', 'link', 'show', 'dev', bridge_name,
            check=False,
        )
        if result.returncode != 0:
            self._run('ip', 'link', 'add', bridge_name, 'type', 'bridge')
        elif ' bridge ' not in f" {result.stdout.replace(chr(10), ' ')} ":
            raise NetworkCommandError(
                f"existing interface {bridge_name} is not a bridge"
            )
        self._run('ip', 'link', 'set', 'dev', bridge_name, 'up')

    def setup_ue_namespace(self, namespace, veth, peer, ue_ip, bridge_name):
        _validate_namespace(namespace)
        _validate_interface(veth)
        _validate_interface(peer)
        _validate_interface(bridge_name)
        address = ipaddress.ip_address(ue_ip)
        if address.version != 4:
            raise ValueError('UE namespace setup requires an IPv4 address')
        network = ipaddress.ip_network(f'{address}/24', strict=False)
        gateway = str(network.network_address + 1)

        if namespace in self.namespaces():
            self.delete_ue_namespace(namespace)
        existing_veth = self._run(
            'ip', 'link', 'show', 'dev', veth,
            check=False,
        )
        if existing_veth.returncode == 0:
            self._run('ip', 'link', 'delete', veth)

        try:
            self._run('ip', 'netns', 'add', namespace)
            self._run('ip', 'link', 'add', veth, 'type', 'veth', 'peer', 'name', peer)
            self._run('ip', 'link', 'set', peer, 'netns', namespace)
            self._run(
                'ip', 'netns', 'exec', namespace,
                'ip', 'addr', 'replace', f'{address}/24', 'dev', peer,
            )
            self._run('ip', 'link', 'set', 'dev', veth, 'master', bridge_name)
            self._run('ip', 'link', 'set', 'dev', veth, 'up')
            self._run(
                'ip', 'netns', 'exec', namespace,
                'ip', 'link', 'set', 'lo', 'up',
            )
            self._run('ip', 'addr', 'replace', f'{gateway}/24', 'dev', bridge_name)
            self._run(
                'ip', 'netns', 'exec', namespace,
                'ip', 'route', 'replace', 'default',
                'via', gateway, 'dev', peer,
            )
        except Exception:
            self.delete_ue_namespace(namespace)
            raise

    def delete_ue_namespace(self, namespace):
        _validate_namespace(namespace)
        if namespace in self.namespaces():
            self._run('ip', 'netns', 'delete', namespace)


def _validate_interface(name):
    if not INTERFACE_NAME.fullmatch(name):
        raise ValueError(f'invalid network interface name: {name!r}')


def _validate_namespace(name):
    if not NAMESPACE_NAME.fullmatch(name):
        raise ValueError(f'invalid network namespace name: {name!r}')
