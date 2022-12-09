import argparse
import pm4py
import utils.extractor as extractor
import utils.frames as frames
import math
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
import multiprocessing
from multiprocessing import Pool
from utils.activityDuration import EventDurationsByMinPossibleTime
from predictor.predictor import PredictorService

G_KnownActivityDurations = {}
scriptArgs = None
simulator  = None
predictor  = None

def handler(signum, frame):
    global simulator
    global scriptArgs
    global predictor

    if simulator is not None:
        simulator.HandleSimulationAbort()
        simulator.ExportSimulationLog(scriptArgs.out, exportSimulatorStartEndTimestamp=False)
    
    if predictor is not None:
        predictor.StopService()
    exit(1)    
signal.signal(signal.SIGINT, handler)


def argsParse(cmdParameterLine = None): 
    global scriptArgs   
    
    parser = argparse.ArgumentParser()
    parser.add_argument('-l', '--log', default='logs/log.xes', type=str, help="The path to the event-log to be loaded")
    parser.add_argument('-o', '--out', default='logs/simLog.xes', type=str, help="The path to which the simulated event-log will be exported")

    parser.add_argument('--actDurations', default=None, type=str, help="A dictionary of activities and their duration \'{\'A\': 1}\'")
    #parser.add_argument('--precision', default=0.0, type=float)
    
    # Fairness parameters
    parser.add_argument('-F', '--Fair', default='W',choices=['W','T'], type=str, help="W: Amount of work / T: Time spent working")
    parser.add_argument('--FairnessBacklogN', default=50, type=int, help="Number of passed windows to consider for fairness calculations")
    
    # Congestion parameters
    parser.add_argument('-C', '--Congestion', default='N',choices=['N','T'], type=str, help="N: Number of cases in segment / T: Time spent in segment")
    parser.add_argument('--CongestionBacklogN', default=50, type=int, help="Number of passed windows to consider for calculations")
    
    # Multi-Simulation mode
    parser.add_argument('-M', '--MultiSimulation', default=None, type=str, help="Path to config file for running multiple simulations in parallel, containing commandline parameters with each line being one experiment")
    parser.add_argument('--MultiSimCores', default=int(multiprocessing.cpu_count() / 2), type=int, help="Amount of cores/processes to use for computation - Python can behave weird if the number is close to the amount of available logical cores")

    # Predictor parameters
    parser.add_argument('--PredictorPort', default=5050, type=int, help="Port of the server handling predictions")
    parser.add_argument('--PredictorHost', default=None, type=str, help="IP address of the server host handling predictions")
    parser.add_argument('--PredictorModelPath', default=None, type=str, help="Pretrained .h5 TF model used for predictions")
    
    parser.add_argument('-v', '--verbose', default=False, action='store_true', help="Display additional runtime information")
    
    
    if cmdParameterLine is None:
        argData = parser.parse_args()
    else:
        argData = parser.parse_args(cmdParameterLine.split())

    
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
    global scriptArgs

    if scriptArgs.Congestion == "N":
        return Congestion.GetProgressByWaitingNumberInFrontOfActivity(simulatorState, scriptArgs.CongestionBacklogN)
    elif scriptArgs.Congestion == "T":
        return Congestion.GetProgressByWaitingTimeInFrontOfActivity(simulatorState, scriptArgs.CongestionBacklogN)

def SimulatorWindowStartScheduling_Callback(simulatorState, schedulingReadyResources, fRatio, cRatio):
    #return Optimization.SimulatorTestScheduling(activeTraces, A, P_AtoR, availableResources, simTime, windowDuration, fRatio, cRatio, optimizationMode)
    return Optimization.OptimizeActiveTraces(simulatorState, schedulingReadyResources, fRatio, cRatio)




def Run(args):
    if type(args) == str:
        args = argsParse(args)

    log = pm4py.read_xes(args.log)
    
    no_events = sum([len(trace) for trace in log])
    windowNumber = 100 * math.ceil(math.sqrt(no_events))
    print(f"Number of windows: {windowNumber}")
    
    # Convert XES-Events into dict {'act', 'ts', 'res', 'single', 'cid'}
    event_dict = extractor.event_dict(log, res_info=True)
    
    # Pairs of events directly following each other, events triggering others (preceed them), events releasing others (follow them)
    # pairs, triggers, releases = extractor.trig_rel_dicts(log, method='df')
    
    print('Computing frames, partitioning events into frames')
    windowWidth = frames.get_width_from_number(event_dict, windowNumber)
    bucketId_borders_dict = frames.bucket_window_dict_by_width(event_dict, windowWidth)
    eventsPerWindowDict, id_frame_mapping = frames.bucket_id_list_dict_by_width(event_dict, windowWidth) # WindowID: [List of EventIDs] , EventID: WindowID
      
    # Simulation -> Callback at the beginning / end of each window
    sim = Simulator(event_dict, eventsPerWindowDict, bucketId_borders_dict, 
                    simulationMode      = SIM_Modes.KNOWN_FUTURE,
                    #optimizationMode    = OptimizationModes.FAIRNESS, 
                    optimizationMode    = OptimizationModes.CONGESTION, 
                    schedulingBehaviour = SchedulingBehaviour.CLEAR_ASSIGNMENTS_EACH_WINDOW,
                    #schedulingBehaviour = SchedulingBehaviour.KEEP_ASSIGNMENTS,
                    endTimestampAttribute='ts', verbose=args.verbose)
    
    global simulator
    simulator = sim
    
    sim.Register(SIM_Callbacks.WND_START_SCHEDULING, SimulatorWindowStartScheduling_Callback)
    sim.Register(SIM_Callbacks.CALC_Fairness, SimulatorFairness_Callback)
    sim.Register(SIM_Callbacks.CALC_Congestion, SimulatorCongestion_Callback)
    sim.Register(SIM_Callbacks.CALC_EventDurations, lambda x,y: EventDurationsByMinPossibleTime(x,y))

    sim.Register(SIM_Callbacks.PREDICT_NEXT_ACT, )
    sim.Register(SIM_Callbacks.PREDICT_ACT_DUR, )

    sim.Run()
    sim.ExportSimulationLog(args.out)
    #sim.ExportSimulationLog('logs/simulated_congestion_log_WAITING_TRACE_COUNT.xes')


def main():
    global predictor
    args = argsParse()

    # Is there a remote prediction service? -> If not set up a local one
    if args.PredictorHost is None and args.PredictorModelPath is not None:
        predictor = PredictorService(None, args.PredictorPort, args.PredictorModelPath)
    
    # Do we run a single simulation or multiple in parallel?
    if args.MultiSimulation is None:
        Run(args)
    else:
        argList = []
        with open(args.MultiSimulation, "r") as f:
            for x in f.readlines():
                cmd = x.replace('\n','').strip()
                if cmd != "":
                    argList.append(cmd)

        with Pool(max(1, args.MultiSimCores)) as p:
            p.map(Run, argList)
    

if __name__ == '__main__':
    main()
