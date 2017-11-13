#           Broadlink RM2 Python Plugin for Domoticz
#
#           Dev. Platform : Win10 x64 & Py 3.5.3 x86
#
#           Author:     zak45, 2017
#

# Below is what will be displayed in Domoticz GUI under HW
#
"""
<plugin key="BroadlinkRM2" name="Broadlink RM2" author="zak45" version="1.0.0" wikilink="http://www.domoticz.com/wiki/plugins/BroadlinkRM2.html" externallink="https://github.com/mjg59/python-broadlink">
    <params>
        <param field="Address" label="IP Address" width="200px" required="true" default="127.0.0.1"/>
        <param field="Mode1" label="Mac" width="100px" required="true" default="000000000000"/>
        <param field="Mode2" label="Folder to store ini files" width="300px" required="true" default="C:\\BroadlinkRM2"/>
        <param field="Mode3" label="Get Temperature Device" width="75px">
            <options>                
                <option label= "False" value="no"/>
                <option label= "True" value="yes" default="True"/>
            </options>
        </param>
        <param field="Mode6" label="Debug" width="75px">
            <options>
                <option label="True" value="Debug"/>
                <option label="False" value="Normal"  default="True" />
            </options>
        </param>
    </params>
</plugin>
"""
#
# Main Import
import Domoticz
import configparser
import datetime
import time
import codecs
#
#
# Required to import path is OS dependent
# Python framework in Domoticz do not include OS dependent path
#
import sys
import os 

if sys.platform.startswith('linux'):
    # linux specific code here
    sys.path.append(os.path.dirname(os.__file__) + '/dist-packages')
elif sys.platform.startswith('darwin'):
    # mac
    sys.path.append(os.path.dirname(os.__file__) + '/site-packages')
elif sys.platform.startswith('win32'):
    #  win specific
    sys.path.append(os.path.dirname(os.__file__) + '\site-packages')

#
import broadlink

#
isConnected = False
numberDev = 2
bypass = False
temp = 0
learnedCommand = "None"
sendCommand = ""
loadedCommand = ""
nbUpdate = 1

# Domoticz call back functions
#

# Executed once at HW creation/ update. Can create up to 255 devices.
def onStart():
    global numberDev, nbUpdate

    if Parameters["Mode6"] == "Debug":
        Domoticz.Debugging(1)
    if (len(Devices) == 0):
        if Parameters["Address"] == '127.0.0.1' and Parameters["Mode1"] == '000000000000':
            Domoticz.Device(Name="Discover",  Unit=1, Type=17, Image=2, Switchtype=17, Used=1).Create()
       
    if ( 1 not in Devices):
        Options =   {   "LevelActions"  :"||||" , 
                        "LevelNames"    :"Off|Learn|Test|Save|Reset" ,
                        "LevelOffHidden":"true",
                        "SelectorStyle" :"0"
                     }    
        Domoticz.Device(Name="Command",  Unit=1, TypeName="Selector Switch", Switchtype=18, Image=12, Options=Options, Used=1).Create()

    if ( 2 not in Devices and Parameters["Mode3"] == 'yes'):
        Domoticz.Device(Name="Temp",  Unit=2, TypeName="Temperature", Used=1).Create()

    DumpConfigToLog()
    Domoticz.Heartbeat(30)
    numberDev = len(Devices)

    Domoticz.Log("Connecting to: "+Parameters["Address"]+":"+Parameters["Mode1"])
    broadlinkConnect()
    UpdateDevice(1, 0, 'Off')    

    return True

def onMessage(Data, Status, Extra):    
    Domoticz.Log('onMessage: '+str(Data)+" ,"+str(Status)+" ,"+str(Extra))    
    return True

# executed each time we click on device thru domoticz GUI
def onCommand(Unit, Command, Level, Hue):
    global sendCommand

    Domoticz.Log("onCommand called for Unit " + str(Unit) + ": Parameter '" + str(Command) + "', Level: " + str(Level) + " , Connected : " + str(isConnected))
    
    Command = Command.strip()

    if (Command == 'Set Level'):
        if (Unit == 1):  # Command selector
            if (Level == 10): 
                    learn()
            if (Level == 20): 
                sendCommand = learnedCommand
                if learnedCommand == "None":
                    Domoticz.Log('Nothing to send')
                else:
                    send()                
            if (Level == 30):
                if learnedCommand == "None":
                    Domoticz.Log('Nothing to save')
                else:
                    save()
            if (Level == 40):
                if learnedCommand == "None":
                    Domoticz.Log('Nothing to reset')
                else:
                    reset()                        
        else:
            Domoticz.Error('Unit unknown')

    elif (Command == 'On'):

        if (Unit == 1 and Devices[1].Name.endswith("Discover")):  # Discovery
            if Discover():            
                UpdateDevice(Unit, 1, 'Found : ' + str(len(brodevices )) + ' device')
            else:
                Domoticz.Error('Not able to find Broadlink device')
        else:
            genCommand(Unit)

    elif (Command == 'Off'):

        if (Unit == 1 and Devices[1].Name.endswith("Discover")):  # Discovery
                UpdateDevice(Unit, 0, 'Off')    
        else:
            Domoticz.Error('Unit unknown')
    else:
        Domoticz.Error('Unknown command')

    return True

def onNotification(Name, Subject, Text, Status, Priority, Sound, ImageFile):

    Domoticz.Log("Notification: " + str(Name))

    return

# execution depend of Domoticz.Heartbeat(x) x in seconds
def onHeartbeat():
    global bypass, isConnected
    
    now = datetime.datetime.now()
    
    if bypass is True:    
        bypass = False
        return

    if Parameters["Mode3"] == "yes":

        if ((now.minute % 2) == 0):
            bypass = True
            if isConnected:
                if checkTemp():
                    UpdateDevice(2, 1, temp)
                else:
                    isConnected = False
            else:
                broadlinkConnect()
    else:
        if (now.minute % 4 == 0):
            broadlinkConnect()
            bypass = True

    return True

def onDisconnect():
    Domoticz.Log("onDisconnect called")
    return

# executed once when HW updated/removed
def onStop():
    Domoticz.Log("onStop called")
    return True

# Generic helper functions
def DumpConfigToLog():
    for x in Parameters:
        if Parameters[x] != "":
            Domoticz.Debug( "'" + x + "':'" + str(Parameters[x]) + "'")
    Domoticz.Debug("Device count: " + str(len(Devices)))
    for x in Devices:
        Domoticz.Debug("Device:           " + str(x) + " - " + str(Devices[x]))
        Domoticz.Debug("Device ID:       '" + str(Devices[x].ID) + "'")
        Domoticz.Debug("Device Name:     '" + Devices[x].Name + "'")
        Domoticz.Debug("Device nValue:    " + str(Devices[x].nValue))
        Domoticz.Debug("Device sValue:   '" + Devices[x].sValue + "'")
        Domoticz.Debug("Device LastLevel: " + str(Devices[x].LastLevel))
    return

# Update Device into DB
def UpdateDevice(Unit, nValue, sValue):
    # Make sure that the Domoticz device still exists (they can be deleted) before updating it 
    if (Unit in Devices):
        if (Devices[Unit].nValue != nValue) or (Devices[Unit].sValue != sValue):
            Devices[Unit].Update(nValue=nValue, sValue=str(sValue))
            Domoticz.Log("Update "+str(nValue)+":'"+str(sValue)+"' ("+Devices[Unit].Name+")")
    return

def genCommand(Unit):
    global loadedCommand, sendCommand, nbUpdate
    
    Domoticz.Log('Generate on Command for learned code stored on unit :' + str(Unit))

    path=str(Parameters["Mode2"]) + "\\" + str(Parameters["Key"]) + "-" + str(Parameters["HardwareID"]) + "-" + str(Unit) + ".ini"

    if not os.path.exists(path):
        Domoticz.Error(' ini file not found: ' + str(path))
        return
 

    config = configparser.ConfigParser()
    config.read(path)
    loadedCommand = config.get("LearnedCode", str(Unit))
    if Parameters["Mode6"] == "Debug":
        Domoticz.Log(" Code loaded : " + loadedCommand)        
    sendCommand = loadedCommand
    if broadlinkConnect():
        send()
    if Parameters["Mode6"] == "Debug":
        Domoticz.Log(' <b> Command line : ' + '"' + Parameters['HomeFolder'] + 'plugin_send.py' +  '" ' + path + ' </b>')

    UpdateDevice(Unit,1,'On-'+str(nbUpdate))
    nbUpdate +=1

    return

# save learned code and create Domoticz device
def save():
    global path, learnedCommand, Unit, numberDev

    numberDev +=1
    path=str(Parameters["Mode2"]) + "\\" + str(Parameters["Key"]) + "-" + str(Parameters["HardwareID"]) + "-" + str(numberDev) + ".ini"

    if os.path.exists(path):
        Domoticz.Error('File exist : ' + path)
        return False
    else:
        try:
            create_config(path,str(numberDev),learnedCommand)
        except:
            Domoticz.Error('Not able to create : ' + path)
            return False
    try:
        Domoticz.Device(Name=str(Parameters["HardwareID"])+"-" + str(numberDev),  Unit=numberDev, TypeName="Selector Switch", Type=244, Switchtype=9, Subtype=73).Create()
    except:
        Domoticz.Error('Not able to create device')
        return False
    
    UpdateDevice(1, 0, 'Off')   
    learnedCommand = "None" 
    if Parameters["Mode6"] == "Debug":
        Domoticz.Log(" <b> Command line : " + Parameters["HomeFolder"] + "plugin_send.py " + path + " </b>")
    
    return True

def reset():
    global learnedCommand
    
    UpdateDevice(1, 0, 'Off')   
    learnedCommand = "None" 
    if Parameters["Mode6"] == "Debug":
        Domoticz.Log("Reset learned command")
    
    return True

# discover Broadlink device on the Network
def Discover():
    global brodevices, broip

    Domoticz.Log("All plugin system is on pause for 5s...")
    brodevices = broadlink.discover(timeout=5)
    Domoticz.Log("Found " + str(len(brodevices )) + " broadlink devices")

    if str(len(brodevices )) == 0:
        return False
    
    for index, item in enumerate(brodevices):

        brodevices[index].auth()

        broip = brodevices[index].host
        broip = str(broip)
        Domoticz.Log( "<b>Device " + str(index + 1) +" Host address = " + broip[1:19] + "</b>")
        macadd = ''.join(format(x, '02x') for x in brodevices[index].mac[::-1])
        macadd = str(macadd)        
        Domoticz.Log( "<b>Device " + str(index + 1) +" MAC address = " + macadd + "</b>")

    return True

# Put Broadlink on Learn , packet received converted in Hex
def learn():
    global learnedCommand,learnedCommand1,learnedCommand2
    
    broadlinkConnect()

    Domoticz.Log("All plugin system is on pause for 5s...")
    Domoticz.Log("When Broadlink led is lit press the button on your remote within 5 seconds")
    
    device.enter_learning()

    time.sleep(5)    

    ir_packet = device.check_data()
    if Parameters["Mode6"] == "Debug":
        Domoticz.Log(str(ir_packet))
    
    if str(ir_packet) == "None":
        Domoticz.Log('Command not received')
        learnedCommand= "None"
        UpdateDevice(1, 0, ' ')
        return False

    #learnedCommand=str(ir_packet.hex())
    learnedCommand=str.replace(str.replace(str(codecs.encode(ir_packet, 'hex_codec')),"b'",""),"'","")
    #learnedCommand2=str(binascii.hexlify(ir_packet))
    if Parameters["Mode6"] == "Debug":
        Domoticz.Log(learnedCommand)
        
    Domoticz.Log( "Code written in memory" )
    UpdateDevice(1, 1, '10')

    return True

# send Hex command
def send():
    global sendCommand

    if not sendCommand:
        Domoticz.Error('Nothing to send')
        return False
    
    sendCommand = bytes.fromhex(sendCommand)
    #sendCommand=binascii.unhexlify(sendCommand)
    if Parameters["Mode6"] == "Debug":
        Domoticz.Log(str(sendCommand))

    try:
        device.send_data(sendCommand)
        Domoticz.Log( "Code Sent....")
    except:
        Domoticz.Error( "Code Sent WARNING....Probably timeout")
        return False

    return True

#Create a config file
def create_config(path,Unit,learnedCommand):
    
    config = configparser.ConfigParser()
    config['DEFAULT'] = {   'PluginKey'     : Parameters["Key"],
                            'PluginName'    : Parameters["Name"],
                            'PluginFolder'  : Parameters["HomeFolder"],
                            'HardwareID'    : Parameters["HardwareID"],
                            'Unit'          : Unit
                        }

    config['Device'] = {    'Host'  : Parameters["Address"],
                            'Mac'   : Parameters["Mode1"]
                        }
    config['LearnedCode'] = {}    
    UniteCode = config['LearnedCode']
    UniteCode[str(Unit)] = learnedCommand
    try:
        with open(path, 'w') as configfile:
            config.write(configfile)
    except IOError:
        Domoticz.Error('Error create config file')
    
    if Parameters["Mode6"] == "Debug":
        Domoticz.Log( "ini file creation...." + path)    

    return

# connect to Broadlink
def broadlinkConnect():
    global device, isConnected

    try:
        device = broadlink.rm(host=(Parameters["Address"],80), mac=bytearray.fromhex(Parameters["Mode1"]))
        device.auth()
        device.host
        isConnected = True
        Domoticz.Log( "Connected to Broadlink device.")        
    except:
        Domoticz.Error( "Error Connecting to Broadlink device....")
        isConnected = False
        return False

    return True

# get temperature
def checkTemp():
    global temp, device

    try:
        temp=device.check_temperature()
    except:
        Domoticz.Error( "Error getting temperature data from Broadlink device....Timeout")
        return False

    if temp > 60:
        return False

    return True