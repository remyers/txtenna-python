# TxTenna-Python Example Script

The TxTenna Python project is an example script that demonstrates how you can use an offline computer with an attached [goTenna Mesh](http://gotennamesh.com) radio to settle Bitcoin transactions on the Bitcoin network. This script also provides an example of how an offline computer can relay over the TxTenna Mesh network arbitrary data received from the [Blockstream Blocksat](https://blockstream.com/satellite/) and uplinked using the [Blocksat API example](https://github.com/Blockstream/satellite/tree/master/api/examples) scripts.

This project is inspired by the ideas of the [Mule Tools](http://mule.tools) initiative and uses a JSON based messaging protocol derived from the mobile [TxTenna App](https://TxTenna.com) and [TxTenna Server](https://github.com/MuleTools/txTenna-server) projects. The [txtenna.py](./txtenna.py) example script builds on the [sample.py](https://github.com/gotenna/PublicSDK/blob/master/python-public-sdk/sample.py) script created for the goTenna [Public SDK](https://gotenna.com/pages/sdk).

![TxTenna Mesh Relay Architecture](./doc/txtenna_architecture.png?raw=true "TxTenna Mesh Relay Architecture")

## <a name='Environment'></a>Environment

The first step in order to use the examples that follow is to prepare the environment.

For Python, create a virtual environment with the packages listed in the `requirements.txt` file of this directory. For example, if using *virtualenvwrapper*, run the following:

```
mkvirtualenv --python=`which python2` -r requirements.txt txtenna
```

Note this virtual environment will be required for all example scripts described in this page. Hence, once you open a new terminal session in order to launch txtenna.py, ensure you activate the environment again. For example, assuming you are using `virtualenvwrapper`, run the following on every new terminal session:

 ```
 workon txtenna
 ```

 Use the 'deactivate' command if you want to stop using the environment.

> NOTE: for a quick introduction to *virtualenvwrapper* visit their
> [introduction
> page](https://virtualenvwrapper.readthedocs.io/en/latest/index.html#introduction).
> Also, after installing *virtualenvwrapper*, make sure to follow the shell
> startup instructions on [their
> documentation](https://virtualenvwrapper.readthedocs.io/en/latest/install.html#shell-startup-file).

You will also need to do the following:

* request a free SDK Token, from goTenna [here](https://www.gotenna.com/pages/sdk).
* plug a [goTenna Mesh](https://gotennamesh.com) device into the USB port of your computer (RPi, PC, Mac, Linux, etc)
* From the settings menu of the [TxTenna App](https://txtenna.com) on your phone, set the 'goTenna Token' to match the one you use with the txtenna.py examples below.

> IMPORTANT: Make sure your goTennas are upgraded to firmware 1.1.12 or higher following the [instructions from the goTenna Python SDK](https://github.com/gotenna/PublicSDK/blob/master/python-public-sdk/Mesh%20Firmware%20Upgrade%20to%201.1.12.pdf).

> NOTE: if you will be accessing a local [bitcoind](https://bitcoincore.org/en/download/) daemon, we use the [getrawtransaction](https://bitcoin.org/en/developer-reference#getrawtransaction) RPC call which expects a local **indexed** installation of bitcoind.

> TIP: You may need to install the [77-gotenna.rules](https://github.com/gotenna/PublicSDK/blob/master/python-public-sdk/77-gotenna.rules) file for linux systems that use the udev device manager.

> TIP: if you change your SDK Token, delete the .goTenna file created by txtenna.py .

# How does it work
  
    $ python txtenna.py -h
    usage: Run a txTenna transaction gateway [-h] [--gateway] [--local]
                                         [--send_dir SEND_DIR]
                                         [--receive_dir RECEIVE_DIR] [-p PIPE]
                                         SDK_TOKEN GEO_REGION

        positional arguments:
        SDK_TOKEN             The token for the goTenna SDK
        GEO_REGION            The geo region number you are in

        optional arguments:
        -h, --help            show this help message and exit
        --gateway             Use this computer as an internet connected transaction
                                gateway with a default GID
        --local               Use local bitcoind to confirm and broadcast
                                transactions
        --send_dir SEND_DIR   Broadcast message data from files in this directory
        --receive_dir RECEIVE_DIR
                                Write files from received message data in this
                                directory
        -p PIPE, --pipe PIPE  Pipe on which relayed message data is written out to
                                (default: /tmp/blocksat/api)
    
## Example 1: Bitcoin Transactions Gateway (using a remote txtenna-server)

Run txtenna-python with your SDK token and geographic region (eg. 1 = North America, 2 = Europe). Transactions will be confirmed via the default txtenna-server instance operated by Samourai Wallet at [api.samourai.io](https://api.samourai.io).
    
    $ python txtenna.py --gateway <Your SDK Token String> 2
    region=2
    Device physically connected, configure to continue
    gid= 241887036765613
    Connected!
    connect: port: /dev/cu.usbmodemMX180629041 serial: MX18062904 type: 900 firmware version: (1, 1, 12)
    Welcome to the txTenna API sample! Press ? for a command list.

    txTenna>

Use an Android phone running the [Samourai Wallet App](SamouraiWallet.com) and the [TxTenna App](txtenna.com) to broadcast a signed Bitcoin transaction using a second goTenna Mesh radio paired via bluetooth. From your instance of python.py you will see something like the following messages:

    Sent to GID: 9579079488: Transaction 05b8038c8622a51245e13c948d4eb8f99b77267f3815e90145b38a5776dc6165 added to the mempool.
    Private message to 9579079488: {"h":"05b8038c8622a51245e13c948d4eb8f99b77267f3815e90145b38a5776dc6165","b":"2"} succeeded!
    Private message to 9579079488: delivery confirmed
    
    Sent to GID: 9579079488: Transaction 05b8038c8622a51245e13c948d4eb8f99b77267f3815e90145b38a5776dc6165 confirmed in 2 blocks.
    Private message to 9579079488: {"h":"05b8038c8622a51245e13c948d4eb8f99b77267f3815e90145b38a5776dc6165","b":"2"} succeeded!
    Private message to 9579079488: delivery confirmed
    
## Example 2: Send A Bitcoin Transactions (using an offline computer with a local testnet bitcoind daemon running)
    
    $ python txtenna.py --gateway <Your SDK Token String> 2
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
  
To originate an offline testnet transaction from your local bitcoind wallet use mesh_sendtoaddress:

    txTenna>mesh_sendtoaddress 2N5pgmUiWfo1TWxvcNX5winhA4Bvk3K3esH 133700 t
    sendtoaddress_mesh (tx, txid, network): 0100000000010199eac24fffcd09cd4dac0e31515aa63a4cf894d9136370670dcdf60fd1b1932c01000000171600149960e38700a5ea15351d1fb7804c65a76c3810d8feffffff02b95b12000000000017a9146ce02ade2fbc0872bfe524594c87b320ba29b0ef87440a02000000000017a91489f5971e9e02250554f388e27ba5503bb37ce5428702473044022055d8c84a3025ea158c1c59581f478686b0caa713f04f76ba6074ac448c919c8802202d2fc11748416125cfe9f998bfeb3fbd28e9efe81cabb5a9d67d3da75134cb0c01210255eaaf070c085ff81681b5ff50deac761df796a93897952687da2a876b45870a00000000, 05b8038c8622a51245e13c948d4eb8f99b77267f3815e90145b38a5776dc6165 , t
    Broadcast message: {"i":"c1fb91490592667a","h":"05b8038c8622a51245e13c948d4eb8f99b77267f3815e90145b38a5776dc6165","s":4,"t":"0100000000010199eac24fffcd09cd4dac0e31515aa63a4cf894d9136370670dcdf60fd1b1932c01000000171600149960e3","n":"t"} succeeded!
    Broadcast message: {"i":"c1fb91490592667a","c":1,"t":"8700a5ea15351d1fb7804c65a76c3810d8feffffff02b95b12000000000017a9146ce02ade2fbc0872bfe524594c87b320ba29b0ef87440a02000000000017a91489f5971e9e02250554f388e27ba5503bb37ce5428702473044"} succeeded!
    Broadcast message: {"i":"c1fb91490592667a","c":2,"t":"022055d8c84a3025ea158c1c59581f478686b0caa713f04f76ba6074ac448c919c8802202d2fc11748416125cfe9f998bfeb3fbd28e9efe81cabb5a9d67d3da75134cb0c01210255eaaf070c085ff81681b5ff50deac761df796"} succeeded!
    Broadcast message: {"i":"c1fb91490592667a","c":3,"t":"a93897952687da2a876b45870a00000000"} succeeded!
    txTenna>
    
If there is a mobile phone running TxTenna App nearby, or an online instance of txtenna.py, you will see the following confirmations:

    Transaction d67a9b3a19fc81809f839830569574c8747e835d121d6d50e099a57daac363ee added to the the mem pool
    Transaction d67a9b3a19fc81809f839830569574c8747e835d121d6d50e099a57daac363ee confirmed in block 1478674
    
Note, the mobile TxTenna App returns the block number and txtenna.py returns the number of confirmations.

## Example 3: Bitcoin Transactions Gateway (using a local bitcoind)

Run python.py as in Example 1, but include the --local flag to access your local bitcoind via RPC calls.
    
    $ python txtenna.py --gateway --local <Your SDK Token String> 2
    region=2
    Device physically connected, configure to continue
    gid= 241887036765613
    Connected!
    connect: port: /dev/cu.usbmodemMX180629041 serial: MX18062904 type: 900 firmware version: (1, 1, 12)
    Welcome to the txTenna API sample! Press ? for a command list.

    txTenna>

Use an Android phone running the [Samourai Wallet App](SamouraiWallet.com) and the [TxTenna App](txtenna.com) to broadcast a signed Bitcoin transaction using a second goTenna Mesh radio paired via bluetooth. From your instance of python.py you will see something like the following messages:

    Sent to GID: 9579079488: Transaction 05b8038c8622a51245e13c948d4eb8f99b77267f3815e90145b38a5776dc6165 added to the mempool.
    Private message to 9579079488: {"h":"05b8038c8622a51245e13c948d4eb8f99b77267f3815e90145b38a5776dc6165","b":"2"} succeeded!
    Private message to 9579079488: delivery confirmed
    
    Sent to GID: 9579079488: Transaction 05b8038c8622a51245e13c948d4eb8f99b77267f3815e90145b38a5776dc6165 confirmed in 2 blocks.
    Private message to 9579079488: {"h":"05b8038c8622a51245e13c948d4eb8f99b77267f3815e90145b38a5776dc6165","b":"2"} succeeded!
    Private message to 9579079488: delivery confirmed

## Example 4: Relay Blocksat Data (from an offline Blocksat connected computer)

Testing this feature theoretically involves three systems:

- System A: An internet connected computer that pays to broadcast some data via the Blockstream satellite network using the Blocksat API example script [api_data_sender](https://github.com/Blockstream/satellite/blob/master/api/examples/api_data_sender.py).
- System B: An offline computer that receives data from system A via a Blockstream Satellite Receiver and the Blocksat API example script [api_data_reader](https://github.com/Blockstream/satellite/blob/master/api/examples/api_data_reader.py) and then relays it to system C using a goTenna Mesh radio and txtenna.py .
- System C: An offline computer that receives data from system A using a goTenna Mesh radio, txtenna.py and the Blocksat API example script [api_data_reader](https://github.com/Blockstream/satellite/blob/master/api/examples/api_data_reader.py) instead of using a Blockstream Satellite Receiver.

Although these systems will normally be different computers, you can also run this test from a single internet connected machine without a satellite receiver to observe how it works. Follow the steps for the Blocksat API [Example 3](https://github.com/Blockstream/satellite/tree/master/api/examples#example-3-testing-the-api-while-receiving-data-directly-via-internet) to simulate sending and receiving data, and pay with a testnet lightning payment. 

If using a single computer and a simulated Blocksat, each of the systems should be a different console window and you will need to connect both goTenna Mesh radios to the same computer via USB ports.

### System A (online data sender)

Follow the instructions to setup the Blockstream Blocksat API environment and run [Example 3](https://github.com/Blockstream/satellite/tree/master/api/examples#example-3-testing-the-api-while-receiving-data-directly-via-internet). You should first run 'demo-rx.py' with the --net test flag in one window to simulate a satellite receiver. 

    (blocksat-api) $ ./demo-rx.py --net test
    Connecting with Satellite API server...
    Connected. Waiting for events...

then in a new window run 'api_data_sender.py' with the --net test flag to use the Blocksat API testnet interface.

    (blocksat-api) macbook-pro-5:examples richard$ ./api_data_sender.py --net test -f manifesto.txt
    File has 5156 bytes
    Packed in data structure with a total of 5416 bytes
    Encrypted version of the data structure has 3364 bytes
    Satellite transmission will use 3396 bytes
    Your bid to transmit 3396 bytes (in millisatoshis): [169800] 
    Post data with bid of 169800 millisatoshis (50.00 msat/byte)
    Data successfully transmitted
    --
    Authentication Token:
    d9a5db1c283d8f01a84a006102bde0562d098302656e478029f9776ea705427b
    --
    UUID:
    0b0d7e54-b8d1-40d1-b3b2-1e678f3674e4
    --
    Lightning Invoice Number:
    lntb1698n1pwt08nepp5ypq9cacz4p6pr2jhxl6vkeqqvqzc4yfjga0xe9vk4puuc3vf9j5sdphgfkx7cmtwd68yetpd5s9xct5v4kxc6t5v5s9gunpdeek66tnwd5k7mscqp2rzjqt24x3myn9ytymg8gu0sqefdxllyxd3jgystzexte5x38y9srrequ93u7cqqqtcqqqqqqq02qqqqqzsqqcqrr5uqzdfh04jqqn3aj8w2g2ysz75sudrfeg2keywtpj38v3pgspfa0w6fzed8k04xmns4e447m27rrtlh2arcgcnd729tcknl6y57qqp64ku0
    --
    Amount Due:
    169800 millisatoshis

Before you pay the lightning invoice with a testnet lightning wallet, setup and run the scripts on Systems B and C.

### System B (mesh and satellite connected data receiver/relay)

Follow the instructions to setup the Blockstream Blocksat API environment and run [Examples 3](https://github.com/Blockstream/satellite/tree/master/api/examples#example-3-testing-the-api-while-receiving-data-directly-via-internet). Run 'api_data_reader.py' with the --plaintext flag to read Blocksat API data written to the /tmp/blocksat/api named pipe. The --plaintext flag ensures that all data received will be written to the 'downloads' directory (eg. ./downloads), including encrypted data meant for someone else.

    (blocksat-api) $ ./api_data_reader.py --plaintext
    Waiting for data...

    [2019-04-16 13:41:41]: Got    6098 bytes        Saving as plaintext
    Saved in downloads/20190416134141.

In a different window, follow the instructions to setup the TxTenna-Python environment (described above) and run 'txtenna.py' with the '--send_dir' argument set to the directory where 'api_data_reader.py' will save file data (eg. ../blockstream/satellite/api/examples/downloads/). 

    (txtenna) $ python txtenna.py --send_dir ../blockstream/satellite/api/examples/downloads <Your SDK Token String> 2
    region=2
    Device physically connected, configure to continue
    set gid= 199376656922447
    Connected!
    connect: port: /dev/cu.usbmodemMX180310881 serial: MX18031088 type: 900 firmware version: (1, 1, 12)
    Welcome to the txTenna API sample! Press ? for a command list.

    txTenna>Broadcasting  downloads/20190416134141
    payload valid = False, message size = 165

    Broadcast message: {"i":"998fad2527a7c0e6","h":"20190412000540","s":35,"t":"-----BEGIN PGP MESSAGE-----\n\nhIwDCIiWOv+ihhsBA/99pLqksVsMFCub9r/K8XbnCJp0TtLiISrwg4jWDa6Qyt2s\ns","n":"d"}

    succeeded!

If data exists in the specified send_dir directory, that data will be broadcast over the goTenna Mesh radio. All other goTenna Mesh radios within range will receive the data. 

### System C (mesh connected data receiver)

Follow the instructions to setup the Blockstream Blocksat API environment and run [Examples 3](https://github.com/Blockstream/satellite/tree/master/api/examples#example-3-testing-the-api-while-receiving-data-directly-via-internet). Run 'api_data_reader.py' with the --pipe /tmp/blocksat/api2 flag to read Blocksat API data written to the /tmp/blocksat/api2 named pipe. Also use the --plaintext flag to ensure that all data received will be saved. Data will be written to the 'downloads' directory so you should run ./api_data_reader.py from a different directory to avoid writing data to the same downloads directory being read from by the System B txtenna.py script. Changing to a new directory is only and specifying a second pipe are only required if you are testing on a single system.

    (blocksat-api) $ mkdir system_c
    (blocksat-api) $ cd system_c
    (blocksat-api) $ ../api_data_reader.py --plaintext --pipe /tmp/blocksat/api2
    Waiting for data...

    [2019-04-18 00:22:13]: Got    6098 bytes        Saving as plaintext
    Saved in downloads/20190418002213.

In a new window, follow the instructions to setup the TxTenna-Python environment (described above) and run 'txtenna.py' with the --pipe /tmp/blocksat/api2 argument. This copy of txtenna.py will wait for incoming message data and write it out to the 2nd named pipe created above.

    (txtenna) $ python txtenna.py --pipe /tmp/blocksat/api2 <Your SDK Token String> 2
    region=2
    Device physically connected, configure to continue
    set gid= 199376656922447
    Connected!
    connect: port: /dev/cu.usbmodemMX180310881 serial: MX18031088 type: 900 firmware version: (1, 1, 12)
    Welcome to the txTenna API sample! Press ? for a command list.

    txTenna>
    received transaction payload: {"i":"16d322e7db2acd52","h":"20190412000540","s":35,"t":"-----BEGIN PGP MESSAGE-----\n\nhIwDCIiWOv+ihhsBA/99pLqksVsMFCub9r/K8XbnCJp0TtLiISrwg4jWDa6Qyt2s\ns","n":"d"}
    received transaction payload: {"i":"16d322e7db2acd52","c":1,"t":"lb/WLHYozht+I8hmYGcLuOG41qrZclOLDKcdo+vaxD8qmYw6HAnwaJJ67BT0xXE\nd97TGPR3PhaSegAf/CdKWO/X9BIc2vBfpdDrqFuzlSNPX6s/4//r6jyNVFajX9Ls\nAXSHj07/kMneqzaawFYwvKfLJx1q8m4Q0ttFcISFlrAdIO5ES"}
    received transaction payload: {"i":"16d322e7db2acd52","c":2,"t":"U8QBsjfZqwOdn9y\nJxcfyR0y/qmpTnsHKCU4lmuHawJyVWZ/VLI/jXF/Eq899YLOh0CRMp3e/NbUJlnU\n1BudDLDhJnrL5RvRAYKyhts3gRJQjwEyMpnJ85gyMUoHLvBFjSkoQL+CnaL46WxN\nnoqXBYi5qkCQxF1F+Wp5TAz88HF52+P"}

### Conclusion

At the end of this test, the data sent by System A should appear in the download directories of Systems B and C. There can be any number of mesh connected System C machines receiving the data and System A can specifically encrypt data for any one of them. This example shows how a single offline system with a Blocksat can distribute API data to many more offline nodes operating on a local goTenna Mesh network.
