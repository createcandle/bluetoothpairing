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
        
        self.addon_name = 'bluetoothpairing' # overwritteb by data in manifest
        
        
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
            self.addon_name = manifest['id']

            if self.DEBUG:
                print("self.manager_proxy = " + str(self.manager_proxy))
                print("Created new API HANDLER: " + str(manifest['id']))
        
        except Exception as e:
            print("Failed to init UX extension API handler: " + str(e))
        
        
        
        self.running = True
        self.persistent_data = {'connected':[],'power':True,'audio_receiver':False}
        
        
        # Device scanning
        self.do_device_scan = True
        self.scanning = False
        self.scanning_start_time = 0
        self.periodic_scanning_duration = 2
        self.periodic_scanning_interval = 5
        self.scan_duration = 2 # in reality, with all the sleep cooldowns, it takes longer than the value of this variable
        self.made_agent = False
        
        
        self.all_devices = []
        self.paired_devices = []
        self.discovered_devices = []
        
        self.scan_result = []
        
        # Tracker scanning
        self.trackers = [] # contains a list of trackers that are unlikely to change mac address. Tiles don't change. Airtags change every 15 minutes.
        self.do_periodic_tracker_scan = False
        self.recent_new_tracker = None
        
        
        # Audio receiver
        self.discoverable = False
        self.discoverable_countdown = 0
        
        
        # Paths
        #print(" self.user_profile: " + str( self.user_profile))
        self.addon_dir = os.path.join(self.user_profile['addonsDir'], self.addon_name)
        self.data_dir = os.path.join(self.user_profile['dataDir'], self.addon_name)
        
        # Persistence file
        self.persistence_file_path = os.path.join(self.data_dir, 'persistence.json')
        
        # Silence wav
        self.silence_file_path = os.path.join(self.addon_dir, 'silence.wav')
        
        
        self.scanner_origin_lib_dir = os.path.join(self.addon_dir, 'lib')
        self.scanner_destination_lib_dir = os.path.join(self.data_dir, 'lib')
        self.scanner_origin_path = os.path.join(self.addon_dir, 'scanner.py')
        self.scanner_path = os.path.join(self.data_dir, 'scanner.py')
        
        self.manufacturers_csv_file_path = os.path.join(self.addon_dir, 'bluetooth_manufacturers.csv')
        
        # Move tracker to data dir so it doesn't interfere with addon updating
        os.system('sudo rm ' + str(self.scanner_path))
        os.system('sudo rm -rf ' + str(self.scanner_destination_lib_dir))
        os.system('sudo cp -r ' + str(self.scanner_origin_lib_dir) + ' ' + str(self.scanner_destination_lib_dir))
        os.system('sudo cp ' + str(self.scanner_origin_path) + ' ' + str(self.scanner_path))
        
        
        # Generate manufacturers lookup tables
        self.manufacturers_lookup_table = {}
        #self.manufacturers_code_lookup_table = {}
        try:
            
            with open(self.manufacturers_csv_file_path, newline='') as csvfile:
                manus = csv.reader(csvfile, delimiter=',', quotechar='"')
                for row in manus:
                    if row[0] == 'Decimal':
                        continue
                    manu_number = int(row[0])
                    #manu_code = row[1].replace("0x","")
                    
                    self.manufacturers_lookup_table[manu_number] = row[2]
                    #self.manufacturers_code_lookup_table[manu_code] = row[2]
            
            #print(str(self.manufacturers_lookup_table))
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

        if self.DEBUG:
            print("persistent data: " + str(self.persistent_data))

        if not 'power' in self.persistent_data:
            self.persistent_data['power'] = True
        
        if not 'audio_receiver' in self.persistent_data:
            self.persistent_data['audio_receiver'] = False        
        
        if not 'connected' in self.persistent_data:
            self.persistent_data['connected'] = []
        
        if not 'recent_trackers' in self.persistent_data:
            self.persistent_data['recent_trackers'] = {}
        
        if not 'previous_tracker_count' in self.persistent_data:
            self.persistent_data['previous_tracker_count'] = 0

        if not 'previous_airtag_count' in self.persistent_data:
            self.persistent_data['previous_airtag_count'] = 0
        
        if not 'previous_previous_airtag_count' in self.persistent_data:
            self.persistent_data['previous_previous_airtag_count'] = 0
        
        if not 'last_time_new_tracker_detected' in self.persistent_data:
            self.persistent_data['last_time_new_tracker_detected'] = 0

        
        
        # LOAD CONFIG
        try:
            self.add_from_config()
        except Exception as ex:
            print("Error loading config: " + str(ex))


        # Respond to gateway version
        try:
            if self.DEBUG:
                print("Gateway version: " + str(self.gateway_version))
        except:
            print("self.gateway_version did not exist")


        # Get initial list of connected devices, to update persistent data for other addons.
        #self.paired_devices = self.create_devices_list('paired-devices')



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


        # Reconnect to previously connected devices.
        for previously_connected_device in self.persistent_data['connected']:
            if 'address' in previously_connected_device:
                if self.DEBUG:
                    print(" reconnecting to: " + str(previously_connected_device))
                self.bluetoothctl('connect ' + str(previously_connected_device['address']) )
                time.sleep(3)
        

        # Start clock thread
        self.running = True
        
        if self.DEBUG:
            print("Starting the internal clock")
        try:
            pass         
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
                print("Error, could not open settings database")
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
            
        if 'Periodic scanning duration' in config:
            self.periodic_scanning_duration = int(config['Periodic scanning duration'])
            if self.DEBUG:
                print("-Scannning duration preference was in config: " + str(self.periodic_scanning_duration))
            
        if 'Periodic scanning interval' in config:
            self.periodic_scanning_interval = int(config['Periodic scanning interval'])
            if self.DEBUG:
                print("-Scannning interval preference was in config: " + str(self.periodic_scanning_interval))
            
        


#
#  CLOCK
#

    def clock(self):
        """ Runs every second and handles the various timers """
        
        if self.DEBUG:
            print("CLOCK INIT")
            
        speaker_keep_alive_counter = 0
        clock_loop_counter = 0
        while self.running:
            try:
                if self.do_device_scan:
                    if self.DEBUG:
                        print("clock: starting scan. Duration: " + str(self.scan_duration))
                        
                    
                        
                    self.do_device_scan = False
                    self.scanning = True
                    self.scanning_start_time = time.time()
                    clock_loop_counter = 0
                
                    try:
                    
                        time.sleep(2) # make sure other commands have finished
                    
                        if self.running:
                            #scan_output = self.bluetoothctl('--timeout ' + str(self.scan_duration) + ' scan on>/dev/null')
                            scan_output = run_command("sudo python3 " + str(self.scanner_path) + ' ' + str(self.scan_duration))
                            if self.DEBUG:
                                print("scan output: \n" + str(scan_output))
                            try:
                                self.scan_result = json.loads(scan_output)
                            
                                self.create_devices_list()
                            except Exception as ex:
                                print("error calling/parsing scanner: " + str(ex))
                        
                        
                    except Exception as ex:
                        print("clock: scan error: " + str(ex))
                    
                    
                    self.scan_duration = self.periodic_scanning_duration # reset scan duration to the periodic one, in case this was a user-initiated scan
                    self.scanning = False
                    if self.DEBUG:
                        print("clock: scan complete")
                    
                
                # Discoverable countdown
                if self.discoverable_countdown > 0:
                    if self.discoverable_countdown == 1:
                        self.set_discoverable(False)
                    self.discoverable_countdown -= 1
                    
                    
                # Periodic scanning timer
                if self.periodic_scanning_interval > 0:
                    clock_loop_counter += 1
                
                    # Every X minutes check if connected devices are still connected, or if trusted paired devices have reconnected themselves, or if trackers are present
                    if clock_loop_counter > self.periodic_scanning_interval * 60:
                        clock_loop_counter = 0
                        self.do_device_scan = True
                            
                
                    # Updating tracker detected state on thing
                    if clock_loop_counter % 3 == 0:
                        current_time = time.time()
                        recent_new_tracker_detected = False
                        
                        if time.time() - self.persistent_data['last_time_new_tracker_detected'] < 300:
                            recent_new_tracker_detected = True
                        
                        for tracker_mac in self.persistent_data['recent_trackers']:
                            #first_time_spotted = self.persistent_data['recent_trackers'][tracker_mac]
                            #if current_time - first_time_spotted < 600:
                            #    recent_new_tracker_detected = False
                            
                            # trackers that were spotted over a year ago may be forgotten? I believe Airtags change their mac every 6 weeks. High-traffic areas could be swamped with data.
                            if len(self.persistent_data['recent_trackers']) > 200:
                                if current_time - first_time_spotted > 11557600: # about three months
                                    del self.persistent_data['recent_trackers'][tracker_mac]
                        
                        if recent_new_tracker_detected != self.recent_new_tracker:
                            self.recent_new_tracker = recent_new_tracker_detected
                            self.adapter.set_recent_tracker_on_thing(recent_new_tracker_detected)
                        


                # Keep connected speakers awake
                speaker_keep_alive_counter += 1
                if speaker_keep_alive_counter > 26:
                    speaker_keep_alive_counter = 0
                    if self.DEBUG:
                        print("clock: starting attempt to keep connected speakers awake")
                    # Play silence.wav to connected speakers
                    for previously_connected_device in self.persistent_data['connected']:
                        if 'type' in previously_connected_device and 'address' in previously_connected_device:
                            if previously_connected_device['type'] == 'audio-card':
                                if self.DEBUG:
                                    print(" keeping speaker awake: " + str(previously_connected_device))
                                try:
                                    os.system('aplay  -D bluealsa:DEV=' + previously_connected_device['address'] + ' ' + self.silence_file_path)
                                except Exception as ex:
                                    print("error while keeping speaker alive: " + str(ex))

            except Exception as ex:
                print("Bluetooth Pairing clock error: " + str(ex))

            time.sleep(1)

        
        
        
    def create_devices_list(self):
        if self.DEBUG:
            print("in create_devices_list")
        
        
        try:
            devices = []
            connected_devices = []
            paired_devices = []
            trackers = []
            airtag_count = 0
            
            
            # Part 1, using the information from BluetoothCTL to gat an initial list of paired and connected devices.
            
            result = self.bluetoothctl('paired-devices', True) # ask to be returned an array
        
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
                            device['address'] = parts[0]
                            device['name'] = parts[1]
                        
                            device['paired'] = False
                            device['trusted'] = False
                            device['connected'] = False
                        
                            info_test = self.bluetoothctl('info ' + device['address'])
                        
                            device['info'] = info_test
                        
                            for line in info_test:
                            
                                #if self.DEBUG:
                                #    print("- info test line: " + str(line))
                                if 'Icon: audio-card' in line:
                                     device['type'] = 'audio-card'
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
                                    if self.DEBUG:
                                        print("device is connected")
                                        
                                if 'ManufacturerData Key:' in line:
                                    try:
                                        line = line.replace('\n','')
                                        manu_code = str(line[-4:])
                                    

                                        if manu_code != None:
                                            manu_number = int('0x' + manu_code, 16)
                                            if manu_number in self.manufacturers_code_lookup_table:
                                                device['manufacturer'] = self.manufacturers_lookup_table[manu_number]
                                            
                                            #manu_code = manu_code.upper()
                                            #if self.DEBUG:
                                            #    print("manu code: -" + str(manu_code) + "-")
                                            #if manu_code in self.manufacturers_code_lookup_table:
                                            #    device['manufacturer'] = self.manufacturers_code_lookup_table[manu_code]
                                            else:
                                                if self.DEBUG:
                                                    print("manufacturer number not found in lookup table: " + str(manu_number))
                                    except Exception as ex:
                                        print("error parsing manufacturer code: " + str(ex))
                                
                            
                            if device['paired']:
                                paired_devices.append(device)
                                
                            if device['connected']:
                                connected_devices.append(device)
                            
                            devices.append(device)    
            
            
                except Exception as ex:
                    print("Error parsing bluetoothCTL scan result" + str(ex))
            
            self.persistent_data['connected'] = connected_devices
            self.paired_devices = paired_devices
            
            
            
            # Part 2: parsing the actual scan results
            
            if time.time() - self.scanning_start_time  > 300:
                self.scan_result = [] # clear the scan results if they're too old.
            
            
            for device in self.scan_result:
                if 'manufacturer' in device:
                    if device['manufacturer'] in self.manufacturers_lookup_table:
                        device['manufacturer'] = self.manufacturers_lookup_table[device['manufacturer']]
                
                
                if device['type'] == 'tracker':
                    trackers.append(device)
                    if device['name'] == 'Airtag':
                        airtag_count += 1
                    else:
                        if device['address'] not in self.persistent_data['recent_trackers']:
                            if self.DEBUG:
                                print("Detected a new tracker that is not an Airtag. Adding to persistent memory.")
                            self.persistent_data['recent_trackers'][ device['address'] ] = int(time.time())
                            self.persistent_data['last_time_new_tracker_detected'] = int(time.time())

                devices.append(device)


            
            # If periodic scanning is active, indicate when the tracker count increases
            if self.periodic_scanning_interval > 0:
                if len(trackers) != self.persistent_data['previous_tracker_count']:
                    self.adapter.set_trackers_on_thing(len(trackers))
                    if self.DEBUG:
                        print("number of detected trackers changed to: " + str(len(trackers)))
                self.persistent_data['previous_tracker_count'] = len(trackers)
                
                if airtag_count != self.persistent_data['previous_airtag_count']:
                    if airtag_count > self.persistent_data['previous_airtag_count'] and airtag_count > self.persistent_data['previous_previous_airtag_count']: # compare with previous two scans, to avoid flutter
                        self.persistent_data['last_time_new_tracker_detected'] = time.time()
                    self.persistent_data['previous_previous_airtag_count'] = self.persistent_data['previous_airtag_count']
                    self.persistent_data['previous_airtag_count'] = airtag_count
                    
                
            
            if self.DEBUG:
                print("\n\n----------------------------------------devices: " + str(devices))

            self.all_devices = devices
            
            self.save_persistent_data()
            
        except Exception as ex:
            print('Error while parsing scan result: ' + str(ex))
                
        




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
            self.discoverable_countdown = 60 # discoverable will also turn itself off automatically after 90 seconds. This is mostly to make the UI reflect that.
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
                        
                        #self.paired_devices = self.create_devices_list('paired-devices')
                        
                        self.scan_duration = 18
                        
                        if self.scanning == False:
                            self.scanning_start_time = time.time()
                            self.scanning = True
                            self.do_device_scan = True
                            
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
                                get_paired = bool(request.body['get_paired']) # used to refresh the paired devices list
                                if self.DEBUG:
                                    print("get_paired: " + str(get_paired))
                                if request.path == '/init' or get_paired == True:
                                    if self.DEBUG:
                                        print("-updating list of paired devices")
                                    #self.paired_devices = self.create_devices_list('paired-devices')
                                    self.create_devices_list()
                                    
                            except Exception as ex:
                                print("Error with get_paired in poll request: " + str(ex))
                        
                        # calculate scan progress percentage
                        scan_progress = time.time() - self.scanning_start_time 
                        expected_scan_duration = 5 + self.scan_duration
                        if scan_progress > expected_scan_duration:
                            scan_progress = expected_scan_duration
                    
                        ratio = 100 / expected_scan_duration
                        scan_progress = int(scan_progress * ratio)
                        if self.DEBUG:
                            print("scan_progress: " + str(scan_progress) + "%")
                        
                        return APIResponse(
                            status=200,
                            content_type='application/json',
                            content=json.dumps({'state':'ok', 'scanning':self.scanning, 'scan_progress':scan_progress, 'all_devices':self.all_devices}),
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
                                self.bluetoothctl('pairable on')
                                result = self.bluetoothctl('pair ' + mac)
                                if 'Pairing successful' in result:
                                    state = True
                                    
                                    time.sleep(3)
                                    
                                    self.paired_devices = self.create_devices_list()
                                
                            
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
                                    self.paired_devices = self.create_devices_list() # udpates connected devices list in persistent json
                                    
                                
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
                                    self.create_devices_list()
                            
                            
                            
                            
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
                            
                            
        if self.api_handler.periodic_scanning_interval > 0:
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