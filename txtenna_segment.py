import json
from zmq.utils import z85
import md5
import string

class TxTennaSegment:

    def __init__(self, payload_id, payload, tx_hash=None, sequence_num=0, testnet=False, segment_count=None, block=None, message=False):
        self.segment_count = segment_count
        self.tx_hash = tx_hash
        self.payload_id = payload_id
        self.testnet = testnet
        self.sequence_num = sequence_num
        self.payload = payload
        self.block = block
        self.message = message

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

        if self.message:
            data["n"] = "d"

        # transaction confirmations contain only two elements
        if self.block:
            data = {
                "h": self.tx_hash,
                "b": self.block
            }

        return json.dumps(data,separators=(',',':'))

    @classmethod
    def deserialize_from_json(cls, json_string):
        data = json.loads(json_string)

        # Validate
        if not cls.segment_json_is_valid(data):
            raise AttributeError(
                'Segment JSON is valid but not properly constructed. Refer to MuleTools documentation for details.\r\n\
                    {json_string}')

        # present for normal segments, but not for block confirmations
        payload_id = data["i"] if "i" in data else ''
        payload = data["t"] if "t" in data else ''

        # Tail segments
        sequence_num = data["c"] if "c" in data else 0

        # Head segments
        segment_count = data["s"] if "s" in data else None
        tx_hash = data["h"] if "h" in data else None

        # Optional network flag
        testnet = True if "n" in data and data["n"] == "t" else False
        message = True if "n" in data and data["n"] == "d" else False

        # Block confirmation
        block = data["b"] if "b" in data else None

        return cls( payload_id, payload, tx_hash=tx_hash, sequence_num=sequence_num, testnet=testnet, segment_count=segment_count, block=block,message=message)

    @classmethod
    def segment_json_is_valid(cls, data):
        return ("i" in data and "t" in data and
                (
                        ("s" in data and "h" in data and ("c" not in data or ("c" in data and data["c"] == 0)))
                        or
                        ("c" in data and data["c"] > 0 and "s" not in data and "h" not in data)
                ) or
                ("b" in data and data["b"] >= 0 and "h" in data))

    @classmethod
    def tx_to_segments(self, gid, strHexTx, strHexTxHash, messageIdx=0, network='m', isZ85=False):
        ##
        ## if Z85 encoding, use 24 extra characters for tx in segment0. Hash encoded on 40 characters instead of 64
        ##
        ## This method translated to python from txTenna app PayloadFactory.java : toJSON method
        ##
        ## JSON Parameters
        ##    * **s** - `integer` - Number of segments for the transaction. Only used in the first segment for a given transaction.
        ##    * **h** - `string` - Hash of the transaction. Only used in the first segment for a given transaction. May be Z85-encoded.
        ##    * **n** - `char` (optional) - Network to use. 't' for TestNet3, 'd' for message data, otherwise assume MainNet. Only used in the first segment for a given transaction.
        ##    * **i** - `string` - TxTenna unid identifying the transaction (8 bytes).
        ##    * **c** - `integer` - Sequence number for this segment. May be omitted in first segment for a given transaction (assumed to be 0).
        ##    * **t** - `string` - Hex transaction data for this segment. May be Z85-encoded.
        ##    * **b** - `integer` - Block height of corresponding transaction hash. Will be 0 for mempool transactions.

        segment0Len = 100  ## 110?
        segment1Len = 180  ## 190?

        if isZ85 : 
            segment0Len += 24

        strRaw = strHexTx
        if isZ85 :
            strRaw = z85.encode(strHexTx)

        seg_count = 0
        if len(strRaw) <= segment0Len :
            seg_count = 1
        else :
            escaped_chars = len(''.join(s for s in strRaw if s in string.whitespace))
            length = len(strRaw) + escaped_chars
            length -= segment0Len
            seg_count = 1
            seg_count += (length / segment1Len)
            if length % segment1Len > 0 :
                seg_count += 1

        tx_id = messageIdx

        # a unique identifier for set of segments from a particular node
        _id = str(gid) + "|" + str(messageIdx)

        try :
            buf = _id.decode("UTF-8")
            md5_hash = md5.new(buf).digest()
            idBytes = md5_hash[:8] ## first 8 bytes of md5 digest
            if isZ85 :
                tx_id = z85.encode(idBytes.encode("hex"))
            else :
                tx_id = idBytes.encode("hex")
        except Exception: # pylint: disable=broad-except
            return None

        ret = []
        for seg_num in range(0, seg_count) :

            if seg_num == 0 :
                if isZ85 :
                    tx_hash = z85.encode(strHexTxHash.decode("hex"))
                else :
                    tx_hash = strHexTxHash

                seg_len = len(strRaw)
                tx_seg = strRaw
                if len(strRaw) > segment0Len :
                    seg_len = segment0Len
                    ## json encodes escaped characters as two characters, eg. /n -> //n
                    escaped_chars = len(''.join(s for s in strRaw[:seg_len] if s in string.whitespace))
                    seg_len -= escaped_chars
                    tx_seg = strRaw[:seg_len]
                    strRaw = strRaw[seg_len:]
                
                testnet = network is 't' ## testnet
                message = network is 'd' ## data network
                rObj = TxTennaSegment(tx_id, tx_seg, tx_hash=tx_hash, segment_count=seg_count, testnet=testnet, message=message)
                ret.append(rObj)

            else :
                seg_len = len(strRaw)
                tx_seg = strRaw
                if len(strRaw) > segment1Len :
                    seg_len = segment1Len
                    ## json encodes escaped characters as two characters, eg. /n -> //n
                    escaped_chars = len(''.join(s for s in strRaw[:seg_len] if s in string.whitespace))
                    seg_len -= escaped_chars
                    tx_seg = strRaw[:seg_len]
                    strRaw = strRaw[seg_len:]

                rObj = TxTennaSegment(tx_id, tx_seg, sequence_num=seg_num)
                ret.append(rObj)

        return ret

