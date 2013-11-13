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
    def __init__(self, c, instance_id):
        """ file to send data to the master """
        self.wfile = None
        
        """ file to receive data from the master """
        self.rfile = None
        
        """ session pool """
        self.sessions = {}
        
        """ configuration object """
        self.config = c
        
        """ name of this instance """
        self.instance_name = None
        
        """ the owner of this instance """
        self.owner = None
        
        """ the capacity of this instance """
        self.capacity = None

        """ get the slave name """
        if self.config.has_option("general", "name"):
            self.instance_name = self.config.get("general", "name")
        else:
            self.instance_name = socket.gethostname()
            
        """ add instance_name suffix """
        if instance_id != None:
            self.instance_name += "-" + str(instance_id)

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
        
    def cleanup(self):
        for key, s in self.sessions.iteritems():
            logging.info(self.log_format(("clean up session " + str(key))))
            s.cleanup()
        
    def log_format(self, message):
        return "[" + self.instance_name + "] " + message
    
    """ this method handles the chat between the master and the slave """
    def handle(self):
        self.writeline("### HYDRA SLAVE ###")
        self.writeline("Identifier: " + self.instance_name)
        
        if self.owner != None:
            self.writeline("Owner: " + self.owner);
            
        if self.capacity != None:
            self.writeline("Capacity: " + str(self.capacity));
            
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
        
    def createsession(self, session_id, hydra_url):
        """ make config and sessions locally available """
        try:
            return self.getsession(session_id)
        except SessionNotFoundError:
            """ create a new session object """
            ret = Session(self, self.config, session_id, hydra_url)
            
            """ store the session locally """
            self.sessions[session_id] = ret
            
            return ret
        
    def getsession(self, session_id):
        """ make sessions locally available """
        ret = None
        
        if session_id in self.sessions:
            ret = self.sessions[session_id]
        else:
            raise SessionNotFoundError("Session ID " + str(session_id) + " is not created yet")
        
        return ret
    
    def removesession(self, session_id):
        """ make config and sessions locally available """
        if session_id in self.sessions:
            del self.sessions[session_id]
            
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
    def __init__(self, c, instance_id):
        threading.Thread.__init__(self)
        
        """ client socket """
        self.sock = None
        
        """ mark this instance as running or not """
        self.running = True
    
        """ condition to synchronize this instance with the main thread """
        self.cond = threading.Condition()

        """ get master address """
        self.address = (c.get('master','host'), c.getint('master','port'))
        
        """ create a new uplink handler """
        self.uplink = UplinkHandler(c, instance_id);
            
        """ debugging """
        logging.info(self.log_format("New uplink instance created"))
    
    def log_format(self, message):
        return self.uplink.log_format(message)
    
    def run(self):
        """ get condition lock """
        self.cond.acquire()
        
        try:
            while self.running:
                try:
                    """ create a new socket """
                    self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    
                    """ connect to the master server """
                    self.sock.connect(self.address)
                    
                    """ create file handles for the socket """
                    self.uplink.rfile = self.sock.makefile('rb')
                    self.uplink.wfile = self.sock.makefile('wb')
                    
                    """ release condition lock while handling communication """
                    self.cond.release()
                    
                    try:
                        """ logging """
                        logging.info(self.log_format(("master connection opened (" + self.address[0] + ":" + str(self.address[1]) + ")")))

                        """ handle connection data """
                        self.uplink.handle()
                    except socket.error, e:
                        logging.error(self.log_format((str(e))))
                    finally:
                        """ logging """
                        logging.info(self.log_format(("master connection closed (" + self.address[0] + ":" + str(self.address[1]) + ")")))
                        
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
        except:
            pass
        finally:
            self.cond.notify()
            self.cond.release()
            
    def shutdown(self):
        self.close()
        self.uplink.cleanup()

class ControlPointServer(SocketServer.StreamRequestHandler):
    """ configuration """
    config = None
    
    def handle(self):
        uplink = UplinkHandler(self.config, None);
        uplink.rfile = self.rfile
        uplink.wfile = self.wfile
        
        """ logging """
        logging.info(uplink.log_format(("master connected (" + self.client_address[0] + ":" + str(self.client_address[1]) + ")")))
        
        """ handle communication """
        uplink.handle()
        
        """ logging """
        logging.info(uplink.log_format(("master disconnected (" + self.client_address[0] + ":" + str(self.client_address[1]) + ")")))

class ThreadedTCPServer(SocketServer.ThreadingMixIn, SocketServer.TCPServer):
    allow_reuse_address = 1
    daemon_threads = True

class UplinkServer(threading.Thread):
    def __init__(self, c):
        threading.Thread.__init__(self)
            
        """ assign configuration as static variable """
        ControlPointServer.config = c
        
        """ define address to listen to """
        address = ('', c.getint('general','port'))
        
        """ create threaded tcp server """
        self.server = ThreadedTCPServer(address, ControlPointServer)
        
    def run(self):
        """ start tcp server loop """
        self.server.serve_forever()
        
    def shutdown(self):
        if self.server != None:
            self.server.shutdown()
