""" txtenna.py - 
This code is derived from sample.py available from the goTenna Public SDK (https://github.com/gotenna/PublicSDK)
"""
from __future__ import print_function
import cmd # for the command line application
import sys # To quit
import os
import traceback
import logging
import requests
import json
from threading import Thread
from time import sleep
import random
import string
import binascii
import goTenna # The goTenna API
from segment_storage import SegmentStorage
from txtenna_segment import TxTennaSegment
from io import BytesIO
import httplib
import struct
import zlib

# For SPI connection only, set SPI_CONNECTION to true with proper SPI settings
SPI_CONNECTION = False
SPI_BUS_NO = 0
SPI_CHIP_NO = 0
SPI_REQUEST = 22
SPI_READY = 27

# Configure the Python logging module to print to stderr. In your application,
# you may want to route the logging elsewhere.
logging.basicConfig()

# Import readline if the system has it
try:
    import readline
    assert readline # silence pyflakes
except ImportError:
    pass

# Import support for bitcoind RPC interface
import bitcoin
import bitcoin.rpc
from bitcoin.core import x, lx, b2x, b2lx, CMutableTxOut, CMutableTransaction
from bitcoin.wallet import CBitcoinAddress
bitcoin.SelectParams('mainnet')

TXTENNA_GATEWAY_GID = 2573394689

class goTennaCLI(cmd.Cmd):
    """ CLI handler function
    """
    def __init__(self):
        self.api_thread = None
        self.status = {}
        cmd.Cmd.__init__(self)
        self.prompt = 'txTenna>'
        self.in_flight_events = {}
        self._set_frequencies = False
        self._set_tx_power = False
        self._set_bandwidth = False
        self._set_geo_region = False
        self._settings = goTenna.settings.GoTennaSettings(
            rf_settings=goTenna.settings.RFSettings(), 
            geo_settings=goTenna.settings.GeoSettings())
        self._do_encryption = True
        self._awaiting_disconnect_after_fw_update = [False]
        self.messageIdx = 0
        self.local = False
        self.segment_storage = SegmentStorage()
        self.send_dir = None
        self.receive_dir = None
        self.watch_dir_thread = None
        self.pipe_file = None

    def precmd(self, line):
        if not self.api_thread\
           and not line.startswith('sdk_token')\
           and not line.startswith('quit'):
            print("An SDK token must be entered to begin.")
            return ''
        return line

    def do_sdk_token(self, rst):
        """ Enter an SDK token to begin usage of the driver. Usage: sdk_token TOKEN"""
        if self.api_thread:
            print("To change SDK tokens, restart the sample app.")
            return
        try:
            if not SPI_CONNECTION:
                self.api_thread = goTenna.driver.Driver(sdk_token=rst, gid=None, 
                                                    settings=None, 
                                                    event_callback=self.event_callback)
            else:
                self.api_thread = goTenna.driver.SpiDriver(
                                    SPI_BUS_NO, SPI_CHIP_NO, 22, 27,
                                    rst, None, None, self.event_callback)
            self.api_thread.start()
        except ValueError:
            print("SDK token {} is not valid. Please enter a valid SDK token."
                  .format(rst))

    def emptyline(self):
        pass

    def event_callback(self, evt):
        """ The event callback that will print messages from the API.

        See the documentation for ``goTenna.driver``.

        This will be invoked from the API's thread when events are received.
        """
        if evt.event_type == goTenna.driver.Event.MESSAGE:
            try:
                ## print(str(evt))
                self.handle_message(evt.message)
            except Exception:
                traceback.print_exc()
        elif evt.event_type == goTenna.driver.Event.DEVICE_PRESENT:
            ## print(str(evt))
            if self._awaiting_disconnect_after_fw_update[0]:
                print("Device physically connected")
            else:
                print("Device physically connected, configure to continue")
        elif evt.event_type == goTenna.driver.Event.CONNECT:
            if self._awaiting_disconnect_after_fw_update[0]:
                print("Device reconnected! Firmware update complete!")
                self._awaiting_disconnect_after_fw_update[0] = False
            else:
                print("Connected!")
                print(str(evt))
        elif evt.event_type == goTenna.driver.Event.DISCONNECT:
            if self._awaiting_disconnect_after_fw_update[0]:
                # Do not reset configuration so that the device will reconnect on its own
                print("Firmware update: Device disconnected, awaiting reconnect")
            else:
                print("Disconnected! {}".format(evt))
                # We reset the configuration here so that if the user plugs in a different
                # device it is not immediately reconfigured with new and incorrect data
                self.api_thread.set_gid(None)
                self.api_thread.set_rf_settings(None)
                self._set_frequencies = False
                self._set_tx_power = False
                self._set_bandwidth = False
        elif evt.event_type == goTenna.driver.Event.STATUS:
            self.status = evt.status
        elif evt.event_type == goTenna.driver.Event.GROUP_CREATE:
            index = -1
            for idx, member in enumerate(evt.group.members):
                if member.gid_val == self.api_thread.gid.gid_val:
                    index = idx
                    break
            print("Added to group {}: You are member {}"
                  .format(evt.group.gid.gid_val,
                          index))

    def build_callback(self, error_handler=None):
        """ Build a callback for sending to the API thread. May speciy a callable
        error_handler(details) taking the error details from the callback. The handler should return a string.
        """
        def default_error_handler(details):
            """ Easy error handler if no special behavior is needed. Just builds a string with the error.
            """
            if details['code'] in [goTenna.constants.ErrorCodes.TIMEOUT,
                                   goTenna.constants.ErrorCodes.OSERROR,
                                   goTenna.constants.ErrorCodes.EXCEPTION]:
                return "USB connection disrupted"
            return "Error: {}: {}".format(details['code'], details['msg'])
        # Define a second function here so it implicitly captures self
        captured_error_handler = [error_handler]
        def callback(correlation_id, success=None, results=None,
                     error=None, details=None):
            """ The default callback to pass to the API.

            See the documentation for ``goTenna.driver``.

            Does nothing but print whether the method succeeded or failed.
            """
            method = self.in_flight_events.pop(correlation_id.bytes,
                                               'Method call')
            if success:
                if results:
                    print("{} succeeded: {}".format(method, results))
                else:
                    print("{} succeeded!".format(method))
            elif error:
                if not captured_error_handler[0]:
                    captured_error_handler[0] = default_error_handler
                print("{} failed: {}".format(method,
                                             captured_error_handler[0](details)))
        return callback

    def do_set_gid(self, rem):
        """ Create a new profile (if it does not already exist) with default settings.

        Usage: set_gid GID

        GID should be a 15-digit numerical GID.
        """
        if self.api_thread.connected:
            print("Must not be connected when setting GID")
            return
        (gid, _) = self._parse_gid(rem, goTenna.settings.GID.PRIVATE)
        if not gid:
            return
        self.api_thread.set_gid(gid)

    def do_quit(self, arg):
        """ Safely quit.

        Usage: quit
        """
        # pylint: disable=unused-argument
        if self.api_thread:
            self.api_thread.join()
        sys.exit()

    def do_send_broadcast(self, message):
        """ Send a broadcast message

        Usage: send_broadcast MESSAGE
        """
        if not self.api_thread.connected:
            print("No device connected")
        else:
            def error_handler(details):
                """ A special error handler for formatting message failures
                """
                if details['code'] in [goTenna.constants.ErrorCodes.TIMEOUT,
                                       goTenna.constants.ErrorCodes.OSERROR]:
                    return "Message may not have been sent: USB connection disrupted"
                return "Error sending message: {}".format(details)
            try:
                method_callback = self.build_callback(error_handler)
                payload = goTenna.payload.TextPayload(message)
                print("payload valid = {}, message size = {}\n".format(payload.valid, len(message)))

                corr_id = self.api_thread.send_broadcast(payload, method_callback)
                while (corr_id is None):
                    ## try again if send_broadcast fails
                    sleep(10)
                    corr_id = self.api_thread.send_broadcast(payload, method_callback)

                self.in_flight_events[corr_id.bytes] = 'Broadcast message: {} ({} bytes)\n'.format(message,len(message))
            except ValueError:
                print("Message too long!")
                return

    @staticmethod
    def _parse_gid(line, gid_type, print_message=True):
        parts = line.split(' ')
        remainder = ' '.join(parts[1:])
        gidpart = parts[0]
        try:
            gid = int(gidpart)
            if gid > goTenna.constants.GID_MAX:
                print('{} is not a valid GID. The maximum GID is {}'
                      .format(str(gid), str(goTenna.constants.GID_MAX)))
                return (None, line)
            gidobj = goTenna.settings.GID(gid, gid_type)
            return (gidobj, remainder)
        except ValueError:
            if print_message:
                print('{} is not a valid GID.'.format(line))
            return (None, remainder)

    def do_send_private(self, rem):
        """ Send a private message to a contact

        Usage: send_private GID MESSAGE

        GID is the GID to send the private message to.

        MESSAGE is the message.
        """
        if not self.api_thread.connected:
            print("Must connect first")
            return
        (gid, rest) = self._parse_gid(rem, goTenna.settings.GID.PRIVATE)
        if not gid:
            return
        message = rest
        def error_handler(details):
            """ Special error handler for sending private messages to format errors
            """
            return "Error sending message: {}".format(details)

        try:
            method_callback = self.build_callback(error_handler)
            payload = goTenna.payload.TextPayload(message)
            def ack_callback(correlation_id, success):
                if success:
                    print("Private message to {}: delivery confirmed"
                          .format(gid.gid_val))
                else:
                    print("Private message to {}: delivery not confirmed, recipient may be offline or out of range"
                          .format(gid.gid_val))
            corr_id = self.api_thread.send_private(gid, payload,
                                                   method_callback,
                                                   ack_callback=ack_callback,
                                                   encrypt=self._do_encryption)
        except ValueError:
            print("Message too long!")
            return
        self.in_flight_events[corr_id.bytes]\
            = 'Private message to {}: {}'.format(gid.gid_val, message)

    def get_device_type(self):
        return self.api_thread.device_type

    def do_list_geo_region(self, rem):
        """ List the available region.

        Usage: list_geo_region
        """
        print("Allowed region:")
        for region in goTenna.constants.GEO_REGION.DICT:
            print("region {} : {}"
                  .format(region, goTenna.constants.GEO_REGION.DICT[region]))

    def do_set_geo_region(self, rem):
        """ Configure the frequencies the device will use.

        Usage: set_geo_region REGION

        Allowed region displayed with list_geo_region.
        """
        if self.get_device_type() == "pro":
            print("This configuration cannot be done for Pro devices.")
            return
        region = int(rem.strip())
        print('region={}'.format(region))
        if not goTenna.constants.GEO_REGION.valid(region):
            print("Invalid region setting {}".format(rem))
            return
        self._set_geo_region = True
        self._settings.geo_settings.region = region
        self.api_thread.set_geo_settings(self._settings.geo_settings)

    def do_can_connect(self, rem):
        """ Return whether a goTenna can connect. For a goTenna to connect, a GID and RF settings must be configured.
        """
        # pylint: disable=unused-argument
        if self.api_thread.gid:
            print("GID: OK")
        else:
            print("GID: Not Set")
        if self._set_tx_power:
            print("PRO - TX Power: OK")
        else:
            print("PRO - TX Power: Not Set")
        if self._set_frequencies:
            print("PRO - Frequencies: OK")
        else:
            print("PRO - Frequencies: Not Set")
        if self._set_bandwidth:
            print("PRO - Bandwidth: OK")
        else:
            print("PRO - Bandwidth: Not Set")
        if self._set_geo_region:
            print("MESH - Geo region: OK")
        else:
            print("MESH - Geo region: Not Set")

    def do_get_system_info(self, args):
        """ Get system information.

        Usage: get_system_info
        """
        if not self.api_thread.connected:
            print("Device must be connected")
        print(self.api_thread.system_info)

    def do_rpc_getrawtransaction(self, tx_id) :
        """
        Call local Bitcoin RPC method 'getrawtransaction'

        Usage: rpc_sendtoaddress TX_ID
        """
        try :
            proxy = bitcoin.rpc.Proxy()
            r = proxy.getrawtransaction(lx(tx_id), True)
            print(str(r))
        except:
            traceback.print_exc()

    def confirm_bitcoin_tx_local(self, hash, sender_gid):
        """ 
        Confirm bitcoin transaction using local bitcoind instance

        Usage: confirm_bitcoin_tx tx_id gid
        """ 

        ## send transaction to local bitcond
        segments = self.segment_storage.get_by_transaction_id(hash)
        raw_tx = self.segment_storage.get_raw_tx(segments)

        ## pass hex string converted to bytes
        try :
            proxy1 = bitcoin.rpc.Proxy()
            raw_tx_bytes = x(raw_tx)
            tx = CMutableTransaction.stream_deserialize(BytesIO(raw_tx_bytes))
            r1 = proxy1.sendrawtransaction(tx)
        except :
            print("Invalid Transaction! Could not send to network.")
            return

        ## try for 30 minutes to confirm the transaction
        for n in range(0, 30) :
            try :
                proxy2 = bitcoin.rpc.Proxy()
                r2 = proxy2.getrawtransaction(r1, True)

                ## send zero-conf message back to tx sender
                confirmations = r2.get('confirmations', 0)
                rObj = TxTennaSegment('', '', tx_hash=hash, block=confirmations)
                arg = str(sender_gid) + ' ' + rObj.serialize_to_json()
                self.do_send_private(arg)

                print("\nSent to GID: " + str(sender_gid) + ": Transaction " + hash + " added to the mempool.")
                break      
            except IndexError:
                ## tx_id not yet in the global mempool, sleep for a minute and then try again
                sleep(60)
                continue      
            
            ## wait for atleast one confirmation
            for m in range(0, 30):
                sleep(60) # sleep for a minute
                try :
                    proxy3= bitcoin.rpc.Proxy()
                    r3 = proxy3.getrawtransaction(r1, True)
                    confirmations = r3.get('confirmations', 0)
                    ## keep waiting until 1 or more confirmations
                    if confirmations > 0:
                        break
                except :
                    ## unknown RPC error, but keep trying
                    traceback.print_exc()

            if confirmations > 0 :
                ## send confirmations message back to tx sender if confirmations > 0
                rObj = TxTennaSegment('', '', tx_hash=hash, block=confirmations)
                arg = str(sender_gid) + ' ' + rObj.serialize_to_json()
                self.do_send_private(arg)
                print("\nSent to GID: " + str(sender_gid) + ", Transaction " + hash + " confirmed in " + str(confirmations) + " blocks.")
            else :
                print("\CTransaction from GID: " + str(sender_gid) + ", Transaction " + hash + " not confirmed after 30 minutes.")

    def confirm_bitcoin_tx_online(self, hash, sender_gid, network):
        """ confirm bitcoin transaction using default online Samourai API instance

        Usage: confirm_bitcoin_tx tx_id gid network
        """

        if  network == 't' :
            url = "https://api.samourai.io/test/v2/tx/" + hash ## default testnet txtenna-server
        else :
            url = "https://api.samourai.io/v2/tx/" + hash ## default txtenna-server
        
        try:
            r = requests.get(url)
            ## print(r.text)

            while r.status_code != 200:
                sleep(60) # sleep for a minute
                r = requests.get(url)

            ## send zero-conf message back to tx sender
            rObj = TxTennaSegment('', '', tx_hash=hash, block=0)
            arg = str(sender_gid) + ' ' + rObj.serialize_to_json()
            self.do_send_private(arg)    

            print("\nSent to GID: " + str(sender_gid) + ": Transaction " + hash + " added to the mempool.")            

            r_text = "".join(r.text.split()) # remove whitespace
            obj = json.loads(r_text)
            while not 'block' in obj.keys():
                sleep(60) # sleep for a minute
                r = requests.get(url)
                r_text = "".join(r.text.split())
                obj = json.loads(r_text)

            ## send block height message back to tx sender
            blockheight = obj['block']['height']
            rObj = TxTennaSegment('', '', tx_hash=hash, block=blockheight)
            arg = str(sender_gid) + ' ' + rObj.serialize_to_json()
            self.do_send_private(arg)

            print("\nSent to GID: " + str(sender_gid) + ": Transaction " + hash + " confirmed in block " + str(blockheight) + ".")

        except:
            traceback.print_exc()

    def create_output_data_struct(self, data):
        """Create the output data structure generated by the blocksat receiver

        The "Protocol Sink" block of the blocksat-rx application places the incoming
        API data into output structures. This function creates the exact same
        structure that the blocksat-rx application would.

        Args:
            data : Sequence of bytes to be placed in the output structure

        Returns:
            Output data structure as sequence of bytes

        """

        # Header of the output data structure that the Blockstream Satellite Receiver
        # generates prior to writing user data into the API named pipe
        OUT_DATA_HEADER_FORMAT     = '64sQ'
        OUT_DATA_DELIMITER         = 'vyqzbefrsnzqahgdkrsidzigxvrppato' + \
                             '\xe0\xe0$\x1a\xe4["\xb5Z\x0bv\x17\xa7\xa7\x9d' + \
                             '\xa5\xd6\x00W}M\xa6TO\xda7\xfaeu:\xac\xdc'

        # Struct is composed of a delimiter and the message length
        out_data_header = struct.pack(OUT_DATA_HEADER_FORMAT,
                                    OUT_DATA_DELIMITER,
                                    len(data))

        # Final output data structure
        out_data = out_data_header + data

        return out_data            
            
    def receive_message_from_gateway(self, filename):
        """ 
        Receive message data from a mesh gateway node

        Usage: receive_message_from_gateway filename
        """ 

        ## send transaction to local blocksat reader pipe
        segments = self.segment_storage.get_by_transaction_id(filename)
        raw_data = self.segment_storage.get_raw_tx(segments).encode("utf-8")

        decoded_data = zlib.decompress(raw_data.decode('base64'))

        deliminted_data = self.create_output_data_struct(decoded_data)

        ## send the data to the blocksat pipe
        try :
            print("Message Data received for [" + filename + "] ( " + str(len(decoded_data)) + " bytes ) :\n" + str(decoded_data) + "\n")
        except UnicodeDecodeError :
            print("Binary Data received for [" + filename + "] ( " + str(len(decoded_data)) + " bytes )\n")
        
        if not self.pipe_file is None and os.path.exists(self.pipe_file) is True :
            # Open pipe and write raw data to it
            pipe_f = os.open(self.pipe_file, os.O_RDWR)
            os.write(pipe_f, deliminted_data)
        elif not self.receive_dir is None and os.path.exists(self.receive_dir) is True :
            # Create file
            dump_f = os.open(os.path.join(self.receive_dir, filename), os.O_CREAT | os.O_RDWR)
            os.write(dump_f, decoded_data)
        else :
            print("ERROR: Could not save data. No pipe found at [" + self.pipe_file + "] and no receive directory found at [" + self.receive_dir +"]\n")

    def handle_message(self, message):
        """ handle a txtenna message received over the mesh network

        Usage: handle_message message
        """
        payload = str(message.payload.message)
        print("received transaction payload: " + payload)

        segment = TxTennaSegment.deserialize_from_json(payload)
        self.segment_storage.put(segment)
        network = self.segment_storage.get_network(segment.payload_id)

        ## process incoming transaction confirmation from another server
        if (segment.block > 0):
            print("\nTransaction " + segment.payload_id + " confirmed in block " + str(segment.block))
        elif (segment.block is 0):
            print("\nTransaction " + segment.payload_id + " added to the the mem pool")
        elif (network is 'd'):
            ## process message data
            if (self.segment_storage.is_complete(segment.payload_id)):
                filename = self.segment_storage.get_transaction_id(segment.payload_id)
                t = Thread(target=self.receive_message_from_gateway, args=(filename,))
                t.start()
        else:
            ## process incoming tx segment
            if not self.local :
                headers = {u'content-type': u'application/json'}
                url = "https://api.samouraiwallet.com/v2/txtenna/segments" ## default txtenna-server
                r = requests.post(url, headers= headers, data=payload)
                print(r.text)

            if (self.segment_storage.is_complete(segment.payload_id)):
                sender_gid = message.sender.gid_val
                tx_id = self.segment_storage.get_transaction_id(segment.payload_id)

                ## check for confirmed transaction in a new thread
                if (self.local) :
                    t = Thread(target=self.confirm_bitcoin_tx_local, args=(tx_id, sender_gid))
                else :
                    t = Thread(target=self.confirm_bitcoin_tx_online, args=(tx_id, sender_gid, network))
                t.start()

    def do_mesh_broadcast_rawtx(self, rem):
        """ 
        Broadcast the raw hex of a Bitcoin transaction and its transaction ID over mainnet or testnet. 
        A local copy of txtenna-server must be configured to support the selected network.

        Usage: mesh_broadcast_tx RAW_HEX TX_ID NETWORK(m|t)

        eg. txTenna> mesh_broadcast_rawtx 01000000000101bf6c3ed233e8700b42c1369993c2078780015bab7067b9751b7f49f799efbffd0000000017160014f25dbf0eab0ba7e3482287ebb41a7f6d361de6efffffffff02204e00000000000017a91439cdb4242013e108337df383b1bf063561eb582687abb93b000000000017a9148b963056eedd4a02c91747ea667fc34548cab0848702483045022100e92ce9b5c91dbf1c976d10b2c5ed70d140318f3bf2123091d9071ada27a4a543022030c289d43298ca4ca9d52a4c85f95786c5e27de5881366d9154f6fe13a717f3701210204b40eff96588033722f487a52d39a345dc91413281b31909a4018efb330ba2600000000 94406beb94761fa728a2cde836ca636ecd3c51cbc0febc87a968cb8522ce7cc1 m
        """

        ## TODO: test Z85 binary encoding and add as an option
        (strHexTx, strHexTxHash, network) = rem.split(" ")
        gid = self.api_thread.gid.gid_val
        segments = TxTennaSegment.tx_to_segments(gid, strHexTx, strHexTxHash, str(self.messageIdx), network, False)
        for seg in segments :
            self.do_send_broadcast(seg.serialize_to_json())
            sleep(10)
        self.messageIdx = (self.messageIdx+1) % 9999

    def do_rpc_getbalance(self, rem) :
        """
        Call local Bitcoin RPC method 'getbalance'

        Usage: rpc_getbalance
        """
        try :
            proxy = bitcoin.rpc.Proxy()
            balance = proxy.getbalance()
            print("getbalance: " + str(balance))
        except Exception: # pylint: disable=broad-except
            traceback.print_exc()     

    def do_rpc_sendrawtransaction(self, hex) :
        """
        Call local Bitcoin RPC method 'sendrawtransaction'

        Usage: rpc_sendrawtransaction RAW_TX_HEX
        """
        try :
            proxy = bitcoin.rpc.Proxy()
            r = proxy.sendrawtransaction(hex)
            print("sendrawtransaction: " + str(r))
        except Exception: # pylint: disable=broad-except
            traceback.print_exc()

    def do_rpc_sendtoaddress(self, rem) :
        """
        Call local Bitcoin RPC method 'sendtoaddress'

        Usage: rpc_sendtoaddress ADDRESS SATS
        """
        try:
            proxy = bitcoin.rpc.Proxy()
            (addr, amount) = rem.split()
            r = proxy.sendtoaddress(addr, amount)
            print("sendtoaddress, transaction id: " + str(r["hex"]))
        except Exception: # pylint: disable=broad-except
            traceback.print_exc() 

    def do_mesh_sendtoaddress(self, rem) :
        """ 
        Create a signed transaction and broadcast it over the connected mesh device. The transaction 
        spends some amount of satoshis to the specified address from the local bitcoind wallet and selected network. 

        Usage: mesh_sendtoaddress ADDRESS SATS NETWORK(m|t)

        eg. txTenna> mesh_sendtoaddress 2N4BtwKZBU3kXkWT7ZBEcQLQ451AuDWiau2 13371337 t
        """
        try:

            proxy = bitcoin.rpc.Proxy()
            (addr, sats, network) = rem.split()

            # Create the txout. This time we create the scriptPubKey from a Bitcoin
            # address.
            txout = CMutableTxOut(sats, CBitcoinAddress(addr).to_scriptPubKey())

            # Create the unsigned transaction.
            unfunded_transaction = CMutableTransaction([], [txout])
            funded_transaction = proxy.fundrawtransaction(unfunded_transaction)
            signed_transaction = proxy.signrawtransaction(funded_transaction["tx"])
            txhex = b2x(signed_transaction["tx"].serialize())
            txid = b2lx(signed_transaction["tx"].GetTxid())
            print("sendtoaddress_mesh (tx, txid, network): " + txhex + ", " + txid, ", " + network)

            # broadcast over mesh
            self.do_mesh_broadcast_rawtx( txhex + " " + txid + " " + network)

        except Exception: # pylint: disable=broad-except
            traceback.print_exc()

        try :
            # lock UTXOs used to fund the tx if broadcast successful
            vin_outpoints = set()
            for txin in funded_transaction["tx"].vin:
                vin_outpoints.add(txin.prevout)
            ## json_outpoints = [{'txid':b2lx(outpoint.hash), 'vout':outpoint.n}
            ##              for outpoint in vin_outpoints]
            ## print(str(json_outpoints))
            proxy.lockunspent(False, vin_outpoints)
            
        except Exception: # pylint: disable=broad-except
            ## TODO: figure out why this is happening
            print("RPC timeout after calling lockunspent")

    def do_broadcast_messages(self, send_dir) :
        """ 
        Watch a particular directory for files with message data to be broadcast over the mesh network

        Usage: broadcast_messages DIRECTORY

        eg. txTenna> broadcast_messages ./downloads
        """

        if (send_dir is not None):
            #start new thread to watch directory
            self.watch_dir_thread = Thread(target=self.watch_messages, args=(send_dir,))
            self.watch_dir_thread.start()

    def watch_messages(self, send_dir):
        
        before = {}
        while os.path.exists(send_dir):
            sleep (10)
            after = dict ([(f, None) for f in os.listdir (send_dir)])
            new_files = [f for f in after if not f in before]
            if new_files:
                self.broadcast_message_files(send_dir, new_files)
            before = after

    def broadcast_message_files(self, directory, filenames):
        for filename in filenames:
            print("Broadcasting ",directory+"/"+filename)
            f = open(directory+"/"+filename,'r')
            message_data = f.read()
            f.close
            
            ## binary to ascii encoding and strip out newlines
            encoded = zlib.compress(message_data, 9).encode('base64').replace('\n','')
            print("[\n" + encoded.decode() + "\n]")

            gid = self.api_thread.gid.gid_val
            segments = TxTennaSegment.tx_to_segments(gid, encoded, filename, str(self.messageIdx), "d", False)
            for seg in segments :
                self.do_send_broadcast(seg.serialize_to_json())
                sleep(10)
            self.messageIdx = (self.messageIdx+1) % 9999


def run_cli():
    """
    The main function of the sample app.

    Instantiates a CLI object and runs it.
    """
    cli_obj = goTennaCLI()

    import argparse
    import six

    parser = argparse.ArgumentParser('Run a txTenna transaction gateway')
    parser.add_argument('SDK_TOKEN', type=six.b,
                        help='The token for the goTenna SDK')
    parser.add_argument('GEO_REGION', type=six.b,
                        help='The geo region number you are in')
    parser.add_argument("--gateway", action="store_true",
                        help="Use this computer as an internet connected transaction gateway with a default GID")
    parser.add_argument("--local", action="store_true",
                        help="Use local bitcoind to confirm and broadcast transactions")
    parser.add_argument("--send_dir",
                        help="Broadcast message data from files in this directory")
    parser.add_argument("--receive_dir",
                        help="Write files from received message data in this directory")
    parser.add_argument('-p', '--pipe',
                        default='/tmp/blocksat/api',
                        help='Pipe on which relayed message data is written out to ' +
                        '(default: /tmp/blocksat/api)')
    args = parser.parse_args()  

    ## start goTenna SDK thread by setting the SDK token
    cli_obj.do_sdk_token(args.SDK_TOKEN)

    ## set geo region
    cli_obj.do_set_geo_region(args.GEO_REGION)

    if args.gateway :
        ## use default gateway GID
        _gid = str(TXTENNA_GATEWAY_GID)
    else :
        ## create a random GID to use for sending transaction
        _gid = ''.join(random.SystemRandom().choice(string.hexdigits) for _ in range(12))
        _gid = str(int(_gid, 16))

    cli_obj.do_set_gid(_gid)
    print("set gid=",_gid)

    ## use local bitcoind to confirm transactions if 'local' is true
    cli_obj.local = args.local

    ## broadcast message data from files in this directory, eg. created by the blocksat
    cli_obj.send_dir = args.send_dir
    if (args.send_dir is not None):
        cli_obj.do_broadcast_messages(args.send_dir)

    cli_obj.pipe_file = args.pipe
    cli_obj.receive_dir = args.receive_dir

    try:
        sleep(5)
        cli_obj.cmdloop("Welcome to the txTenna API sample! "
                        "Press ? for a command list.\n")
    except Exception: # pylint: disable=broad-except
        traceback.print_exc()
        cli_obj.do_quit('')

if __name__ == '__main__':
    run_cli()
