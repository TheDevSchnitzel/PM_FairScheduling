import socket
from pythread import PyThread
import signal
import argparse
from enums import Callbacks
import time
    
SERVER_OBJ = None
SCRIPT_ARGS = {}
   
def handler(signum, frame):
    global SERVER_OBJ
    
    if SERVER_OBJ is not None:
        SERVER_OBJ.Stop()
        print('Shutting down server')    
    exit(1)    

def argsParse(): 
    global SCRIPT_ARGS   
    
    parser = argparse.ArgumentParser()
    parser.add_argument('-p', '--port', default=5050, type=int, help="Port of the server")
    parser.add_argument('-d', '--host', default=socket.gethostname(), type=str, help="IP address of the server host")    
    parser.add_argument('-v', '--verbose', default=False, action='store_true', help="Display additional runtime information")
    parser.add_argument('--UDP', default=False, action='store_true', help="Use UDP datagrams")
        
    argData = parser.parse_args()
        
    SCRIPT_ARGS = argData
    return argData

    
class Server:
    def __init__(self, host, port, bufferSize=1024, allowOpenConnections=True, verbose=False):
        self.host = host
        self.port = port
        self.IS_ABORTED = False
        self.ServerThread = None
        
        self.P_BufferSize = bufferSize
        self.P_AllowOpenConnections = allowOpenConnections
        self.P_Verbose = verbose
        
        self.callbacks = { x: None for x in Callbacks }
        
        # Store open connections by the client id given at connect
        self.connections = {}
        
        # Create socket
        self.socket = socket.socket()
        
        # Bind socket to host and port
        self.socket.bind((self.host, self.port))

        # Let the socket listen for incoming conenctions
        self.socket.listen()
        self.socket.settimeout(2)
        
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
        
    def __HandleOpenConnection(self, clientNr, conn, address): 
        msg = []
        
        while not self.IS_ABORTED:            
            # receive data stream. it won't accept data packet greater than self.P_BufferSize bytes
            data = conn.recv(self.P_BufferSize)
            
            if data:            
                msg.append(data)
                
            # Message fully received?
            if len(data) < self.P_BufferSize:
                bytestring = b"".join(msg)
                
                if bytestring == b'\x04':
                    self.__vPrint(f"Connection termination requested by client ({clientNr} / {address})")
                    break
                
                self.__Call(Callbacks.MESSAGE_RECEIVED, (clientNr, address, bytestring))
                self.__vPrint(f"Message received ({clientNr} / {address}): {bytestring}")
                msg = []

        # Close the connection
        conn.close()
        del self.connections[clientNr]
        
        self.__Call(Callbacks.CONNECTION_TERMINATED, (clientNr, address))
        self.__vPrint("Connection " + str(address) + " terminated!")
        
    def __ListenerLoop(self):
        clientNr = 0
        
        while not self.IS_ABORTED:
            # Accept new connections or retry if timeout is reached (needed for Crtl+C to work)
            try:
                conn, address = self.socket.accept()
                self.__Call(Callbacks.NEW_CLIENT_CONNECTED, (clientNr, address))
                self.__vPrint(f"New connection({clientNr}) from {str(address)}")
            except:
                continue
            
            if not self.IS_ABORTED:
                if self.P_AllowOpenConnections:
                    t = PyThread(clientNr, self.__HandleOpenConnection, (clientNr, conn, address), f"Client-Communication thread - {clientNr}")
                    self.connections[clientNr] = (conn, address)
                else:
                    t = PyThread(clientNr, self.__HandleSingleTransmissionConnection, (clientNr, conn, address), f"Client-Service thread - {clientNr}")
                t.start()
                clientNr += 1
    
    def __vPrint(self, msg):
        if self.P_Verbose:
            print(msg)    
               
    def __Call(self, callback, parameters):
        """ Call any registered callback with the parameters provided and measure exec-time in case verbose is on"""
        
        ret = None
        cb = self.callbacks.get(callback)
        if cb is not None:
            fTimeStart = time.time()
            ret = cb(*parameters)
            self.__vPrint(f"    - {str(callback)} took: {time.time() - fTimeStart}s")
        return ret
        
    def __SendMessage(self, clientNr, msg):
        if clientNr not in self.connections:
            raise("No such connection registered!")
            
        # Send data to the client
        if type(msg) is bytes:
            self.connections[clientNr][0].send(msg)
        else:
            self.connections[clientNr][0].send(msg.encode())
        
    ##############################################
    #############                    #############
    ##########      PUBLIC METHODS      ##########
    #############                    #############
    ##############################################
    def Register(self, callbackType, callback):
        self.callbacks[callbackType] = callback
        
    def Stop(self):
        for clientNr in self.connections:
            try:
                self.__SendMessage(clientNr, b'\x04')
            except:
                pass
        self.IS_ABORTED = True
    
    def RunServer(self, runInMainThread=False):
        if runInMainThread:
            self.__ListenerLoop()
        else:
            self.ServerThread = PyThread(-1, self.__ListenerLoop, None, f"Listener thread")
            self.ServerThread.start()
    
    def SendMessage(self, clientNr, msg):
        if clientNr not in self.connections:
            raise("No such connection registered!")
            
        # Send data to the client
        t = PyThread(-1, self.__SendMessage, (clientNr, msg), f"Sender thread")
        t.start()
        

if __name__ == '__main__':   
    # Only add this handler if we are running the script in stand-alone mode
    signal.signal(signal.SIGINT, handler) 
    
    # Get cmd parameters
    args = argsParse()
    
    # Run
    SERVER_OBJ = Server(args.host, args.port, verbose=args.verbose)
    SERVER_OBJ.RunServer(True)