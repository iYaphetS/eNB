import unittest

from enb_id_allocator import allocate_enb_ue_s1ap_id


class EnbUeS1apIdAllocatorTest(unittest.TestCase):
    def test_allocates_next_id(self):
        self.assertEqual(1001, allocate_enb_ue_s1ap_id(1000, set()))

    def test_skips_ids_used_by_online_users(self):
        self.assertEqual(1004, allocate_enb_ue_s1ap_id(1000, {1001, 1002, 1003}))

    def test_wraps_without_reusing_an_active_id(self):
        self.assertEqual(2, allocate_enb_ue_s1ap_id(9999, {1}))

    def test_fails_when_all_ids_are_in_use(self):
        with self.assertRaises(RuntimeError):
            allocate_enb_ue_s1ap_id(9999, range(1, 10000))


if __name__ == '__main__':
    unittest.main()
