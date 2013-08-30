#!/usr/bin/python
#
# hydra opportunistic emulator
# (c) 2010 IBR

import sys
import time
import ConfigParser
from disco import DiscoverySocket, DiscoveryService
from control import NodeControl
from optparse import OptionParser
import server
import sys
from node import NodeList

if __name__ == '__main__':
    print("- hydra slave node 0.2 -")
    
    usage = "usage: %prog [options]"
    parser = OptionParser(usage=usage)
    
    """ add options to the parser """
    parser.add_option("-c", "--config-file", dest="configfile", default="slave.properties",
        help="specify the configuration file")
    
    ''' parse arguments '''
    (options, args) = parser.parse_args()
    
    """ read configuration """
    config = ConfigParser.RawConfigParser()
    print("read configuration: " + options.configfile)
    config.read(options.configfile)
    
    """ load discovery address from configuration """
    discovery_address = (config.get('master','discovery_addr'), config.getint('master','discovery_port'))
    
    ds = DiscoveryService(discovery_address, config.get('master','interface'))
    ds.start()
    
    try:
        server.serve_controlpoint(config)
    except KeyboardInterrupt:
        pass
