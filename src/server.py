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

global virt_connection

class Setup(object):
    """
    load the configuration from a webserver and
    hold any meta data about the partial setup
    """
    
    def __init__(self):
        '''
        Constructor
        '''
        self.name = socket.gethostname()
        self.workdir = "hydra-setup"
        self.baseurl = None
        self.nodes = None
        self.scan_nodes = None
        self.virt_nodes = None
        
    def loadURL(self, url):
        self.baseurl = url
        
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
        
        self.load()
        
    def load(self):
        self.nodes = []
        self.scan_nodes = []
        self.virt_nodes = []
        
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
            
        print(str(len(self.nodes)) + " nodes loaded.")
            
    def prepare(self):
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
            
        """ scan for nodes """
        self.scan_for_nodes()
        
    def scan_for_nodes(self):
        ''' create a discovery socket '''
        ds = DiscoverySocket()
        
        while True:
            ''' scan for neighboring nodes '''
            node_dict = ds.scan(("225.16.16.1", 3232), 2)
        
            """ check if all nodes are available """
            active_node_count = 0
            for n in self.nodes:
                if n in node_dict:
                    active_node_count = active_node_count + 1
            
            print(str(active_node_count) + " nodes discovered")
            
            """ all nodes available, create new node list """
            if len(self.nodes) == active_node_count:
                for n in self.nodes:
                    ''' create control object with the discovery data '''
                    self.scan_nodes.append( control.NodeControl(n, node_dict[n]) )
                break
            
            """ wait some time until the next scan is started """
            time.sleep(10)
    
    def shutdown(self):
        if self.virt_nodes != None:
            for v in self.virt_nodes:
                v.destroy()
    
    def cleanup(self):
        if self.virt_nodes != None:
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
    
    def setup(self):
        print("master connection opened (" + self.client_address[0] + ":" + str(self.client_address[1]) + ")")
        global _setup
        
        try:
            if _setup == None:
                _setup = Setup()
                _setup.load()
        except:
            _setup = None
    
    def finish(self):
        print("master connection closed (" + self.client_address[0] + ":" + str(self.client_address[1]) + ")")

    def handle(self):
        global _setup
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
                    _setup = Setup()
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
                
                # report that we are ready
                self.request.send("READY\n")

class ReusableTCPServer(SocketServer.ThreadingTCPServer):
    allow_reuse_address = True

def serve_controlpoint(address, virtconn):
    global virt_connection
    virt_connection = virtconn
    server = ReusableTCPServer(address, ControlPointServer)
    server.serve_forever()
