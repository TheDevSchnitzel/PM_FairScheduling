from distutils.log import error
import time
from .objects.traceInstance import Trace
from .objects.enums import Callbacks, TimestampModes, SimulationModes, SchedulingBehaviour
from datetime import datetime, timezone
from pm4py.objects.log.exporter.xes import exporter as xes_exporter
from pm4py.objects.conversion.log import converter as log_converter
import pandas as pd

class Simulator:
    
    def __init__(self, event_dict, eventsPerWindowDict, windows, simulationMode, optimizationMode, startTimestampAttribute=None, endTimestampAttribute=None, verbose=False):
        self.P_Events = event_dict
        self.P_EventsPerWindowDict = eventsPerWindowDict
        self.P_Windows = windows
        self.P_WindowCount = len(windows)
        self.P_Verbose = verbose
        self.P_SimulationMode = simulationMode
        self.P_OptimizationMode = optimizationMode
        self.P_SchedulingBehaviour = SchedulingBehaviour.CLEAR_ASSIGNMENTS_EACH_WINDOW
        
        self.P_AtoR, self.P_RtoA = self.__GetAttributeResourceMapping()        
        self.R = [r for r in self.P_RtoA.keys()]
        self.A = [a for a in self.P_AtoR.keys()]
        
        self.completedTraces = list()
        self.callbacks = { x: None for x in Callbacks }
        
        self.SimulatedTimestep = 0    
        self.traceCount = 0        
        self.traces = []
        self.activeTraces = []

        
        # Determine what type of timestamps are available for the simulation
        if startTimestampAttribute is None and endTimestampAttribute is None:
            raise Exception("At least one of the parameters 'startTimestampAttribute' and 'endTimestampAttribute' needs to be set!")
        elif startTimestampAttribute is not None and endTimestampAttribute is not None:
            self.TimestampMode = TimestampModes.BOTH
            self.TimestampAttribute = (startTimestampAttribute, endTimestampAttribute)
        elif startTimestampAttribute is not None:
            self.TimestampMode = TimestampModes.START
            self.TimestampAttribute = startTimestampAttribute
        elif endTimestampAttribute is not None:
            self.TimestampMode = TimestampModes.END
            self.TimestampAttribute = endTimestampAttribute
        
        # Build trace objects from the event data
        self.__GenerateTraces()
        
        # Get resources that only perform activities that no other resource can perform
        self.LonelyResources = self.__GetLonelyResources()
        
        # Startup-Information Display
        self.__vPrint(f'### Simulator Data ###')
        self.__vPrint(f'    -> TimestampMode: {str(self.TimestampMode)}')
        self.__vPrint(f'    -> SimulationMode: {str(self.P_SimulationMode)}')
        self.__vPrint(f'    -> SchedulingBehaviour: {str(self.P_SchedulingBehaviour)}')
        self.__vPrint(f'    -> LonelyResources: {self.LonelyResources}')
        self.__vPrint(f'    -> Activity-Resource Mappping: {self.P_AtoR}')

    ##############################################
    #############                    #############
    ##########     PRIVATE METHODS      ##########
    #############                    #############
    ##############################################
    def __vPrint(self, msg):
        if self.P_Verbose:
            print(msg)    
    
    def __GetAttributeResourceMapping(self):
        """ Get the mapping between Resources and Activities in order """
        AtoR = {}
        RtoA = {}
        
        for _, e in self.P_Events.items():
            if e['act'] not in AtoR:
                AtoR[e['act']] = []                
            if e['res'] not in RtoA:
                RtoA[e['res']] = []
            
            if e['res'] not in AtoR[e['act']]:
                AtoR[e['act']].append(e['res'])            
            if e['act'] not in RtoA[e['res']]:
                RtoA[e['res']].append(e['act'])
        
        return {a: sorted(AtoR[a]) for a in AtoR}, {r: sorted(RtoA[r]) for r in RtoA}
        
    def __GetLonelyResources(self):
        """Lonely resources are carrying out activities without any other resource taking part in the same activity
        They have to be treated differently for e.g. fairness calculations"""
        
        res = {r:[] for r in self.R}
        
        for _, rSet in self.P_AtoR.items():
            rList = list(rSet)
            if len(rList) > 1:
                for r in rList:
                    res[r] += [l for l in rList if l != r]
                
        return sorted([r for r in res if len(list(set(res[r]))) == 0])
        
    def __GenerateTraces(self):
        eventTraces = {cid:[] for cid in set([e['cid'] for _, e in self.P_Events.items()])}
        
        # Build the event traces
        for _, e in self.P_Events.items():
            eventTraces[e['cid']].append(e)
        
        # Sort events in traces by timestamp
        for cid in eventTraces.keys():
            if self.TimestampMode == TimestampModes.START or self.TimestampMode == TimestampModes.END:
                eventTraces[cid].sort(key=lambda e: e[self.TimestampAttribute])
                self.traces.append(Trace(str(cid), [(e['act'], e['res'], e[self.TimestampAttribute]) for e in eventTraces[cid]]))
            else:
                eventTraces[cid].sort(key=lambda e: e[self.TimestampAttribute[0]])
                self.traces.append(Trace(str(cid), [(e['act'], e['res'], e[self.TimestampAttribute[0]], e[self.TimestampAttribute[1]]) for e in eventTraces[cid]]))
        
            print(self.traces[-1].future)
        self.traceCount = len(self.traces)
    
    def __GetNewlyBeginningTraces(self, windowLower, windowUpper):
        activeTracesList = [x for x in self.traces if x.NextEventInWindow(windowLower, windowUpper)]
        
        # Remove newly active traces from To-Do list
        for x in activeTracesList:
            self.traces.remove(x)
            
        return sorted(activeTracesList, key=lambda x: x.case)
              
    def __Call(self, callback, parameters):
        """ Call any registered callback with the parameters provided and measure exec-time in case verbose is on"""
        
        ret = None
        cb = self.callbacks.get(callback)
        if cb is not None:
            fTimeStart = time.time()
            ret = cb(*parameters)
            self.__vPrint(f"    - {str(callback)} took: {time.time() - fTimeStart}s")
        return ret
    
    def __RunScheduler(self, currentSchedule, currentWindow, currentWindowDuration):
        # Calculate fairness ratio
        fRatio = self.__Call(Callbacks.CALC_Fairness, (self.activeTraces, self.completedTraces, self.LonelyResources, self.R, self.P_Windows, currentWindow))
        
        # Calculate congestion ratio
        cRatio = self.__Call(Callbacks.CALC_Congestion, (self.activeTraces, self.completedTraces, self.LonelyResources, self.A, self.R, self.P_Windows, currentWindow, self.SimulatedTimestep))
        
        # Add resources which will become free during this window to be scheduled
        schedulingReadyResources = {r: currentWindowDuration for r in self.R}
        for trace in self.activeTraces:
            if trace.HasRunningActivity():
                remTime = trace.GetRemainingActivityTime(self.TimestampMode, self.SimulatedTimestep) 
                if remTime < currentWindowDuration:
                    schedulingReadyResources[trace.currentAct[1]] = currentWindowDuration - remTime
        
        # Call to get the new schedule (most likely a MIP scheduling)
        if self.P_SchedulingBehaviour == SchedulingBehaviour.KEEP_ASSIGNMENTS:
            # Get traces without a current schedule (no need to double schedule traces if they have already been scheduled)
            unscheduledTraces = [x for x in self.activeTraces if x.case not in schedule]
            
            if len(unscheduledTraces) > 0:
                # Perform the scheduling callback (Leave it to the Sim-User to provide a way to calculate the schedule)
                newSchedule = self.__Call(Callbacks.WND_START_SCHEDULING, (unscheduledTraces, self.A, self.P_AtoR, schedulingReadyResources, self.SimulatedTimestep, currentWindowDuration, fRatio, cRatio, self.P_OptimizationMode))
                
                # Merge schedule dicts (Trace-ID is key, no duplicates ;) )
                schedule = {**currentSchedule, **newSchedule}
                            
        elif self.P_SchedulingBehaviour == SchedulingBehaviour.CLEAR_ASSIGNMENTS_EACH_WINDOW:
            schedule = self.__Call(Callbacks.WND_START_SCHEDULING, (self.activeTraces, self.A, self.P_AtoR, schedulingReadyResources, self.SimulatedTimestep, currentWindowDuration, fRatio, cRatio, self.P_OptimizationMode))
        
        return schedule
                
    
    ##############################################
    #############                    #############
    ##########      PUBLIC METHODS      ##########
    #############                    #############
    ##############################################
    def Register(self, callbackType, callback):
        self.callbacks[callbackType] = callback
         
    def Run(self):
        currentWindow = -1
        currentWindowLower = self.P_Windows[0][0]
        currentWindowUpper = self.P_Windows[0][1]
        self.SimulatedTimestep = currentWindowLower
        
        simStart = time.time()
        self.__vPrint("Simulation started at %s" % (datetime.now().strftime("%d/%m/%Y, %H:%M:%S")))
        self.__vPrint(f"    Traces: {self.traceCount}")
                
        # Create a list of initially active traces
        self.activeTraces = self.__GetNewlyBeginningTraces(currentWindowLower, currentWindowUpper)
        
        # Initially all resources are available for the full window time 
        availableResources = {r: currentWindowUpper - currentWindowLower for r in self.R}
        
        # An empty schedule
        schedule = {}
        
        # Enter the simulation loop
        while len(self.completedTraces) != self.traceCount:            
            
            # If a new window has begun, run the planning again
            if currentWindowUpper < self.SimulatedTimestep or currentWindow == -1:
                currentWindow += 1
                
                if currentWindow < len(self.P_Windows):
                    currentWindowLower = self.P_Windows[currentWindow][0]
                    currentWindowUpper = self.P_Windows[currentWindow][1]
                else:
                    currentWindowLower = self.SimulatedTimestep
                    currentWindowUpper = self.SimulatedTimestep + (self.P_Windows[0][1] - self.P_Windows[0][0])
                    self.P_Windows[currentWindow] = (currentWindowLower, currentWindowUpper)
                    
                self.__vPrint(f' ### New Window {currentWindow} - {datetime.fromtimestamp(currentWindowLower)} <==> {datetime.fromtimestamp(currentWindowUpper)} ###')
                self.__vPrint(f'    - Traces (Active / Finished / Total): {len(self.activeTraces)} / {len(self.completedTraces)} / {self.traceCount}')
                self.__vPrint(f'    - Progress: {len(self.completedTraces) / self.traceCount * 100}% complete traces')
                            
                # Start new traces that arrive in this window
                self.activeTraces = self.activeTraces + self.__GetNewlyBeginningTraces(currentWindowLower, currentWindowUpper)
                
                # Call the scheduler
                schedule = self.__RunScheduler(schedule, currentWindow, currentWindowUpper - currentWindowLower)
                
            
                
                
            # Do the simulation that has to be done at each timestep (second???)
            # Apply pre-calculated schedule
            # Begin new / end old traces
            
            # Speedup by trying to skip unimportant timesteps in the simulation
            minRemainingTime = currentWindowUpper - self.SimulatedTimestep
            
            # First stop all activities ending in this timestep
            for trace in self.activeTraces:
                if trace.HasRunningActivity():
                    remainingTime = trace.GetRemainingActivityTime(self.TimestampMode, self.SimulatedTimestep)
                    if remainingTime <= 0:
                        trace.EndCurrentActivity(self.SimulatedTimestep)
                            
                        # Return the now free resource to the resource pool (Resource actually used by newest event in history of trace)
                        availableResources[trace.history[-1][2]] = currentWindowUpper - self.SimulatedTimestep
                        self.__vPrint(f"    -> Trace '{trace.case}' has ended freeing res '{trace.history[-1][2]}' at simtime {self.SimulatedTimestep}")
                            
                        if trace.HasEnded():
                            self.activeTraces.remove(trace)
                            self.completedTraces.append(trace)
                    elif remainingTime < minRemainingTime:
                        minRemainingTime = remainingTime
                        
                # self.vPrint(f"    -> Trace '{trace.case}', Waiting: '{trace.IsWaiting()}', Running: '{trace.HasRunningActivity()}'")
                            
            # As the previous step released new resources, now start new activities that might need them (double assigned resources)
            for trace in self.activeTraces:
                if trace.IsWaiting():
                    # It the trace on the schedule?
                    traceSched = schedule.get(trace.case)
                    if traceSched is not None and traceSched['StartTime'] <= self.SimulatedTimestep:
                        if traceSched['Resource'] in availableResources:
                            self.__vPrint(f"    -> Trace '{trace.case}' about to start on res '{traceSched['Resource']}' at simtime {self.SimulatedTimestep}")
                            
                            # Assign the next activity a resource and let it run
                            trace.StartNextActivity(self.P_SimulationMode, self.SimulatedTimestep, traceSched['Resource'])
                            
                            # Remove trace from current schedule
                            del availableResources[traceSched['Resource']]
                            del schedule[trace.case]
                            
                            # Again try to determine whether we can skip unimportant timesteps for the simulation
                            remainingTime = trace.GetRemainingActivityTime(self.TimestampMode, self.SimulatedTimestep)
                            if remainingTime < minRemainingTime:
                                minRemainingTime = remainingTime
                                
                            # All resources busy, try again next simulation step
                            if len(availableResources) == 0:
                                break
                                
                        # else:
                        #     print("    -> Warning: Resource scheduled but currently unavailable!")

            if minRemainingTime > 0:
                self.__vPrint(f"Timestep: {self.SimulatedTimestep} - Skipping: {minRemainingTime}")
                self.SimulatedTimestep += minRemainingTime
            else:
                self.SimulatedTimestep += 1
                
        print(f"Total time for simulation {time.time() - simStart :.1f}s") 
        print(f"    -> Windows simulated {currentWindow + 1} (given: {self.P_WindowCount} / additional: {(currentWindow + 1) - self.P_WindowCount})")
    
    def HandleSimulationAbort(self):
        """ As the 'ExportSimulationLog' saves the Historic data of a trace: Add abort events to show how far the process got"""
        
        print(f" ###################################### ")
        print(f" ######### SIMULATION ABORTED ######### ")
        print(f" ###################################### ")
        
        stats = {
            'RunningTraces': 0,
            'WaitingTraces': 0,
            'FinishedTraces': len(self.completedTraces),
            'NotStartedTraces':  len(self.traces)
        }
        
        for trace in self.activeTraces:
            if trace.HasRunningActivity():
                stats['RunningTraces'] += 1
                trace.currentAct = (trace.currentAct[0],trace.currentAct[1],(trace.currentAct[2][0] + '_ABORTED', trace.currentAct[2][1],trace.currentAct[2][2]))
                trace.EndCurrentActivity(self.SimulatedTimestep)
            else:                
                stats['WaitingTraces'] += 1
                trace.history.append((self.SimulatedTimestep, self.SimulatedTimestep, 'SIMULATOR', ('ABORTED','SIMULATOR',self.SimulatedTimestep)))
            
            self.completedTraces.append(trace)
        
        for trace in self.traces:
            trace.history.append((self.SimulatedTimestep, self.SimulatedTimestep, 'SIMULATOR', ('ABORTED_BEFORE_START','SIMULATOR',self.SimulatedTimestep)))
            self.completedTraces.append(trace)
        
        print(stats)
        
    def ExportSimulationLog(self, logPath, exportSimulatorStartEndTimestamp=False):
        log = []
        
        # Determine which timestamps to use
        ts = 1 # By default TimestampModes.END
        if self.TimestampMode == TimestampModes.BOTH or exportSimulatorStartEndTimestamp:
            ts = None
        elif self.TimestampMode == TimestampModes.START:
            ts = 0
            
        colCase = []
        colAct = []
        colRes = []
        colTS = []
        colTS_End = []
            
        for trace in self.completedTraces:
            if ts is not None:
                for x in trace.history:
                    colCase.append(trace.case)
                    colAct.append(x[3][0])
                    colRes.append(x[2])
                    colTS.append(datetime.fromtimestamp(x[ts], timezone.utc))
                    # History entry : (start_ts, end_ts, res, (a,r,ts)
            else:
                for x in trace.history:
                    colCase.append(trace.case)
                    colAct.append(x[3][0])
                    colRes.append(x[2])
                    colTS.append(datetime.fromtimestamp(x[0], timezone.utc))
                    colTS_End.append(datetime.fromtimestamp(x[1], timezone.utc))
        
        if ts is not None:
            df = pd.DataFrame(list(zip(colCase, colAct, colTS, colRes)), columns=['case', 'concept:name', 'time:timestamp', 'org:resource'])
        else:
            df = pd.DataFrame(list(zip(colCase, colAct, colTS, colTS_End, colRes)), columns=['case', 'concept:name', 'time:start','time:end', 'org:resource'])
            
        parameters = {log_converter.Variants.TO_EVENT_LOG.value.Parameters.CASE_ID_KEY: 'case'}
        el = log_converter.apply(df, parameters=parameters, variant=log_converter.Variants.TO_EVENT_LOG)

        xes_exporter.apply(el, logPath)
        del log
        del df
        del el