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
    nodes = {}
    paths = {}

    def __init__(self, session_id, config):
        '''
        Constructor
        '''
        self.session_id = session_id
        
        self.sudomode = config.get('general', 'sudomode')
        self.shell = config.get('general', 'shell')
        
        self.mcast_interface = config.get('master','interface')
        
        """ define basic paths """
        self.paths['workspace'] = os.path.join("hydra-setup", session_id)
        self.paths['images'] = os.path.join(self.paths['workspace'], "images")
        self.paths['base'] = os.path.join(self.paths['workspace'], "base")
        self.paths['setup'] = os.path.join(self.paths['workspace'], "setup")
        
        self.baseurl = config.get("general", "url") + "/dl"
        self.sessionurl = self.baseurl + "/" + session_id

        """ libvirt configuration """
        self.virt_driver = config.get('template','virturl')
        self.virt_connection = libvirt.open( self.virt_driver )
        (self.virt_type, data) = self.virt_driver.split(":", 1)
        
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
            os.makedirs(self.paths['workspace'])
        except OSError:
            pass
        
        files = [ "base.tar.gz", "setup.tar.gz" ]
        
        for f in files:
            (dirname, extension) = f.split(".", 1)
            
            """ download tar archive """
            self.download(self.sessionurl + "/" + f)
            
            """ create directory for content of the archive """
            destdir = os.path.join(self.paths['workspace'], dirname)
            
            try:
                os.makedirs(destdir)
            except OSError:
                pass
        
            if extension == "tar.gz":
                """ extract the tar archive """
                tar = tarfile.open(os.path.join(self.paths['workspace'], f))
                tar.extractall(destdir)
                tar.close()
        
        self.log("done")
        
    def prepare_base(self):
        self.log("read setup configuration: config.properties")
        baseconfig = ConfigParser.RawConfigParser()
        baseconfig.read(self.paths['base'] + "/config.properties")
        
        """ download base image file """
        imagefile = baseconfig.get("image", "file")
        self.download(self.baseurl + "/" + imagefile)
        
        """ define path of the image file """
        self.paths['imagefile'] = os.path.join(self.paths['workspace'], imagefile)

        """ define path to virt template """        
        self.virt_template = os.path.join(self.paths['base'], "node-template." + self.virt_type + ".xml")
        
        """ run preparation script """
        params = [ self.shell,
                  self.paths['base'] + "/prepare_image_base.sh",
                  self.paths['imagefile'],
                  self.paths['base'],
                  self.paths['setup'] ]
                  
        self.sudo(" ".join(params))
        
        """ strip .gz extension """
        if self.paths['imagefile'].endswith(".gz"):
            self.paths['imagefile'] = os.path.splitext(self.paths['imagefile'])[0]
            
        """ create path for image files """
        os.makedirs(self.paths['images'])
        
    def add_node(self, nodeId, address):
        """ create a virtual node object """
        v = control.VirtualNode(self, self.virt_connection, nodeId, address)
        
        """ add the virtual node object """
        self.nodes[nodeId] = v
        
        """ define / create the node object """
        v.define(self.virt_type, self.paths['imagefile'], self.virt_template)
            
        """ debug """
        self.log("node '" + nodeId + "' defined")
        
    def remove_node(self, nodeId):
        try:
            v = self.nodes[nodeId]
            v.undefine()
            del self.nodes[nodeId]
            self.log("node '" + nodeId + "' undefined")
        except:
            self.log("error while removing node '" + nodeId + "'")
        
    def download(self, url):
        """Copy the contents of a file from a given URL
        to a local file.
        """
        try:
            self.log("downloading " + url)
            webFile = urllib.urlopen(url)
            localFile = open(self.paths['workspace'] + "/" + url.split('/')[-1], 'w')
            localFile.write(webFile.read())
            webFile.close()
            localFile.close()
        except IOError:
            self.log("could not get url " + url)
    
    def startup(self):
        """ switch on all nodes """
        for name, v in self.nodes.iteritems():
            v.create()
            
        """ scan for nodes """
        self.scan_for_nodes()
        
        """ connect to all nodes and call setup """
        for name, v in self.nodes.iteritems():
            v.control.connect()
            
            ''' list of open addresses for the node '''
            oalist = []
            
            ''' if the multicast interface is defined use it as open address '''
            if self.mcast_interface != "":
                oalist.append(self.mcast_interface)
                
            ''' open the connection to the default address of the slave '''
            oalist.append(socket.gethostbyname(socket.gethostname()))
            
            ''' read the monitor node list '''
            monitor_list = open(os.path.join(self.paths['base'], "monitor-nodes.txt"), "r")
            for maddress in monitor_list.readlines():
                oalist.append(maddress.strip())
                
            ''' call the setup procedure '''
            v.control.setup(oalist)
        
    def scan_for_nodes(self):
        ''' create a discovery socket '''
        ds = DiscoverySocket((self.mcast_interface, 0))
        
        while True:
            ''' scan for neighboring nodes '''
            ds.scan(("225.16.16.1", 3232), 2, None, self)
        
            """ count the number of discovered nodes """
            active_node_count = 0
            for name, v in self.nodes.iteritems():
                if v.control != None:
                    active_node_count = active_node_count + 1
            
            self.log(str(active_node_count) + " nodes discovered")
            
            if active_node_count == len(self.nodes):
                break
            
            """ wait some time until the next scan is started """
            time.sleep(10)
            
    def callback_discovered(self, name, address):
        if name in self.nodes:
            v = self.nodes[name]
            if v.control == None:
                self.log("New node '" + name + "' (" + str(address[0]) + ":" + str(address[1]) +") discovered")
                v.control = control.NodeControl(self, v.name, address, bindaddr = self.mcast_interface)
    
    def shutdown(self):
        for nodeId, v in self.nodes.iteritems():
            v.destroy()
            self.log("node '" + nodeId + "' destroyed")
    
    def cleanup(self):
        for nodeId, v in self.nodes.iteritems():
            v.undefine()
            self.log("node '" + nodeId + "' undefined")
            
        """ delete the old stuff """
        if os.path.exists(self.paths['workspace']):
            shutil.rmtree(self.paths['workspace'])
            
        self.nodes = {}
            
    def action(self, action):
        if action == "LIST":
            ret = ""
            for n in self.nodes:
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
