lsof -i tcp:5570 | awk 'NR!=1 {print $2}' | xargs kill
lsof -i tcp:23404 | awk 'NR!=1 {print $2}' | xargs kill
lsof -i tcp:5570 | awk 'NR!=1 {print $2}' | xargs kill
lsof -i tcp:23404 | awk 'NR!=1 {print $2}' | xargs kill
lsof -i tcp:5570 | awk 'NR!=1 {print $2}' | xargs kill
lsof -i tcp:23404 | awk 'NR!=1 {print $2}' | xargs kill

find -name "*.log" | xargs rm -f
find -name "*.csv" | xargs rm -f
find -name "*.out" | xargs rm -f
find -name "*.xml" | xargs rm -f
find -name "*.audit" | xargs rm -f
find -name "broker_trace.txt" | xargs rm -f
find -name "*metrics.json" | xargs rm -f
find -name "*dict.json" | xargs rm -f
find -name "*FNCS_Config.txt" | xargs rm -f
find -name "*HELICS_gld_msg.json" | xargs rm -f
find -name "*HELICS_substation.json" | xargs rm -f
find -name "*Weather_Config.json" | xargs rm -f
find -name "*substation.yaml" | xargs rm -f
find -name "*.dat" | xargs rm -f
rm ./fed_energyplus/output/*
rmdir ./fed_energyplus/output
find -name "*.bnd" | xargs rm -f
