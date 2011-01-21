'''
Created on 21.01.2011

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

class Setup(object):
    """
    load the configuration from a webserver and
    hold any meta data about the partial setup
    """
    __virt_connection = None
    __minterface = None
    
    def __init__(self, virt_connection, mcast_interface):
        '''
        Constructor
        '''
        self.name = socket.gethostname()
        self.workdir = "hydra-setup"
        self.baseurl = None
        self.nodes = None
        self.scan_nodes = None
        self.virt_nodes = None
        self.virt_connection = virt_connection
        self.mcast_interface = mcast_interface
        
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
        self.download(self.baseurl + "/prepare_image_node.sh")
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
        
        try:
            """ read the nodes file """
            fd = open(self.workdir + "/nodes.txt", "r")
            for l in fd.readlines():
                self.nodes.append( l.strip() )
            fd.close()
            
            """ define the storage path for images """
            storage_path = self.workdir
            
            """ create virtual nodes """
            for n in self.nodes:
                self.virt_nodes.append( control.VirtualNode(self.virt_connection, n, storage_path) )
                
            print(str(len(self.nodes)) + " nodes loaded.")
        except:
            pass
            
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
        
        """ connect to all nodes and call setup """
        for n in self.scan_nodes:
            n.connect()
            
            ''' list of open addresses for the node '''
            oalist = []
            
            ''' if the multicast interface is defined use it as open address '''
            if self.mcast_interface != "":
                oalist.append(self.mcast_interface)
                
            ''' open the connection to the default address of the slave '''
            oalist.append(socket.gethostbyname(socket.gethostname()))
                
            ''' call the setup procedure '''
            n.setup(oalist)
        
    def scan_for_nodes(self):
        ''' create a discovery socket '''
        ds = DiscoverySocket((self.mcast_interface, 0))
        
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
                    self.scan_nodes.append( control.NodeControl(n, node_dict[n], bindaddr = self.mcast_interface) )
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
            
        self.nodes = []
        self.scan_nodes = []
        self.virt_nodes = []
            
    def action(self, action):
        if action == "LIST":
            ret = ""
            for n in self.scan_nodes:
                ret = ret + n.name + " " + n.address[0] + "\n"
            ret = ret + "EOL"
            return ret
        elif action.startswith("SCRIPT "):
            # extract name and address
            (cmd, action) = action.split(" ", 1)
            (node_name, action) = action.split(" ", 1)
            
            # get the node control object
            n = self.getNode(node_name)
            
            # node not located here, break out
            if n == None:
                return
            
            # call the script on the node
            n.script(action)
            
        elif action == "SETUP":
            # extract name and address
            (cmd, action) = action.split(" ", 1)
            (node_name, action) = action.split(" ", 1)
            (gateway, action) = action.split(" ", 1)
            dns = action
            
            # get the node control object
            n = self.getNode(node_name)
            
            # node not located here, break out
            if n == None:
                return
            
            # send the setup command
            n.setup(gateway, dns)
            
        else:
            # extract name and address
            (cmd, action) = action.split(" ", 1)
            (node_name, action) = action.split(" ", 1)
            address = action
            
            # get the node control object
            n = self.getNode(node_name)
            
            # node not located here, break out
            if n == None:
                return
            
            if cmd == "UP":
                # send the connection up command
                n.connectionUp(address)
            elif cmd == "DOWN":
                # send the connection down command
                n.connectionDown(address)

    def getNode(self, name):
        for n in self.scan_nodes:
            if n.name == name:
                return n
        return None
