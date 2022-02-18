"""Bluetoothpairing API handler."""



import os
import sys
import json
import time
from time import sleep
import logging
import requests
import threading
import subprocess

try:
    from gateway_addon import APIHandler, APIResponse, Adapter, Device, Property, Database
except:
    print("Import APIHandler and APIResponse from gateway_addon failed. Use at least WebThings Gateway version 0.10")
    sys.exit(1)



class BluetoothpairingAPIHandler(APIHandler):
    """Bluetoothpairing API handler."""

    def __init__(self, verbose=False):
        """Initialize the object."""
        #print("INSIDE API HANDLER INIT")
        
        self.DEBUG = False
        
        self.addon_name = 'bluetoothpairing'
        self.running = True
        self.do_scan = False
        self.scanning = False
        #self.cancel_scan = False
        self.scanning_start_time = 0
        self.scan_duration = 20
        self.made_agent = False
        
        self.all_devices = []
        self.paired_devices = []
        self.discovered_devices = []
        
        
        # LOAD CONFIG
        try:
            self.add_from_config()
        except Exception as ex:
            print("Error loading config: " + str(ex))
        
        self.DEBUG = True

            
        # Intiate extension addon API handler
        try:
            manifest_fname = os.path.join(
                os.path.dirname(__file__),
                '..',
                'manifest.json'
            )

            with open(manifest_fname, 'rt') as f:
                manifest = json.load(f)

            APIHandler.__init__(self, manifest['id'])
            self.manager_proxy.add_api_handler(self)
            

            if self.DEBUG:
                print("self.manager_proxy = " + str(self.manager_proxy))
                print("Created new API HANDLER: " + str(manifest['id']))
        
        except Exception as e:
            print("Failed to init UX extension API handler: " + str(e))


        # Respond to gateway version
        try:
            if self.DEBUG:
                print("Gateway version: " + str(self.gateway_version))
        except:
            print("self.gateway_version did not exist")

        # Start clock thread
        self.running = True
        
        if self.DEBUG:
            print("Starting the internal clock")
        try:            
           t = threading.Thread(target=self.clock)
           t.daemon = True
           t.start()
                
        except Exception as ex:
            print("Error starting the clock thread: " + str(ex))

        self.ready = True



    # Read the settings from the add-on settings page
    def add_from_config(self):
        """Attempt to read config data."""
        try:
            database = Database(self.addon_name)
            if not database.open():
                print("Could not open settings database")
                return
            
            config = database.load_config()
            database.close()
            
        except:
            print("Error! Failed to open settings database.")
            self.close_proxy()
        
        if not config:
            print("Error loading config from database")
            return
            
        if 'Debugging' in config:
            self.DEBUG = bool(config['Debugging'])
            if self.DEBUG:
                print("-Debugging preference was in config: " + str(self.DEBUG))



#
#  CLOCK
#

    def clock(self):
        """ Runs every second and handles the various timers """
        
        if self.DEBUG:
            print("CLOCK INIT")
            
        while self.running:
            
            if self.do_scan:
                if self.DEBUG:
                    print("clock: starting scan. Duration: " + str(self.scan_duration))
                self.do_scan = False
                self.scanning = True
                
                try:
                    
                    time.sleep(2) # make sure other commands are complete
                    
                    scan_output = self.bluetoothctl('--timeout 18 scan on')
                    if self.DEBUG:
                        print("scan output: \n" + str(scan_output))

                
                    self.paired_devices = self.get_devices_list('paired-devices')
                    self.available_devices = self.get_devices_list('devices')
                    
                    if self.DEBUG:
                        print("all available devices: " + str(self.available_devices))
                    
                    self.discovered_devices = [d for d in self.available_devices if d not in self.paired_devices]
                    
                except Exception as ex:
                    print("clock: scan error: " + str(ex))
                    
                self.scanning = False
                if self.DEBUG:
                    print("clock: scan complete")
                    
            time.sleep(1)




#
#  GET DEVICES LIST
#

    def get_devices_list(self, devices_type):
        
        devices = []
        
        result = self.bluetoothctl(devices_type, True) # ask to be returned an array
        
        for line in result:
            try:
                if 'Device' in line:
                    line2 = line.split('Device ')[1]
                    if self.DEBUG:
                        print("line2: " + str(line2))
                
                    device = {}
                
                    parts = line2.split(" ", 1)
                    if self.DEBUG:
                        print("LINE PARTS: " + str(parts))
                    
                    if valid_mac(parts[0]):
                        device['mac'] = parts[0]
                        device['name'] = parts[1]
                        
                        device['paired'] = False
                        device['trusted'] = False
                        device['connected'] = False
                        
                        info_test = self.bluetoothctl('info ' + device['mac'])
                        for line in info_test:
                            #if self.DEBUG:
                            #    print("- info test line: " + str(line))
                            if 'Paired: yes' in line:
                                device['paired'] = True
                                if self.DEBUG:
                                    print("device is paired")
                            if 'Connected: yes' in line:
                                device['connected'] = True
                                if self.DEBUG:
                                    print("device is connected")
                            if 'Trusted: yes' in line:
                                device['trusted'] = True
                                if self.DEBUG:
                                    print("device is trusted")
                                    
                    
                        devices.append(device)
                    
            except Exception as ex:
                print("error parsing devices line: " + str(ex))
                
        return devices






#
#  HANDLE REQUEST
#

    def handle_request(self, request):
        """
        Handle a new API request for this handler.

        request -- APIRequest object
        """
        
        try:
        
            if request.method != 'POST':
                return APIResponse(status=404)
            
            if request.path == '/update' or request.path == '/scan' or request.path == '/poll':

                try:
                    
                    
                    if request.path == '/scan':
                        if self.DEBUG:
                            print("/scan - initiating scan")
                        state = 'ok'
                        
                        run_command('rfkill unblock bluetooth')
                        
                        self.bluetoothctl('power on')
                        
                        self.paired_devices = self.get_devices_list('paired-devices')
                        
                        if self.scanning == False:
                            self.scanning = True
                            self.scanning_start_time = time.time()
                            self.do_scan = True
                            
                        return APIResponse(
                            status=200,
                            content_type='application/json',
                            content=json.dumps({'state':state, 'scanning':self.scanning}),
                        )
                            
                            
                    elif request.path == '/poll':
                        if self.DEBUG:
                            print("/poll - returning found bluetooth devices")
                            
                        # optionallt refresh list of paired devices
                        if self.scanning == False:
                            try:
                                get_paired = bool(request.body['get_paired'])
                                #print("get_paired: " + str(get_paired))
                                if request.path == '/init' or get_paired == True:
                                    if self.DEBUG:
                                        print("-updating list of paired devices")
                                    self.paired_devices = self.get_devices_list('paired-devices')
                            except Exception as ex:
                                print("Error with get_paired in poll request: " + str(ex))
                        
                        # calculate scan progress percentage
                        scan_progress = time.time() - self.scanning_start_time 
                        if scan_progress > self.scan_duration:
                            scan_progress = self.scan_duration
                    
                        scan_progress = int(scan_progress * 5)
                        if self.DEBUG:
                            print("scan_progress: " + str(scan_progress) + "%")
                        
                        return APIResponse(
                            status=200,
                            content_type='application/json',
                            content=json.dumps({'state':'ok', 'scanning':self.scanning, 'scan_progress':scan_progress, 'paired':self.paired_devices, 'discovered':self.discovered_devices }),
                        )
                            
                            
                    elif request.path == '/update':
                        if self.DEBUG:
                            print("/update - Updating a single device")
                            
                        try:
                            state = False
                            update = ''
                            
                            action = str(request.body['action'])
                            mac = str(request.body['mac'])
                            
                            if self.DEBUG:
                                print("update action: " + str(action))
                            
                            
                            if self.made_agent == False: 
                                self.made_agent = True
                                self.bluetoothctl('agent on') # TODO: how long does this stick?
                                self.bluetoothctl('default-agent')
                            
                            
                            if self.scanning == True:
                                if self.DEBUG:
                                    print("/update - cancelling current scan")
                                #self.cancel_scan = True
                                self.bluetoothctl('scan off')
                                self.scanning = False
                                sleep(.2)
                            
                            
                            #
                            # ACTIONS
                            #
                            
                            if action == 'info':
                                try:
                                    update = self.bluetoothctl('info ' + mac)
                                    if update != None:
                                        state = True
                                except Exception as ex:
                                    print("error getting device info: " + str(ex))
                                    state = False
                                
                                
                            elif action == 'pair':
                                result = self.bluetoothctl('pair ' + mac)
                                if 'Pairing successful' in result:
                                    state = True
                                    self.paired_devices = self.get_devices_list('paired-devices')
                                
                            
                            elif action == 'connect':
                                result = self.bluetoothctl('connect ' + mac)
                                if 'Connection successful' in result:
                                    state = True
                                
                                time.sleep(2)
                                
                                info_test = self.bluetoothctl('info ' + mac)
                                for line in info_test:
                                    if 'Connected: yes' in line:
                                        state = True
                                        if self.DEBUG:
                                            print("info test: it was connected")
                                    
                                
                            elif action == 'trust':
                                result = self.bluetoothctl('trust ' + mac)
                                if 'successful' in result:
                                    state = True
                                    
                                
                            elif action == 'disconnect':
                                result = self.bluetoothctl('disconnect ' + mac)
                                if 'Successful disconnected' in result:
                                    state = True
                                    
                                
                            elif action == 'unpair':
                                result = self.bluetoothctl('remove ' + mac)
                                if 'Device has been removed' in result:
                                    state = True
                                    
                                time.sleep(2)
                                
                                info_test = self.bluetoothctl('info ' + mac)
                                for line in info_test:
                                    if 'Paired: yes' in line:
                                        state = False
                                        if self.DEBUG:
                                            print("it was still paired")
                                
                                if state:
                                    self.paired_devices = self.get_devices_list('paired-devices')
                            
                            
                            if update == '' and state:
                                update = action + ' succesful'
                            
                            if action != 'info':
                                time.sleep(3) # Give bluetooth some time to settle before the user fires another command
                            
                            return APIResponse(
                                status=200,
                                content_type='application/json',
                                content=json.dumps({'state' : state, 'mac': mac,'update' : update }),
                            )
                        except Exception as ex:
                            print("Error while updating device: " + str(ex))
                            return APIResponse(
                                status=500,
                                content_type='application/json',
                                content=json.dumps({'state' : False, 'update' : "Server error"}),
                            )
                        
                    else:
                        return APIResponse(status=404)
                        
                        
                except Exception as ex:
                    print("API handler issue: " + str(ex))
                    return APIResponse(
                        status=500,
                        content_type='application/json',
                        content=json.dumps("Valid path, but general error in API handler"),
                    )
                    
            else:
                return APIResponse(status=404)
                
        except Exception as e:
            print("Failed to handle UX extension API request: " + str(e))
            return APIResponse(
                status=500,
                content_type='application/json',
                content=json.dumps("API Error"),
            )

       
    # Unload. Not sure if implemented in API_handler?
    def unload(self):
        if self.DEBUG:
            print("Shutting down Bluetooth Pairing")
        self.running = False
        time.sleep(2)
        
        
    # Run BluetoothCTL commands
    def bluetoothctl(self, command, return_array=False):
        result = run_command("sudo bluetoothctl " + command)
        if result != None:
            result = result.strip()
            
            if "\n" in result or return_array:
                result = result.split("\n")
                if self.DEBUG:
                    print("result has been turned into an array")
            
        else:
            result = ""
            if return_array:
                result = []
            
        if self.DEBUG:
            print("bluetoothctl_command result: " + str(result))
        return result
        
        
        
def run_command(cmd, timeout_seconds=30):
    try:
        p = subprocess.run(cmd, timeout=timeout_seconds, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True, universal_newlines=True)

        if p.returncode == 0:
            return str(p.stdout)
        else:
            if p.stderr:
                return str(p.stderr)

    except Exception as e:
        print("Error running command: "  + str(e))
        
        
def valid_mac(mac):
    return mac.count(':') == 5 and \
        all(0 <= int(num, 16) < 256 for num in mac.rstrip().split(':')) and \
        not all(int(num, 16) == 255 for num in mac.rstrip().split(':'))
