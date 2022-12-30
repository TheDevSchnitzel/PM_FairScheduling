from enum import Enum

class Callbacks(Enum):
    WND_START_SCHEDULING = 0
    WND_END_SCHEDULING   = 1
    CALC_Fairness        = 2
    CALC_Congestion      = 4
    CALC_EventDurations  = 8
    PREDICT_NEXT_ACT     = 16
    PREDICT_ACT_DUR      = 32
    
class TimestampModes(Enum):
    START   = 0
    END     = 1
    BOTH    = 2
    
class SimulationModes(Enum):
    KNOWN_FUTURE     = 0
    PREDICTED_FUTURE = 1
    EVENT_STREAM     = 2
    
class OptimizationModes(Enum):
    FAIRNESS   = 0
    CONGESTION = 1
    BOTH       = 2
    
class SchedulingBehaviour(Enum):
    KEEP_ASSIGNMENTS              = 0
    CLEAR_ASSIGNMENTS_EACH_WINDOW = 1

class EventStreamUpdates(Enum):
    CASE_NEW    = 0 # A new instance is created => Tell the simulator to track it
    CASE_CLOSED = 1 # The instance is done => No more tracking
    CASE_REQUEST_ACTIVITY = 2 # An instance wants to performs a certain activity => Does it align with the predicted one, also in the correct timewindow?
    CASE_EVENT  = 4 # An event has actually taken place and needs to be recorded in the instance tracker
    SCHEDULING_FORCE = 8 # Force the simulator to perform a scheduling and send the data immediately