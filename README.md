Hydra Slave
===========

Hydra is a distributed emulation framework for large-scale software testing in disrupted networks. The Hydra Slave is the distributed component on virtualization hosts which
performs the preparation and maintainance of the nodes.

----------


#### Basic setup

In most set-ups all the nodes should be connected to each other. One way to do that is
to create a bridged interface using the bridge tools.

```
sudo brctl addbr sim-br0
sudo ifconfig sim-br0 up
```

Then configure the basic slave.properties according to your needs.


#### Run the slave

To start the slave just call the python interpreter.

```
python src/default.py -c slave.properties
```

