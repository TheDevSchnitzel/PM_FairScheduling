import networkx as nx

G = nx.DiGraph()
                        
G.add_edge('s', 'i1', capacity=100, weight=0) 
G.add_edge('s', 'i2', capacity=100, weight=0) 
G.add_edge('s', 'i3', capacity=100, weight=0) 
G.add_edge('s', 'i4', capacity=100, weight=0) 
G.add_edge('s', 'i5', capacity=100, weight=0) 

G.add_edge('i1', 'R1', weight = 10, capacity = 80)
G.add_edge('i2', 'R1', weight = 12, capacity = 70)
G.add_edge('i2', 'R2', weight = 12, capacity = 70)
            

G.add_edge('R1', 't', capacity=100, weight=0)
G.add_edge('R2', 't', capacity=100, weight=0)
    
    
M = nx.max_flow_min_cost(G, 's', 't')
        
print(M)