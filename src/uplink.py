'''
Created on 19.01.2011

@author: Johannes Morgenroth <morgenroth@ibr.cs.tu-bs.de>

### protocol commands ###

# create a session
session create <session-id> <hydra-url>

# destroy a session (clean-up)
session destroy <session-id>

# prepare session
session prepare <session-id>

# start-up all nodes of a session
session run <session-id>

# stop all nodes of a session
session stop <session-id>

# create a node for a session
# e.g. <ip-address> = 1.2.3.4/255.255.0.0
node create <session-id> <node-id> <ip-address> <node-name>

# destroy a node of a session
node destroy <session-id> <node-id>

# action ...
action <session-id> <node-id> <action-to-execute>

# close connection
quit

'''

import SocketServer
import socket
from session import Session
from setup import TimeoutError
import ConfigParser
import time
import threading

""" global config object """
_config = None

""" global session pool """
_sessions = {}

class SessionNotFoundError(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)

class UplinkHandler:
    """ file to send data to the master """
    wfile = None
    
    """ file to receive data from the master """
    rfile = None
    
    """ write data to the master """
    def writeline(self, data):
        self.wfile.write(data + "\n")
        self.wfile.flush()
    
    """ read one line from the master """
    def readline(self):
        if self.rfile:
            return self.rfile.readline()
        else:
            return None
    
    """ this method handles the chat between the master and the slave """
    def handle(self, peer_address, suffix):
        print("master connection opened (" + peer_address[0] + ":" + str(peer_address[1]) + ")")
        
        """ handshake parameters """
        slavename = socket.gethostname()
        owner = None
        capacity = None
        
        """ get the slave name """
        if _config.has_option("general", "name"):
            slavename = _config.get("general", "name")
        
        """ get owner if set """
        if _config.has_option("general", "owner"):
            owner = _config.get("general", "owner")
        
        """ get capacity if set """
        if _config.has_option("resources", "max_nodes"):
            capacity = _config.getint("resources", "max_nodes")
            
        """ add slavename suffix """
        if suffix != None:
            slavename += "-" + str(suffix)
        
        self.writeline("### HYDRA SLAVE ###")
        self.writeline("Identifier: " + slavename)
        
        if owner != None:
            self.writeline("Owner: " + owner);
            
        if capacity != None:
            self.writeline("Capacity: " + str(capacity));
            
        """ mark the end of parameters """
        self.writeline(".");
        
        """ read the first message from the master """
        data = self.readline()
        
        """ read until no more data is received """
        while data:
            """ remove spaces and endline tags from the data """
            data = data.strip()
            
            try:
                """ forward the received data to the process method """
                self.process(data)
            except ValueError:
                self.writeline("402 INCOMPLETE-COMMAND")
            
            """ read the next message """
            data = self.readline()
            
        print("master connection closed (" + peer_address[0] + ":" + str(peer_address[1]) + ")")
        
    def createsession(self, session_id, hydra_url):
        """ make config and sessions locally available """
        global _config
        global _sessions
        
        try:
            return self.getsession(session_id)
        except SessionNotFoundError:
            """ create a new session object """
            ret = Session(_config, session_id, hydra_url)
            
            """ store the session locally """
            _sessions[session_id] = ret
            
            return ret
        
    def getsession(self, session_id):
        """ make sessions locally available """
        global _sessions
        
        ret = None
        
        if session_id in _sessions:
            ret = _sessions[session_id]
        else:
            raise SessionNotFoundError("Session ID " + str(session_id) + " is not created yet")
        
        return ret
    
    def removesession(self, session_id):
        """ make config and sessions locally available """
        global _config
        global _sessions
        
        if session_id in _sessions:
            del _sessions[session_id]
            
    def process(self, data):
        """ allowed command starts with: session, node, action or quit """
        if data.startswith("session create"):
            """ session create <session-id> <hydra-url> """
            (keyword1, keyword2, session_id, hydra_url) = data.split(" ", 3)
            
            """ create or get session """
            s = self.createsession(session_id, hydra_url)
            
            """ report success """
            self.writeline("200 SESSION-CREATED " + str(session_id))
            
        elif data.startswith("session destroy"):
            """ session destroy <session-id> """
            (keyword1, keyword2, session_id) = data.split(" ", 2)
            
            try:
                """ get the requested session """
                s = self.getsession(session_id)
                
                """ execute clean-up command """
                s.cleanup()
                
                """ remove session """
                self.removesession(session_id)
                
                """ report success """
                self.writeline("200 SESSION-REMOVED " + str(session_id))
            except SessionNotFoundError:
                """ report failure """
                self.writeline("401 SESSION-NOT-EXISTS " + str(session_id))
                
        elif data.startswith("session prepare"):
            """ session prepare <session-id> """
            (keyword1, keyword2, session_id) = data.split(" ", 2)
            
            try:
                """ get the requested session """
                s = self.getsession(session_id)
                
                """ execute prepare command """
                s.prepare()
                
                """ report success """
                self.writeline("200 SESSION-PREPARED " + str(session_id))
            except SessionNotFoundError:
                """ report failure """
                self.writeline("401 SESSION-NOT-EXISTS " + str(session_id))
                
        elif data.startswith("session run"):
            """ session run <session-id> """
            (keyword1, keyword2, session_id) = data.split(" ", 2)
            
            try:
                """ get the requested session """
                s = self.getsession(session_id)
                
                """ execute run command """
                s.run()
                
                """ report success """
                self.writeline("200 RUN-SUCCESSFUL " + str(session_id))
            except SessionNotFoundError:
                """ report failure """
                self.writeline("401 SESSION-NOT-EXISTS " + str(session_id))
            except TimeoutError:
                """ report failure """
                self.writeline("300 RUN-TIMED-OUT " + str(session_id))
            
        elif data.startswith("session stop"):
            """ session stop <session-id> """
            (keyword1, keyword2, session_id) = data.split(" ", 2)
            
            try:
                """ get the requested session """
                s = self.getsession(session_id)
                
                """ execute stop command """
                s.stop()
                
                """ report success """
                self.writeline("200 SESSION-STOPPED " + str(session_id))
            except SessionNotFoundError:
                """ report failure """
                self.writeline("401 SESSION-NOT-EXISTS " + str(session_id))
                
        elif data.startswith("node create"):
            """ node create <session-id> <node-id> <ip-address> <node-name> """
            (keyword1, keyword2, session_id, node_id, address, node_name) = data.split(" ", 5)
            
            try:
                """ get the requested session """
                s = self.getsession(session_id)
                
                """ split ip-address and netmask """
                (ip_address, netmask) = address.split("/", 1)
                
                """ execute add command """
                s.add_node(node_id, node_name, ip_address, netmask)
                
                """ report success """
                self.writeline("200 NODE-CREATED " + str(session_id) + "/" + str(node_id))
            except SessionNotFoundError:
                """ report failure """
                self.writeline("401 SESSION-NOT-EXISTS " + str(session_id))
                
        elif data.startswith("node destroy"):
            """ node destroy <session-id> <node-id> """
            (keyword1, keyword2, session_id, node_id) = data.split(" ", 3)
            
            try:
                """ get the requested session """
                s = self.getsession(session_id)
                
                """ execute remove command """
                s.remove_node(node_id)
                
                """ report success """
                self.writeline("200 NODE-DESTROYED " + str(session_id) + "/" + str(node_id))
            except SessionNotFoundError:
                """ report failure """
                self.writeline("401 SESSION-NOT-EXISTS " + str(session_id))
                
        elif data.startswith("action"):
            """ action <session-id> <action-to-execute> """
            (keyword, session_id, action) = data.split(" ", 2)
            
            try:
                """ get the requested session """
                s = self.getsession(session_id)
                
                """ execute action command """
                ret = s.action(action)
                
                """ report success / result """
                if ret != None:
                    self.writeline("212 ACTION-RESULT-LISTING")
                    self.writeline("\n".join(ret))
                    self.writeline(".")
                else:
                    self.writeline("200 ACTION-EXECUTED " + str(session_id))
            except SessionNotFoundError:
                """ report failure """
                self.writeline("401 SESSION-NOT-EXISTS " + str(session_id))
                
        elif data.startswith("quit"):
            """ quit """
            try:
                self.writeline("200 BYE")
                self.wfile.close()
                self.wfile = None
                self.rfile.close()
                self.rfile = None
            except:
                pass
            
        else:
            self.writeline("404 COMMAND-NOT-FOUND")

class UplinkConnection(threading.Thread):
    
    s = None
    running = True
    suffix = None
    cond = threading.Condition()
    
    def __init__(self, suffix):
        threading.Thread.__init__(self)
        self.suffix = suffix
    
    def run(self):
        """ get configuration credentials """
        address = (_config.get('master','host'), _config.getint('master','port'))
        
        """ create a new uplink handler """
        uplink = UplinkHandler();
        
        """ get condition lock """
        self.cond.acquire()
        
        try:
            while self.running:
                try:
                    """ create a new socket """
                    self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    
                    """ connect to the master server """
                    self.s.connect(address)
                    
                    """ create file handles for the socket """
                    uplink.rfile = self.s.makefile('rb')
                    uplink.wfile = self.s.makefile('wb')
                except socket.error, e:
                    print("Error: " + str(e))
                
                """ release condition lock while handling communication """
                self.cond.release()
                
                try:
                    """ handle connection data """
                    uplink.handle(address, self.suffix)
                except socket.error, e:
                    print("Error: " + str(e))
                finally:
                    """ restore condition lock """
                    self.cond.acquire()
                
                try:
                    """ close the socket """
                    self.s.close()
                except socket.error, e:
                    print("Error: " + str(e))
    
                """ idle for some seconds """
                self.cond.wait(2.0)
        finally:
            """ release condition lock """
            self.cond.release()
        
    def close(self):
        try:
            self.cond.acquire()
            self.running = False
            self.s.close()
        finally:
            self.cond.notify()
            self.cond.release()
        

class ControlPointServer(SocketServer.StreamRequestHandler):
    
    def handle(self):
        uplink = UplinkHandler();
        uplink.rfile = self.rfile
        uplink.wfile = self.wfile
        uplink.handle(self.client_address, None)


class ThreadedTCPServer(SocketServer.ThreadingMixIn, SocketServer.TCPServer):
    allow_reuse_address = 1
    daemon_threads = True

def serve_controlpoint(c, suffix):
    global _config
    
    """ assign global config object """
    _config = c
    conn = None
    
    """ get configuration for master connection """
    if _config.has_option("master", "host") and _config.has_option("master", "port"):
        """ initiate a client connection to the master """
        conn = UplinkConnection(suffix)
        conn.start()

    """ create a listening tcp server if the port is defined """
    if _config.has_option("general", "port"):
        """ define address to listen to """
        address = ('', _config.getint('general','port'))
        
        """ create threaded tcp server """
        server = ThreadedTCPServer(address, ControlPointServer)
        
        """ start tcp server loop """
        server.serve_forever()
    
    """ wait until the client thread has finished """
    if conn != None:
        conn.join()
    
def clean_sessions():
    global _sessions
    
    for key, s in _sessions.iteritems():
        print("clean up session " + str(key))
        s.cleanup()

    