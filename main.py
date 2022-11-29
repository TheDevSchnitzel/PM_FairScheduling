import argparse
import pm4py
import utils.extractor as extractor
import utils.frames as frames
import alex
import math
import visualization.viz as viz
from simulation.simulator import Simulator
from simulation.objects.enums import Callbacks as SIM_Callbacks
from simulation.objects.enums import SimulationModes as SIM_Modes
from simulation.objects.enums import TimestampModes, OptimizationModes, SchedulingBehaviour
import utils.fairness as Fairness
import utils.congestion as Congestion
import utils.optimization as Optimization
import json
import signal
import time
from utils.activityDuration import EventDurationsByMinPossibleTime

G_KnownActivityDurations = {}
scriptArgs = None
simulator = None

def handler(signum, frame):
    global simulator
    global scriptArgs
    if simulator is not None:
        simulator.HandleSimulationAbort()
        simulator.ExportSimulationLog(scriptArgs.out, exportSimulatorStartEndTimestamp=False)
    exit(1)    
signal.signal(signal.SIGINT, handler)


def argsParse(): 
    global scriptArgs   
    
    parser = argparse.ArgumentParser()
    parser.add_argument('-l', '--log', default='logs/log.xes', type=str, help="The path to the event-log to be loaded")
    parser.add_argument('-o', '--out', default='logs/simLog.xes', type=str, help="The path to which the simulated event-log will be exported")

    parser.add_argument('--actDurations', default=None, type=str, help="A dictionary of activities and their duration \'{\'A\': 1}\'")
    #parser.add_argument('--precision', default=0.0, type=float)
    
    parser.add_argument('-F', '--Fair', default='W', type=str, help="W: Amount of work / T: Time spent working")
    parser.add_argument('--FairnessBacklogN', default=50, type=int, help="Number of passed windows to consider for fairness calculations")
    
    parser.add_argument('-v', '--verbose', default=False, action='store_true', help="Display additional runtime information")
    
    argData = parser.parse_args()
    
    if argData.actDurations is not None:
        print(argData.actDurations)
        global G_KnownActivityDurations
        G_KnownActivityDurations = json.loads(argData.actDurations)
    
    scriptArgs = argData
    return argData

 
 
 
 
def SimulatorFairness_Callback(simulatorState):
    global scriptArgs       
        
    if scriptArgs.Fair == "W":
        return Fairness.FairnessBacklogFair_WORK(simulatorState, BACKLOG_N=scriptArgs.FairnessBacklogN)
    elif scriptArgs.Fair == "T":
        return Fairness.FairnessBacklogFair_TIME(simulatorState, BACKLOG_N=scriptArgs.FairnessBacklogN)
    
    

def SimulatorCongestion_Callback(simulatorState):
    #segmentFreq, segmentTime, waitingTraces = Congestion.GetActiveSegments(activeTraces, simTime, SIM_Modes.KNOWN_FUTURE)
    
    # return Congestion.GetProgressByWaitingTimeInFrontOfActivity(A, segmentTime, waitingTraces)
    #return Congestion.GetProgressByWaitingNumberInFrontOfActivity(A, segmentFreq, waitingTraces)
    return {}

def SimulatorWindowStartScheduling_Callback(simulatorState, schedulingReadyResources, fRatio, cRatio):
    #return Optimization.SimulatorTestScheduling(activeTraces, A, P_AtoR, availableResources, simTime, windowDuration, fRatio, cRatio, optimizationMode)
    return Optimization.OptimizeActiveTraces(simulatorState, schedulingReadyResources, fRatio, cRatio)

def main():
    args = argsParse()
    
    log = pm4py.read_xes(args.log)
    
    no_events = sum([len(trace) for trace in log])
    windowNumber = 100 * math.ceil(math.sqrt(no_events))
    print(f"Number of windows: {windowNumber}")
    
    # Convert XES-Events into dict {'act', 'ts', 'res', 'single', 'cid'}
    event_dict = extractor.event_dict(log, res_info=True)
    
    # Pairs of events directly following each other, events triggering others (preceed them), events releasing others (follow them)
    pairs, triggers, releases = extractor.trig_rel_dicts(log, method='df')
    
    

    print('Computing frames, partitioning events into frames')
    windowWidth = frames.get_width_from_number(event_dict, windowNumber)
    bucketId_borders_dict = frames.bucket_window_dict_by_width(event_dict, windowWidth)
    eventsPerWindowDict, id_frame_mapping = frames.bucket_id_list_dict_by_width(event_dict, windowWidth) # WindowID: [List of EventIDs] , EventID: WindowID
        
    # Visualize the events over time with window borders
    # viz.WindowBorders(log, windowNumber)
    # alex.GetResourceLoadDistribution(A_set, R_set, S_set, event_dict, triggers, bucketId_borders_dict, id_frame_mapping, pairs, res_info=True, act_selection='all', res_selection='all')
    # alex.GetResourceTimeDistribution(R_set, event_dict, bucketId_borders_dict, id_frame_mapping, pairs, triggers)
    
    
    # Simulation -> Callback at the beginning / end of each window
    sim = Simulator(event_dict, eventsPerWindowDict, bucketId_borders_dict, 
                    simulationMode      = SIM_Modes.KNOWN_FUTURE,
                    optimizationMode    = OptimizationModes.FAIRNESS, 
                    #optimizationMode    = OptimizationModes.CONGESTION, 
                    schedulingBehaviour = SchedulingBehaviour.CLEAR_ASSIGNMENTS_EACH_WINDOW,
                    #schedulingBehaviour = SchedulingBehaviour.KEEP_ASSIGNMENTS,
                    endTimestampAttribute='ts', verbose=args.verbose)
    
    global simulator
    simulator = sim
    
    sim.Register(SIM_Callbacks.WND_START_SCHEDULING, SimulatorWindowStartScheduling_Callback)
    sim.Register(SIM_Callbacks.CALC_Fairness, SimulatorFairness_Callback)
    #sim.Register(SIM_Callbacks.CALC_Congestion, SimulatorCongestion_Callback)
    sim.Register(SIM_Callbacks.CALC_EventDurations, lambda x,y: EventDurationsByMinPossibleTime(x,y))
    sim.Run()
    sim.ExportSimulationLog(args.out)
    #sim.ExportSimulationLog('logs/simulated_congestion_log_WAITING_TRACE_COUNT.xes')

if __name__ == '__main__':
    main()
