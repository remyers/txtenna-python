# txtenna-python
Python based version of txtenna that can send and receive Bitcoin transactions via a local txtenna-server

# Prerequisits

* [Python 2.7](https://www.python.org/downloads/) - probably works on 3+ but not tested yet
* [Bitcoin Core](https://bitcoincore.org/en/download/) - expects a local **indexed** installation of bitcoind for testnet and/or mainnet
* [txTenna-server](https://github.com/MuleTools/txTenna-server) - configure with RPC access to local bitcoind installations
* [goTenna Python SDK](https://github.com/remyers/PublicSDK/tree/master/python-public-sdk) - install whl file with pip
* A free SDK Token received by email from goTenna: https://www.gotenna.com/pages/sdk
* A goTenna Mesh device plugged into a USB port of your computer (RPi, PC, Mac, Linux, etc)

# How does it work
  
    $ python txtenna.py 
    usage: Run a txTenna transaction gateway [-h] SDK_TOKEN GEO_REGION
    Run a txTenna transaction gateway: error: too few arguments
    
Now you can run python.py with your SDK token and local region (eg. 1 = North America, 2 = Europe)
    
    $ python txtenna.py <Your SDK Token String> 2
    region=2
    Device physically connected, configure to continue
    gid= 241887036765613
    Connected!
    connect: port: /dev/cu.usbmodemMX180629041 serial: MX18062904 type: 900 firmware version: (1, 1, 12)
    Welcome to the txTenna API sample! Press ? for a command list.

    txTenna>

Press ? to get a list of commands. To test sending transactions over the mesh radio, use:
  * mesh_broadcast_rawtx
  * mesh_sendtoaddress

Use an Android phone running the [Samourai Wallet App](SamouraiWallet.com) and the [TxTenna App](txtenna.com) to broadcast a  signed Bitcoin transaction. If you have python.py running you will see the following messages:

