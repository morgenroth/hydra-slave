'''
Created on 17.01.2011

@author: morgenro
'''

import threading
import socket
import select
import struct

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
    