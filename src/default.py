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

if __name__ == '__main__':
    print("- hydra slave node 0.2 -")
    
    usage = "usage: %prog [options]"
    parser = OptionParser(usage=usage)
    
    ''' parse arguments '''
    (options, args) = parser.parse_args()

    ds = DiscoveryService("225.16.16.1", 3234)
    ds.start()

    vc = libvirt.open("qemu:///system")
    server.serve_controlpoint(("", 4242), vc)
