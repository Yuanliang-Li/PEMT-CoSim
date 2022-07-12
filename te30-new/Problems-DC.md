# Problems for DC Microgrid Simulation
1. Select and model the circuit for power router to realize multiple ports and P2P power transmission.
    * Model the power router by formulating the circuit equations/state space equation, etc.
    * Determine the solver to solve the equation, e.g.,transient state solver or steady state solver.
    * how to solve the circuit when there are multiple sources and multiple loads?

2. Choose the routing algorithm for multiple ports
    * we can simply choose the the shortest path algorithm from the communication field and apply it in the power router.
    * When there are multiple sources and multiple loads, how to design the routing algorithm to avoid the conflict?
3. Choose the network topology considering the total cost.
4. How to model the house with PV, battery, and HVAC?
    * modeling of the PV
    * modeling of the battery
    * modeling of the HVAC
5. How to model the connection between the DC micogrid and the bulk transmission system?
6. When there is no transaction in the DC microgrid, what will be the topology of the system?
6. Can we add some events to the DC microgrid, such as the modeling of some faults in the networks? For example, one power router is faulty, one power line is disconnected, since we may want to research on the resilience of the packetized energy. 

