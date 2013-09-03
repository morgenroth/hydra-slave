'''
Created on 19.01.2011

@author: morgenro
'''

import SocketServer
import socket
from session import Session
from setup import Setup

class ControlPointServer(SocketServer.StreamRequestHandler):
    
    session = None

    def handle(self):
        print("master connection opened (" + self.client_address[0] + ":" + str(self.client_address[1]) + ")")
        
        self.wfile.write("### HYDRA SLAVE ###\n")
        self.wfile.write("Identifier: " + socket.gethostname() + "\n")
        
        data = self.rfile.readline().strip()
        
        while data:
            self.process(data)
            data = self.rfile.readline().strip()
            
        print("master connection closed (" + self.client_address[0] + ":" + str(self.client_address[1]) + ")")
            
    def process(self, data):
        if data.startswith("session"):
            (key, skey) = data.split(" ", 1)
            
            if skey in self.server.setups:
                setup = self.server.setups[skey]
            else:
                setup = Setup(skey, self.server.config)
                self.server.setups[skey] = setup
            
            self.session = Session(self.server.config, skey, setup)
            
            self.wfile.write("200 SESSION-KEY-SET " + self.session.session_key + "\n")
            
        elif self.session:
            if data.startswith("prepare"):
                self.session.prepare(data)
                self.wfile.write("200 PREPARED\n")
                
            elif data.startswith("add-node"):
                self.session.add_node(data)
                self.wfile.write("200 ADDED\n")
                
            elif data.startswith("remove-node"):
                self.session.remove_node(data)
                self.wfile.write("200 REMOVED\n")
                
            elif data.startswith("action"):
                ret = self.session.action(data)
                
                if ret != None:
                    self.wfile.write("212 ACTION-RESULT-LISTING\n")
                    self.wfile.write("\n".join(ret))
                    self.wfile.write("\n.\n")
                else:
                    self.wfile.write("200 ACTION-EXECUTED\n")
                
            elif data.startswith("quit"):
                try:
                    self.wfile.write("200 BYE\n")
                except:
                    pass
                
            elif data.startswith("run"):
                self.session.run(data)
                self.wfile.write("200 STARTED\n")
                
            elif data.startswith("stop"):
                self.session.stop(data)
                self.wfile.write("200 STOPPED\n")
                
            elif data.startswith("cleanup"):
                self.session.cleanup(data)
                self.wfile.write("200 CLEAN-UP-DONE\n")
                
            else:
                self.wfile.write("404 COMMAND-NOT-FOUND\n")
                
        else:
            self.wfile.write("300 SESSION-KEY-NOT-SET\n")
                
class ThreadedTCPServer(SocketServer.ThreadingMixIn, SocketServer.TCPServer):
    allow_reuse_address = 1
    daemon_threads = True

def serve_controlpoint(config):
    address = ('', config.getint('general','port'))
    
    server = ThreadedTCPServer(address, ControlPointServer)
    server.setups =  {}
    server.config  = config
    server.serve_forever()
