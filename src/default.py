#!/usr/bin/python

'''
HYDRA - Opportunistic Emulator

@author: Johannes Morgenroth <morgenroth@ibr.cs.tu-bs.de>
@author: Sebastian Schildt <schildt@ibr.cs.tu-bs.de>

'''

import ConfigParser
from optparse import OptionParser
import uplink
import signal
import time

""" slave instances """
instances = []

""" slave server """
server = None

""" flag for main loop """
running = True

def signal_handler(signum = None, frame = None):
    global running
    running = False

""" register SIGTERM handler """
signal.signal(signal.SIGTERM, signal_handler)

""" register SIGINT handler """
signal.signal(signal.SIGINT, signal_handler)

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
    
    """ create a listening tcp server if the port is defined """
    if config.has_option("general", "port"):
        server = uplink.UplinkServer(config)
        server.start()
    
    if config.has_option("master", "host") and config.has_option("master", "port"):
        """ default: launch one client instance """
        num_instances = 1
        
        """ read number of instances """
        if config.has_option("resources", "instances"):
            num_instances = config.getint("resources", "instances")
        
        """ create several client instances """
        for i in range(0, num_instances):
            instances.append(uplink.UplinkInstance(config, i))

        """ start all instances """
        for i in instances:
            i.start()
            
    """ wait until the running flags was set to False """
    try:
        while running:
            time.sleep(1)
    except:
        pass
    
    if server != None:
        print 'shutdown server'
        server.shutdown()

    print 'shutdown all slave instances'
    for i in instances:
        i.shutdown()
    
    """ wait until all instances closed """
    for i in instances:
        i.join()
    
    """ join the server """
    if server != None:
        server.join()
