'''
Created on 21.01.2011

@author: morgenro
'''

import json
import os
import shutil
import urllib
import time
import sys
import libvirt
from disco import DiscoverySocket
import control 
import tarfile
import ConfigParser
import concurrent

class TimeoutError(Exception):
    pass

class State():
    INITIAL = 0
    PREPARED = 1
    RUNNING = 2
    STOPPED = 3

class Setup(object):
    """
    This class manages the node setup of a specific session.
    """
    
    """ all node objects are stored here """
    nodes = {}
    
    """ all custom paths are stored here """
    paths = {}
    
    """ determine if debugging is on """
    debug = False
    
    """ setup state """
    state = State.INITIAL
    
    """ link to the session holding this setup """
    session = None

    def __init__(self, session):
        '''
        Constructor
        '''
        self.session = session
        
        """ read the global configuration """
        self.read_configuration(self.session.config)
        
    def read_configuration(self, config):
        self.sudomode = config.get('general', 'sudomode')
        self.shell = config.get('general', 'shell')
        self.debug = (config.get('general', 'debug') == "yes")
        
        """ IP address of the multicast interface """
        self.mcast_interface = config.get('discovery','interface')
        self.mcast_address = (config.get('discovery','address'), config.getint('discovery','port'))
        
        """ ntp server used to synchronize the nodes or measure the clock offset """
        self.ntp_server = config.get('ntp', 'server')
        
        """ define basic paths """
        self.paths['workspace'] = os.path.join("workspace", self.session.instance_name, str(self.session.session_id))
        self.paths['images'] = os.path.join(self.paths['workspace'], "images")
        self.paths['base'] = os.path.join(self.paths['workspace'], "base")
        
        """ define hydra download path """
        self.baseurl = self.session.hydra_url + "/dl"
        self.sessionurl = self.baseurl + "/" + self.session.session_id
        
        """ define bridge interfaces """
        self.bridges = [ None, None ]
        if config.has_option('general', 'nat_bridge'):
            self.bridges[0] = config.get('general', 'nat_bridge')
        if config.has_option('general', 'slave_bridge'):
            self.bridges[1] = config.get('general', 'slave_bridge')

        """ libvirt configuration """
        self.virt_driver = config.get('template','virturl')
        self.virt_connection = libvirt.open( self.virt_driver )
        (self.virt_type, data) = self.virt_driver.split(":", 1)
        
        if self.virt_connection == None:
            self.log("could not connect to libvirt")
            sys.exit(-1)
            
        self.log("New session created")
            
    def log(self, message):
        print("[" + self.session.session_id + "] " + message)
        
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
        
        files = [ "base.tar.gz" ]
        
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
                  self.ntp_server ]
                  
        self.sudo(" ".join(params))
        
        """ strip .gz extension """
        if self.paths['imagefile'].endswith(".gz"):
            self.paths['imagefile'] = os.path.splitext(self.paths['imagefile'])[0]
            
        """ create path for image files """
        if not os.path.exists(self.paths['images']):
            os.makedirs(self.paths['images'])
        
        """ mark this setup as prepared """
        self.state = State.PREPARED
        
    def add_node(self, nodeId, nodeName, address):
        if self.state != State.PREPARED:
            return
        
        """ create a virtual node object """
        v = control.VirtualNode(self, self.virt_connection, "n" + str(nodeId), address)
        
        """ add the virtual node object """
        self.nodes[nodeId] = v
        
        try:
            """ define / create the node object """
            v.define(self.virt_type, self.paths['imagefile'], self.virt_template, self.bridges)
            
            """ debug """
            self.log("node " + str(nodeId) + " '" + str(nodeName) + "' defined")
        except:
            """ debug """
            self.log("node " + str(nodeId) + " '" + str(nodeName) + "' failed: " + str(sys.exc_info()[0]))
        
    def remove_node(self, nodeId):
        if self.state != State.STOPPED and self.state != State.PREPARED:
            return

        try:
            v = self.nodes[nodeId]
            v.undefine()
            del self.nodes[nodeId]
            self.log("node " + str(nodeId) + " undefined")
        except:
            self.log("error while removing node '" + str(nodeId) + "'")
        
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
        if self.state != State.PREPARED:
            return

        """ switch on all nodes """
        for name, v in self.nodes.iteritems():
            v.create()
        
        try:
            """ scan for nodes """
            self.scan_for_nodes()
            
            """ connect to all nodes and call setup """
            for name, v in self.nodes.iteritems():
                v.control.connect()
                
                ''' list of open addresses for the node '''
                oalist = []

                ''' read the monitor node list '''
                monitor_list = open(os.path.join(self.paths['base'], "monitor-nodes.txt"), "r")
                for maddress in monitor_list.readlines():
                    if len(maddress.strip()) > 0:
                        oalist.append(maddress.strip())
                    
                ''' call the setup procedure '''
                v.control.setup(oalist)
                
            """ mark this setup as running """
            self.state = State.RUNNING
            
        except TimeoutError:
            self.shutdown()
            raise
            
        
    def scan_for_nodes(self):
        ''' create a discovery socket '''
        ds = DiscoverySocket((self.mcast_interface, 0))

        for i in range(0, 5):
            ''' scan for neighboring nodes '''
            ds.scan(self.mcast_address, 2, None, self)
        
            """ count the number of discovered nodes """
            active_node_count = 0
            for name, v in self.nodes.iteritems():
                if v.control != None:
                    active_node_count = active_node_count + 1
            
            self.log(str(active_node_count) + " nodes discovered")
            
            if active_node_count == len(self.nodes):
                return
            
            """ wait some time until the next scan is started """
            time.sleep(10)
            
        raise TimeoutError
            
    def callback_discovered(self, name, address):
        nodeId = name[1:]
        if nodeId in self.nodes:
            v = self.nodes[nodeId]
            if v.control == None:
                self.log("New node '" + name + "' (" + str(address[0]) + ":" + str(address[1]) +") discovered")
                v.control = control.NodeControl(self, v.name, address, bindaddr = self.mcast_interface)
    
    def shutdown(self):
        if self.state != State.RUNNING and self.state != State.PREPARED:
            return

        for nodeId, v in self.nodes.iteritems():
            """ close control connection """
            if v.control != None:
                v.control.close()
                v.control = None
            
            """ destroy (turn-off) the node """
            v.destroy()
            
            self.log("node '" + nodeId + "' destroyed")
            
        """ mark this setup as stopped """
        self.state = State.STOPPED
    
    def cleanup(self):
        if self.state != State.STOPPED and self.state != State.INITIAL:
            """ shutdown the session """
            self.shutdown()
        
        for nodeId, v in self.nodes.iteritems():
            v.undefine()
            if v.imagefile != None:
                try:
                    os.remove(v.imagefile)
                except OSError as e:
                    self.log("OS error: " + str(e))
            self.log("node '" + nodeId + "' undefined")
            
        """ delete the old stuff """
        if os.path.exists(self.paths['workspace']):
            shutil.rmtree(self.paths['workspace'])
            
        self.nodes = {}
        
        """ mark this setup as initial """
        self.state = State.INITIAL
        
    def connectionUp(self, node, peer_address):
        if self.state != State.RUNNING:
            return
        
        try:
            n = self.nodes[node]
            n.control.connectionUp(peer_address)
        except KeyError:
            self.log("ERROR: node '" + node + "' not found")
        
    def connectionDown(self, node, peer_address):
        if self.state != State.RUNNING:
            return
        
        try:
            n = self.nodes[node]
            n.control.connectionDown(peer_address)
        except KeyError:
            self.log("ERROR: node '" + node + "' not found")
            
    def stats(self, n):
        return n.control.stats()
        
    def action(self, action):
        if self.state != State.RUNNING:
            return

        if action.startswith("list nodes"):
            ret = []
            for nodeId, v in self.nodes.iteritems():
                ret.append(nodeId + " " + v.address[0])
            return ret
        elif action.startswith("script "):
            """ extract node name """
            (cmd, node_name, action) = action.split(" ", 2)
            
            try:
                """ call the script on the node """
                return self.nodes[node_name].control.script(action)
            except KeyError:
                self.log("ERROR: node '" + node_name + "' not found")
        elif action.startswith("clock "):
            (cmd, node_name, offset, frequency, sec, usec) = action.strip().split(" ", 5)
            
            if offset == "*":
                offset = None
            else:
                offset = float(offset)
                
            if frequency == "*":
                frequency = None
            else:
                frequency = int(frequency)
                
            if sec == "*":
                sec = None
            else:
                sec = int(sec)
                
            if usec == "*":
                usec = None
            else:
                usec = int(usec)
                
            try:
                self.nodes[node_name].control.clock(offset, frequency, sec, usec)
            except KeyError:
                self.log("ERROR: node '" + node_name + "' not found")
        elif action.startswith("position "):
            (cmd, node_name, x, y, z) = action.split(" ", 4)
            
            try:
                n = self.nodes[node_name]
                
                if float(z) == 0.0:
                    n.control.position(float(x), float(y))
                else:
                    n.control.position(float(x), float(y), float(z))
            except KeyError:
                self.log("ERROR: node '" + node_name + "' not found")
        elif action.startswith("stats "):
            (cmd, node_name) = action.split(" ", 1)
            
            if node_name == "*":
                stats = concurrent.concurrent(self.stats, self.nodes)
                return [ json.dumps(stats) ]
            else:
                try:
                    n = self.nodes[node_name.strip()]
                    return [ json.dumps(n.control.stats()) ]
                except KeyError:
                    self.log("ERROR: node '" + node_name + "' not found")
                    
        elif action.startswith("dtnd "):
            (cmd, node_name, action) = action.split(" ", 2)

            try:
                n = self.nodes[node_name]
                return n.control.dtnd(action.strip())
            except KeyError:
                self.log("ERROR: node '" + node_name + "' not found")
        else:
            # extract name and address
            (cmd, node_name, address) = action.split(" ", 2)
            
            if cmd == "up":
                # send the connection up command
                self.connectionUp(node_name, address)
            elif cmd == "down":
                # send the connection down command
                self.connectionDown(node_name, address)
