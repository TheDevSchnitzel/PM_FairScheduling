from enum import Enum

class Callbacks(Enum):
    WND_START_SCHEDULING = 0
    WND_END_SCHEDULING   = 1
    CALC_Fairness        = 2
    CALC_Congestion      = 3
    
class TimestampModes(Enum):
    START   = 0
    END     = 1
    BOTH    = 2
    
class SimulationModes(Enum):
    KNOWN_FUTURE     = 0
    PREDICTED_FUTURE = 1
    