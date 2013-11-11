#!/usr/bin/python

'''
HYDRA - Opportunistic Emulator

@author: Johannes Morgenroth <morgenroth@ibr.cs.tu-bs.de>
@author: Sebastian Schildt <schildt@ibr.cs.tu-bs.de>

'''

import multiprocessing as mp
import ConfigParser
from optparse import OptionParser
import uplink

def p_main(config, slaveid):
    try:
        uplink.serve_controlpoint(config, slaveid)
    except KeyboardInterrupt:
        """ shutdown all sessions """
        uplink.clean_sessions()

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
    
    """ default: launch on instance """
    num_instances = 1
    
    """ read number of instances """
    if config.has_option("resources", "instances"):
        num_instances = config.getint("resources", "instances")
    
    instances = []
    
    try:
        if num_instances < 2:
            instances.append(mp.Process(target=p_main, args=(config, None)))
        else:
            for i in range(0, num_instances):
                instances.append(mp.Process(target=p_main, args=(config, i + 1)))

        for i in instances:
            i.start()
        
        for i in instances:
            i.join()
    except KeyboardInterrupt:
        pass

