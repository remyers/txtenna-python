''' 
This module derived from Rich D's PyMuleTools respository:

https://github.com/kansas-city-bitcoin-developers/PyMuleTools
'''

from txtenna_segment import TxTennaSegment

class SegmentStorage:
    def __init__(self):
        self.__payloads = {}
        self.__transactionLookup = {}

    def get_raw_tx(self, segments):
        raw_tx = ""
        for segment in segments:
            if segment.payload is not None:
                raw_tx += segment.payload
        return raw_tx

    def get(self, payload_id):
        return self.__payloads[payload_id] if payload_id in self.__payloads else None

    def get_by_transaction_id(self, tx_id):
        if tx_id in self.__transactionLookup:
            return self.__payloads[self.__transactionLookup[tx_id]]
        return None

    def get_transaction_id(self, payload_id):
        if payload_id in self.__payloads:
            for segment in self.__payloads[payload_id]:
                    if segment.tx_hash is not None:
                        return segment.tx_hash
        return None

    def get_network(self, payload_id):
        if payload_id in self.__payloads:
            for segment in self.__payloads[payload_id]:
                    if segment.tx_hash is not None:
                        if segment.testnet is True:
                            return 't'
                        elif segment.message is True:
                            return 'd'
                        else:
                            return 'm'

    def remove(self, payload_id):
        if payload_id in self.__payloads:
            for segment in self.__payloads[payload_id]:
                if segment.tx_hash is not None:
                    del self.__transactionLookup[segment.tx_hash]
                    break
            del self.__payloads[payload_id]

    def put(self, segment):
        if segment.payload_id in self.__payloads:
            payload = self.__payloads[segment.payload_id]
            payload.append(segment)
            if segment.sequence_num+1 != len(payload):
                self.__payloads[segment.payload_id].sort(key=lambda p: p.sequence_num)
        else:
            self.__payloads[segment.payload_id] = [segment]

        if segment.tx_hash is not None:
            self.__transactionLookup[segment.tx_hash] = segment.payload_id

    def is_complete(self, payload_id):
        segments = self.get(payload_id)
        if segments is not None:
            segment = next((s for s in segments if s.segment_count is not None), None)
            return segment is not None and segment.segment_count == len(segments)

        return False
