import unittest

from session_index import SessionIndex, extract_enb_ue_s1ap_id, sync_session_index


class SessionIndexTest(unittest.TestCase):
    def test_indexes_and_updates_session_keys(self):
        index = SessionIndex()
        session = {'ENB-UE-S1AP-ID': 10, 'S-TMSI': b'old'}
        index.update(session)

        session['ENB-UE-S1AP-ID'] = 11
        session['S-TMSI'] = b'new'
        index.update(session)

        self.assertIsNone(index.by_enb_id(10))
        self.assertIsNone(index.by_s_tmsi(b'old'))
        self.assertIs(session, index.by_enb_id(11))
        self.assertIs(session, index.by_s_tmsi(b'new'))
        self.assertEqual({11}, set(index.used_enb_ids()))

    def test_sync_removes_detached_session(self):
        index = SessionIndex()
        session = {'IMSI': '1', 'ENB-UE-S1AP-ID': 10, 'S-TMSI': b'a'}
        users = {'1': session}
        sync_session_index(index, users, session)

        del users['1']
        sync_session_index(index, users, session)

        self.assertIsNone(index.by_enb_id(10))
        self.assertIsNone(index.by_s_tmsi(b'a'))

    def test_extracts_direct_enb_id_information_element(self):
        pdu = {'protocolIEs': [
            {'id': 8, 'value': ('ENB-UE-S1AP-ID', 42)},
        ]}
        self.assertEqual(42, extract_enb_ue_s1ap_id(pdu))

    def test_extracts_enb_id_from_ue_id_pair(self):
        pdu = {
            'id': 99,
            'value': ('UE-S1AP-IDs', ('uE-S1AP-ID-pair', {
                'mME-UE-S1AP-ID': 10,
                'eNB-UE-S1AP-ID': 42,
            })),
        }
        self.assertEqual(42, extract_enb_ue_s1ap_id(pdu))


if __name__ == '__main__':
    unittest.main()
