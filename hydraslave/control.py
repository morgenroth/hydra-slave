'''
Created on 18.01.2011

@author: morgenro
'''

import socket
import shutil
import os
from xml.dom import minidom
import logging

def json_cast(value):
    try:
        try:
            return int(value.strip())
        except ValueError:
            return float(value.strip())
    except ValueError:
        return value.strip()

class PhysicalNode(object):
    def __init__(self, setup, conn, name, address):
        '''
        Constructor
        '''
        self.name = name
        self.address = address
        self.conn = conn
        self.setupobj = setup
        self.control = None
        
        logging.info(self.log_format("physical node defined"))
        
    def log_format(self, message):
        return self.setupobj.log_format("*" + self.name + "* " + message)

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
        self.virt_name = ("hydra", self.setupobj.session.session_id, self.name)
        self.imagefile = None
        self.bridges = None
        
        try:
            self.dom = conn.lookupByName("-".join(self.virt_name))
            logging.warning(self.log_format("previous instance found"))
        except:
            logging.info(self.log_format("create a new instance"))
            
    def log_format(self, message):
        return self.setupobj.log_format("*" + self.name + "* " + message)
        
    def define(self, virt_type, image_template, xml_template, bridges):
        if self.dom != None:
            self.undefine()
        
        ''' get xml for the template host '''
        doc = minidom.parse(xml_template)
        
        ''' define the path for the image file '''
        self.imagefile = os.path.join(self.setupobj.paths['images'], "hydra-" + self.name + ".image")
        
        ''' define the bridge interfaces '''
        self.bridges = bridges
        
        ''' copy the image '''
        shutil.copy(image_template, self.imagefile)
        
        logging.info(self.log_format("image preparation"))
        
        """ run individual preparation script """
        params = [ "/bin/bash",
                  self.setupobj.paths['base'] + "/prepare_image_node.sh",
                  self.imagefile,
                  self.setupobj.paths['base'],
                  self.name,
                  self.address[0],
                  self.address[1] ]
        
        self.setupobj.sudo(" ".join(params))
        
        ''' convert the raw image to virtualizers specific format '''
        if virt_type == "vbox":
            virt_image = os.path.join(self.storage_path, "hydra-" + self.name + ".vdi")
            os.system("VBoxManage convertfromraw " + self.imagefile + " " + virt_image + " --format VDI --variant Standard")
            
            """ remove old image file """
            os.remove(self.imagefile)
            self.imagefile = virt_image
            
            """ close the link to the old image """
            os.system("VBoxManage closemedium disk " + self.imagefile)
        
        ''' rename the node '''
        doc.getElementsByTagName("name")[0].firstChild.nodeValue = "-".join(self.virt_name)
        
        ''' replace image file '''
        for disk in doc.getElementsByTagName("disk"):
            source = disk.getElementsByTagName("source")[0]
            if source.hasAttribute("file"):
                source.setAttribute("file", os.path.abspath(self.imagefile))
                ''' stop processing after the first disk '''
                break
        
        ''' replace bridge interface '''
        index = 0
        for interface in doc.getElementsByTagName("interface"):
            ''' stop if there are no more interfaces to assign '''
            if index >= len(self.bridges):
                break
            
            ''' get the source element '''
            source = interface.getElementsByTagName("source")[0]
            if source.hasAttribute("bridge"):
                if self.bridges[index] != None:
                    source.setAttribute("bridge", self.bridges[index])
                index = index + 1
        
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
        self.current_position = None
        #self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        
        if bindaddr != None:
            self.sock.bind((bindaddr, 0))
            
    def log_format(self, message):
        return self.setupobj.log_format("#" + self.name + "# " + message)
        
    def connect(self):
        try:
            self.sock.connect((self.address[0], self.port))
            self.file = self.sock.makefile()
                      
            """ receive and decode node banner """
            banner = self.file.readline().split(' ')
            logging.info(self.log_format("Node '" + banner[2] + "' connected - " + banner[0] + " version " + banner[1] + " (" + banner[3].strip() + ")"))
            
            if banner[2] != self.name:
                logging.error(self.log_format("Node name does not match: " + self.name + " != " + banner[2]))
            
        except socket.error, msg:
            logging.error(self.log_format(str(msg)))
            raise msg

    def close(self):
        try:
            self.file.close()
            self.sock.close()
        except socket.error, msg:
            logging.error(self.log_format(str(msg)))
    
    def position(self, x, y, z = 0.0):
        logging.debug(self.log_format("new position x:" + str(x) + " y:" + str(y) + " z:" + str(z)))
        try:
            if self.current_position == None:
                data = " ".join(("position", "enable"))
                self.sock.send(data + "\n")
                self.recv_response()
                
            """ store position locally """
            self.current_position = (x, y, z)
                        
            data = " ".join(("position", "set", str(x), str(y), str(z)))
            self.sock.send(data + "\n")
            self.recv_response()
        except socket.error, msg:
            logging.error(self.log_format(str(msg)))
            
    def clock(self, offset, frequency, timeofday_sec, timeofday_usec):
        # offset <useconds>
        if offset != None:
            data = " ".join(("clock", "set", "offset", str(offset)))
            self.sock.send(data + "\n")
            self.recv_response()
        
        # frequency <int>
        if frequency != None:
            data = " ".join(("clock", "set", "frequency", str(frequency)))
            self.sock.send(data + "\n")
            self.recv_response()

        # timeofday <seconds> <useconds>
        if timeofday_sec != None:
            if timeofday_usec != None:
                data = " ".join(("clock", "set", "timeofday", str(timeofday_sec), str(timeofday_usec)))
                self.sock.send(data + "\n")
                self.recv_response()
                
    def toArray(self, result):
        ret = {}
        if result:
            for line in result:
                if len(line.strip()) > 0:
                    (key, data) = line.split(":", 1)
                    ret[key] = json_cast(data)
        return ret
            
    def stats(self):
        logging.info(self.log_format("query node stats"))
        
        """ collect all known stats and return an summary array """
        stats_result = {}
        
        try:
            """ stats interfaces """
            stats_result["iface"] = self.stats_ifaces()
                            
            """ hydra traffic """
            stats_result["traffic"] = {}
            stats_result["traffic"]["in"] = self.stats_traffic("hydra_in")
            stats_result["traffic"]["out"] = self.stats_traffic("hydra_out")
                            
            """ get generic stats """
            stats_result["collection"] = self.stats_generic()

            """ dtnd stats """
            stats_result["dtnd"] = {}

            """ dtnd stats info """
            result = self.query(("dtnd", "stats", "info"))
            stats_result["dtnd"]["info"] = self.toArray(result)
                    
            """ dtnd stats bundles """
            result = self.query(("dtnd", "stats", "bundles"))
            stats_result["dtnd"]["bundles"] = self.toArray(result)
                        
            """ dtnd stats timesync """
            result = self.query(("dtnd", "stats", "timesync"))
            stats_result["dtnd"]["timesync"] = self.toArray(result)
            
            """ clock get all """
            result = self.query(("clock", "get", "all"))
            stats_result["clock"] = self.toArray(result)
                    
            """ get position """
            result = self.query(("position", "get"))
            stats_result["position"] = self.toArray(result)

        except socket.error, msg:
            logging.error(self.log_format(str(msg)))
            
        return stats_result
    
    def stats_generic(self):
        ret = {}
        current = None
        result = self.query(("stats", "collection"))
        if result:
            for line in result:
                if len(line.strip()) > 0:
                    (vkey, value) = line.split(":", 1)
                    
                    if vkey[0] == '#':
                        ret[value.strip()] = {}
                        current = ret[value.strip()]
                    else:
                        if current != None:
                            current[vkey] = json_cast(value)
        return ret
    
    def stats_traffic(self, chain):
        ret = self.script("iptables -L " + chain + " -n -v -x | tail -n 3 | awk '{print $4 \"_pkt: \" $1 \"\\n\" $4 \"_byte: \" $2}'")
        return self.toArray(ret)
    
    def stats_ifaces(self):
        ret = {}
        result = self.query(("stats", "interfaces"))
        if result:
            for line in result:
                if len(line.strip()) > 0:
                    (key, data) = line.split(" ", 1)
                    ret[key] = {}
                    for entry in data.split(" "):
                        (vkey, value) = entry.split(":", 1)
                        ret[key][vkey] = json_cast(value)
        return ret
    
    def dtnd(self, action):
        logging.info(self.log_format("collect DTN daemon data '" + action + "'"))
        return self.query(("dtnd", action))
    
    def query(self, query):
        try:
            """ debug: print query """
            #if self.setupobj.debug:
            #    logging.debug(self.log_format("query '" + " ".join(query) + "'"))
            
            """ send query """
            self.sock.send(" ".join(query) + "\n")
            
            """ wait for the response """
            (code, result) = self.recv_response()
            
            """ debug: print query result """
            #if self.setupobj.debug:
            #    logging.debug(self.log_format("query result [" + str(code) + "]"))
            #    for line in result:
            #        logging.debug(self.log_format(line))
            
            return result
        except socket.error, msg:
            logging.error(self.log_format(str(msg)))
    
    def script(self, data):
        logging.info(self.log_format("calling script"))
        try:
            self.sock.send(" ".join(("system", "script")) + "\n")
            
            """ debug: print script """
            #if self.setupobj.debug:
            #    for line in data.split('\n'):
            #        logging.debug(self.log_format(line.strip()))
            
            (code, result) = self.recv_response(data)
            
            """ debug: print script result """
            #if self.setupobj.debug:
            #    logging.debug(self.log_format("script result [" + str(code) + "]"))
            #    for line in result:
            #        logging.debug(self.log_format(line))
            
            return result
        except socket.error, msg:
            logging.error(self.log_format(str(msg)))
        
    def shutdown(self):
        logging.info(self.log_format("halt"))
        try:
            self.sock.send(" ".join(("system", "shutdown")) + "\n")
            self.recv_response()
        except socket.error, msg:
            logging.error(self.log_format(str(msg)))
            
    def setup(self, open_addresses):
        script = [ "/usr/sbin/iptables -F" ]

        """ create incoming chain """
        script.append("/usr/sbin/iptables -X hydra_in")
        script.append("/usr/sbin/iptables -N hydra_in")
        
        """ create outgoing chain """
        script.append("/usr/sbin/iptables -X hydra_out")
        script.append("/usr/sbin/iptables -N hydra_out")
        
        """ redirect traffic to accounting """
        script.append("/usr/sbin/iptables -A OUTPUT -o $(uci get network.lan.ifname) -j hydra_out")
        
        """ allow static connections """
        for addr in open_addresses:
            script.append("/usr/sbin/iptables -A INPUT -i $(uci get network.lan.ifname) -s " + addr + "/32 -j hydra_in")
        
        """ drop all further traffic """
        script.append("/usr/sbin/iptables -A INPUT -i $(uci get network.lan.ifname) -j DROP")
        
        """ accounting outgoing traffic """
        script.append("/usr/sbin/iptables -A hydra_out -p tcp -j ACCEPT")
        script.append("/usr/sbin/iptables -A hydra_out -p udp -j ACCEPT")
        script.append("/usr/sbin/iptables -A hydra_out -p icmp -j ACCEPT")
        
        """ accounting incoming traffic """
        script.append("/usr/sbin/iptables -A hydra_in -p tcp -j ACCEPT")
        script.append("/usr/sbin/iptables -A hydra_in -p udp -j ACCEPT")
        script.append("/usr/sbin/iptables -A hydra_in -p icmp -j ACCEPT")

        """ set default rules """
        script.append("/usr/sbin/iptables -P OUTPUT ACCEPT")
        script.append("/usr/sbin/iptables -P FORWARD ACCEPT")
        script.append("/usr/sbin/iptables -P INPUT ACCEPT")
        
        self.script('\n'.join(script))
        
    def connectionUp(self, address):
        script = [ "/usr/sbin/iptables -I INPUT -i $(uci get network.lan.ifname) -s " + address + "/32 -j hydra_in" ]
        self.script('\n'.join(script))
        
    def connectionDown(self, address):
        script = [ "/usr/sbin/iptables -D INPUT -i $(uci get network.lan.ifname) -s " + address + "/32 -j hydra_in" ]
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
