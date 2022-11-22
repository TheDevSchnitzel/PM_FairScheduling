import argparse
import pm4py
import utils.component as component
import utils.extractor as extractor
import utils.frames as frames
import alex
import math
import visualization.viz as viz
from simulation.simulator import Simulator
from simulation.objects.enums import Callbacks as SIM_Callbacks
from simulation.objects.enums import SimulationModes as SIM_Modes
from simulation.objects.enums import TimestampModes, OptimizationModes
import utils.fairness as Fairness
import utils.congestion as Congestion
import utils.optimization as Optimization
import json


G_KnownActivityDurations = {}

def argsParse():    
    parser = argparse.ArgumentParser()
    parser.add_argument('-l', '--log', default='logs/log.xes', type=str, help="The path to the event-log to be loaded")

    parser.add_argument('--actDurations', default=None, type=str, help="A dictionary of activities and their duration \'{\'A\': 1}\'")
    #parser.add_argument('--precision', default=0.0, type=float)
    
    argData = parser.parse_args()
    
    if argData.actDurations is not None:
        print(argData.actDurations)
        global G_KnownActivityDurations
        G_KnownActivityDurations = json.loads(argData.actDurations)
    
    return argData

 
 
 
 
def SimulatorFairness_Callback(activeTraces, completedTraces, LonelyResources, R, windows, currentWindow):
    
    #return Fairness.FairnessEqualWork(R)
    return Fairness.FairnessBacklogFair_WORK(activeTraces, completedTraces, LonelyResources, R, windows, currentWindow, BACKLOG_N=200)
    #return Fairness.FairnessBacklogFair_TIME(activeTraces, completedTraces, LonelyResources, R, windows, currentWindow, BACKLOG_N=50)
    

def SimulatorCongestion_Callback(activeTraces, completedTraces, LonelyResources, A, R, windows, currentWindow, simTime):
    print("Congestion:")
    segmentFreq, segmentTime, waitingTraces = Congestion.GetActiveSegments(activeTraces, simTime, SIM_Modes.KNOWN_FUTURE)
    
    # return Congestion.GetProgressByWaitingTimeInFrontOfActivity(A, segmentTime, waitingTraces)
    return Congestion.GetProgressByWaitingNumberInFrontOfActivity(A, segmentFreq, waitingTraces)

def SimulatorWindowStartScheduling_Callback(activeTraces, A, P_AtoR, availableResources, simTime, windowDuration, fRatio, cRatio, optimizationMode):
    return Optimization.OptimizeActiveTraces(activeTraces, A, P_AtoR, availableResources, simTime, windowDuration, fRatio, cRatio, optimizationMode)

    
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
    
    # All activities, resources and DFG-Segments as sets
    A_set, R_set, S_set, AtoR, RtoA = component.components(event_dict, pairs, res_info=True)
    

    print('Computing frames, partitioning events into frames')
    windowWidth = frames.get_width_from_number(event_dict, windowNumber)
    bucketId_borders_dict = frames.bucket_window_dict_by_width(event_dict, windowWidth)
    eventsPerWindowDict, id_frame_mapping = frames.bucket_id_list_dict_by_width(event_dict, windowWidth) # WindowID: [List of EventIDs] , EventID: WindowID
        
    # Visualize the events over time with window borders
    # viz.WindowBorders(log, windowNumber)
    # alex.GetResourceLoadDistribution(A_set, R_set, S_set, event_dict, triggers, bucketId_borders_dict, id_frame_mapping, pairs, res_info=True, act_selection='all', res_selection='all')
    # alex.GetResourceTimeDistribution(R_set, event_dict, bucketId_borders_dict, id_frame_mapping, pairs, triggers)
    
    
    # Simulation -> Callback at the beginning / end of each window
    sim = Simulator(event_dict, eventsPerWindowDict, AtoR, RtoA, bucketId_borders_dict, 
                    simulationMode=SIM_Modes.KNOWN_FUTURE,
                    optimizationMode = OptimizationModes.FAIRNESS, 
                    endTimestampAttribute='ts', 
                    verbose=False)
    sim.Register(SIM_Callbacks.WND_START_SCHEDULING, SimulatorWindowStartScheduling_Callback)
    sim.Register(SIM_Callbacks.CALC_Fairness, SimulatorFairness_Callback)
    # sim.Register(SIM_Callbacks.CALC_Congestion, SimulatorCongestion_Callback)
    sim.Run()
    sim.ExportSimulationLog('logs/simulated_fairness_log_EQUAL_WORK_BACKLOG_200_CONSTANTLY_RESSCHEDULED_NEW_GRAPH.xes')
    #sim.ExportSimulationLog('logs/simulated_congestion_log_WAITING_TRACE_COUNT.xes')

if __name__ == '__main__':
    main()
