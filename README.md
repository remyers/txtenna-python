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

Use an Android phone running the [Samourai Wallet App](SamouraiWallet.com) and the [TxTenna App](txtenna.com) to broadcast a  signed Bitcoin transaction. If you have python.py running you will see the following messages:

    Sent to GID: 9579079488: Transaction 05b8038c8622a51245e13c948d4eb8f99b77267f3815e90145b38a5776dc6165 added to the mempool.
    Private message to 9579079488: {"h":"05b8038c8622a51245e13c948d4eb8f99b77267f3815e90145b38a5776dc6165","b":"2"} succeeded!
    Private message to 9579079488: delivery confirmed
    
    Sent to GID: 9579079488: Transaction 05b8038c8622a51245e13c948d4eb8f99b77267f3815e90145b38a5776dc6165 confirmed in 2 blocks.
    Private message to 9579079488: {"h":"05b8038c8622a51245e13c948d4eb8f99b77267f3815e90145b38a5776dc6165","b":"2"} succeeded!
    Private message to 9579079488: delivery confirmed
    
Press ? to get a list of commands. To test sending transactions over the mesh radio, use:
  * mesh_broadcast_rawtx
  * mesh_sendtoaddress
  
To originate an offline transaction from your local bitcoind wallet use mesh_sendtoaddress:

    txTenna>mesh_sendtoaddress 2N5pgmUiWfo1TWxvcNX5winhA4Bvk3K3esH 133700 t
    sendtoaddress_mesh (tx, txid, network): 0100000000010199eac24fffcd09cd4dac0e31515aa63a4cf894d9136370670dcdf60fd1b1932c01000000171600149960e38700a5ea15351d1fb7804c65a76c3810d8feffffff02b95b12000000000017a9146ce02ade2fbc0872bfe524594c87b320ba29b0ef87440a02000000000017a91489f5971e9e02250554f388e27ba5503bb37ce5428702473044022055d8c84a3025ea158c1c59581f478686b0caa713f04f76ba6074ac448c919c8802202d2fc11748416125cfe9f998bfeb3fbd28e9efe81cabb5a9d67d3da75134cb0c01210255eaaf070c085ff81681b5ff50deac761df796a93897952687da2a876b45870a00000000, 05b8038c8622a51245e13c948d4eb8f99b77267f3815e90145b38a5776dc6165 , t
    Broadcast message: {"i":"c1fb91490592667a","h":"05b8038c8622a51245e13c948d4eb8f99b77267f3815e90145b38a5776dc6165","s":4,"t":"0100000000010199eac24fffcd09cd4dac0e31515aa63a4cf894d9136370670dcdf60fd1b1932c01000000171600149960e3","n":"t"} succeeded!
    Broadcast message: {"i":"c1fb91490592667a","c":1,"t":"8700a5ea15351d1fb7804c65a76c3810d8feffffff02b95b12000000000017a9146ce02ade2fbc0872bfe524594c87b320ba29b0ef87440a02000000000017a91489f5971e9e02250554f388e27ba5503bb37ce5428702473044"} succeeded!
    Broadcast message: {"i":"c1fb91490592667a","c":2,"t":"022055d8c84a3025ea158c1c59581f478686b0caa713f04f76ba6074ac448c919c8802202d2fc11748416125cfe9f998bfeb3fbd28e9efe81cabb5a9d67d3da75134cb0c01210255eaaf070c085ff81681b5ff50deac761df796"} succeeded!
    Broadcast message: {"i":"c1fb91490592667a","c":3,"t":"a93897952687da2a876b45870a00000000"} succeeded!
    RPC timeout after calling lockunspent
    txTenna>
    
If there is a mobile phone running txTenna nearby, you will get the following confirmations:

    Transaction d67a9b3a19fc81809f839830569574c8747e835d121d6d50e099a57daac363ee added to the the mem pool
    Transaction d67a9b3a19fc81809f839830569574c8747e835d121d6d50e099a57daac363ee confirmed in block 1478674
    
Note, the mobile txTenna returns the block number and the python version returns the number of confirmations.
