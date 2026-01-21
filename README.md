# demo-pyigtlcompose
demo for trying to use py igtl between containers

Using an attempt to run novnc gui with a 3dslicer instance and a python pyigtl server in separate docker containers, and have them communicate using IGT Link.
This is being attempted on the two components of SlicerTMS https://github.com/lorifranke/SlicerTMS.


Currently, the tmsserver which has the python pyigtl server can connect to SlicerTMS when it is run locally on the machine but cannot connect to SlicerTMS when run in a the novnc gui container
First, the OpenIGTLinkIF extension does not properly install in the slicergui container, to remedy this the OpenIGTLinkIF extension need to be uninstalled and reinstalled through 3d SLicer's extension manager
