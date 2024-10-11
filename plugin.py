# Plugin for Peblar Peblar
#
# Author: Achterhoeker
# Mods: 
#
"""
<plugin key="Peblar" name="Peblar" author="Achterhoeker" version="0.0.1" wikilink="https://github.com/Achterhoeker/domoticz-peblar" externallink="https://github.com/Achterhoeker/domoticz-peblar">
    <description>
        <h2>Peblar plugin for Domoticz</h2><br/>
        <h3>Features</h3>
        <ul style="list-style-type:square">
            <li>Read all available data from the rest api from your Peblar wallbox, and set the maximum charger current if needed</li>
        </ul>
        <h3>Devices</h3>
        The following devices will be created:
        <ul style="list-style-type:square">
            <li>Charger Cp Status - Device to show the actual Peblar status (read-only)</li>
            <li>Charging current phase 1 - Current current on phase 1</li>
            <li>Charging current phase 2 - Current current on phase 2</li>
            <li>Charging current phase 3 - Current current on phase 3</li>
            <li>Charging voltage phase 1 - Current measured voltage on phase 1</li>
            <li>Charging voltage phase 2 - Current measured voltage on phase 2</li>
            <li>Charging voltage phase 3 - Current measured voltage on phase 3</li>
            <li>Charging energy total - Device to the current power and total energy used</li>
            <li>Charging energy last session - Device to the current power and energy used in the last session</li>
            <li>Charger firmware version - Firmware version of the charger </li>
            <li>Charging current max current - Charger maximum current allowed </li>
            <li>Charger reason for max current - The reason for the current max current set </li>
            <li>Charging rest api max current limit - Device to set the maximum current allowed by the rest api. This device is also set if loadbalancing is active!. </li>
            <li>Charger serial number - Information about the serial number. </li>
            <li>Charger version - Hardware version id</li>
            <li>Charger nr supported phases - The number of supported phases </li>
            <li>Charging mode - If the p1 meter idx number is set, load balancing is active.See readme for the options </li>
        </ul>
        <h3>Configuration</h3>
        Fill in your Peblar ip address and api key generated for your Peblar rest api.
    </description>
    <params>
        <param field="Address" label="Ip address or host name" width="200px" required="true" default="192.168.2.250"/>
        <param field="Password" label="Api token" width="400px" required="true" default="" password="false"/>
        <param field="Mode1" label="Idx nr household power meter" width="100px" required="false" default="0" password="false"/>
        <param field="Mode2" label="Maximum power usage in Ampere for houshold" width="100px" required="false" default="35" password="false"/>        
        <param field="Mode6" label="Debug" width="150px">
            <options>
                <option label="None" value="0" default="true" />
                <option label="Python Only" value="2"/>
                <option label="Basic Debugging" value="62"/>
                <option label="Basic+Messages" value="126"/>
                <option label="Queue" value="128"/>
                <option label="Connections Only" value="16"/>
                <option label="Connections+Queue" value="144"/>
                <option label="All" value="-1"/>
            </options>
        </param>
    </params>
</plugin>
"""
import DomoticzEx as Domoticz

import time
import datetime
import queue
import threading
import json
import requests

def dumpJson(name, msg):
    messageJson = json.dumps(msg,
                skipkeys = True,
                allow_nan = True,
                indent = 6)
    Domoticz.Debug('Message: '+name )
    Domoticz.Debug(messageJson)

class PeblarPlugin:
    enabled = False
    DEVICELOCK = 1
    DEVICECPSTATE = 2
    DEVICECURRENT1 = 3
    DEVICECURRENT2 = 4
    DEVICECURRENT3 = 5
    DEVICEVOLTAGE1 = 6    
    DEVICEVOLTAGE2 = 7    
    DEVICEVOLTAGE3 = 8        
    DEVICETOTALENERGY = 9
    DEVICEENERGYLASTSSESSION = 10
    DEVICEFIRMWARE = 11
    DEVICEMAXCHARGINGCURRENT = 12
    DEVICEMAXCHARGINGCURRENTREASON = 13    
    DEVICESELECTHARGINGCURRENT = 14
    DEVICESERIAL = 15
    DEVICEVERSION = 16
    DEVICENRPHASES = 17
    DEVICEMODESELECT = 18

    def __init__(self):
        self.messageQueue = queue.Queue()
        self.countDownInit = 3         # Update devices every countDownInit * 10 seconds
        self.countDown = 1
        self.stop_event = threading.Event()  # Event to stop the thread
        self.thread = None  # Referentie naar de thread
        self.pluginJustStarted = True  # Used to prevent dual entries set to True if plugin starts!
        self.MaxHousholdAmperes = 35  # Maximum stroom die het huis mag afnemen
        self.lastChargeLimit = 0      # Laatste ingestelde laadstroom
        self.Profile = "LoadBalancing"  # Huidig profiel
        self.lastDisabledTime = 0     # Tijdstip waarop opladen is uitgeschakeld
        self.enableDelay = 300        # Wachttijd voordat de lader weer mag inschakelen (5 minuten in seconden)
        self.nightStart = 23          # Nachtstroom begint om 23:00
        self.nightEnd = 6             # Nachtstroom eindigt om 06:00
        self.currentcurrent = 0       # last measured real current
        self.voltage = 230            # last measured voltage
        self.mainpowerdeviceidx = 0   # household power device to measure for loadbalancing
        self.domoticz_ip = "127.0.0.1"
        self.domoticz_port = None


    def wbThread(self):
        try:    
            Domoticz.Debug("Worker thread started")
            self.token = Parameters['Password'] 
            Domoticz.Debug('token = ' + self.token)                
            self.base_url = f"http://{Parameters['Address']}/api/wlac/v1/"
            self.mainpowerdeviceidx = int(Parameters['Mode1'])
            Domoticz.Debug('mainpowerdeviceidx = ' + str(self.mainpowerdeviceidx))
            self.MaxHousholdAmperes = int(Parameters['Mode2'])
            Domoticz.Debug('MaxHousholdAmperes = ' + str(self.MaxHousholdAmperes))
                            
            self.domoticz_port =  8080 
            #Settings["ListenPort"]
            Domoticz.Debug('domoticz_port = ' + str(self.domoticz_port))
            self.headers = {
                "Authorization": self.token
            }
            self.authenticated = False
        except Exception as err:
            Domoticz.Error('init problem.: ' + str(err))
            
        # first check ip address
        try:
            url = f"{self.base_url}/health"
            Domoticz.Log('Url = : ' + url)
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                self.ApiVersion = data.get("ApiVersion")
                Domoticz.Log('Succesvol connect to ip address, api version = ' + self.ApiVersion)                
            else:
                Domoticz.Error('Connection problem. Check ip address response is:' + response.status_code)
                return
        except Exception as err:
            Domoticz.Error('Connection problem. Check ip address: ' + str(err))
            return

        # Check api token
        try:
            url = f"{self.base_url}/system"
            Domoticz.Log('Url = : ' + url)
            response = requests.get(url, headers=self.headers, timeout=5)
            if response.status_code == 200:
                data = response.json()
                self.chargerId = data.get("ProductSn")
                Domoticz.Log('Succesvol connected to ip address with autentication, serialNr = ' + self.chargerId)                                
            else:
                Domoticz.Error('Authentication problem. Check Api token:' + response.status_code)
                return
        except Exception as err:
            Domoticz.Error("Authentication problem. Check Api token: "+str(err))
            return
        self.authenticated = True

        self.initDevices(self.chargerId)

        Domoticz.Debug("Entering message handler")
        while not self.stop_event.is_set():
            try:
                Message = self.messageQueue.get(block=True, timeout=1)
                dumpJson('Message', Message)
                
                if Message is None:
                    self.messageQueue.task_done()
                    continue

                if (Message["Type"] == "Update"):
                    self.updateDevices(self.chargerId)
                elif (Message["Type"] == "Command"):
                    deviceID = Message["DeviceID"]
                    try: 
                        if Message["Unit"]==self.DEVICESELECTHARGINGCURRENT: #Set new MAX CHarging
                            desiredmaxchargecurrent = get_selectormilliamp_from_level(str(Message["Level"]))
                            Domoticz.Debug('Set new Max Charging to: ' + str(desiredmaxchargecurrent))
                            self.setChargeCurrentLimit(desiredmaxchargecurrent)
                        elif Message["Unit"]==self.DEVICEMODESELECT: # new charging mode selected
                            self.Profile = get_selectorprofile_from_level( str(Message["Level"]))
                            self.updateSvalue(self.DEVICEMODESELECT, get_selectorlevel_from_profile(self.Profile))                            
                            Domoticz.Debug('Set new charging profile to: ' + self.Profile)
                    except Exception as err:
                        Domoticz.Error("Command error: "+str(err))
                elif (Message["Type"] == "Loadbalance"):
                    Domoticz.Debug("Loadbalance start")
                    url = f"http://{self.domoticz_ip}:{self.domoticz_port}/json.htm?type=devices&rid={self.mainpowerdeviceidx}"
                    response = requests.get(url)
                    if response.status_code == 200:
                        data = response.json()
                        if "result" in data:
                            device_info = data["result"][0]
                            dumpJson('device_info', device_info)
                            sValue = device_info["Data"]
                            
                            Domoticz.Debug(f"Device {self.mainpowerdeviceidx} sValue: {sValue}")
                            power_parts = sValue.split(";")
                            if len(power_parts) >= 6:
                                current_power = int(power_parts[4])  # Het vermogen in Watt
                                if  current_power > 0:
                                    amperes = current_power / self.voltage
                                    Domoticz.Debug(f"Current houshold power usage : {amperes} Amperes")                                                                        
                                    self.control_charging(amperes)
                                else:
                                    current_power = -1*int(power_parts[5])  # Het vermogen in Watt teruglevering
                                    amperes = current_power / self.voltage                             
                                    Domoticz.Debug(f"Current houshold power: {amperes} Amperes")                                    
                                    self.control_charging(amperes)
                        else:
                            Domoticz.Error(f"Device with idx {self.mainpowerdeviceidx} not found in Domoticz.")
                    else:
                        Domoticz.Error(f"HTTP error: {response.status_code}")
                self.messageQueue.task_done()
            except queue.Empty:
                # empty queue is allowed, timeout is set to check exit situation
                pass
            except Exception as err:
                Domoticz.Error("handleMessage: "+str(err))

    def onStart(self):
        self.debugging=False
        Domoticz.Log("onStart called")

        if Parameters["Mode6"] != "0":
            Domoticz.Debugging(int(Parameters["Mode6"]))
            DumpConfigToLog()

        self.thread = threading.Thread(name="QueueThread", target=PeblarPlugin.wbThread, args=(self,))
        self.thread.start()
        Domoticz.Log('Thread started')
        heartBeat = 10     # heartBeat can be changed in debug session
        Domoticz.Heartbeat(heartBeat)

    def initDevices(self, chargerId):

        defaultUnits = [
            { #1
                "Unit": self.DEVICELOCK,
                "Name": "Charger Lock",
                "Type": 244,
                "Switchtype": 19,
            },
            { #2
                "Unit": self.DEVICECPSTATE,
                "Name": "Charger Cp Status",
                "Type": 243,
                "Subtype": 19,
            },
            { #3
                "Unit": self.DEVICECURRENT1,
                "Name": "Charging current phase 1",
                "Type": 243,
                "Subtype": 23,
            },
            { #4
                "Unit": self.DEVICECURRENT2,
                "Name": "Charging current phase 2",
                "Type": 243,
                "Subtype": 23,
            },
            { #5
                "Unit": self.DEVICECURRENT3,
                "Name": "Charging current phase 3",
                "Type": 243,
                "Subtype": 23,
            },
            { #6
                "Unit": self.DEVICEVOLTAGE1,
                "Name": "Charging voltage phase 1",
                "Type": 243,
                "Subtype": 8,
            },            
            { #7
                "Unit": self.DEVICEVOLTAGE2,
                "Name": "Charging voltage phase 2",
                "Type": 243,
                "Subtype": 8,
            },
            { #8
                "Unit": self.DEVICEVOLTAGE3,
                "Name": "Charging voltage phase 3",
                "Type": 243,
                "Subtype": 8,
            },
            { #9
                "Unit": self.DEVICETOTALENERGY,
                "Name": "Charging energy total",
                "Type": 243,
                "Subtype": 29,
            },
            
            { #10
                "Unit": self.DEVICEENERGYLASTSSESSION,
                "Name": "Charging energy last session",
                "Type": 243,
                "Subtype": 29,
            },
            { #11
                "Unit": self.DEVICEFIRMWARE,
                "Name": "Charger firmware version",
                "Type": 243,
                "Subtype": 19,
            },            
            { #12
                "Unit": self.DEVICEMAXCHARGINGCURRENT,
                "Name": "Charging current max current",
                "Type": 243,
                "Subtype": 23,
            },
            { #13
                "Unit": self.DEVICEMAXCHARGINGCURRENTREASON,
                "Name": "Charger reason for max current",
                "Type": 243,
                "Subtype": 19,
            },            
            { #14
                "Unit": self.DEVICESELECTHARGINGCURRENT,
                "Name": "Charging rest api max current limit",
                "Type": 244,
                "Subtype": 73,
                "Switchtype": 18,
                "Options": {
                    "LevelNames": "Pause|6A|7A|8A|9A|10A|11A|12A|13A|14A|15A|16A",
                    "LevelOffHidden": "false",
                    "SelectorStyle": "1"
                }
            },
            { #15
                "Unit": self.DEVICESERIAL,
                "Name": "Charger serial number",
                "Type": 243,
                "Subtype": 19,
            },
            { #16
                "Unit": self.DEVICEVERSION,
                "Name": "Charger version",
                "Type": 243,
                "Subtype": 19,
            },
            { #17
                "Unit": self.DEVICENRPHASES,
                "Name": "Charger nr supported phases",
                "Type": 243,
                "Subtype": 31,
            },
            { #14
                "Unit": self.DEVICEMODESELECT,
                "Name": "Charging mode",
                "Type": 244,
                "Subtype": 73,
                "Switchtype": 18,
                "Options": {
                    "LevelNames": "LoadBalancing|RelaxedLoading|SolarOnly",
                    "LevelOffHidden": "false",
                    "SelectorStyle": "0"
                }
            },            
        ]
        id=str(chargerId)
        Domoticz.Log('init devices')
        try:
            device=Devices[id]
            for defaultUnit in defaultUnits:
                unit = defaultUnit["Unit"]
                if unit in device.Units:
                    myUnit = device.Units[unit]
                else:
                    myUnit = Domoticz.Unit(DeviceID=id, Used=1, **defaultUnit)
                    myUnit.Create()
        except:
            Domoticz.Log('init devices, not found, create!!')        
            for defaultUnit in defaultUnits:
                myUnit = Domoticz.Unit(DeviceID=id, Used=1, **defaultUnit)
                myUnit.Create()



    def updateEVInterfaceData(self):
        try:
            url = f"{self.base_url}/evinterface"
            response = requests.get(url, headers=self.headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                cp_state = data.get("CpState", "Unknown")
                cp_state = get_cp_state_description(cp_state)
                self.updateSvalue(self.DEVICECPSTATE, cp_state)

                lock_state = data.get("LockState", False)
                charge_current_limit = data.get("ChargeCurrentLimit")
                self.updateSvalue(self.DEVICESELECTHARGINGCURRENT, get_selectorlevel_from_milliamp(charge_current_limit))
                
                actual_current = str(round(data.get("ChargeCurrentLimitActual", 0)/1000,1))
                self.updateSvalue(self.DEVICEMAXCHARGINGCURRENT, actual_current)

                limit_source = data.get("ChargeCurrentLimitSource", "Unknown")
                self.updateSvalue(self.DEVICEMAXCHARGINGCURRENTREASON, limit_source)

            else:
                Domoticz.Log(f"Error fetching EV Interface data: {response.status_code}")
        except Exception as e:
            Domoticz.Error(f"Failed to fetch EV Interface data: {str(e)}")


    def updateSystemData(self):
        try:
            url = f"{self.base_url}/system"
            response = requests.get(url, headers=self.headers, timeout=10)
            if response.status_code == 200:
                data = response.json()

                product_pn = data.get("ProductPn", "Unknown")
                self.updateSvalue(self.DEVICEVERSION, product_pn)
                product_sn = data.get("ProductSn", "Unknown")
                self.updateSvalue(self.DEVICESERIAL, product_sn)
                firmware_version = data.get("FirmwareVersion", "Unknown")
                self.updateSvalue(self.DEVICEFIRMWARE, firmware_version)
                wlan_signal_strength = data.get("WlanSignalStrength", None)
                cellular_signal_strength = data.get("CellularSignalStrength", None)
                uptime = data.get("Uptime", 0)
                phase_count = data.get("PhaseCount", 0)
                self.updateSvalue(self.DEVICENRPHASES, phase_count)
                force1phase_allowed = data.get("Force1PhaseAllowed", False)
                
                Domoticz.Debug(f"Firmware Version: {firmware_version}")
                Domoticz.Debug(f"WLAN Signal Strength: {wlan_signal_strength} dBm")
                Domoticz.Debug(f"Cellular Signal Strength: {cellular_signal_strength} dBm")
                Domoticz.Debug(f"Uptime: {uptime} seconds")
                Domoticz.Debug(f"Phase Count: {phase_count}")
                Domoticz.Debug(f"Force 1 Phase Allowed: {force1phase_allowed}")

            else:
                Domoticz.Log(f"Error fetching System data: {response.status_code}")
        except Exception as e:
            Domoticz.Error(f"Failed to fetch System data: {str(e)}")

    def updateMeterData(self):
        try:
            url = f"{self.base_url}/meter"
            response = requests.get(url, headers=self.headers, timeout=10)
            if response.status_code == 200:
                data = response.json()

                current_phase1 = str(round(data.get("CurrentPhase1", 0)/1000,1))
                self.updateSvalue(self.DEVICECURRENT1, current_phase1)
                self.currentcurrent = float(current_phase1)
                current_phase2 = str(round(data.get("CurrentPhase2", 0)/1000,1))
                self.updateSvalue(self.DEVICECURRENT2, current_phase2)
                current_phase3 = str(round(data.get("CurrentPhase3", 0)/1000,1))
                self.updateSvalue(self.DEVICECURRENT3, current_phase3)
                voltage_phase1 = data.get("VoltagePhase1", 0)
                self.updateSvalue(self.DEVICEVOLTAGE1, voltage_phase1)
                voltage_phase2 = data.get("VoltagePhase2", 0)
                self.updateSvalue(self.DEVICEVOLTAGE2, voltage_phase2)
                voltage_phase3 = data.get("VoltagePhase3", 0)
                self.updateSvalue(self.DEVICEVOLTAGE3, voltage_phase3)
                power_phase1 = data.get("PowerPhase1", 0)
                power_phase2 = data.get("PowerPhase2", 0)
                power_phase3 = data.get("PowerPhase3", 0)
                power_total = data.get("PowerTotal", 0)
                energy_total = data.get("EnergyTotal", 0)
                self.updateSvalue2(self.DEVICETOTALENERGY, power_total, energy_total)
                energy_session = data.get("EnergySession", 0)
                self.updateSvalue2(self.DEVICEENERGYLASTSSESSION, power_total, energy_session)             

                Domoticz.Debug(f"Current Phase 1: {current_phase1} mA")
                Domoticz.Debug(f"Current Phase 2: {current_phase2} mA")
                Domoticz.Debug(f"Current Phase 3: {current_phase3} mA")
                Domoticz.Debug(f"Voltage Phase 1: {voltage_phase1} V")
                Domoticz.Debug(f"Voltage Phase 2: {voltage_phase2} V")
                Domoticz.Debug(f"Voltage Phase 3: {voltage_phase3} V")
                Domoticz.Debug(f"Power Phase 1: {power_phase1} W")
                Domoticz.Debug(f"Power Phase 2: {power_phase2} W")
                Domoticz.Debug(f"Power Phase 3: {power_phase3} W")
                Domoticz.Debug(f"Power Total: {power_total} W")
                Domoticz.Debug(f"Energy Total: {energy_total} Wh")
                Domoticz.Debug(f"Energy Session: {energy_session} Wh")

            else:
                Domoticz.Log(f"Error fetching Meter data: {response.status_code}")
        except Exception as e:
            Domoticz.Error(f"Failed to fetch Meter data: {str(e)}")

    def setChargeCurrentLimit(self, current_limit):
        try:
            url = f"{self.base_url}/evinterface"
            payload = {
                "ChargeCurrentLimit": int(current_limit)
            }
            Domoticz.Debug(f"Payload: {payload}")
            response = requests.patch(url, json=payload, headers=self.headers, timeout=5)
            
            if response.status_code == 200:
                Domoticz.Log(f"Charge Current Limit set to: {current_limit} mA")
                data = response.json()
                cp_state = data.get("CpState", "Unknown")
                cp_state = get_cp_state_description(cp_state)
                self.updateSvalue(self.DEVICECPSTATE, cp_state)
                charge_current_limit = data.get("ChargeCurrentLimit")
                self.updateSvalue(self.DEVICESELECTHARGINGCURRENT, get_selectorlevel_from_milliamp(charge_current_limit))
                actual_current = str(round(data.get("ChargeCurrentLimitActual", 0)/1000,1))
                self.updateSvalue(self.DEVICEMAXCHARGINGCURRENT, actual_current)
                limit_source = data.get("ChargeCurrentLimitSource", "Unknown")
                self.updateSvalue(self.DEVICEMAXCHARGINGCURRENTREASON, limit_source)
            elif response.status_code == 400:
                Domoticz.Error("Bad Request: Invalid fields in payload")
            elif response.status_code == 403:
                Domoticz.Error("Forbidden: Read-only fields provided or API is in ReadOnly mode")
            elif response.status_code == 401:
                Domoticz.Error("Unauthorized: Invalid or missing API token")
            else:
                Domoticz.Error(f"Failed to set Charge Current Limit: {response.status_code}")
        except Exception as e:
            Domoticz.Error(f"Exception while setting Charge Current Limit: {str(e)}")


    def updateSvalue(self, unit, sValueIn):
        myUnit = Devices[self.chargerId].Units[unit]
        sValue = f"{sValueIn}"
        if myUnit.sValue != sValue:
            myUnit.sValue = sValue
            myUnit.Update(Log=True)
            
    def updateSvalue2(self, unit, sValueIn, sValueIn2):
        myUnit = Devices[self.chargerId].Units[unit]
        sValue = f"{sValueIn};{sValueIn2}"
        if myUnit.sValue != sValue:
            myUnit.sValue = sValue
            myUnit.Update(Log=True)

                    
    def updateDevices(self, chargerId):
        self.updateSystemData()
        self.updateEVInterfaceData()
        self.updateMeterData()


    def onStop(self):
        Domoticz.Log("onStop called")

        # signal queue thread to exit
        self.messageQueue.put(None)
        self.stop_event.set()  
        if self.thread is not None:
            self.thread.join()  

        Domoticz.Debug('Plugin stopped' )

    def onConnect(self, Connection, Status, Description):
        Domoticz.Debug('onConnect called ({}) with status={}'.format(Connection.Name, Status))        
        Domoticz.Log("onConnect called")

    def onMessage(self, Connection, Data):
        Domoticz.Debug('onMessage called ({})'.format(Connection.Name))
        Domoticz.Log("onMessage called")

    def onCommand(self, DeviceID, Unit, Command, Level, Color):
        Domoticz.Log("onCommand called for Device " + str(DeviceID) + " Unit " + str(Unit) + ": Parameter '" + str(Command) + "', Level: " + str(Level))
        self.messageQueue.put(
            {"Type":"Command", 
             "DeviceID": DeviceID,
             "Unit": Unit,
             "Command": Command,
             "Level": Level
            })

    def onNotification(self, Name, Subject, Text, Status, Priority, Sound, ImageFile):
        Domoticz.Log("Notification: " + Name + "," + Subject + "," + Text + "," + Status + "," + str(Priority) + "," + Sound + "," + ImageFile)

    def onDisconnect(self, Connection):
        Domoticz.Debug('onDisconnect called ({})'.format(Connection.Name))
        Domoticz.Log("onDisconnect called")

    def onHeartbeat(self):
        self.countDown = self.countDown-1
        Domoticz.Debug(f"onHeartbeat called {self.countDown}")
        if self.countDown <= 0:
            self.countDown = self.countDownInit
            self.messageQueue.put(
                {"Type":"Update", 
                })
        if self.mainpowerdeviceidx != 0:
            Domoticz.Debug(f"onHeartbeat asked loadbalncing")
            self.messageQueue.put(
                {"Type":"Loadbalance", 
                })
        
                
    import time

    def setChargeCurrentLimitBalancing(self, current_limit):
        """ Stel de laadstroom limiet in. """
        print(f"Setting charger current limit to {current_limit}A")
        if self.lastChargeLimit != current_limit:
            self.setChargeCurrentLimit(str( int(current_limit) * 1000))
            self.lastChargeLimit = current_limit

    def is_night_time(self):
        """ Controleer of het momenteel nacht is (tussen 23:00 en 06:00). """
        return self.nightStart <= time.localtime().tm_hour or time.localtime().tm_hour < self.nightEnd

    def control_charging(self, household_current):
        """ Controleer elke heartbeat de status en pas de laadstroom aan op basis van het huidige profiel. """
        available_amperes = self.MaxHousholdAmperes - household_current 
        Domoticz.Debug("control_charging")
        profile_actions = {
            "LoadBalancing": lambda: self.handle_load_balancing(available_amperes),
            "RelaxedLoading": lambda: self.handle_relaxed_loading(available_amperes, household_current),
            "SolarOnly": lambda: self.handle_solar_only(available_amperes, household_current),
        }
        profile_actions.get(self.Profile, lambda: None)()

    def handle_load_balancing(self, available_amperes):
        Domoticz.Debug("control_charging")        
        self.set_charge_within_limits(available_amperes + self.currentcurrent if (available_amperes + self.currentcurrent) >= 0 else 0)

    def handle_relaxed_loading(self, available_amperes, household_current):
        Domoticz.Debug("control_charging")        
        if self.is_night_time():
            self.set_charge_within_limits(self.MaxHousholdAmperes - household_current)
        elif household_current < 0:
            self.set_charge_within_limits(max(-household_current + self.currentcurrent, 6))
        else:
            self.set_charge_within_limits(6)

    def handle_solar_only(self, available_amperes, household_current):
        Domoticz.Debug("control_charging")
        self.set_charge_within_limits(-household_current + self.currentcurrent  if (-household_current + self.currentcurrent) > 6 else 0)

    def set_charge_within_limits(self, available_amperes):
        """ 
        Zet de laadstroom binnen de limieten of pauzeert het opladen. 
        Als de beschikbare stroom lager is dan 6A en de lader is actief, zet hem op pauze. 
        Houd de cooldown bij.
        """
        current_time = time.time()
        
        if available_amperes >= 6 and (current_time - self.lastDisabledTime >= self.enableDelay):
            charge_limit = min(16, max(6, available_amperes // 1))  # Zet laadstroom binnen de limieten
            self.setChargeCurrentLimitBalancing(charge_limit)
        elif available_amperes < 6:
            self.pause_charging()

    def pause_charging(self):
        """
        Pauzeer het opladen door de laadstroom op 0 te zetten.
        De cooldown wordt alleen opnieuw ingesteld als de lader nog actief is.
        """
        self.lastDisabledTime = time.time()
        if self.lastChargeLimit != 0:
            # Zet de laadstroom op 0 en start de cooldown-periode.
            self.setChargeCurrentLimitBalancing(0)

            
                
                
                
                
                
global _plugin
_plugin = PeblarPlugin()

def onStart():
    global _plugin
    _plugin.onStart()

def onStop():
    global _plugin
    _plugin.onStop()

def onConnect(Connection, Status, Description):
    global _plugin
    _plugin.onConnect(Connection, Status, Description)

def onMessage(Connection, Data):
    global _plugin
    _plugin.onMessage(Connection, Data)

def onCommand(DeviceID, Unit, Command, Level, Color):
    global _plugin
    _plugin.onCommand(DeviceID, Unit, Command, Level, Color)

def onNotification(Name, Subject, Text, Status, Priority, Sound, ImageFile):
    global _plugin
    _plugin.onNotification(Name, Subject, Text, Status, Priority, Sound, ImageFile)

def onDisconnect(Connection):
    global _plugin
    _plugin.onDisconnect(Connection)

def onHeartbeat():
    global _plugin
    _plugin.onHeartbeat()

# Generic helper functions
    
def get_cp_state_description(state):
    CP_STATE_DESCRIPTIONS = {
        "State A": "No EV connected",
        "State B": "EV connected but suspended by either EV or charger",
        "State C": "EV connected and charging",
        "State D": "Same as C but ventilation requested (not supported)",
        "State E": "Error, short to PE or powered off",
        "State F": "Fault detected by charger",
        "Invalid": "Invalid CP level measured",
        "Unknown": "CP signal cannot be measured."
    }
    return CP_STATE_DESCRIPTIONS.get(state, "Unknown state")

LEVEL_SELECTOR_DESCRIPTIONS = {
    "0": "0",
    "10": "6000",
    "20": "7000",
    "30": "8000",
    "40": "9000",
    "50": "10000",
    "60": "11000",
    "70": "12000",
    "80": "13000",
    "90": "14000",
    "100": "15000",
    "110": "16000"
    }

def get_selectormilliamp_from_level(level):
    return LEVEL_SELECTOR_DESCRIPTIONS.get(level, "Unknown state")
    
def get_selectorlevel_from_milliamp(milliamp_in):
    for level, milliamp in LEVEL_SELECTOR_DESCRIPTIONS.items():
        if milliamp == str(milliamp_in):
            return level
    return "Unknown level"

LEVEL_PROFILE_DESCRIPTIONS = {
    "0": "LoadBalancing",
    "10": "RelaxedLoading",
    "20": "SolarOnly"
}

def get_selectorprofile_from_level(level):
    return LEVEL_PROFILE_DESCRIPTIONS.get(level, "LoadBalancing")
    
def get_selectorlevel_from_profile(profile_in):
    for level, profile in LEVEL_PROFILE_DESCRIPTIONS.items():
        if profile == str(profile_in):
            return level
    return "0"


def DumpConfigToLog():
    for x in Parameters:
        if Parameters[x] != "":
            Domoticz.Debug( "'" + x + "':'" + str(Parameters[x]) + "'")
    Domoticz.Debug("Device count: " + str(len(Devices)))
    for DeviceName in Devices:
        Device = Devices[DeviceName]
        Domoticz.Debug("Device ID:       '" + str(Device.DeviceID) + "'")
        Domoticz.Debug("--->Unit Count:      '" + str(len(Device.Units)) + "'")
        for UnitNo in Device.Units:
            Unit = Device.Units[UnitNo]
            Domoticz.Debug("--->Unit:           " + str(UnitNo))
            Domoticz.Debug("--->Unit Name:     '" + Unit.Name + "'")
            Domoticz.Debug("--->Unit nValue:    " + str(Unit.nValue))
            Domoticz.Debug("--->Unit sValue:   '" + Unit.sValue + "'")
            Domoticz.Debug("--->Unit LastLevel: " + str(Unit.LastLevel))
    return



