import argparse
import signal
import socket
import time

from .enums import Callbacks
from .pythread import PyThread

CLIENT_OBJ = None
SCRIPT_ARGS = {}
   
def handler(signum, frame):
    global CLIENT_OBJ
    
    if CLIENT_OBJ is not None:
        CLIENT_OBJ.Stop()
        print('Shutting down client')    
    exit(1)    

def argsParse(): 
    global SCRIPT_ARGS   
    
    parser = argparse.ArgumentParser()
    parser.add_argument('-p', '--port', default=5050, type=int, help="Port of the server destination")
    parser.add_argument('-d', '--destination', default=socket.gethostname(), type=str, help="IP address of the server destination")    
    parser.add_argument('-v', '--verbose', default=False, action='store_true', help="Display additional runtime information")
    parser.add_argument('--UDP', default=False, action='store_true', help="Use UDP datagrams")
        
    argData = parser.parse_args()
        
    SCRIPT_ARGS = argData
    return argData

    
class Client:
    def __init__(self, bufferSize=1024, allowOpenConnections=True, verbose=False):
        self.P_AllowOpenConnections = allowOpenConnections
        self.IS_ABORTED = False
        self.ListenerThread = None
        self.P_Verbose = verbose
        self.P_BufferSize = bufferSize
        
        self.callbacks = { x: None for x in Callbacks }
        
        self.socket = None
        
        
    ##############################################
    #############                    #############
    ##########     PRIVATE METHODS      ##########
    #############                    #############
    ##############################################
    def __HandleSingleTransmissionConnection(self, clientNr, conn, address): 
        msg = []
        while True:
            print("Connection from: " + str(address))
            
            # receive data stream. it won't accept data packet greater than 1024 bytes
            data = conn.recv(self.P_BufferSize)
            
            if not data:
                # if data is not received break
                break
            
            msg.append(data)
            
            # Message fully received?
            if len(data) < self.P_BufferSize:
                break
        
        print(f"MSG: {msg}")
        
        # Send data to the client
        conn.send("Message received!".encode())

        # Close the connection
        conn.close()  
        print(f"Connection {str(address)} shutting down...")
        
    def __HandleOpenConnection(self): 
        msg = []
        while not self.IS_ABORTED:            
            # receive data stream. it won't accept data packet greater than self.P_BufferSize bytes
            # As sending and receiving socket are identical, timeout applies to both, hence we need the try-except
            try:
                data = self.socket.recv(self.P_BufferSize)
            except:
                continue
            
            if data:
                msg.append(data)
                            
            # Message fully received?
            if len(data) < self.P_BufferSize and len(msg) > 0:
                bytestring = b"".join(msg)
                
                if bytestring == b'\x04':
                    self.__vPrint(f"Connection termination requested by server...")
                    break
                
                self.__Call(Callbacks.MESSAGE_RECEIVED, [bytestring])
                self.__vPrint(f"Server message received: {bytestring}")
                msg = []

        # Close the connection
        self.socket.close()
        self.IS_ABORTED = True
        self.__Call(Callbacks.CONNECTION_TERMINATED)
        self.__vPrint("Connection terminated!")
        
    
    def __vPrint(self, msg):
        if self.P_Verbose:
            print(msg)    
               
    def __Call(self, callback, parameters=None):
        """ Call any registered callback with the parameters provided and measure exec-time in case verbose is on"""
        
        ret = None
        cb = self.callbacks.get(callback)
        if cb is not None:
            fTimeStart = time.time()
            if parameters is None:
                ret = cb()
            else:
                ret = cb(*parameters)
            self.__vPrint(f"    - {str(callback)} took: {time.time() - fTimeStart}s")
        return ret
        
    def __SendMessage(self, msg):
        if self.socket is None:
            raise("No open conenction available!")
            
        # Send data to the server
        if type(msg) is bytes:
            self.socket.send(msg)
        else:
            self.socket.send(str(msg).encode())
        
    ##############################################
    #############                    #############
    ##########      PUBLIC METHODS      ##########
    #############                    #############
    ##############################################
    def Register(self, callbackType, callback):
        self.callbacks[callbackType] = callback
        
    def Stop(self):
        # Send connection termination without creating a new thread (do it syncronously)
        try:
            self.__SendMessage(b'\x04')
        except:
            pass
        self.IS_ABORTED = True
    
    def Connect(self, host, port, udp=False, timeout=2):
        self.host = host
        self.port = port
        self.timeout = timeout
        
        if self.host is None:
            self.host = socket.gethostname()
        
        # Create socket
        if udp:
            self.socket = socket.socket(type=socket.SOCK_DGRAM, proto=socket.IPPROTO_UDP)
        else:
            self.socket = socket.socket(type=socket.SOCK_STREAM, proto=socket.IPPROTO_TCP)
        
        self.socket.settimeout(self.timeout)
        
        # Connect to the server
        self.socket.connect((self.host, self.port))
        
        # Set up the loop for server messages/replies
        self.ListenerThread = PyThread(-1, self.__HandleOpenConnection, None, f"Listener thread")
        self.ListenerThread.start()
    
    def SendMessage(self, msg):
        if self.socket is None:
            raise("No open conenction available!")
            
        # Send data to the server
        t = PyThread(-1, self.__SendMessage, [msg], f"Sender thread")
        t.start()
        
        

def msgRecv(msg):
    print(f"Received new message: '{msg}'")
    
if __name__ == '__main__':   
    # Only add this handler if we are running the script in stand-alone mode
    signal.signal(signal.SIGINT, handler) 
    
    # Get cmd parameters
    args = argsParse()
    
    # Run
    CLIENT_OBJ = Client(verbose=args.verbose)
    CLIENT_OBJ.Register(Callbacks.MESSAGE_RECEIVED, msgRecv)
    CLIENT_OBJ.Connect(args.destination, args.port, args.UDP)
    
    while not CLIENT_OBJ.IS_ABORTED:
        message = input(" -> ")  # take input
        CLIENT_OBJ.SendMessage(message)