'''
Created on 21.01.2011

@author: morgenro
'''

import os
import shutil
import urllib
import socket
import time
import sys
import libvirt
from disco import DiscoverySocket
import control 
from node import NodeList
import tarfile
import ConfigParser

class Setup(object):
    """
    This class manages the node setup of a specific session.
    """

    def __init__(self, session_id, config):
        '''
        Constructor
        '''
        
        """ create a node list """
        self.nodes = NodeList()
        self.session_id = session_id
        
        self.sudomode = config.get('general', 'sudomode')
        self.shell = config.get('general', 'shell')
        
        self.workdir = os.path.join("hydra-setup", session_id)
        self.baseurl = config.get("general", "url") + "/dl"
        self.sessionurl = self.baseurl + "/" + session_id
        self.nodes = None
        self.scan_nodes = None
        self.virt_nodes = None
        self.virt_driver = config.get('template','virturl')
        self.virt_connection = libvirt.open( self.virt_driver )
        self.mcast_interface = config.get('master','interface')
        (self.virt_type, data) = self.virt_driver.split(":", 1)
        self.virt_template = "node-template." + self.virt_type + ".xml"

        if self.virt_connection == None:
            self.log("could not connect to libvirt")
            sys.exit(-1)
            
        self.log("New session created")
            
    def log(self, message):
        print("[" + self.session_id + "] " + message)
        
    def sudo(self, command):
        self.log("(sudo) " + str(command))
        
        if self.sudomode == "plain":
            os.system("sudo " + str(command))
        elif self.sudomode == "gksu":
            os.system("gksu '" + str(command) + "'")
        elif self.sudomode == "mockup":
            pass
        
    def load(self):
        """ delete the old stuff """
        self.cleanup()
            
        """ create the working directory """
        try:
            os.makedirs(self.workdir)
        except OSError:
            pass
        
        files = [ "base.tar.gz", "setup.tar.gz" ]
        
        for f in files:
            (dirname, extension) = f.split(".", 1)
            
            """ download tar archive """
            self.download(self.sessionurl + "/" + f)
            
            """ create directory for content of the archive """
            destdir = os.path.join(self.workdir, dirname)
            
            try:
                os.makedirs(destdir)
            except OSError:
                pass
        
            if extension == "tar.gz":
                """ extract the tar archive """
                tar = tarfile.open(os.path.join(self.workdir, f))
                tar.extractall(destdir)
                tar.close()
        
        #self.download(self.baseurl + "/template.image")
        #self.download(self.baseurl + "/prepare_image_node.sh")
        #self.download(self.baseurl + "/modify_image_node.sh")
        #self.download(self.baseurl + "/magicmount.sh")
        #self.download(self.baseurl + "/" + self.virt_template)
        #self.download(self.baseurl + "/" + self.name + "/nodes.txt")
        #self.download(self.baseurl + "/monitor-nodes.txt")
        self.log("done")
        
    def prepare_base(self):
        base_path = os.path.join(self.workdir, "base")
        setup_path = os.path.join(self.workdir, "setup")
        
        self.log("read setup configuration: config.properties")
        baseconfig = ConfigParser.RawConfigParser()
        baseconfig.read(base_path + "/config.properties")
        
        """ download base image file """
        imagefile = baseconfig.get("image", "file")
        self.download(self.baseurl + "/" + imagefile)
        imagefile_path = os.path.join(self.workdir, imagefile)
        
        """ run preparation script """
        self.sudo(self.shell + " " + base_path + "/prepare_image_base.sh " + imagefile_path + " " + base_path + " " + setup_path)
        
        
    def prepare_nodes(self):
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
                
            self.log(str(len(self.nodes)) + " nodes loaded.")
        except:
            pass
        
        for v in self.virt_nodes:
            v.define(self.virt_type, os.path.join(self.workdir, "template.image"), os.path.join(self.workdir, self.virt_template))
        
    def download(self, url):
        """Copy the contents of a file from a given URL
        to a local file.
        """
        try:
            self.log("downloading " + url)
            webFile = urllib.urlopen(url)
            localFile = open(self.workdir + "/" + url.split('/')[-1], 'w')
            localFile.write(webFile.read())
            webFile.close()
            localFile.close()
        except IOError:
            self.log("could not get url " + url)
    
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
            
            ''' read the monitor node list '''
            monitor_list = open(os.path.join(self.workdir, "monitor-nodes.txt"), "r")
            for maddress in monitor_list.readlines():
                oalist.append(maddress.strip())
                
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
            
            self.log(str(active_node_count) + " nodes discovered")
            
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
