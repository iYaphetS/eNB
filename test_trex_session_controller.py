import json
import tempfile
import unittest
from pathlib import Path

from trex_adapter import BearerState, _shard_for
from trex_session_controller import output_path, write_shards


class TrexSessionControllerTest(unittest.TestCase):
    def test_writes_all_shards_from_live_state(self):
        state = BearerState()
        base = {
            'event': 'bearer-up', 'ue_ip': '10.45.0.2',
            'upf_ip': '192.0.2.20', 'enb_gtpu_ip': '192.0.2.10',
            'uplink_teid': 1001, 'downlink_teid': 2001, 'bearer_id': 5,
        }
        for index in range(1, 5):
            state.apply(dict(base, imsi=f'11111100000000{index}', sequence=index))
        with tempfile.TemporaryDirectory() as directory:
            template = str(Path(directory) / 'sessions-{index}.json')
            paths = write_shards(state, template, 2, 10, 20, 64)
            manifests = [json.loads(Path(path).read_text()) for path in paths]
            self.assertEqual(4, sum(len(item['sessions']) for item in manifests))
            self.assertEqual([0, 1], [item['shard']['index'] for item in manifests])

    def test_formats_output_path(self):
        self.assertEqual('/tmp/sessions-3.json', output_path('/tmp/sessions-{index}.json', 3))

    def test_writes_only_selected_dirty_shard(self):
        state = BearerState()
        event = {
            'event': 'bearer-up', 'imsi': '111111000000001',
            'ue_ip': '10.45.0.2', 'upf_ip': '192.0.2.20',
            'enb_gtpu_ip': '192.0.2.10', 'uplink_teid': 1001,
            'downlink_teid': 2001, 'bearer_id': 5,
        }
        state.apply(event)
        dirty = _shard_for(event['imsi'], 4)
        with tempfile.TemporaryDirectory() as directory:
            template = str(Path(directory) / 'sessions-{index}.json')
            paths = write_shards(state, template, 4, 10, 20, 64, {dirty})
            self.assertEqual([output_path(template, dirty)], paths)
            self.assertEqual(
                [dirty],
                [int(path.stem.rsplit('-', 1)[1]) for path in Path(directory).glob('*.json')])


if __name__ == '__main__':
    unittest.main()
