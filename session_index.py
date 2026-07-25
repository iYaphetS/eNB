class SessionIndex:
    def __init__(self):
        self._by_enb_id = {}
        self._by_s_tmsi = {}
        self._keys_by_session = {}

    def update(self, session):
        self.remove(session)
        enb_id = session.get('ENB-UE-S1AP-ID')
        s_tmsi = session.get('S-TMSI')
        if enb_id is not None:
            self._by_enb_id[enb_id] = session
        if s_tmsi is not None:
            self._by_s_tmsi[s_tmsi] = session
        self._keys_by_session[id(session)] = (enb_id, s_tmsi)

    def remove(self, session):
        old_keys = self._keys_by_session.pop(id(session), None)
        if old_keys is None:
            return
        enb_id, s_tmsi = old_keys
        if self._by_enb_id.get(enb_id) is session:
            del self._by_enb_id[enb_id]
        if self._by_s_tmsi.get(s_tmsi) is session:
            del self._by_s_tmsi[s_tmsi]

    def by_enb_id(self, enb_id):
        return self._by_enb_id.get(enb_id)

    def by_s_tmsi(self, s_tmsi):
        return self._by_s_tmsi.get(s_tmsi)

    def used_enb_ids(self):
        return self._by_enb_id.keys()


def sync_session_index(index, users, session):
    imsi = session.get('IMSI')
    if imsi is not None and users.get(imsi) is session:
        index.update(session)
    else:
        index.remove(session)


def extract_enb_ue_s1ap_id(value):
    if isinstance(value, dict):
        if 'eNB-UE-S1AP-ID' in value:
            return value['eNB-UE-S1AP-ID']
        if value.get('id') == 8:
            ie_value = value.get('value')
            if isinstance(ie_value, tuple) and len(ie_value) > 1:
                return ie_value[1]
        for child in value.values():
            result = extract_enb_ue_s1ap_id(child)
            if result is not None:
                return result
    elif isinstance(value, (list, tuple)):
        for child in value:
            result = extract_enb_ue_s1ap_id(child)
            if result is not None:
                return result
    return None
