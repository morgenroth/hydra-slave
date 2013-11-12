'''
Created on 30.08.2013

@author: morgenro
'''

from setup import Setup
import logging

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
    
    """ name of the instance this session is running """
    instance_name = None

    def __init__(self, instance_name, config, session_id, hydra_url):
        '''
        Constructor
        '''
        self.instance_name = instance_name
        self.config = config
        self.session_id = session_id
        self.hydra_url = hydra_url
        self.setup = Setup(self)

        if self.config.has_option('general', 'fake'):
            self.fake = (self.config.get('general', 'fake') == "yes")
        
    def prepare(self):
        logging.info(self.setup.log_format(("preparing setup")))
        if not self.fake:
            self.setup.load()
            self.setup.prepare_base()
        
    def add_node(self, node_id, node_name, ip_address, netmask):
        try:
            logging.info(self.setup.log_format(("add node " + str(node_id) + " '" + str(node_name) + "'")))
            if not self.fake:
                self.setup.add_node(node_id, node_name, (ip_address, netmask))
        except ValueError:
            pass
        
    def remove_node(self, node_id):
        logging.info(self.setup.log_format(("remove node " + str(node_id))))
        if not self.fake:
            self.setup.remove_node(node_id)
        
    def action(self, data):
        try:
            logging.info(self.setup.log_format(("call action: " + data)))
            if not self.fake:
                return self.setup.action(data)
        except ValueError:
            pass
        
    def run(self):
        """ run the nodes """
        logging.info(self.setup.log_format(("run all the nodes")))
        if not self.fake:
            self.setup.startup()
    
    def stop(self):
        """ stop the nodes """
        logging.info(self.setup.log_format(("stop all the nodes")))
        if not self.fake:
            self.setup.shutdown()
    
    def cleanup(self):
        """ cleanup the setup """
        logging.info(self.setup.log_format(("cleaning up")))
        
        """ stop all nodes """
        if not self.fake:
            self.setup.shutdown()
        
        """ delete the setup folder """
        if not self.fake:
            self.setup.cleanup()
    
    
