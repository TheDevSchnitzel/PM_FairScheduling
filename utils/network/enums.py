from enum import Enum

class Callbacks(Enum):
    NEW_CLIENT_CONNECTED  = 0
    MESSAGE_RECEIVED      = 1
    CONNECTION_TERMINATED = 2