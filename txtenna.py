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
from zmq.utils import z85
import md5
import random
import string
import binascii
import goTenna # The goTenna API

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
from bitcoin.core import lx, b2x, b2lx, CMutableTxOut, CMutableTransaction
from bitcoin.wallet import CBitcoinAddress
bitcoin.SelectParams('testnet')


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

        Usage: make_profile GID

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
                corr_id = self.api_thread.send_broadcast(payload,
                                                         method_callback)
            except ValueError:
                print("Message too long!")
                return
            self.in_flight_events[corr_id.bytes] = 'Broadcast message: {}'.format(message)

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

    def confirm_bitcoin_tx_local(self, hash, sender_gid, network):
        """ 
        Confirm bitcoin transaction using local txtenna-server instance

        Usage: confirm_bitcoin_tx tx_id gid network
        """ 

        ## try for 30 minutes to confirm the transaction
        for n in range(0, 30) :
            try :
                proxy = bitcoin.rpc.Proxy()
                r = proxy.getrawtransaction(lx(hash), True)

                ## send zero-conf message back to tx sender
                confirmations = r.get('confirmations', 0)
                rObj = json.dumps({'b': str(confirmations), 'h': hash})
                ## print(str(rObj))
                r_text = "".join(str(rObj).split()) # remove whitespace
                arg = str(sender_gid) + ' ' + r_text
                self.do_send_private(arg)

                print("\nSent to GID: " + str(sender_gid) + ": Transaction " + hash + " added to the mempool.")
                sleep(60) # sleep for a minute            
            
                ## wait for atleast one
                for m in range(0, 30) :
                    if ( confirmations == 0 ) :
                        sleep(60) # sleep for a minute
                        r = proxy.getrawtransaction(lx(hash), True)
                        confirmations = r.get('confirmations', 0)
                    else :
                        break

                ## send confirmations message back to tx sender
                rObj = json.dumps({'b': str(confirmations), 'h': hash})
                ## print(str(rObj))
                r_text = "".join(str(rObj).split()) # remove whitespace
                arg = str(sender_gid) + ' ' + r_text
                self.do_send_private(arg)

                print("\nSent to GID: " + str(sender_gid) + ": Transaction " + hash + " confirmed in " + str(confirmations) + " blocks.")
            except IndexError:
                ## tx_id not yet in the global mempool, sleep for a minute and then try again
                sleep(60)
                continue
            except :
                ## unknown RPC error, but keep trying
                traceback.print_exc()
                sleep(60)
                continue
            break

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
            rObj = json.dumps({'b': 0, 'h': hash})
            ## print(str(rObj))
            arg = str(sender_gid) + ' ' + str(rObj)
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
            bObj = obj['block']
            rObj = json.dumps({'b': bObj['height'], 'h': hash})
            ## print(str(rObj))
            arg = str(sender_gid) + ' ' + str(rObj)
            self.do_send_private(arg)

            print("\nSent to GID: " + str(sender_gid) + ": Transaction " + hash + " confirmed in block " + str(bObj['height']) + ".")

        except:
            traceback.print_exc()

    def handle_message(self, message):
        """ handle a txtenna message received over the mesh network

        Usage: handle_message message
        """
        payload = str(message.payload.message)
        ## print("received transaction payload: " + payload)

        obj = json.loads(payload)
        if 'b' in obj.keys() :
            ## process incoming transaction confirmation from another server
            if (obj['b'] > 0) :
                print("\nTransaction " + obj['h'] + " confirmed in block " + str(obj['b']))
            else :
                print("\nTransaction " + obj['h'] + " added to the the mem pool")

        else :
            ## process incoming segment
            headers = {u'content-type': u'application/json'}
            url = "http://127.0.0.1:8091/segments" ## local txtenna-server
            ## url = "https://api.samouraiwallet.com/v2/txtenna/segments" ## default txtenna-server
            r = requests.post(url, headers= headers, data=payload)
            ## print(r.text)

            if 'i' in obj.keys() and not 'c' in obj.keys() :
                ## print(obj['h'])
                sender_gid = message.sender.gid_val

                ## check for confirmed transaction in a new thread
                ## self.confirm_bitcoin_tx_online(obj['h'], sender_gid)
                t = Thread(target=self.confirm_bitcoin_tx_local, args=(obj['h'], sender_gid,obj['n']))
                t.start()

    def do_mesh_broadcast_rawtx(self, rem):
        """ 
        Broadcast the raw hex of a Bitcoin transaction and its transaction ID over mainnet or testnet. 
        A local copy of txtenna-server must be configured to support the selected network.

        Usage: mesh_broadcast_tx RAW_HEX TX_ID NETWORK(m|t)

        eg. txTenna> mesh_broadcast_rawtx 01000000000101bf6c3ed233e8700b42c1369993c2078780015bab7067b9751b7f49f799efbffd0000000017160014f25dbf0eab0ba7e3482287ebb41a7f6d361de6efffffffff02204e00000000000017a91439cdb4242013e108337df383b1bf063561eb582687abb93b000000000017a9148b963056eedd4a02c91747ea667fc34548cab0848702483045022100e92ce9b5c91dbf1c976d10b2c5ed70d140318f3bf2123091d9071ada27a4a543022030c289d43298ca4ca9d52a4c85f95786c5e27de5881366d9154f6fe13a717f3701210204b40eff96588033722f487a52d39a345dc91413281b31909a4018efb330ba2600000000 94406beb94761fa728a2cde836ca636ecd3c51cbc0febc87a968cb8522ce7cc1 m
        """

        ## TODO: test Z85 compression and add as an option
        (strHexTx, strHexTxHash, network) = rem.split(" ")
        messages = self.tx_to_json(strHexTx, strHexTxHash, str(self.messageIdx), network, False)
        for msg in messages :
            _msg = "".join(msg.split()) ## strip whitespace
            self.do_send_broadcast(_msg)
            sleep(10)
        self.messageIdx = (self.messageIdx+1) % 9999

    def tx_to_json(self, strHexTx, strHexTxHash, messageIdx=0, network='m', isZ85=False):
        ##
        ## if Z85 encoding, use 24 extra characters for tx in segment0. Hash encoded on 40 characters instead of 64
        ##
        ## This method translated to python from txTenna app PayloadFactory.java : toJSON method
        ##
        ## JSON Parameters
        ##    * **s** - `integer` - Number of segments for the transaction. Only used in the first segment for a given transaction.
        ##    * **h** - `string` - Hash of the transaction. Only used in the first segment for a given transaction. May be Z85-encoded.
        ##    * **n** - `char` (optional) - Network to use. 't' for TestNet3, otherwise assume MainNet. Only used in the first segment for a given transaction.
        ##    * **i** - `string` - TxTenna unid identifying the transaction (8 bytes).
        ##    * **c** - `integer` - Sequence number for this segment. May be omitted in first segment for a given transaction (assumed to be 0).
        ##    * **t** - `string` - Hex transaction data for this segment. May be Z85-encoded.
        ##    * **b** - `integer` - Block height of corresponding transaction hash. Will be 0 for mempool transactions.

        segment0Len = 100  ## 110?
        segment1Len = 180  ## 190?

        tx_network = network

        if isZ85 : 
            segment0Len += 24

        strRaw = strHexTx
        if isZ85 :
            strRaw = z85.encode(strHexTx)

        seg_count = 0
        if len(strRaw) <= segment0Len :
            seg_count = 1
        else :
            length = len(strRaw)
            length -= segment0Len
            seg_count = 1
            seg_count += (length / segment1Len)
            if length % segment1Len > 0 :
                seg_count += 1

        tx_id = messageIdx

        # a unique identifier for set of segments from a particular node
        _id = str(self.api_thread.gid.gid_val) + "|" + str(messageIdx)

        try :
            buf = _id.decode("UTF-8")
            md5_hash = md5.new(buf).digest()
            idBytes = md5_hash[:8] ## first 8 bytes of md5 digest
            if isZ85 :
                tx_id = z85.encode(idBytes.encode("hex"))
            else :
                tx_id = idBytes.encode("hex")
        except Exception: # pylint: disable=broad-except
            traceback.print_exc()

        ret = []
        for seg_num in range(0, seg_count) :

            ## Gson gson = new GsonBuilder().disableHtmlEscaping().create();

            if seg_num == 0 :
                if isZ85 :
                    tx_hash = z85.encode(strHexTxHash.decode("hex"))
                else :
                    tx_hash = strHexTxHash

                seg_len = len(strRaw)
                tx_seg = strRaw
                if len(strRaw) > segment0Len :
                    seg_len = segment0Len
                    tx_seg = strRaw[:seg_len]
                    strRaw = strRaw[seg_len:]
                
                rObj = json.dumps({'s': seg_count,'i': tx_id,'n': tx_network,'h': tx_hash,'t': tx_seg})
                ret.append(rObj)

            else :
                seg_len = len(strRaw)
                tx_seg = strRaw
                if len(strRaw) > segment1Len :
                    seg_len = segment1Len
                    tx_seg = strRaw[:seg_len]
                    strRaw = strRaw[seg_len:]

                rObj = json.dumps({'c': seg_num,'i': tx_id,'t': tx_seg})
                ret.append(rObj)

        return ret

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

def run_cli():
    """
    The main function of the sample app.

    Instantiates a CLI object and runs it.
    """
    cli_obj = goTennaCLI()

    import argparse
    import six
    import code
    parser = argparse.ArgumentParser('Run a txTenna transaction gateway')
    parser.add_argument('SDK_TOKEN', type=six.b,
                        help='The token for the goTenna SDK')
    parser.add_argument('GEO_REGION', type=six.b,
                        help='The geo region number you are in')
    args = parser.parse_args()  

    cli_obj.do_sdk_token(args.SDK_TOKEN)

    ## set geo region
    cli_obj.do_set_geo_region(args.GEO_REGION)
    
    ## set new random GID every time the server starts
    _gid = ''.join(random.SystemRandom().choice(string.hexdigits) for _ in range(12))
    _gid_int = int(_gid, 16)
    cli_obj.do_set_gid(str(_gid_int))
    print("gid=",str(_gid_int))

    try:
        sleep(5)
        cli_obj.cmdloop("Welcome to the txTenna API sample! "
                        "Press ? for a command list.\n")
    except Exception: # pylint: disable=broad-except
        traceback.print_exc()
        cli_obj.do_quit('')

if __name__ == '__main__':
    run_cli()
