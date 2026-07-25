MIN_ENB_UE_S1AP_ID = 1
MAX_ENB_UE_S1AP_ID = 9999


def allocate_enb_ue_s1ap_id(current_id, used_ids):
    """Return the next free eNB UE S1AP ID, wrapping when necessary."""
    used_ids = used_ids or ()
    candidate = current_id

    for _ in range(MIN_ENB_UE_S1AP_ID, MAX_ENB_UE_S1AP_ID + 1):
        candidate += 1
        if candidate > MAX_ENB_UE_S1AP_ID:
            candidate = MIN_ENB_UE_S1AP_ID
        if candidate not in used_ids:
            return candidate

    raise RuntimeError("No free eNB UE S1AP ID is available")
