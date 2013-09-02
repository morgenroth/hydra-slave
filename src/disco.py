'''
Created on 17.01.2011

@author: morgenro
'''

import threading
import socket
import select
import struct

class DiscoveryService(threading.Thread):
    '''
    classdocs
    '''
    
    def __init__(self, addr, listen = "0.0.0.0"):
        '''
        Constructor
        '''
        threading.Thread.__init__(self)
        self.listen = listen
        self.daemon = True
        
        # Create the socket
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        # Set some options to make it multicast-friendly
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        except AttributeError:
            pass # Some systems don't support SO_REUSEPORT
        s.setsockopt(socket.SOL_IP, socket.IP_MULTICAST_TTL, 20)
        s.setsockopt(socket.SOL_IP, socket.IP_MULTICAST_LOOP, 1)

        # Bind to the port
        s.bind(('', addr[1]))

        # Set some more multicast options
        s.setsockopt(socket.SOL_IP, socket.IP_MULTICAST_IF, socket.inet_aton(self.listen))
        s.setsockopt(socket.SOL_IP, socket.IP_ADD_MEMBERSHIP, socket.inet_aton(addr[0]) + socket.inet_aton(self.listen))

        self.sock = s
        self.addr = addr
        self.running = True

        
    def run(self):
        while self.running:
            data, sender_addr = self.sock.recvfrom(1500)
            if data[1:6] == "HELLO":
                hostname = socket.gethostname()
                header = struct.pack("!BI", 1, len(hostname))
                self.sock.sendto(header + hostname, sender_addr)
            
    def shutdown(self):
        self.running = False
        self.sock.setsockopt(socket.SOL_IP, socket.IP_DROP_MEMBERSHIP, socket.inet_aton(self.addr[0]) + socket.inet_aton(self.listen))
        self.sock.close()


class DiscoverySocket(object):
    '''
    classdocs
    '''
    
    def __init__(self, address = ('', 0)):
        '''
        Constructor
        '''
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        
        ''' Make the socket multicast-aware, and set TTL. '''
        self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 20) # Change TTL (=20) to suit
        self.sock.setsockopt(socket.SOL_IP, socket.IP_MULTICAST_LOOP, 1)
        self.sock.bind(address)
        
    def scan(self, addr, timeout = 5, maxnodes = None, setup = None):
        ''' create an empty list '''
        node_dict = dict()
        
        ''' send out a discovery request '''
        self.sock.sendto('\x00' + "HELLO", addr)
        
        read_list = []
        write_list = []
        exc_list = []
        
        read_list.append(self.sock)
        
        retry = True
        
        while retry:
            (in_, out_, exc_) = select.select(read_list, write_list, exc_list, timeout)
            retry = False
        
            for fd in in_:
                retry = True
                (data, address) = fd.recvfrom(1024)
                values = struct.unpack_from("!BI", data)
                if values[0] == 1:
                    name = data[5:(values[1]+5)]
                    
                    if setup != None:
                        setup.callback_discovered(name, address)
                        
                    node_dict[ name ] = address
                    # we are done if the maximum number of nodes is reached
                    if maxnodes != None:
                        if maxnodes == len(node_dict):
                            return node_dict
                
            for fd in out_:
                pass

            for fd in exc_:
                pass
            
        return node_dict
    