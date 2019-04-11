import json


class TxTennaSegment:

    def __init__(self, payload_id, payload, tx_hash=None, sequence_num=0, testnet=False, segment_count=None, block=None):
        self.segment_count = segment_count
        self.tx_hash = tx_hash
        self.payload_id = payload_id
        self.testnet = testnet
        self.sequence_num = sequence_num
        self.payload = payload
        self.block = block

    def __str__(self):
        return "Tx {self.tx_hash} Part {self.sequence_num}"

    def __repr__(self):
        return self.serialize_to_json()

    def serialize_to_json(self):
        data = {
            "i": self.payload_id,
            "t": self.payload
        }

        if self.sequence_num > 0:
            data["c"] = self.sequence_num

        if self.sequence_num == 0:
            data["s"] = self.segment_count
            data["h"] = self.tx_hash

        if self.testnet:
            data["n"] = "t"

        if self.block:
            data["b"] = self.block

        return json.dumps(data)

    @classmethod
    def deserialize_from_json(cls, json_string):
        data = json.loads(json_string)

        # Validate
        if not cls.segment_json_is_valid(data):
            raise AttributeError(
                'Segment JSON is valid but not properly constructed. Refer to MuleTools documentation for details.\r\n\
                    {json_string}')

        # Always present
        payload_id = data["i"]
        payload = data["t"]

        # Tail segments
        sequence_num = data["c"] if "c" in data else 0

        # Head segments
        segment_count = data["s"] if "s" in data else None
        tx_hash = data["h"] if "h" in data else None

        # Optional network flag
        testnet = True if "n" in data and data["n"] == "t" else False

        # Block confirmation
        block = data["b"] if "b" in data else None

        return cls( payload_id, payload, tx_hash=tx_hash, sequence_num=sequence_num, testnet=testnet, segment_count=segment_count, block=block)

    @classmethod
    def segment_json_is_valid(cls, data):
        return ("i" in data and "t" in data and
                (
                        ("s" in data and "h" in data and ("c" not in data or ("c" in data and data["c"] == 0)))
                        or
                        ("c" in data and data["c"] > 0 and "s" not in data and "h" not in data)
                ) or
                ("b" in data and data["b"] >= 0 and "h" in data))

