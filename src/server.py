'''
Created on 19.01.2011

@author: morgenro
'''

import SocketServer
import os
import shutil
import urllib
import socket
import time
from disco import DiscoverySocket
import control

""" definition of the static setup object """
_setup = None

class ControlPointServer(SocketServer.BaseRequestHandler):
    """
    The RequestHandler class for our server.

    It is instantiated once per connection to the server, and must
    override the handle() method to implement communication to the
    client.
    """
    
    def setup(self):
        print("master connection opened (" + self.client_address[0] + ":" + str(self.client_address[1]) + ")")
        try:
            _setup.load()
        except:
            pass
    
    def finish(self):
        print("master connection closed (" + self.client_address[0] + ":" + str(self.client_address[1]) + ")")

    def handle(self):
        data = ""
        
        while True:
            while not "\n" in data:
                try:
                    data = data + self.request.recv(1500)
                except:
                    return
            
            """ execute the received command """
            while "\n" in data:
                (line, data) = data.split("\n", 1)
                line = line.strip()
                
                if line == "PREPARE":
                    """ prepare the setup """
                    (url, data) = data.split("\n", 1)
                    print("preparing setup with url " + url)
                    _setup.loadURL(url)
                    _setup.prepare()
                    
                elif line == "ACTION":
                    (action, data) = data.split("\n", 1)
                    print("call action: " + action)
                    ret = _setup.action(action)
                    if ret != None:
                        self.request.send(ret + "\n")
                    continue
                
                elif line == "QUIT":
                    self.request.send("BYE\n")
                    return
                    
                elif line == "RUN":
                    """ run the nodes """
                    print("run all the nodes")
                    _setup.startup()
                    
                elif line == "STOP":
                    """ stop the nodes """
                    print("stop all the nodes")
                    _setup.shutdown()
                    
                elif line == "CLEANUP":
                    """ cleanup the setup """
                    print("cleaning up")
                    
                    """ stop all nodes """
                    _setup.shutdown()
                    
                    """ delete the setup folder """
                    _setup.cleanup()
                
                # report that we are ready
                self.request.send("READY\n")

class ReusableTCPServer(SocketServer.ThreadingTCPServer):
    allow_reuse_address = True

def serve_controlpoint(address, setup):
    global _setup
    _setup = setup
    server = ReusableTCPServer(address, ControlPointServer)
    server.serve_forever()
