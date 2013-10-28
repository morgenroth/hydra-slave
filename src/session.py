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
    
    """ if true, the session will fake all commands """
    fake = False

    def __init__(self, config, session_id, hydra_url):
        '''
        Constructor
        '''
        self.config = config
        self.session_id = session_id
        self.hydra_url = hydra_url
        self.setup = Setup(self)
        self.fake = (self.config.get('general', 'fake') == "yes")
        
    def prepare(self):
        self.setup.log("preparing setup")
        if not self.fake:
            self.setup.load()
            self.setup.prepare_base()
        
    def add_node(self, node_id, node_name, ip_address, netmask):
        try:
            self.setup.log("add node " + str(node_id) + " '" + str(node_name) + "'")
            if not self.fake:
                self.setup.add_node(node_id, node_name, (ip_address, netmask))
        except ValueError:
            pass
        
    def remove_node(self, node_id):
        self.setup.log("remove node " + str(node_id))
        if not self.fake:
            self.setup.remove_node(node_id)
        
    def action(self, data):
        try:
            self.setup.log("call action: " + data)
            if not self.fake:
                return self.setup.action(data)
        except ValueError:
            pass
        
    def run(self):
        """ run the nodes """
        self.setup.log("run all the nodes")
        if not self.fake:
            self.setup.startup()
    
    def stop(self):
        """ stop the nodes """
        self.setup.log("stop all the nodes")
        if not self.fake:
            self.setup.shutdown()
    
    def cleanup(self):
        """ cleanup the setup """
        self.setup.log("cleaning up")
        
        """ stop all nodes """
        if not self.fake:
            self.setup.shutdown()
        
        """ delete the setup folder """
        if not self.fake:
            self.setup.cleanup()
    
    
