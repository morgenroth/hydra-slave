'''
Created on 30.08.2013

@author: morgenro
'''

class Node(object):
    '''
    classdocs
    '''
    session_id = ""

    def __init__(self, session_id):
        '''
        Constructor
        '''
        self.session_id = session_id
    

class NodeList(object):
    '''
    classdocs
    '''
    nodes = []

    def __init__(self):
        '''
        Constructor
        '''
        
    def create(self, session_id):
        n = Node(session_id)
        self.nodes.append(n)
        return n

    def get(self, session_id):
        return self.nodes
