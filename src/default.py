#!/usr/bin/python
#
# hydra opportunistic emulator
# (c) 2010 IBR

import sys
import time
from disco import DiscoverySocket, DiscoveryService
from control import NodeControl
from optparse import OptionParser
import server
import libvirt
import sys
from setup import Setup

if __name__ == '__main__':
    print("- hydra slave node 0.2 -")
    
    usage = "usage: %prog [options]"
    parser = OptionParser(usage=usage)
    
    """ add options to the parser """
    parser.add_option("-t", "--tmp-dir", dest="tmpdir", default="./hydra-setup",
        help="define a temporary directory")
    parser.add_option("-i", "--multicast-interface", dest="minterface", default="",
        help="specify the outgoing multicast interface to reach the virtual nodes")
    parser.add_option("-d", "--libvirt-driver", dest="virtdriver", default="qemu:///system",
        help="specify the driver for libvirt (e.g. 'qemu:///system')")
    
    ''' parse arguments '''
    (options, args) = parser.parse_args()

    ds = DiscoveryService(("225.16.16.1", 3234), options.minterface)
    ds.start()

    vc = libvirt.open(options.virtdriver)
    if vc == None:
        print("could not connect to libvirt")
        sys.exit(-1)
        
    ''' create a setup object '''
    s = Setup(vc, options.minterface)
    
    try:
        server.serve_controlpoint(('', 4242), s)
    except KeyboardInterrupt:
        pass
