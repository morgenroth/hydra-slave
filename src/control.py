'''
Created on 18.01.2011

@author: morgenro
'''

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
        self.virt_name = ("hydra", self.setupobj.session_id, self.name)
        
        try:
            self.dom = conn.lookupByName("-".join(self.virt_name))
            self.log("previous instance found")
        except:
            self.log("create a new instance")
            
    def log(self, message):
        self.setupobj.log("*" + self.name + "* " + message)
        
    def define(self, virt_type, image_template, xml_template):
        if self.dom != None:
            self.undefine()
        
        ''' get xml for the template host '''
        doc = minidom.parse(xml_template)
        
        ''' define the path for the image file '''
        image = os.path.join(self.setupobj.paths['images'], "hydra-" + self.name + ".image")
        
        ''' copy the image '''
        shutil.copy(image_template, image)
        
        self.log("image preparation")
        
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
        doc.getElementsByTagName("name")[0].firstChild.nodeValue = "-".join(self.virt_name)
        
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
            
    def log(self, message):
        self.setupobj.log("#" + self.name + "# " + message)
        
    def connect(self):
        try:
            self.sock.connect((self.address[0], self.port))
            self.file = self.sock.makefile()
                      
            """ receive and decode node banner """
            banner = self.file.readline().split(' ')
            self.log("Node '" + banner[2] + "' connected - " + banner[0] + " version " + banner[1] + " (" + banner[3].strip() + ")")
            
            if banner[2] != self.name:
                self.log("[ERROR] Node name does not match: " + self.name + " != " + banner[2])
            
        except socket.error, msg:
            self.log("[ERROR] " + str(msg))
            raise msg

    def close(self):
        try:
            self.file.close()
            self.sock.close()
        except socket.error, msg:
            self.log("[ERROR] " + str(msg))
    
    def position(self, lon, lat, alt = 0.0):
        self.log("new position")
        try:
            data = " ".join(("position", "set", lon, lat, alt))
            self.sock.send(data + "\n")
            self.recv_response()
        except socket.error, msg:
            self.log("[ERROR] " + str(msg))
    
    def script(self, data):
        self.log("calling script")
        try:
            self.sock.send(" ".join(("system", "script")) + "\n")
            
            """ debug: print script """
            if self.setupobj.debug:
                for line in data.split('\n'):
                    self.log(line.strip())
            
            (code, result) = self.recv_response(data)
            
            """ debug: print script result """
            if self.setupobj.debug:
                self.log("script result [" + str(code) + "]")
                for line in result:
                    self.log(line)
                
        except socket.error, msg:
            self.log("[ERROR] " + str(msg))
        
    def shutdown(self):
        self.log("halt")
        try:
            self.sock.send(" ".join(("system", "shutdown")) + "\n")
            self.recv_response()
        except socket.error, msg:
            self.log("[ERROR] " + str(msg))
            
    def setup(self, open_addresses):
        script = [ "/usr/sbin/iptables -F" ]
        
        for addr in open_addresses:
            script.append("/usr/sbin/iptables -A OUTPUT -d " + addr + "/32 -j ACCEPT")
            script.append("/usr/sbin/iptables -A INPUT -s " + addr + "/32 -j ACCEPT")

        """ allow loopback traffic """
        script.append("/usr/sbin/iptables -A OUTPUT -d 127.0.0.1/8 -j ACCEPT")
        script.append("/usr/sbin/iptables -A INPUT -s 127.0.0.1/8 -j ACCEPT")

        """ allow multicast traffic """
        #script.append("/usr/sbin/iptables -A OUTPUT -m pkttype --pkt-type multicast -j ACCEPT")
        script.append("/usr/sbin/iptables -A OUTPUT --protocol igmp -j ACCEPT")
        script.append("/usr/sbin/iptables -A OUTPUT --dst 224.0.0.0/4 -j ACCEPT")
        
        script.append("/usr/sbin/iptables -P OUTPUT DROP")
        script.append("/usr/sbin/iptables -P INPUT DROP")
        
        self.script('\n'.join(script))
        
    def connectionUp(self, address):
        script = [ "/usr/sbin/iptables -I OUTPUT -d " + address + "/32 -j ACCEPT",
                  "/usr/sbin/iptables -I INPUT -s " + address + "/32 -j ACCEPT" ]
        self.script('\n'.join(script))
        
    def connectionDown(self, address):
        script = [ "/usr/sbin/iptables -D OUTPUT -d " + address + "/32 -j ACCEPT", 
                  "/usr/sbin/iptables -D INPUT -s " + address + "/32 -j ACCEPT" ]
        self.script('\n'.join(script))
        
    def recv_response(self, data = None):
        response = []
        (code, msg) = self.file.readline().split(' ', 1)
        
        if int(code) == 201:
            """ continue """
            if data != None:
                self.sock.send(data + "\n.\n")
            else:
                self.sock.send("\n.\n")

            return self.recv_response()
        
        if int(code) == 212:
            """ read listing """
            while True:
                line = self.file.readline().strip()
                
                """ abort on end marker """
                if line == ".":
                    break
                
                response.append(line)
                
        elif int(code) == 211:
            """ read value """
            response.append(self.file.readline().strip())
        
        return (int(code), response)
