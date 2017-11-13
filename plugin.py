#           Broadlink RM2 Python Plugin for Domoticz
#
#           Dev. Platform : Win10 x64 & Py 3.5.3 x86
#
#           Author:     zak45, 2017
#           1.1.0:  code compatible py  3.x
#           2.0.0:  import from e-Control or any other ini file with similar structure
#                   webserver for file transfer
#                   Off action managed for generated devices
#                   clean action to erase files from import folder
#           3.0.0:  Add Remote Control device with custom codes on ini file
#                   Broadlink lib to v 0.5.0: timeout error solved, Pad the payload for AES encryption (16) (TC2 switch), Add support for pure python AES implementation ...
#

# Below is what will be displayed in Domoticz GUI under HW
#
"""
<plugin key="BroadlinkRM2" name="Broadlink RM2 with Kodi Remote" author="zak45" version="3.0.0" wikilink="http://www.domoticz.com/wiki/plugins/BroadlinkRM2.html" externallink="https://github.com/mjg59/python-broadlink">
    <params>
        <param field="Address" label="IP Address" width="200px" required="true" default="127.0.0.1"/>
        <param field="Mode1" label="Mac" width="100px" required="true" default="000000000000"/>
        <param field="Mode2" label="Folder to store ini files" width="300px" required="true" default="C:/BroadlinkRM2"/>
        <param field="Mode3" label="Get Temperature Device" width="75px">
            <options>                
                <option label= "False" value="no"/>
                <option label= "True" value="yes" default="True"/>
            </options>
        </param>
        <param field="Mode4" label="Generate import Device" width="75px">
            <options>                
                <option label= "False" value="no"/>
                <option label= "True" value="yes" default="True"/>
            </options>
        </param>
        <param field="Mode5" label="Port for HTTP server" width="50px" required="true" default="9000"/>
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
import subprocess
import socket
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
isRunning = False
custom = ""
clear = False
RemoteCommand = ""

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

    if ( 254 not in Devices ):
        Domoticz.Device(Name="Remote",  Unit=254, Type=17, Image=2, Switchtype=17, Used=1).Create()

    if ( 255 not in Devices and Parameters["Mode4"] == 'yes'):
        Options =   {   "LevelActions"  :"||||" , 
                        "LevelNames"    :"Off|WebStart|Generate|Import|Clear" ,
                        "LevelOffHidden":"true",
                        "SelectorStyle" :"0"
                     }    
        Domoticz.Device(Name="Import",  Unit=255, TypeName="Selector Switch", Switchtype=18, Image=12, Options=Options, Used=1).Create()

    DumpConfigToLog()
    Domoticz.Heartbeat(30)

    numberDev = len(Devices) - 1    
    if (255 in Devices):
        UpdateDevice(255, 0, 'Off')
        numberDev = numberDev - 1
    
    Domoticz.Log("Connecting to: "+Parameters["Address"]+":"+Parameters["Mode1"])
    broadlinkConnect()
    UpdateDevice(1, 0, 'Off')

    if not os.path.exists(Parameters["Mode2"] + "/import"):
        os.makedirs(Parameters["Mode2"] + "/import")
    if not os.path.exists(Parameters["Mode2"] + "/remote"):
        os.makedirs(Parameters["Mode2"] + "/remote")

    Domoticz.Log("Device Number begin to : "+ str(numberDev))

    genRemote()

    return True

# executed each time we click on device thru domoticz GUI
def onCommand(Unit, Command, Level, Hue):
    global sendCommand, isRunning, learnedCommand

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
                    custom = ""
                    if save():
                        UpdateDevice(1,0,'Off')
                        learnedCommand = "None" 
            if (Level == 40):
                if learnedCommand == "None":
                    Domoticz.Log('Nothing to reset')
                else:
                    reset()
        elif (Unit == 255):
            if (Level == 10):                
                if startWeb():
                    isRunning = True
                    UpdateDevice(255,1,'10')
                else:
                    UpdateDevice(255,0,'Off')
                    Domoticz.Error ('Not able to start Web server')
            if (Level == 20):                
                if createIniImport():
                    UpdateDevice(255,1,'20')
                else:
                    UpdateDevice(255,0,'Off')
                    Domoticz.Error ('Error with json files to import')
            if (Level == 30):  
                clear = False              
                if manageIniImport(clear):
                    UpdateDevice(255,1,'30')
                else:
                    UpdateDevice(255,0,'Off')
            if (Level == 40):  
                clear = True              
                if manageIniImport(clear):
                    UpdateDevice(255,1,'40')
                else:
                    UpdateDevice(255,0,'Off')
        else:
            Domoticz.Error('Unit unknown')

    elif (Command == 'On'):

        if (Unit == 1 and Devices[1].Name.endswith("Discover")):  # Discovery
            if Discover():            
                UpdateDevice(Unit, 1, 'Found : ' + str(len(brodevices )) + ' device')
            else:
                Domoticz.Error('Not able to find Broadlink device')        
        elif (Unit==254 and RemoteCommand != "" ):
                UpdateDevice(Unit, 1, 'On')
        else:
            genCommand(Unit)

    elif (Command == 'Off'):

        if (Unit == 1 and Devices[1].Name.endswith("Discover")):  # Discovery
                UpdateDevice(Unit, 0, 'Off')              
        else:            
            try:    
                UpdateDevice(Unit, 0, 'Off')
            except:
                Domoticz.Error('Unit error update')
                raise
    elif ( Unit == 254):
        if remoteSend(Command):
            UpdateDevice(Unit, 1, Command)
        else:
            UpdateDevice(Unit, 1, 'undefined')

    else:
        Domoticz.Error('Unknown command')
            
    return True

# execution depend of Domoticz.Heartbeat(x) x in seconds
def onHeartbeat():
    global bypass, isConnected, isRunning
    
    now = datetime.datetime.now()

    if (255 in Devices and isRunning == True):
            isAlive()
    
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
        if (now.minute % 5 == 0):
            broadlinkConnect()
            bypass = True

    return True

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

# generate command to execute and update name in ini file if necessary
def genCommand(Unit):
    global loadedCommand, sendCommand, nbUpdate
    
    Domoticz.Log('Generate on Command for learned code stored on unit/ini :' + str(Unit))

    path=str(Parameters["Mode2"]) + "/" + str(Parameters["Key"]) + "-" + str(Parameters["HardwareID"]) + "-" + str(Unit) + ".ini"

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

    if Unit in Devices:
        try:
            UpdateDevice(Unit,1,'On-'+str(nbUpdate))
            nbUpdate +=1
        except:
            Domoticz.Error("Not able to update device : " + str(Unit))

        try:
            if not (Devices[Unit].Name == config.get("DEFAULT","customname")):

                config.set('DEFAULT','customname',Devices[Unit].Name)
        
                try:
                    with open(path, 'w') as configfile:
                        config.write(configfile)                
                except IOError:
                    Domoticz.Error('Error updating config file')
                    raise
        except:
            Domoticz.Error('Error updating config file, customname param missing')
            raise

    return

# save learned/imported code and create Domoticz device
def save():
    global path, learnedCommand, Unit, numberDev, custom

    numberDev +=1    
    path=str(Parameters["Mode2"]) + "/" + str(Parameters["Key"]) + "-" + str(Parameters["HardwareID"]) + "-" + str(numberDev) + ".ini"

    if os.path.exists(path):
        Domoticz.Error('File exist : ' + path)        
        return False
    else:
        try:
            create_config(path,str(numberDev),learnedCommand,custom)
        except:
            Domoticz.Error('Not able to create : ' + path)
            return False
    try:
        Domoticz.Device(Name=str(Parameters["HardwareID"])+"-" + str(numberDev)+ " " + custom,  Unit=numberDev, TypeName="Selector Switch", Type=244, Switchtype=9, Subtype=73).Create()
    except:
        Domoticz.Error('Not able to create device')
        return False

    if Parameters["Mode6"] == "Debug":
        Domoticz.Log(' <b> Command line : ' + '"' + Parameters['HomeFolder'] + 'plugin_send.py' +  '" ' + path + ' </b>')
    
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

# Put Broadlink on Learn , packet received converted to Hex
def learn():
    global learnedCommand
    
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

    learnedCommand=(codecs.encode(ir_packet, 'hex_codec')).decode('utf-8')
    if Parameters["Mode6"] == "Debug":
        Domoticz.Log(learnedCommand)
        
    Domoticz.Log( "Code stored in memory" )
    UpdateDevice(1, 1, '10')

    return True

# send Hex command
def send():
    global sendCommand

    if not sendCommand:
        Domoticz.Error('Nothing to send')
        return False
    
    sendCommand = bytes.fromhex(sendCommand)
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
def create_config(path,Unit,learnedCommand,custom):    

    config = configparser.ConfigParser()
    config['DEFAULT'] = {   'PluginKey'     : Parameters["Key"],
                            'PluginName'    : Parameters["Name"],
                            'PluginFolder'  : Parameters["HomeFolder"],
                            'HardwareID'    : Parameters["HardwareID"],
                            'Unit'          : Unit,
                            'CustomName'    : custom
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
        raise
    
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

# Start Web server for Transfert
def startWeb():

    if sys.platform.startswith('linux'):
    # linux specific code here
        cmdFile = Parameters["HomeFolder"] + 'plugin_http.sh'
    elif sys.platform.startswith('darwin'):
    # mac
        cmdFile = Parameters["HomeFolder"] + 'plugin_http.sh'
    elif sys.platform.startswith('win32'):
    #  win specific
        cmdFile = '"' + Parameters["HomeFolder"] + 'plugin_http.cmd' + '"'

    commandtoexecute =  cmdFile + " 0.0.0.0 " + Parameters["Mode5"] + " " + Parameters["Mode2"] 

    try:
        subprocess.check_call(commandtoexecute, shell=True, timeout=5)    
    except subprocess.CalledProcessError as e:
        Domoticz.Error(str(e.returncode))
        Domoticz.Error(str(e.cmd))
        Domoticz.Error(str(e.output))
        return False

    if Parameters["Mode6"] == "Debug":
        Domoticz.Log("Subprocess " + commandtoexecute + " launched...")    

    return True

# check Webserver is running, if not put device Off
def isAlive():
    global isRunning

    socket.setdefaulttimeout(5)    
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    try:
        s.connect(('127.0.0.1', int(Parameters["Mode5"])))
        isRunning = True
        s.sendall(b"GET /")    
    except socket.error as e:
        isRunning = False
        UpdateDevice(255,0,'Off') 
        
    s.close()
    if Parameters["Mode6"] == "Debug":
            Domoticz.Log("Web isAlive status :" +str(isRunning))
        
    return

#import json files and transfrom to ini file and hex imported code
def createIniImport():
    global learnedCommand, custom

    import json
    
    path=Parameters["Mode2"] + "/import/"

    try:
        with open(path+"jsonSubIr") as remote_name:    
            data_remote = json.load(remote_name)
    except ValueError: # includes simplejson.decoder.JSONDecodeError
        return False

    try:
        with open(path+"jsonButton") as button_name:    
            data_button = json.load(button_name)
    except ValueError: # includes simplejson.decoder.JSONDecodeError
        return False

    try:
        with open(path+"jsonIrCode") as code_name:    
            data_code = json.load(code_name)
    except ValueError: # includes simplejson.decoder.JSONDecodeError
        return False
    
    recCode = open(path+"simulate.txt", 'w')
    CRLF="\n"

    for i in range(0, len(data_code)):        
        button = data_code[i]['buttonId']
        for j in range(0, len(data_button)):
            if data_button[j]['id'] == button:
                numName = data_button[j]['subIRId']
                buttonName = data_button[j]['name']
                for k in range(0, len(data_remote)):                    
                    if data_remote[k]['id'] == numName:
                        name = data_remote[k]['name']
                        break
                    else:
                        name = "unknown"
                break
            else:
                buttonName = "unknown"

        code = ''.join('%02x' % (i & 0xff) for i in data_code[i]['code'])
        result = "Numrec : " + str(i) + " Button number: " + str(button ) + " " + "Number name : " + str(numName) + " Name : " + name + " " + buttonName + " Code : " + str(code)        
        custom = name + " " + buttonName 
        path = Parameters["Mode2"] + "/import/" + "IMP-" + str(i) + ".ini"        

        create_config(path,i,code,custom)
        recCode.writelines(result+CRLF)

        if Parameters["Mode6"] == "Debug":
            Domoticz.Log(result)
    
    filelink = "file://" +  Parameters["Mode2"] + "/import/" + "simulate.txt"
    Domoticz.Log("Number of devices to create : " + str( i + 1 ))
    Domoticz.Log("You need to select Import for that")
    Domoticz.Log('Simulate.txt file has been created with all codes on it. Click <a target="_blank"  href="' + filelink + '" style="color:blue">here</a> to see the path')

    return True

# if clear is True we will erase all files if False we will create devices and erase ini files
def manageIniImport(clear):
    global custom, learnedCommand

    import glob
    import errno

    path = Parameters["Mode2"] + "/import/*.ini"
    files = glob.glob(path)   

    if not files:
        Domoticz.Log("No ini files found")
        if clear == False:
            return False
    else:
        for name in files: # 'file' is a builtin type, 'name' is a less-ambiguous variable name.
            if clear == False:
                try:
                    with open(name) as f: # No need to specify 'r': this is the default.                    
                        config = configparser.ConfigParser()
                        config.read(name)
                        UnitNumber=config.get("DEFAULT", "unit")
                        custom=config.get("DEFAULT", "customname")
                        learnedCommand = config.get("LearnedCode", str(UnitNumber))
                        createDev()                    
                except IOError as exc:
                    if exc.errno != errno.EISDIR: # Do not fail if a directory is found, just ignore it.
                        raise # Propagate other kinds of IOErro
            os.remove(name)
            if Parameters["Mode6"] == "Debug":
                Domoticz.Log(name + "  removed")                

    if clear == True:
        path = Parameters["Mode2"] + "/import/json*"
        files = glob.glob(path)   
        if not files:
            Domoticz.Log("No json files found")        
            return False
        else:
            for name in files:
                os.remove(name)
                if Parameters["Mode6"] == "Debug":
                    Domoticz.Log(name + "  removed")

    return True

def createDev():
    
    if not save() and numberDev < 254:
        createDev()

    return

def remoteSend(Command):
    
    if Command in remoteKEY:
        k = remoteKEY.index(Command)
        try:
            genCommand(remotetoSEND[k])
        except IndexError: 
            Domoticz.Error('Send error or Remote command not set in ini file: ' + Command)         
            return False
        if Parameters["Mode6"] == "Debug":
            Domoticz.Log('Remote send: ' + str(k+1) + " " + str(remotetoSEND[k]))            
    else:
        Domoticz.Error('Remote command not defined: ' + Command)        
        return False
    
    return True

# get config ini file
def get_remoteconfig():
    global RemoteCommand

    name = Parameters["Mode2"] + "/remote/plugin_remote_"+ str(Parameters["HardwareID"]) + ".ini"

    if os.path.isfile(name):
        try:
            with open(name) as f: # No need to specify 'r': this is the default.                    
                        config = configparser.ConfigParser()
                        config.read(name)
                        RemoteCommand = config.get("Custom", "Command")                        
        except IOError as exc:
            Domoticz.Error('error : ' + str(exc))        
            raise # Propagate other kinds of IOErro

        if Parameters["Mode6"] == "Debug":
            Domoticz.Log( "ini file read...." + name)    
            Domoticz.Log( "Custom Commands: " + RemoteCommand)    
    else:
        if Parameters["Mode6"] == "Debug":
            Domoticz.Log( "No ini file :" + name)    
            Domoticz.Log( "Custom Commands for Remote not managed")
            
    return

# generate tuple for remote
def genRemote():
    global remoteKEY, remotetoSEND

    from ast import literal_eval as make_tuple

    get_remoteconfig()

    if RemoteCommand:        
        remotetoSEND = make_tuple(RemoteCommand)
    
    remoteKEY=( "Home",
                "Up",
                "Info",                
                "Left",
                "Select",
                "Right",
                "Back",
                "Down",                
                "ContextMenu",
                "ChannelUp",
                "FullScreen",
                "VolumeUp",
                "Channels",
                "ShowSubtitles",
                "Mute",
                "ChannelDown",                
                "Stop",                
                "VolumeDown",
                "BigStepBack",
                "Rewind",
                "PlayPause",
                "FastForward",
                "BigStepForward"
                )

    return
    
