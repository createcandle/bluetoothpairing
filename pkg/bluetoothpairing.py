"""Bluetoothpairing API handler."""



import os
import sys
import csv
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
        self.scan_duration = 18 # in reality, with all the cooldowns, it takes closer to 25 seconds.
        self.tracker_scan_duration = 10 # currently only used for progress bar calcualtion
        self.made_agent = False
        self.disable_periodic_scanning = False
        
        self.all_devices = []
        self.paired_devices = []
        self.discovered_devices = []
        
        self.trackers = []
        self.last_time_new_tracker_detected = 0
        self.recent_new_tracker = None
        
        self.persistent_data = {'connected':[],'power':True,'audio_receiver':False}
        
        # Audio receiver
        self.discoverable = False
        self.discoverable_countdown = 0
        
        
        #self.addon_path = os.path.join(self.user_profile['addonsDir'], self.addon_name)
        #self.persistence_file_path = os.path.join(self.user_profile['dataDir'], self.addon_name, 'persistence.json')
        self.addon_path = os.path.join('/home/pi/.webthings/addons', self.addon_name)
        self.data_dir = os.path.join('/home/pi/.webthings/data', self.addon_name)
        self.persistence_file_path = os.path.join(self.data_dir, 'persistence.json')
        
        self.tracker_scanner_origin_lib_dir = os.path.join(self.addon_path, 'lib')
        self.tracker_scanner_destination_lib_dir = os.path.join(self.data_dir, 'lib')
        self.tracker_scanner_origin_path = os.path.join(self.addon_path, 'tracker_scanner.py')
        self.tracker_scanner_path = os.path.join(self.data_dir, 'tracker_scanner.py')
        
        self.manufacturers_csv_file_path = os.path.join(self.addon_path, 'bluetooth_manufacturers.csv')
        
        os.system('sudo cp -r ' + str(self.tracker_scanner_origin_lib_dir) + ' ' + str(self.tracker_scanner_destination_lib_dir))
        os.system('sudo cp ' + str(self.tracker_scanner_origin_path) + ' ' + str(self.tracker_scanner_path))
        
        
        # Generate manufacturers lookup table
        self.manufacturers_lookup_table = {}
        try:
            
            with open(self.manufacturers_csv_file_path, newline='') as csvfile:
                manus = csv.reader(csvfile, delimiter=',', quotechar='"')
                for row in manus:
                    manu_code = row[1].replace("0x","")
                    self.manufacturers_lookup_table[manu_code] = row[2]
            
            print(str(self.manufacturers_lookup_table))
        except Exception as ex:
            print("error parsing manufacturers csv: " + str(ex))
        
        
        # Get persistent data
        try:
            with open(self.persistence_file_path) as f:
                self.persistent_data = json.load(f)
                if self.DEBUG:
                    print('self.persistent_data loaded from file: ' + str(self.persistent_data))
        except:
            print("Could not load persistent data (if you just installed the add-on then this is normal)")
            #self.persistent_data = {'connected':[],'power':True,'audio_receiver':False}

        print("persistent data: " + str(self.persistent_data))

        if not 'power' in self.persistent_data:
            self.persistent_data['power'] = True
        
        if not 'audio_receiver' in self.persistent_data:
            self.persistent_data['audio_receiver'] = False        
        
        if not 'recent_trackers' in self.persistent_data:
            self.persistent_data['recent_trackers'] = {}
        
        # LOAD CONFIG
        try:
            self.add_from_config()
        except Exception as ex:
            print("Error loading config: " + str(ex))


            
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


        # Get initial list of connected devices, so update persistent data for other addons.
        self.paired_devices = self.get_devices_list('paired-devices')



        # Create adapter
        try:
            self.adapter = BluetoothpairingAdapter(self,verbose=False)
            if self.DEBUG:
                print("Bluetoothpairing ADAPTER created")

        except Exception as ex:
            print("Failed to start Bluetoothpairing ADAPTER. Error: " + str(ex))


        # Restore states from persistent data
        self.set_power(self.persistent_data['power'])
        self.set_audio_receiver(self.persistent_data['audio_receiver'])


        # reconnect to previously connected devices.
        for previously_connected_device in self.persistent_data['connected']:
            if self.DEBUG:
                print(" reconnecting to: " + str(previously_connected_device))
            self.bluetoothctl('connect ' + str(previously_connected_device['mac']) )
            time.sleep(3)



        

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
            
        if 'Disable periodic scanning' in config:
            self.disable_periodic_scanning = bool(config['Disable periodic scanning'])
            if self.DEBUG:
                print("-Disable periodic scanning preference was in config: " + str(self.disable_periodic_scanning))


        


#
#  CLOCK
#

    def clock(self):
        """ Runs every second and handles the various timers """
        
        if self.DEBUG:
            print("CLOCK INIT")
            
        clock_loop_counter = 0
        while self.running:
            try:
                if self.do_scan:
                    if self.DEBUG:
                        print("clock: starting scan. Duration: " + str(self.scan_duration))
                    self.do_scan = False
                    self.scanning = True
                    self.scanning_start_time = time.time()
                    clock_loop_counter = 0
                
                    try:
                    
                        time.sleep(2) # make sure other commands have finished
                    
                        if self.running:
                            scan_output = self.bluetoothctl('--timeout ' + str(self.scan_duration) + ' scan on>/dev/null')
                            if self.DEBUG:
                                print("scan output: \n" + str(scan_output))
                        
                        
                        if self.running:
                            
                            time.sleep(1)
                        
                            self.paired_devices = self.get_devices_list('paired-devices')
                            self.available_devices = self.get_devices_list('devices')
                    
                            if self.DEBUG:
                                print("all available devices: " + str(self.available_devices))
                    
                            self.discovered_devices = [d for d in self.available_devices if d not in self.paired_devices]
                    
                            time.sleep(1)
                        
                        if self.running:
                            self.tracker_scan()
                        
                    except Exception as ex:
                        print("clock: scan error: " + str(ex))
                    
                    self.scanning = False
                    if self.DEBUG:
                        print("clock: scan complete")
                    
            

                # Discoverable countdown
                if self.discoverable_countdown > 0:
                    if self.discoverable_countdown == 1:
                        self.set_discoverable(False)
                    self.discoverable_countdown -= 1
                    
                    
                # Periodic scanning
                if self.disable_periodic_scanning == False:
                    clock_loop_counter += 1
            
                    # Every 5 minutes check if connected devices are still connected, or if trusted paired devices have reconnected themselves
                    if clock_loop_counter > 300:
                        clock_loop_counter = 0
                        self.scan_duration = 2
                        self.do_scan = True
                        
                
                # Was a new tracker found recently?
                if clock_loop_counter % 3 == 0:
                    current_time = time.time()
                    recent_new_tracker_detected = False
                    for tracker_mac in self.persistent_data['recent_trackers']:
                        first_time_spotted = self.persistent_data['recent_trackers'][tracker_mac]
                        if current_time - first_time_spotted < 600:
                            recent_new_tracker_detected = False
                        
                    if recent_new_tracker_detected != self.recent_new_tracker:
                        self.recent_new_tracker = recent_new_tracker_detected
                        self.adapter.set_recent_tracker_on_thing(recent_new_tracker_detected)

                        

            except Exception as ex:
                print("Bluetooth Pairing clock error: " + str(ex))

            time.sleep(1)

#
#  GET DEVICES LIST
#

    def get_devices_list(self, devices_type):
        
        devices = []
        connected_devices = []
        
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
                        
                        device['info'] = info_test
                        
                        for line in info_test:
                            
                            #if self.DEBUG:
                            #    print("- info test line: " + str(line))
                            if 'Icon: audio-card' in line:
                                 device['audio-card'] = True
                                 if self.DEBUG:
                                     print("device is speaker")
                            if 'Paired: yes' in line:
                                device['paired'] = True
                                if self.DEBUG:
                                    print("device is paired")
                            if 'Trusted: yes' in line:
                                device['trusted'] = True
                                if self.DEBUG:
                                    print("device is trusted")
                            if 'Connected: yes' in line:
                                device['connected'] = True
                                connected_devices.append(device)
                                if self.DEBUG:
                                    print("device is connected")
                            if 'ManufacturerData Key:' in line:
                                line = line.replace('\n','')
                                manu_code = str(line[-4:])
                                if manu_code != None:
                                    manu_code = manu_code.upper()
                                    if self.DEBUG:
                                        print("manu code: -" + str(manu_code) + "-")
                                    if manu_code in self.manufacturers_lookup_table:
                                        device['manufacturer'] = self.manufacturers_lookup_table[manu_code]
                                    else:
                                        if self.DEBUG:
                                            print("manufacturer code not found in lookup table")
                                
                    
                        devices.append(device)
                    
            except Exception as ex:
                print("error parsing devices line: " + str(ex))
                
        if len(connected_devices) > 0 and devices_type == 'paired-devices':
                self.persistent_data['paired'] = devices
                self.persistent_data['connected'] = connected_devices
                self.save_persistent_data()
                
        return devices




#
#  BLUETOOTH TRACKERS SCANNER
#

    def tracker_scan(self):
        result = run_command("sudo python3 " + self.tracker_scanner_path)
        if self.DEBUG:
            print("tracker scan result: " + str(result))
        if result != None and result != '':
            result = result.strip()
            self.trackers = []
            if "\n" in result:
                result = result.split("\n")
            else:
                result = [result]
                
            if self.DEBUG:
                print("tracker scan result has been turned into an array")
            for line in result:
                if len(line) > 10:
                    try:
                        #line = line.replace('\n','')
                    
                        device = {}
                        parts = line.split(" ")
                    
                        device['name'] = parts[0]
                        if parts[0] == 'Airtag':
                            device['manufacturer'] = "Apple, Inc."
                        device['mac'] = parts[1]
                        device['rssi'] = parts[2]
                        
                            
                        if device['mac'] not in self.persistent_data['recent_trackers']:
                            self.persistent_data['recent_trackers'][ device['mac'] ] = int(time.time())
                            self.save_persistent_data()
                            
                        try:    
                            device['info'] = parts[2] + " " + parts[3] + " " + parts[4]
                        except:
                             if self.DEBUG:
                                 print("ERROR in parsing tracker info from line")
                             
                        self.trackers.append(device)
                    
                    except Exception as ex:
                        if self.DEBUG:
                            print("Error while parsing line from tracker_scanner: " + str(ex))
                else:
                    if self.DEBUG:
                        print("short line in tracker scanner results?")
            
            if self.DEBUG:
                print("\n\nTOTAL TRACKERS DETECTED: " + str(len(self.trackers)))
            self.adapter.set_trackers_on_thing(len(self.trackers))
        else:
            if self.DEBUG:
                print("No trackers detected")


    #
    #  SET STATES
    #

    def set_power(self,state):
        if self.DEBUG:
            print("Setting power to: " + str(state))
            
        if state == True:
            self.bluetoothctl('power on')
        else:
            self.bluetoothctl('power off')
        
        self.adapter.set_power_on_thing(state)
        
        self.persistent_data['power'] = state
        self.save_persistent_data()


    def set_audio_receiver(self,state):
        if self.DEBUG:
            print("Setting audio receiver to: " + str(state))
            
        if state == True:
            self.bluetoothctl('agent NoInputNoOutput')      # this should already be the default agent
            self.bluetoothctl('default-agent')
            self.bluetoothctl('pairable on')                # should already be pairable by default

            self.set_discoverable(True)
            run_command('sudo systemctl start bluealsa-aplay.service')
            
            
        else:
            self.set_discoverable(False)
            run_command('sudo systemctl stop bluealsa-aplay.service')
        
        self.persistent_data['audio_receiver'] = state
        self.save_persistent_data()
        
            
    def set_discoverable(self,state):
        if self.DEBUG:
            print("Setting discoverable to: " + str(state))
        
        self.discoverable = state
        
        if state == True:
            self.bluetoothctl('discoverable on')
            self.discoverable_countdown = 60                    # discoverable will also turn itself off automatically after 90 seconds. This is mostly to make the UI reflect that.
        else:
            self.bluetoothctl('discoverable off')
            
        self.adapter.set_discoverable_on_thing(state)
            




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
                        
                        self.set_power(True)
                        
                        self.paired_devices = self.get_devices_list('paired-devices')
                        
                        self.scan_duration = 18
                        
                        if self.scanning == False:
                            self.scanning = True
                            self.do_scan = True
                            
                        return APIResponse(
                            status=200,
                            content_type='application/json',
                            content=json.dumps({'state':state, 'scanning':self.scanning, 'debug':self.DEBUG}),
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
                        expected_scan_duration = 5 + self.scan_duration + self.tracker_scan_duration
                        if scan_progress > expected_scan_duration:
                            scan_progress = expected_scan_duration
                    
                        ratio = 100 / expected_scan_duration
                        scan_progress = int(scan_progress * ratio)
                        if self.DEBUG:
                            print("scan_progress: " + str(scan_progress) + "%")
                        
                        return APIResponse(
                            status=200,
                            content_type='application/json',
                            content=json.dumps({'state':'ok', 'scanning':self.scanning, 'scan_progress':scan_progress, 'paired':self.paired_devices, 'discovered':self.discovered_devices, 'trackers':self.trackers }),
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
                                self.bluetoothctl('agent NoInputNoOutput') # TODO: how long does this stick? 300 seconds?
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
                                    
                                    time.sleep(3)
                                    
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
                                    
                                if state:
                                    self.paired_devices = self.get_devices_list('paired-devices') # udpates connected devices list in persistent json
                                    
                                
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
                                    
                                time.sleep(3)
                                
                                info_test = self.bluetoothctl('info ' + mac)
                                for line in info_test:
                                    if 'Paired: yes' in line:
                                        state = False
                                        if self.DEBUG:
                                            print("it was still paired")
                                
                                if state:
                                    self.paired_devices = self.get_devices_list('paired-devices')
                            
                            
                            
                            
                            if action != 'info':
                                if update == '' and state:
                                    update = action + ' succesful'
                                time.sleep(2) # Give bluetooth some time to settle before the user fires another command
                            
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
        


    def save_persistent_data(self):
        if self.DEBUG:
            print("Saving to persistence data store")

        try:
            if not os.path.isfile(self.persistence_file_path):
                open(self.persistence_file_path, 'a').close()
                if self.DEBUG:
                    print("Created an empty persistence file")
            else:
                if self.DEBUG:
                    print("Persistence file existed. Will try to save to it.")

            with open(self.persistence_file_path) as f:
                if self.DEBUG:
                    print("saving: " + str(self.persistent_data))
                try:
                    json.dump( self.persistent_data, open( self.persistence_file_path, 'w+' ) )
                except Exception as ex:
                    print("Error saving to persistence file: " + str(ex))
                return True
            #self.previous_persistent_data = self.persistent_data.copy()

        except Exception as ex:
            if self.DEBUG:
                print("Error: could not store data in persistent store: " + str(ex) )
            return False






#
#  ADAPTER
#        

class BluetoothpairingAdapter(Adapter):
    """Adapter that can hold and manage things"""

    def __init__(self, api_handler, verbose=False):
        """
        Initialize the object.

        verbose -- whether or not to enable verbose logging
        """

        self.api_handler = api_handler
        self.name = self.api_handler.addon_name #self.__class__.__name__
        #print("adapter name = " + self.name)
        self.adapter_name = self.api_handler.addon_name #'Bluetoothpairing-adapter'
        Adapter.__init__(self, self.adapter_name, self.adapter_name, verbose=verbose)
        self.DEBUG = self.api_handler.DEBUG
        
        try:
            # Create the thing
            bluetoothpairing_device = BluetoothpairingDevice(self,api_handler,"bluetoothpairing","Bluetooth","OnOffSwitch")
            self.handle_device_added(bluetoothpairing_device)
            self.devices['bluetoothpairing'].connected = True
            self.devices['bluetoothpairing'].connected_notify(True)
            self.thing = self.get_device("bluetoothpairing")
            
            print("adapter: self.ready?: " + str(self.ready))
        
        except Exception as ex:
            print("Error during bluetooth pairing adapter init: " + str(ex))


    def remove_thing(self, device_id):
        if self.DEBUG:
            print("Removing bluetoothpairing thing: " + str(device_id))
        
        try:
            obj = self.get_device(device_id)
            self.handle_device_removed(obj)                     # Remove from device dictionary

        except Exception as ex:
            print("Could not remove thing from Bluetoothpairing adapter devices: " + str(ex))
            
    
    def set_discoverable_on_thing(self, state):
        if self.DEBUG:
            print("new discoverable state on thing: " + str(state))
        try:
            if self.thing:
                self.thing.properties["bluetooth_discoverable"].update( state )
            else:
                print("Error: could not set discoverable state on thing, the thing did not exist?")
        except Exception as ex:
            print("Error setting discoverable state of thing: " + str(ex))    
        
    
    def set_power_on_thing(self, state):
        if self.DEBUG:
            print("new power state on thing: " + str(state))
        try:
            if self.thing:
                self.thing.properties["bluetooth_power"].update( state )
            else:
                print("Error: could not set power state on thing, the thing did not exist?")
        except Exception as ex:
            print("Error setting power state of thing: " + str(ex))           

    def set_trackers_on_thing(self, count):
        if self.DEBUG:
            print("new trackers count on thing: " + str(count))
        try:
            if self.thing:
                self.thing.properties["bluetooth_trackers"].update( count )
            else:
                print("Error: could not set trackers count on thing, the thing did not exist?")
        except Exception as ex:
            print("Error setting trackers count of thing: " + str(ex))        


    def set_recent_tracker_on_thing(self, state):
        if self.DEBUG:
            print("updating recent tracker on thing: " + str(state))
        try:
            if self.thing:
                self.thing.properties["bluetooth_recent_tracker"].update( state )
            else:
                print("Error: could not set recent tracker on thing, the thing did not exist?")
        except Exception as ex:
            print("Error setting recent tracker of thing: " + str(ex))   

#
#  DEVICE
#

class BluetoothpairingDevice(Device):
    """Bluetoothpairing device type."""
        
    def __init__(self, adapter, api_handler, device_name, device_title, device_type):
        """
        Initialize the object.
        adapter -- the Adapter managing this device
        """

        
        Device.__init__(self, adapter, device_name)
        #print("Creating Bluetoothpairing thing")
        
        self._id = device_name
        self.id = device_name
        self.adapter = adapter
        self.api_handler = self.adapter.api_handler
        self._type.append(device_type)
        #self._type = ['OnOffSwitch']

        self.name = device_name
        self.title = device_title
        self.description = 'Connect to Bluetooth devices'

        #if self.adapter.DEBUG:
        #print("Empty Bluetoothpairing thing has been created. device_name = " + str(self.name))
        #print("new thing's adapter = " + str(self.adapter))

        #print("self.api_handler.persistent_data['enabled'] = " + str(self.api_handler.persistent_data['enabled']))
        
        
        self.properties["bluetooth_power"] = BluetoothpairingProperty(
                            self,
                            "bluetooth_power",
                            {
                                '@type': 'OnOffProperty',
                                'title': "State",
                                'type': 'boolean',
                                'readOnly': False,
                            },
                            bool(self.adapter.api_handler.persistent_data['power']))


        self.properties["bluetooth_audio_receiver"] = BluetoothpairingProperty(
                            self,
                            "bluetooth_audio_receiver",
                            {
                                'title': "Audio receiver",
                                'type': 'boolean',
                                'readOnly': False,
                            },
                            bool(self.adapter.api_handler.persistent_data['audio_receiver']))

        
        
        self.properties["bluetooth_discoverable"] = BluetoothpairingProperty(
                            self,
                            "bluetooth_discoverable",
                            {
                                'title': "Discoverable",
                                'type': 'boolean',
                                'readOnly': True,
                            },
                            False)
                            
                            
        self.properties["bluetooth_trackers"] = BluetoothpairingProperty(
                            self,
                            "bluetooth_trackers",
                            {
                                'title': "Trackers",
                                'type': 'integer',
                                'readOnly': True,
                            },
                            None)
                            
                            
        
        self.properties["bluetooth_recent_tracker"] = BluetoothpairingProperty(
                            self,
                            "bluetooth_recent_tracker",
                            {
                                'title': "New tracker detected",
                                'type': 'boolean',
                                'readOnly': True,
                            },
                            False)
       
        """
        self.properties["bluetooth_audio_receiver"] = BluetoothpairingProperty(
                        self,
                        "bluetooth_audio_receiver",
                        {
                            'title': "Time span",
                            'type': 'string',
                            'enum': duration_strings_list  #["1 minute","10 minutes","30 minutes","1 hour","2 hours","4 hours","8 hours"]
                        },
                        duration_string)
        """
                            
    

#
#  PROPERTY
#


class BluetoothpairingProperty(Property):
    """Bluetoothpairing property type."""

    def __init__(self, device, name, description, value):
        Property.__init__(self, device, name, description)
        
        #print("new property with value: " + str(value))
        self.device = device
        self.name = name
        self.title = name
        self.description = description # dictionary
        self.value = value
        self.set_cached_value(value)
        self.device.notify_property_changed(self)
        if self.device.adapter.DEBUG:
            print("bluetooth pairing property initiated: " + str(self.name) + ", with value: " + str(self.value))
        #self.update(value)
        #self.set_cached_value(value)
        #self.device.notify_property_changed(self)
        #print("property initialized")


    def set_value(self, value):
        if self.device.adapter.DEBUG:
            print("set_value is called on a Bluetoothpairing property: " + str(self.name) + ", with new value: " + str(value))

        try:
            
            if self.name == 'bluetooth_power':
                self.device.adapter.api_handler.set_power(value)
            
            elif self.name == 'bluetooth_audio_receiver':
                self.device.adapter.api_handler.set_audio_receiver(value)
                

            self.update(value)
            
            
        except Exception as ex:
            print("property:set value:error: " + str(ex))
        

    def update(self, value):
        if self.device.adapter.DEBUG:
            print("bluetoothpairing property -> update to: " + str(value))
        #print("--prop details: " + str(self.title) + " - " + str(self.original_property_id))
        #print("--pro device: " + str(self.device))
        if value != self.value:
            self.value = value
            self.set_cached_value(value)
            self.device.notify_property_changed(self)
        










    
    



        
def run_command(cmd, timeout_seconds=20):
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