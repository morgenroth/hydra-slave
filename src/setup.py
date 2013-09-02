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
import tarfile
import ConfigParser

class Setup(object):
    """
    This class manages the node setup of a specific session.
    """
    scan_nodes = []
    virt_nodes = {}


    def __init__(self, session_id, config):
        '''
        Constructor
        '''
        
        """ create a node list """
        self.session_id = session_id
        
        self.sudomode = config.get('general', 'sudomode')
        self.shell = config.get('general', 'shell')
        
        self.workdir = os.path.join("hydra-setup", session_id)
        self.baseurl = config.get("general", "url") + "/dl"
        self.sessionurl = self.baseurl + "/" + session_id

        self.virt_driver = config.get('template','virturl')
        self.virt_connection = libvirt.open( self.virt_driver )
        self.mcast_interface = config.get('master','interface')
        (self.virt_type, data) = self.virt_driver.split(":", 1)
        
        """ define the storage path for images """
        self.images_path = os.path.join(self.workdir, "images")

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
        
        """ define path of the image file """
        self.imagefile_path = os.path.join(self.workdir, imagefile)

        """ define path to virt template """        
        self.virt_template = os.path.join(base_path, "node-template." + self.virt_type + ".xml")
        
        """ run preparation script """
        self.sudo(self.shell + " " + base_path + "/prepare_image_base.sh " + self.imagefile_path + " " + base_path + " " + setup_path)
        
        """ strip .gz extension """
        if self.imagefile_path.endswith(".gz"):
            self.imagefile_path = os.path.splitext(self.imagefile_path)[0]
        
    def add_node(self, nodeId):
        """ create a virtual node object """
        v = control.VirtualNode(self, self.virt_connection, nodeId, self.workdir)
        
        """ add the virtual node object """
        self.virt_nodes[nodeId] = v
        
        """ define / create the node object """
        v.define(self.virt_type, self.imagefile_path, self.virt_template)
            
        """ debug """
        self.log("node '" + nodeId + "' defined")
        
    def remove_node(self, nodeId):
        v = self.virt_nodes[nodeId]
        v.undefine()
        del self.virt_nodes[nodeId]
        self.log("node '" + nodeId + "' undefined")
        
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
        for nodeId, v in self.virt_nodes.iteritems():
            v.destroy()
            self.log("node '" + nodeId + "' destroyed")
    
    def cleanup(self):
        for nodeId, v in self.virt_nodes.iteritems():
            v.undefine()
            self.log("node '" + nodeId + "' undefined")
            
        """ delete the old stuff """
        if os.path.exists(self.workdir):
            shutil.rmtree(self.workdir)
            
        self.scan_nodes = []
        self.virt_nodes = {}
            
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
