'''
Created on 18.01.2011

@author: morgenro
'''

import struct
import socket
import shutil
import os
from xml.dom import minidom

class VirtualNode(object):
    '''
    classdocs
    '''
    def __init__(self, setup, conn, name, address):
        '''
        Constructor
        '''
        self.name = name
        self.address = address
        self.dom = None
        self.conn = conn
        self.setupobj = setup
        self.control = None
        
        try:
            self.dom = conn.lookupByName("hydra-" + self.name)
            self.setupobj.log("previous instance of " + self.name + " found.")
        except:
            self.setupobj.log("create a new instance of " + self.name + ".")
        
    def define(self, virt_type, image_template, xml_template):
        if self.dom != None:
            self.undefine()
        
        ''' get xml for the template host '''
        doc = minidom.parse(xml_template)
        
        ''' define the path for the image file '''
        image = os.path.join(self.setupobj.paths['images'], "hydra-" + self.name + ".image")
        
        ''' copy the image '''
        shutil.copy(image_template, image)
        
        self.setupobj.log("image preparation for " + self.name)
        
        """ run individual preparation script """
        params = [ "/bin/bash",
                  self.setupobj.paths['base'] + "/prepare_image_node.sh",
                  image,
                  self.setupobj.paths['base'],
                  self.setupobj.paths['setup'],
                  self.name,
                  self.address[0],
                  self.address[1] ]
        
        self.setupobj.sudo(" ".join(params))
        
        ''' convert the raw image to virtualizers specific format '''
        if virt_type == "qemu":
            virt_image = image
        elif virt_type == "vbox":
            virt_image = os.path.join(self.storage_path, "hydra-" + self.name + ".vdi")
            os.system("VBoxManage convertfromraw " + image + " " + virt_image + " --format VDI --variant Standard")
            
            # close the link to the old image
            os.system("VBoxManage closemedium disk " + virt_image)
        
        ''' rename the node '''
        doc.getElementsByTagName("name")[0].firstChild.nodeValue = "hydra-" + self.name
        
        for disk in doc.getElementsByTagName("disk"):
            source = disk.getElementsByTagName("source")[0]
            if source.hasAttribute("file"):
                source.setAttribute("file", os.path.abspath(virt_image))
        
        self.dom = self.conn.defineXML(doc.toxml())
        
    def create(self):
        try:
            self.dom.create()
        except:
            pass
    
    def destroy(self):
        try:
            self.dom.destroy()
        except:
            pass
    
    def undefine(self):
        try:
            self.dom.undefine()
        except:
            pass
    
        
class NodeControl(object):
    '''
    classdocs
    '''
    
    def __init__(self, setup, name, address, port = 3486, bindaddr = None):
        '''
        Constructor
        '''
        self.setupobj = setup
        self.name = name
        self.address = address
        self.port = port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        #self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        
        if bindaddr != None:
            self.sock.bind((bindaddr, 0))

        
    def connect(self):
        try:
            self.sock.connect((self.address[0], self.port))
            
            """ TODO: receive and decode node banner """
            
        except socket.error, msg:
            self.setupobj.log("[ERROR] " + str(msg))
            raise msg

    def close(self):
        try:
            self.sock.close()
        except socket.error, msg:
            self.setupobj.log("[ERROR] " + str(msg))
    
    def position(self, lon, lat, alt = 0.0):
        self.setupobj.log("new position for node " + self.name)
        try:
            data = struct.pack("!Bfff", 2, lon, lat, alt)
            self.sock.send(data)
        except socket.error, msg:
            self.setupobj.log("[ERROR] " + str(msg))
    
    def script(self, data):
        self.setupobj.log("call script data on " + self.name)
        try:
            header = struct.pack("!BI", 1, len(data))
            self.sock.send(header)
            self.sock.send(data)
        except socket.error, msg:
            self.setupobj.log("[ERROR] " + str(msg))
        
    def shutdown(self):
        self.setupobj.log("halt node " + self.name)
        try:
            data = struct.pack("!B", 3)
            self.sock.send(data)
        except socket.error, msg:
            self.setupobj.log("[ERROR] " + str(msg))
            
    def setup(self, open_addresses):
        script = "/usr/sbin/iptables -F\n"
        
        for addr in open_addresses:
            script = script + "/usr/sbin/iptables -A OUTPUT -d " + addr + "/32 -j ACCEPT\n" + \
            "/usr/sbin/iptables -A INPUT -s " + addr + "/32 -j ACCEPT\n"
            
        script = script + "/usr/sbin/iptables -A OUTPUT -d 255.255.255.255/32 -j ACCEPT\n" + \
            "/usr/sbin/iptables -A OUTPUT -d 127.0.0.1/8 -j ACCEPT\n" + \
            "/usr/sbin/iptables -A INPUT -s 127.0.0.1/8 -j ACCEPT\n" + \
            "/usr/sbin/iptables -P OUTPUT DROP\n" + \
            "/usr/sbin/iptables -P INPUT DROP\n"
        self.script(script)
        
    def connectionUp(self, address):
        script = "/usr/sbin/iptables -A OUTPUT -d " + address + "/32 -j ACCEPT\n" + \
            "/usr/sbin/iptables -A INPUT -s " + address + "/32 -j ACCEPT\n"
        self.script(script)
        
    def connectionDown(self, address):
        script = "/usr/sbin/iptables -D OUTPUT -d " + address + "/32 -j ACCEPT\n" + \
            "/usr/sbin/iptables -D INPUT -s " + address + "/32 -j ACCEPT\n"
        self.script(script)
