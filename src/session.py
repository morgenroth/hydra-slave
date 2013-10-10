'''
Created on 30.08.2013

@author: morgenro
'''

from setup import Setup

class Session(object):
    """ global ID of this session """
    session_id = None
    
    """ URL where the data is retrieved from """
    hydra_url = None
    
    """ setup object to handle all virtual nodes """
    setup = None
    
    """ configuration object """
    config = None

    def __init__(self, config, session_id, hydra_url):
        '''
        Constructor
        '''
        self.config = config
        self.session_id = session_id
        self.hydra_url = hydra_url
        self.setup = Setup(self)
        
    def prepare(self):
        self.setup.log("preparing setup")
        self.setup.load()
        self.setup.prepare_base()
        
    def add_node(self, node_id, node_name, ip_address, netmask):
        try:
            self.setup.log("add node " + str(node_id) + " '" + str(node_name) + "'")
            self.setup.add_node(node_id, node_name, (ip_address, netmask))
        except ValueError:
            pass
        
    def remove_node(self, node_id):
        self.setup.log("remove node " + str(node_id))
        self.setup.remove_node(node_id)
        
    def action(self, data):
        try:
            self.setup.log("call action: " + data)
            return self.setup.action(data)
        except ValueError:
            pass
        
    def run(self):
        """ run the nodes """
        self.setup.log("run all the nodes")
        self.setup.startup()
    
    def stop(self):
        """ stop the nodes """
        self.setup.log("stop all the nodes")
        self.setup.shutdown()
    
    def cleanup(self):
        """ cleanup the setup """
        self.setup.log("cleaning up")
        
        """ stop all nodes """
        self.setup.shutdown()
        
        """ delete the setup folder """
        self.setup.cleanup()
    
    