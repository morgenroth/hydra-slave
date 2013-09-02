'''
Created on 30.08.2013

@author: morgenro
'''

class Session(object):
    '''
    classdocs
    '''
    session_key = None
    setup = None

    def __init__(self, config, session_key, setup):
        '''
        Constructor
        '''
        self.config = config
        self.session_key = session_key
        self.setup = setup
        
    def prepare(self, data):
        print("[" + self.session_key + "] preparing setup")
        self.setup.load()
        self.setup.prepare_base()
        
    def add_node(self, data):
        (action, data) = data.split(" ", 1)
        print("[" + self.session_key + "] add node '" + data + "'")
        self.setup.add_node(data)
        
    def remove_node(self, data):
        (action, data) = data.split(" ", 1)
        print("[" + self.session_key + "] remove node '" + data + "'")
        self.setup.remove_node(data)
        
    def action(self, data):
        try:
            (action, data) = data.split("\n", 1)
            print("call action: " + action)
            ret = self.setup.action(action)
            if ret != None:
                self.request.send(ret + "\n")
        except ValueError:
            pass
        
    def run(self, data):
        """ run the nodes """
        print("[" + self.session_key + "] run all the nodes")
        self.setup.startup()
    
    def stop(self, data):
        """ stop the nodes """
        print("[" + self.session_key + "] stop all the nodes")
        self.setup.shutdown()
    
    def cleanup(self, data):
        """ cleanup the setup """
        print("[" + self.session_key + "] cleaning up")
        
        """ stop all nodes """
        self.setup.shutdown()
        
        """ delete the setup folder """
        self.setup.cleanup()
    
    