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
            #manifest_fname = os.path.join(
            #    os.path.dirname(__file__),
            #    '..',
            #    'manifest.json'
            #)

            #with open(manifest_fname, 'rt') as f:
            #    manifest = json.load(f)

            #APIHandler.__init__(self, manifest['id'])
            APIHandler.__init__(self, self.addon_name)
            self.manager_proxy.add_api_handler(self)
            #self.addon_name = manifest['id']

            if self.DEBUG:
                print("self.manager_proxy = " + str(self.manager_proxy))
                print("Created new API HANDLER: " + str(manifest['id']))
        
        except Exception as e:
            print("Failed to init UX extension API handler: " + str(e))
        
        
        
        self.running = True
        self.persistent_data = {'connected':[],'power':True,'audio_receiver':False}
        

        self.blues_version = int(run_command('bluetoothctl --version | cut -d "." -f2'))
        
        # Device scanning
        self.do_device_scan = True
        self.scanning = False
        self.scanning_start_time = 0
        self.periodic_scanning_duration = 1
        self.periodic_scanning_interval = 1
        self.scan_duration = 2 # in reality, with all the sleep cooldowns, it takes longer than the value of this variable
        self.made_agent = False
        self.busy_creating_devices_list = False
        
        
        self.all_devices = []
        self.paired_devices = []
        self.discovered_devices = []
        
        self.scan_result = []
        
        # Tracker scanning
        self.trackers = [] # contains a list of trackers that are unlikely to change mac address. Tiles don't change. Airtags change every 15 minutes.
        self.do_periodic_tracker_scan = False
        self.recent_new_tracker = None
        self.show_tracker_popup = False
        self.suspiciousness_duration = 1800 # seconds. 30 minutes.
        self.tracker_names_list = ['nanolink aps'] # additional trackers could be added here
        
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
        try:
            
            with open(self.manufacturers_csv_file_path, newline='') as csvfile:
                manus = csv.reader(csvfile, delimiter=',', quotechar='"')
                for row in manus:
                    if row[0] == 'Decimal':
                        continue
                    manu_number = str(row[0])
                    #manu_code = row[1].replace("0x","")
                    
                    self.manufacturers_lookup_table[manu_number] = row[2]
            
            
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


        if not 'power' in self.persistent_data:
            self.persistent_data['power'] = True
        
        if not 'audio_receiver' in self.persistent_data:
            self.persistent_data['audio_receiver'] = False        
        
        if not 'connected' in self.persistent_data:
            self.persistent_data['connected'] = []
        
        if not 'known_trackers' in self.persistent_data:
            self.persistent_data['known_trackers'] = {}
        
        if not 'previous_tracker_count' in self.persistent_data:
            self.persistent_data['previous_tracker_count'] = 0

        #if not 'previous_airtag_count' in self.persistent_data:
        #    self.persistent_data['previous_airtag_count'] = 0
        
        #if not 'previous_previous_airtag_count' in self.persistent_data:
        #    self.persistent_data['previous_previous_airtag_count'] = 0
        
        if not 'last_time_new_tracker_detected' in self.persistent_data:
            self.persistent_data['last_time_new_tracker_detected'] = 0

        if not 'tracker_suspects' in self.persistent_data:
            self.persistent_data['tracker_suspects'] = {} # holds data on recent airtags, with their mac address as the key
        
        
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

        if self.DEBUG:
            print("persistent data: " + str(self.persistent_data))
            #print("self.manufacturers_lookup_table: " + str(self.manufacturers_lookup_table))


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
        try:
            for previously_connected_device in self.persistent_data['connected']:
                if 'address' in previously_connected_device:
                    if self.DEBUG:
                        print(" reconnecting to: " + str(previously_connected_device))
                    self.bluetoothctl('connect ' + str(previously_connected_device['address']) )
                    time.sleep(3)
        except Exception as ex:
            print("Error reconnecting to bluetooth devices: " + str(ex))

        # Start clock thread
        self.running = True
        
        run_command('sudo bluetoothctl agent NoInputNoOutput')
        run_command('sudo bluetoothctl default-agent')
        
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
        
        #print("self.manufacturers_lookup_table: " + str(self.manufacturers_lookup_table))
        
        #print("hasattr()?: " + str(  self.hasattr(manufacturers_lookup_table)  ))
        #print("-------------- 2557 0: " + str(self.manufacturers_code_lookup_table[0]))


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
        
        if 'Airtag certainty duration' in config:
            self.suspiciousness_duration = int(config['Airtag certainty duration']) * 60
            if self.DEBUG:
                print("-Airtag certainty duration preference was in config: " + str(self.suspiciousness_duration))
        
        if 'Show tracker pop-up' in config:
            self.show_tracker_popup = bool(config['Show tracker pop-up'])
            if self.DEBUG:
                print("-Show tracker pop-up preference was in config: " + str(self.show_tracker_popup))
        


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
                            subprocess.Popen(["sudo","bluetoothctl","--timeout",str(self.scan_duration),"scan","on"],stdout=subprocess.PIPE) # running this alongside the Bleak scan helps it detect non-BLE devices too.
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
                    if clock_loop_counter % 6 == 0:
                        try:
                            current_time = time.time()
                            
                            # Toggle the "recent new tracker" switch on the thing
                            recent_new_tracker_detected = False
                            if current_time - self.persistent_data['last_time_new_tracker_detected'] < 300:
                                recent_new_tracker_detected = True
                                
                            if recent_new_tracker_detected != self.recent_new_tracker:
                                self.recent_new_tracker = recent_new_tracker_detected 
                                self.adapter.set_recent_tracker_on_thing(recent_new_tracker_detected)
                        
                        
                            if self.DEBUG:
                                print("__checking known trackers. Length: " + str(len(self.persistent_data['known_trackers'])))
                                
                            recently_spotted_known_trackers_count = 0
                            for tracker_mac in self.persistent_data['known_trackers']:
                                #if self.DEBUG:
                                #    print("known_trackers mac: " + str(tracker_mac))
                                    
                                # Get timestamps for tracker
                                last_time_spotted = self.persistent_data['known_trackers'][tracker_mac]['last_seen']
                                first_time_spotted = self.persistent_data['known_trackers'][tracker_mac]['first_seen']
                                #if self.DEBUG:
                                #    print("- known tracker first time spotted: " + str(first_time_spotted))
                                #    print("- known tracker last time spotted: " + str(last_time_spotted))
                                    
                                # count how many known trackers were detected in the last 15 minutes. This helps ignore passers by, and helps accumulate data from multiple separate scans that may have occured in the last 15 minutes.
                                if current_time - last_time_spotted < self.suspiciousness_duration:
                                    recently_spotted_known_trackers_count += 1
                            
                                # trackers that were spotted long ago may be forgotten? Just in case someone living in a high-traffic areas is swamped with trackers that linger for 15 minutes (living above a store?).
                                if len(self.persistent_data['known_trackers']) > 100:
                                    if current_time - first_time_spotted > 604800: # a week
                                        del self.persistent_data['known_trackers'][tracker_mac]
                        
                            if self.DEBUG:
                                print("recently_spotted_known_trackers_count: " + str(recently_spotted_known_trackers_count))
                            if recently_spotted_known_trackers_count != self.persistent_data['previous_tracker_count']:
                                self.adapter.set_trackers_on_thing(recently_spotted_known_trackers_count)
                                if self.DEBUG:
                                    print("number of detected known trackers changed to: " + str(recently_spotted_known_trackers_count))
                            self.persistent_data['previous_tracker_count'] = recently_spotted_known_trackers_count
                            
                        except Exception as ex:
                            print("clock: error while looping over known trackers: " + str(ex))
                        
                        


                # Keep connected speakers awake
                speaker_keep_alive_counter += 1
                if speaker_keep_alive_counter > 26:
                    speaker_keep_alive_counter = 0
                    
                    if 'omxplayer -o alsa:bluealsa' in run_command('ps aux | grep omxplayer'):
                        if self.DEBUG:   
                            print("omxplayer seems to already be streaming music to a bluetooth speaker")
                    else:
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
        if self.busy_creating_devices_list == False:
            self.busy_creating_devices_list == True
        
        try:
            devices = []
            connected_devices = []
            paired_devices = []
            trackers = []
            airtag_count = 0
            dubious_airtag_count = 0 # airtags that are suspicious, as they seem to be far away from their owner
            
            now_stamp = int(time.time())
            
            # Part 1, using the information from BluetoothCTL to gat an initial list of paired and connected devices.
            
            if self.blues_version < 60:
                result = self.bluetoothctl('paired-devices', True) # ask to be returned an array
            else:
                esult = self.bluetoothctl('devices Paired', True) # ask to be returned an array
            for line in result:
                try:
                    if 'Device' in line:
                        line2 = line.split('Device ')[1]
                        if self.DEBUG:
                            print("line2: " + str(line2))
                
                        device = {'suspiciousness':'safe', 'last_seen':now_stamp}
                
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
                                            if self.DEBUG:
                                                print("manu_number: " + str(manu_number))
                                            #print("self.manufacturers_lookup_table: " + str(self.manufacturers_lookup_table))
                                            #print("self.manufacturers_code_lookup_table[manu]: " + str( self.manufacturers_code_lookup_table[str(manu_number)] ))
                                            if str(manu_number) in self.manufacturers_lookup_table.keys():
                                                
                                                device['manufacturer'] = self.manufacturers_lookup_table[str(manu_number)]
                                                if self.DEBUG:
                                                    print("bingo, spotted manufacturer id. It is now: " + str(device['manufacturer']))
                                            
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
            self.paired_devices = paired_devices # TODO self.paired_devices is not used anymore
            
            
            
            # Part 2: parsing the actual scan results
            
            if now_stamp - self.scanning_start_time > 300:
                if self.DEBUG:
                    print("clearing old scan results (they were older than 5 minutes)") # with periodic scanning enabled, is it even possible to get stale scan result?
                self.scan_result = [] # clear the scan results if they're too old.
            else:
                if self.DEBUG:
                    print("scan results were fresh enough")
            
            for device in self.scan_result:
                if self.DEBUG:
                    print(".")
                if 'address' in device:
                    if not any(d['address'] == device['address'] for d in devices):
                        
                        device['suspiciousness'] = 'unknown'
                
                        device['last_seen'] = now_stamp
                        
                        # Mark a device as a tracker based on its name
                        if device['name'].lower() in self.tracker_names_list:
                            device['type'] = 'tracker'
                
                        # Change manufacturer number into manufacturer name
                        if 'manufacturer' in device:
                            if self.DEBUG:
                                print("device['manufacturer'] before: " + str(device['manufacturer']))
                                
                            if str(device['manufacturer']) in self.manufacturers_lookup_table.keys():
                                if self.DEBUG:
                                    print("BINGO2")
                                device['manufacturer'] = self.manufacturers_lookup_table[ str(device['manufacturer'])]
                
                            if self.DEBUG:
                                print("device['manufacturer'] after: " + str(device['manufacturer']))
                            
                        # If continuous scanning is enabled, handle the suspects list
                        if device['type'] == 'tracker' and self.periodic_scanning_interval > 0:
                            
                            if self.DEBUG:
                                print("Parsing a tracker__")
                            
                            try:

                                # Airtag?
                                if device['name'] == 'Airtag':
                                    airtag_count += 1
                                
                                    if self.DEBUG:
                                        print("- Airtag device: " + str(device))
                                else:
                                    if self.DEBUG:
                                        print("NOT an airtag. name: " + str(device['name']))
                                

                                # Check if tracker has been around for a while, or is just passing by
                                if device['address'] in self.persistent_data['known_trackers']:
                                    if self.DEBUG:
                                        print("- it's a known tracker")
                                        print("now_stamp: " + str(now_stamp))
                                        print("self.persistent_data['known_trackers'][ device['address'] ]: " + str(self.persistent_data['known_trackers'][ device['address'] ]))
                                        print("self.persistent_data['known_trackers'][ device['address'] ]['last_seen']: " + str(self.persistent_data['known_trackers'][ device['address'] ]['last_seen']))
                                        
                                    self.persistent_data['known_trackers'][ device['address'] ]['last_seen'] = now_stamp
                                    
                                    if self.DEBUG:
                                        print("setting suspiciousness to known")
                                    device['suspiciousness'] = 'known'
                                    device['first_seen'] = self.persistent_data['known_trackers'][ device['address'] ]['first_seen']
                                    
                                    if device['name'] == 'Airtag':
                                        dubious_airtag_count += 1
                                        device['suspiciousness'] = 'dangerous'
                                    
                                elif not device['address'] in self.persistent_data['tracker_suspects']:
                                    if self.DEBUG:
                                        print("adding newly spotted tracker to suspects list: " + str(device['address']))
                                    self.persistent_data['tracker_suspects'][ device['address'] ] = {'address':device['address'], 'first_seen':now_stamp, 'last_seen':now_stamp}
                                    device['first_seen'] = now_stamp
                                    device['suspiciousness'] = 'fresh'
                                    
                                else:
                                    # it's in the suspicious list, but not yet in the known trackers list
                                    
                                    try:
                                        if 'first_seen' in self.persistent_data['tracker_suspects'][ device['address'] ]:
                                            if self.persistent_data['tracker_suspects'][ device['address'] ]['first_seen'] < (now_stamp - self.suspiciousness_duration):
                                                if self.DEBUG:
                                                    print("ALERT! NEW TRACKER SPOTTED for longer than 15 minutes: " + str(device['address']))
                                        
                                                # update the device data to mark it as suspicious
                                                device['suspiciousness'] = 'known-new'
                                        
                                                # mark the last time that we found a new tracker
                                                self.persistent_data['last_time_new_tracker_detected'] = now_stamp
                                        
                                                # move from suspects list to known trackers list
                                                self.persistent_data['known_trackers'][ device['address'] ] = {'name':device['name'], 'first_seen': self.persistent_data['tracker_suspects'][ device['address'] ]['first_seen'], 'last_seen':now_stamp} # stores the first_seen time of known trackers
                                                
                                                try:
                                                    del self.persistent_data['tracker_suspects'][ device['address'] ]
                                                except Exception as ex:
                                                    print("Error while trying to delete tracker from suspects list: " + str(ex))
                                        
                                                if device['name'] == 'Airtag':
                                                    dubious_airtag_count += 1
                                                    device['suspiciousness'] = 'dangerous-new'
                                    
                                            else:
                                                device['suspiciousness'] = 'waiting'
                                                if self.DEBUG:
                                                    print("This device is in the suspects list, but hasn't been around for 15 minutes yet.")
                                                    
                                            
                                            device['first_seen'] = self.persistent_data['tracker_suspects'][ device['address'] ]['first_seen'] # copy first seen data over from the suspects list, might be nice in the UI
                                            
                                        else:
                                            if self.DEBUG:
                                                print("error, tracker had no first_seen timestamp")
                                            
                                        
                                            
                                    except Exception as ex:
                                        print('Error while parsing tracker in limbo: ' + str(ex))
                                        
                                
                                    
                            except Exception as ex:
                                print('Error while parsing tracker: ' + str(ex))
                                    
                            trackers.append(device)

                        devices.append(device)
                    else:
                        if self.DEBUG:
                            print("that detected device was already in the paired devices list from BluetoothCTL. Skipping.")

            
            # If periodic scanning is active, indicate when the tracker count increases
            if self.periodic_scanning_interval > 0:
                #if len(trackers) != self.persistent_data['previous_tracker_count']:
                #    self.adapter.set_trackers_on_thing(len(trackers))
                #    if self.DEBUG:
                #        print("number of detected trackers changed to: " + str(len(trackers)))
                #self.persistent_data['previous_tracker_count'] = len(trackers)
                
                #if airtag_count != self.persistent_data['previous_airtag_count']:
                    #if airtag_count > self.persistent_data['previous_airtag_count'] and airtag_count > self.persistent_data['previous_previous_airtag_count']: # compare with previous two scans, to avoid flutter
                    #    self.persistent_data['last_time_new_tracker_detected'] = time.time()
                    #self.persistent_data['previous_previous_airtag_count'] = self.persistent_data['previous_airtag_count']
                    #self.persistent_data['previous_airtag_count'] = airtag_count
                
                # remove airtags that haven't been seen for more than half an hour from the suspects list
                try:
                    for suspect_mac in self.persistent_data['tracker_suspects']:
                        
                        if self.persistent_data['tracker_suspects'][suspect_mac]['first_seen'] < (now_stamp - (2 * self.suspiciousness_duration)) and self.persistent_data['tracker_suspects'][suspect_mac]['last_seen'] < (now_stamp - (2 * self.suspiciousness_duration)):
                            del self.persistent_data['tracker_suspects'][ suspect_mac ]
                        
                            if self.DEBUG:
                                print("removed an Airtag from the suspect list")
                                
                except Exception as ex:
                    print('Error while pruning airtag suspects: ' + str(ex))
            
            if self.DEBUG:
                print("\n\n----------------------------------------devices: " + str(devices))

            self.all_devices = devices
            
            self.save_persistent_data()
            
        except Exception as ex:
            print('Error while parsing scan result: ' + str(ex))
                
        self.busy_creating_devices_list = False




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
            #if self.scanning == False:
            #    if self.DEBUG:
            #        print("Disabling discoverable cancelled: device is currently busy scanning")
            #    self.bluetoothctl('discoverable off')
            
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
                        self.bluetoothctl('agent on')
                        self.set_discoverable(True)
                        
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
                            
                        # optionally refresh list of paired devices
                        if self.scanning == False:
                            try:
                                get_paired = bool(request.body['get_paired']) # used to refresh the paired devices list
                                if self.DEBUG:
                                    print("get_paired: " + str(get_paired))
                                #if request.path == '/init' or get_paired == True:
                                #    if self.DEBUG:
                                #        print("-updating list of paired devices")
                                #    #self.paired_devices = self.create_devices_list('paired-devices')
                                
                                self.create_devices_list()
                                    
                            except Exception as ex:
                                print("Error with get_paired in poll request: " + str(ex))
                        
                        # calculate scan progress percentage
                        scan_progress = time.time() - self.scanning_start_time 
                        expected_scan_duration = 6 + self.scan_duration
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
                                print("target mac: " + str(mac))
                            
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
                                    
                                    #self.paired_devices = self.create_devices_list()
                                    self.create_devices_list()
                            
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
                                    #self.paired_devices = self.create_devices_list() # udpates connected devices list in persistent json
                                    self.create_devices_list()
                                    
                                
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
                
            if self.api_handler.show_tracker_popup:
                if state:
                    self.send_pairing_prompt("The number of detected Bluetooth trackers has increased")
                
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
                            self.adapter.api_handler.persistent_data['previous_tracker_count'])
                            
                            
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
        return None
        
        
def valid_mac(mac):
    return mac.count(':') == 5 and \
        all(0 <= int(num, 16) < 256 for num in mac.rstrip().split(':')) and \
        not all(int(num, 16) == 255 for num in mac.rstrip().split(':'))