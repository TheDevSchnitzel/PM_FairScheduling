# PM_FairScheduling

### Usage
 ```
  $ python main.py -l logs/log_ResReduced.xes -o logs/output.xes --F W --FairnessBacklogN 500
  ```
  - Useable Script Parameters:
     - -h, --help            show this help message and exit
     - -l LOG, --log LOG     The path to the event-log to be loaded
     - -o OUT, --out OUT     The path to which the simulated event-log will be exported
     - -F <TYPE>  W: Amount of work / T: Time spent working
     - --FairnessBacklogN <NUMBER> Number of passed windows to consider for fairness calculations
     - -v, --verbose         Display additional runtime information

### Requirements:

- This code is written in Python 3.9.13. In addition, you need to install the packages listed in requirements.txt.
- To install:
  ```
  $ pip install -r requirements.txt
  ```
