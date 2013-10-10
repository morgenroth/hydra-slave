#!/usr/bin/python

'''
HYDRA - Opportunistic Emulator

@author: Johannes Morgenroth <morgenroth@ibr.cs.tu-bs.de>
@author: Sebastian Schildt <schildt@ibr.cs.tu-bs.de>

'''

import ConfigParser
from optparse import OptionParser
import uplink

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
    
    try:
        uplink.serve_controlpoint(config)
    except KeyboardInterrupt:
        pass
