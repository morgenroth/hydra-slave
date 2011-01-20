'''
Created on 18.01.2011

@author: morgenro
'''

import struct
import socket
import libvirt
import sys
import shutil
import os
from xml.dom import minidom
from disco import DiscoverySocket

class VirtualNode(object):
    '''
    classdocs
    '''
    def __init__(self, conn, name, storage_path):
        '''
        Constructor
        '''
        self.name = name
        self.storage_path = storage_path
        self.dom = None
        self.conn = conn
        
        try:
            self.dom = conn.lookupByName("hydra-" + self.name)
            print("previous instance of " + self.name + " found.")
        except:
            print("create a new instance of " + self.name + ".")
        
    def define(self, image_template, xml_template):
        if self.dom != None:
            self.undefine()
        
        ''' get xml for the template host '''
        doc = minidom.parse(xml_template)
        
        ''' define the path for the image file '''
        image = self.storage_path + "/hydra-" + self.name + ".image"
        
        ''' copy the image '''
        shutil.copy(image_template, image)
        
        ''' rename the node '''
        doc.getElementsByTagName("name")[0].firstChild.nodeValue = "hydra-" + self.name
        
        for disk in doc.getElementsByTagName("disk"):
            source = disk.getElementsByTagName("source")[0]
            if source.hasAttribute("file"):
                source.setAttribute("file", os.path.abspath(image))
        
        self.dom = self.conn.defineXML(doc.toxml())
        
    def create(self):
        self.dom.create()
    
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
    
    def __init__(self, name, address, port = 3486):
        '''
        Constructor
        '''
        self.name = name
        self.address = address
        self.port = port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        #self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

        
    def connect(self):
        try:
            self.sock.connect((self.address[0], self.port))
        except socket.error, msg:
            print("[ERROR] " + str(msg))
            raise msg

    def close(self):
        try:
            self.sock.close()
        except socket.error, msg:
            print("[ERROR] " + str(msg))
    
    def position(self, lon, lat, alt = 0.0):
        print("new position for node " + self.name)
        try:
            data = struct.pack("!Bfff", 2, lon, lat, alt)
            self.sock.send(data)
        except socket.error, msg:
            print("[ERROR] " + str(msg))
    
    def script(self, data):
        print("call script data on " + self.name)
        try:
            header = struct.pack("!BI", 1, len(data))
            self.sock.send(header)
            self.sock.send(data)
        except socket.error, msg:
            print("[ERROR] " + str(msg))
        
    def shutdown(self):
        print("halt node " + self.name)
        try:
            data = struct.pack("!B", 3)
            self.sock.send(data)
        except socket.error, msg:
            print("[ERROR] " + str(msg))
            
    def setup(self, gateway, dns):
        script = "/usr/sbin/iptables -F\n" + \
            "/usr/sbin/iptables -A OUTPUT -d " + gateway + "/32 -j ACCEPT\n" + \
            "/usr/sbin/iptables -A OUTPUT -d " + dns + "/32 -j ACCEPT\n" + \
            "/usr/sbin/iptables -A OUTPUT -d 192.168.56.255/32 -j ACCEPT\n" + \
            "/usr/sbin/iptables -A OUTPUT -d 255.255.255.255/32 -j ACCEPT\n" + \
            "/usr/sbin/iptables -A OUTPUT -d 127.0.0.1/8 -j ACCEPT\n" + \
            "/usr/sbin/iptables -A INPUT -s " + gateway + "/32 -j ACCEPT\n" + \
            "/usr/sbin/iptables -A INPUT -s " + dns + "/32 -j ACCEPT\n" + \
            "/usr/sbin/iptables -A INPUT -s 127.0.0.1/8 -j ACCEPT\n" + \
            "/usr/sbin/iptables -P OUTPUT DROP\n" + \
            "/usr/sbin/iptables -P INPUT DROP\n"
        self.script(script)
        
    def connectionUp(self, address):
        script = "/usr/sbin/iptables -A OUTPUT -d " + address + "/32 -j ACCEPT" + \
            "/usr/sbin/iptables -A INPUT -s " + address + "/32 -j ACCEPT"
        self.script(script)
        
    def connectionDown(self, address):
        script = "/usr/sbin/iptables -D OUTPUT -d " + address + "/32 -j ACCEPT" + \
            "/usr/sbin/iptables -D INPUT -s " + address + "/32 -j ACCEPT"
        self.script(script)
