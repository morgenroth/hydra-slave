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
import threading
import logging

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
    
    """ parent object holding sessions and the config object """
    parent = None
    
    def __init__(self, parent):
        self.parent = parent
    
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
        
    def close(self):
        """ quit """
        try:
            self.wfile.close()
            self.wfile = None
            self.rfile.close()
            self.rfile = None
        except:
            pass
        
    def log_format(self, message):
        return message
    
    """ this method handles the chat between the master and the slave """
    def handle(self, instance_name, peer_address, owner, capacity):
        logging.info(self.log_format(("master connection opened (" + peer_address[0] + ":" + str(peer_address[1]) + ")")))
        
        self.writeline("### HYDRA SLAVE ###")
        self.writeline("Identifier: " + instance_name)
        
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
            
        logging.info(self.log_format(("master connection closed (" + peer_address[0] + ":" + str(peer_address[1]) + ")")))
        
    def createsession(self, session_id, hydra_url):
        """ make config and sessions locally available """
        try:
            return self.getsession(session_id)
        except SessionNotFoundError:
            """ create a new session object """
            ret = Session(self.parent.instance_name, self.parent.config, session_id, hydra_url)
            
            """ store the session locally """
            self.parent.sessions[session_id] = ret
            
            return ret
        
    def getsession(self, session_id):
        """ make sessions locally available """
        ret = None
        
        if session_id in self.parent.sessions:
            ret = self.parent.sessions[session_id]
        else:
            raise SessionNotFoundError("Session ID " + str(session_id) + " is not created yet")
        
        return ret
    
    def removesession(self, session_id):
        """ make config and sessions locally available """
        if session_id in self.parent.sessions:
            del self.parent.sessions[session_id]
            
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

class UplinkInstance(threading.Thread):
    """ config object """
    config = None
    
    """ session pool """
    sessions = {}
    
    """ name of this instance """
    instance_name = None
    
    """ the owner of this instance """
    owner = None
    
    """ the capacity of this instance """
    capacity = None
    
    """ client socket """
    sock = None
    
    """ client handler """
    uplink = None
    
    """ mark this instance as running or not """
    running = True

    """ condition to synchronize this instance with the main thread """
    cond = threading.Condition()
    
    def __init__(self, c, instanceId):
        threading.Thread.__init__(self)
        self.config = c
        
        """ get the slave name """
        if self.config.has_option("general", "name"):
            self.instance_name = self.config.get("general", "name")
        else:
            self.instance_name = socket.gethostname()
            
        """ add slavename suffix """
        if instanceId != None:
            self.instance_name += "-" + str(instanceId)

        """ get owner if set """
        if self.config.has_option("general", "owner"):
            self.owner = self.config.get("general", "owner")
        
        """ get capacity if set """
        if self.config.has_option("resources", "max_nodes"):
            self.capacity = self.config.getint("resources", "max_nodes")
    
    def run(self):
        """ get configuration credentials """
        address = (self.config.get('master','host'), self.config.getint('master','port'))
        
        """ create a new uplink handler """
        self.uplink = UplinkHandler(self);
        
        """ get condition lock """
        self.cond.acquire()
        
        try:
            while self.running:
                try:
                    """ create a new socket """
                    self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    
                    """ connect to the master server """
                    self.sock.connect(address)
                    
                    """ create file handles for the socket """
                    self.uplink.rfile = self.sock.makefile('rb')
                    self.uplink.wfile = self.sock.makefile('wb')
                    
                    """ release condition lock while handling communication """
                    self.cond.release()
                    
                    try:
                        """ handle connection data """
                        self.uplink.handle(self.instance_name, address, self.owner, self.capacity)
                    except socket.error, e:
                        logging.error(self.log_format((str(e))))
                    finally:
                        """ restore condition lock """
                        self.cond.acquire()
                except socket.error, e:
                    logging.error(self.log_format((str(e))))
                
                try:
                    """ close the socket """
                    self.sock.close()
                except socket.error, e:
                    logging.error(self.log_format((str(e))))
    
                """ idle for some seconds """
                self.cond.wait(2.0)
        finally:
            """ release condition lock """
            self.cond.release()
        
    def close(self):
        try:
            self.cond.acquire()
            self.running = False
            self.uplink.close()
            self.sock.shutdown(socket.SHUT_RDWR)
            self.sock.close()
        finally:
            self.cond.notify()
            self.cond.release()
            
    def cleanup(self):
        for key, s in self.sessions.iteritems():
            logging.info(self.log_format(("clean up session " + str(key))))
            s.cleanup()
        
    def shutdown(self):
        self.close()
        self.cleanup()

class ControlPointServer(SocketServer.StreamRequestHandler):
    
    def handle(self):
        parent = self.__class__.parent
        
        uplink = UplinkHandler(parent);
        uplink.rfile = self.rfile
        uplink.wfile = self.wfile
        uplink.handle(parent.instance_name, self.client_address, parent.owner, parent.capacity)

class ThreadedTCPServer(SocketServer.ThreadingMixIn, SocketServer.TCPServer):
    allow_reuse_address = 1
    daemon_threads = True

class UplinkServer(threading.Thread):
    """ config object """
    config = None
    
    """ session pool """
    sessions = {}
    
    """ server for connections of the master """
    server = None
    
    """ name of this instance """
    instance_name = None
    
    """ the owner of this instance """
    owner = None
    
    """ the capacity of this instance """
    capacity = None
    
    def __init__(self, c):
        threading.Thread.__init__(self)
        self.config = c

        """ get the slave name """
        if self.config.has_option("general", "name"):
            self.instance_name = self.config.get("general", "name")
        else:
            self.instance_name = socket.gethostname()

        """ get owner if set """
        if self.config.has_option("general", "owner"):
            self.owner = self.config.get("general", "owner")
        else:
            self.owner = None
        
        """ get capacity if set """
        if self.config.has_option("resources", "max_nodes"):
            self.capacity = self.config.getint("resources", "max_nodes")
        else:
            self.capacity = None
            
        """ assign ourself as static parent """
        ControlPointServer.parent = self
        
        """ define address to listen to """
        address = ('', self.config.getint('general','port'))
        
        """ create threaded tcp server """
        self.server = ThreadedTCPServer(address, ControlPointServer)
        
    def log_format(self, message):
        return message
        
    def run(self):
        """ start tcp server loop """
        self.server.serve_forever()
        
    def shutdown(self):
        if self.server != None:
            self.server.shutdown()
        
    def cleanup(self):
        for key, s in self.sessions.iteritems():
            logging.info(self.log_format(("clean up session " + str(key))))
            s.cleanup()
