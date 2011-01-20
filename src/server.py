'''
Created on 19.01.2011

@author: morgenro
'''

import SocketServer
import os
import shutil
import urllib
import socket
from disco import DiscoverySocket
import control 

global virt_connection

class Setup(object):
    """
    load the configuration from a webserver and
    hold any meta data about the partial setup
    """
    
    def __init__(self, baseurl):
        '''
        Constructor
        '''
        self.name = socket.gethostname()
        self.baseurl = baseurl
        self.workdir = "hydra-setup"
        self.nodes = []
        self.scan_nodes = []
        self.virt_nodes = []
        
    def load(self):
        """ delete the old stuff """
        self.cleanup()
            
        """ create the working directory """
        try:
            os.mkdir(self.workdir)
        except OSError:
            pass
        
        print("downloading setup files")
        
        self.download(self.baseurl + "/template.image")
        self.download(self.baseurl + "/modify_image_node.sh")
        self.download(self.baseurl + "/magicmount.sh")
        self.download(self.baseurl + "/virt-template.xml")
        self.download(self.baseurl + "/" + self.name + "/nodes.txt")
        
        print("done")
        
        """ read the nodes file """
        fd = open(self.workdir + "/nodes.txt", "r")
        for l in fd.readlines():
            self.nodes.append( l.strip() )
        fd.close()
        
        """ define the storage path for images """
        storage_path = self.workdir
        
        """ create virtual nodes """
        global __virt_connection
        
        for n in self.nodes:
            self.virt_nodes.append( control.VirtualNode(virt_connection, n, storage_path) )
            
        for v in self.virt_nodes:
            v.define(self.workdir + "/template.image", self.workdir + "/virt-template.xml")
        
    def download(self, url):
        """Copy the contents of a file from a given URL
        to a local file.
        """
        try:
            webFile = urllib.urlopen(url)
            localFile = open(self.workdir + "/" + url.split('/')[-1], 'w')
            localFile.write(webFile.read())
            webFile.close()
            localFile.close()
        except IOError:
            print("could not get url " + url)
    
    def startup(self):
        """ switch on all nodes """
        for v in self.virt_nodes:
            v.create()
        
        """ wait until they are available """
        self.scan_nodes = control.scan(("225.16.16.1", 3232), 5, len(self.nodes))
        
        if len(self.scan_nodes) < len(self.nodes):
            print "WARNING: not all nodes has been discovered"
        else:
            print "INFO: all nodes has been discovered"
    
    def shutdown(self):
        for v in self.virt_nodes:
            v.destroy()
    
    def cleanup(self):
        for v in self.virt_nodes:
            v.undefine()
            
        """ delete the old stuff """
        if os.path.exists(self.workdir):
            shutil.rmtree(self.workdir)
            
    def action(self, action):
        if action == "LIST":
            ret = ""
            for n in self.scan_nodes:
                ret = ret + n.name + " " + n.address[0] + "\n"
            ret = ret + "EOL"
            return ret

""" definition of the static setup object """
_setup = None

class ControlPointServer(SocketServer.BaseRequestHandler):
    """
    The RequestHandler class for our server.

    It is instantiated once per connection to the server, and must
    override the handle() method to implement communication to the
    client.
    """

    def handle(self):
        global _setup
        running = True
        data = ""
        
        while running:
            while not "\n" in data:
                try:
                    data = data + self.request.recv(1500)
                except:
                    return
            
            """ execute the received command """
            while "\n" in data:
                (line, data) = data.split("\n", 1)
                
                if line == "PREPARE":
                    """ prepare the setup """
                    (url, data) = data.split("\n", 1)
                    print("preparing setup with url " + url)
                    _setup = Setup(url)
                    _setup.load()
                elif _setup == None:
                    """ failed: need to prepare first """
                    print("No setup available. Please prepare the setup first!")
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
                    
                elif line == "ACTION":
                    (action, data) = data.split("\n", 1)
                    print("call action: " + action)
                    ret = _setup.action(action)
                    if ret != None:
                        self.request.send(ret + "\n")
                    continue
                elif line == "QUIT":
                    running = False
                
                # report that we are ready
                self.request.send("READY\n")

class ReusableTCPServer(SocketServer.TCPServer):
    allow_reuse_address = True

def serve_controlpoint(address, virtconn):
    global virt_connection
    virt_connection = virtconn
    server = ReusableTCPServer(address, ControlPointServer)
    server.serve_forever()
