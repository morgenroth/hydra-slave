'''
Created on 19.01.2011

@author: morgenro
'''

import SocketServer
import socket
from session import Session
import setup
import ConfigParser
import time

""" global config object """
config = None

""" global setup pool """
setups = {}

class UplinkHandler:
    
    setup = None
    session = None
    wfile = None
    rfile = None
    
    def write(self, data):
        self.wfile.write(data)
        self.wfile.flush()
        
    def readline(self):
        return self.rfile.readline()
    
    def handle(self, peer_address):
        print("master connection opened (" + peer_address[0] + ":" + str(peer_address[1]) + ")")
        
        self.write("### HYDRA SLAVE ###\n")
        self.write("Identifier: " + socket.gethostname() + "\n")
        
        data = self.readline().strip()
        
        while data:
            self.process(data)
            data = self.readline().strip()
            
        print("master connection closed (" + peer_address[0] + ":" + str(peer_address[1]) + ")")
            
    def process(self, data):
        global setups
        
        if data.startswith("session"):
            (key, skey) = data.split(" ", 1)
            
            if skey in setups:
                self.setup = setups[skey]
            else:
                self.setup = setup.Setup(skey, config)
                setups[skey] = self.setup
            
            self.session = Session(config, skey, self.setup)
            
            self.write("200 SESSION-KEY-SET " + self.session.session_key + "\n")
            
        elif self.session:
            if data.startswith("prepare"):
                self.session.prepare(data)
                self.write("200 PREPARED\n")
                
            elif data.startswith("add-node"):
                self.session.add_node(data)
                self.write("200 ADDED\n")
                
            elif data.startswith("remove-node"):
                self.session.remove_node(data)
                self.write("200 REMOVED\n")
                
            elif data.startswith("action"):
                ret = self.session.action(data)
                
                if ret != None:
                    self.write("212 ACTION-RESULT-LISTING\n")
                    self.write("\n".join(ret))
                    self.write("\n.\n")
                else:
                    self.write("200 ACTION-EXECUTED\n")
                
            elif data.startswith("quit"):
                try:
                    self.write("200 BYE\n")
                except:
                    pass
                
            elif data.startswith("run"):
                self.session.run(data)
                self.write("200 STARTED\n")
                
            elif data.startswith("stop"):
                self.session.stop(data)
                self.write("200 STOPPED\n")
                
            elif data.startswith("cleanup"):
                self.session.cleanup(data)
                self.write("200 CLEAN-UP-DONE\n")
                
            else:
                self.write("404 COMMAND-NOT-FOUND\n")
                
        else:
            self.write("300 SESSION-KEY-NOT-SET\n")


class UplinkConnection:
    
    s = None
    running = True
    
    def run(self):
        """ get configuration credentials """
        address = (config.get('master','host'), config.getint('master','port'))
        
        """ create a new uplink handler """
        uplink = UplinkHandler();
        
        while self.running:
            try:
                """ create a new socket """
                self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                
                """ connect to the master server """
                self.s.connect(address)
                
                """ create file handles for the socket """ 
                uplink.rfile = self.s.makefile('rb')
                uplink.wfile = self.s.makefile('wb')
                
                """ handle connection data """
                uplink.handle(address)
            except socket.error, e:
                print("Error: " + str(e))
            
            """ idle for some seconds """
            time.sleep(2)
        
    def close(self):
        self.running = False
        self.s.close()

class ControlPointServer(SocketServer.StreamRequestHandler):
    
    def handle(self):
        uplink = UplinkHandler();
        uplink.rfile = self.rfile
        uplink.wfile = self.wfile
        uplink.handle(self.client_address)


class ThreadedTCPServer(SocketServer.ThreadingMixIn, SocketServer.TCPServer):
    allow_reuse_address = 1
    daemon_threads = True

def serve_controlpoint(c):
    global config
    
    """ assign global config object """
    config = c

    """ try to create a server socket if general:port is defined """
    try:
        """ define address to listen to """
        address = ('', config.getint('general','port'))
        
        """ create threaded tcp server """
        server = ThreadedTCPServer(address, ControlPointServer)
        
        """ start tcp server loop """
        server.serve_forever()
        
        return
    except ConfigParser.NoSectionError:
        pass
    except ConfigParser.NoOptionError:
        pass

    """ initiate a client connection to the master """
    conn = UplinkConnection()
    conn.run()

    print("exit")