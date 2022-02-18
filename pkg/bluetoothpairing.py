"""Bluetoothpairing API handler."""



import os
import sys
import json
import time
from time import sleep
import logging
import pexpect
import pexpect.exceptions
import requests
import threading
import subprocess




try:
    from gateway_addon import APIHandler, APIResponse, Adapter, Device, Property, Database
    #print("succesfully loaded APIHandler and APIResponse from gateway_addon")
except:
    print("Import APIHandler and APIResponse from gateway_addon failed. Use at least WebThings Gateway version 0.10")
    sys.exit(1)



class BluetoothpairingAPIHandler(APIHandler):
    """Bluetoothpairing API handler."""

    def __init__(self, verbose=False):
        """Initialize the object."""
        #print("INSIDE API HANDLER INIT")
        
        
        self.addon_name = 'bluetoothpairing'
        self.running = True
        self.do_scan = False
        self.scanning = False
        #self.cancel_scan = False
        self.scanning_start_time = 0
        self.last_poll_time = 0
        self.scan_duration = 20
        self.made_agent = False
        
        self.DEBUG = False

        self.bl = None
        
        self.all_devices = []
        self.paired_devices = []
        self.discovered_devices = []
        
        # LOAD CONFIG
        try:
            self.add_from_config()
        except Exception as ex:
            print("Error loading config: " + str(ex))
        
        self.DEBUG = True

        """
        first_run = False
        try:
            with open(self.persistence_file_path) as f:
                self.persistent_data = json.load(f)
                if self.DEBUG:
                    print("Persistence data was loaded succesfully.")
                
        except:
            first_run = True
            print("Could not load persistent data (if you just installed the add-on then this is normal)")
            self.persistent_data = {'items':[]}
            
            
        if self.DEBUG:
            print("Bluetoothpairing self.persistent_data is now: " + str(self.persistent_data))
        """

        #try:
            #self.adapter = BluetoothpairingAdapter(self,verbose=False)
            #self.manager_proxy.add_api_handler(self.extension)
            #print("ADAPTER created")
        #except Exception as e:
        #    print("Failed to start ADAPTER. Error: " + str(e))
        
        
        
        
        # Is there user profile data?    
        #try:
        #    print(str(self.user_profile))
        #except:
        #    print("no user profile data")
                

            
            
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

        # Start the internal clock
        #print("Starting the internal clock")
        #try:            
        #    t = threading.Thread(target=self.clock)
        #    t.daemon = True
        #    t.start()
        #except:
        #    print("Error starting the clock thread")
        
        


        self.bl = Bluetoothctl()
            
        
        # Start the internal clock
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
            print("CLOCK INIT.. ")
        #time.sleep(2)
        #time.sleep(initial_sleep)
            
        while self.running: # and self.player != None
            
            if self.do_scan: # and self.scanning == False:
                if self.DEBUG:
                    print("clock: starting scan. Duration: " + str(self.scan_duration))
                self.do_scan = False
                self.scanning = True
                
                self.last_poll_time = time.time()
                try:
                    #self.scanning_start_time = time.time()
                    #self.start_scan()
                    #self.bl.power_on()
                    #self.bl.make_agent()
                    time.sleep(2) # make sure other commands are complete
                    #self.available_devices = self.scan_devices()
                    scan_output = self.bl.start_scan()
                    #subprocess.Popen(['sudo','bluetoothctl','scan','on'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True, universal_newlines=True)
                    if self.DEBUG:
                        print("scan output: \n" + str(scan_output))
                    #time.sleep(10)

                
                    self.get_paired_devices_list()
                    self.available_devices = self.bl.get_available_devices()
                    if self.DEBUG:
                        print(str(self.available_devices))
                    self.discovered_devices = [d for d in self.available_devices if d not in self.paired_devices]

                    self.bl.stop_scan()
                    if self.DEBUG:
                        print("scan stopped")
                
                    #self.all_devices.append(self.paired_devices[i])
                
                
                    #self.discovered_devices = self.bl.get_discoverable_devices()
                    #sleep(2)
                    if self.DEBUG:
                        print("raw discovered devices:")
                        print(str(self.discovered_devices))
            
                    for i in range(len(self.discovered_devices)):
                        self.discovered_devices[i]['paired'] = False
                        self.discovered_devices[i]['trusted'] = False
                        self.discovered_devices[i]['connected'] = False
                        #self.all_devices.append(self.discovered_devices[i])
                        # TODO: is there value in testing these devices to see if any of them are unpaired.. but trusted? It's technically possible.
                
                except Exception as ex:
                    print("clock: scan error: " + str(ex))
                    
                self.scanning = False
                if self.DEBUG:
                    print("clock: scan complete")
                
                    #print("DEVICES:")
                    #print(run_command("sudo bluetoothctl devices"))
                    
                    
            time.sleep(1)

        # cleanup
        if self.bl != None:
            if self.scanning:
                self.bl.stop_scan()
            self.bl.exit()



    def get_paired_devices_list(self):
        self.paired_devices = self.bl.get_paired_devices()
        for i in range(len(self.paired_devices)):
            self.paired_devices[i]['paired'] = True
            self.paired_devices[i]['trusted'] = False
            self.paired_devices[i]['connected'] = False
        
        
            try:
                mac = self.paired_devices[i]['mac']
                #print("getting extra info for paired device: " + str(mac))
                #info_test = [] # getting device info was causing issues
                info_test = self.bl.get_device_info(mac)
                #print(str(info_test))
                trusted = False
                connected = False
                for line in info_test:
                    if self.DEBUG:
                        print(str(line))
                    if 'Trusted: yes' in line:
                        if self.DEBUG:
                            print("it was already trusted")
                        self.paired_devices[i]['trusted'] = True
                    if 'Connected: yes' in line:
                        if self.DEBUG:
                            print("it was already connected")
                        self.paired_devices[i]['connected'] = True
            except Exception as ex:
                print("error doing extra test if connected: " + str(ex))







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
            
            if request.path == '/init' or request.path == '/update' or request.path == '/scan' or request.path == '/poll' or request.path == '/exit':

                try:
                    
                    
                    if request.path == '/scan':
                        if self.DEBUG:
                            print("/scan - initiating scan")
                        state = 'ok'
                        
                        #if self.bl == None:
                            
                        self.bl.power_on()
                        
                        self.get_paired_devices_list()
                        
                        if self.scanning == False:
                            self.scanning = True
                            self.scanning_start_time = time.time()
                            self.do_scan = True
                            
                        return APIResponse(
                            status=200,
                            content_type='application/json',
                            content=json.dumps({'state':state, 'scanning':self.scanning}),
                        )
                            
                            
                    elif request.path == '/poll' or request.path == '/init':
                        if self.DEBUG:
                            print("/poll - returning found bluetooth devices")
                            
                        state = 'ok'
                        
                        if self.scanning == False:
                            try:
                                get_paired = bool(request.body['get_paired'])
                                #print("get_paired: " + str(get_paired))
                                if request.path == '/init' or get_paired == True:
                                    if self.DEBUG:
                                        print("-updating list of paired devices")
                                    self.get_paired_devices_list()
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
                            content=json.dumps({'state':state, 'scanning':self.scanning, 'scan_progress':scan_progress, 'paired':self.paired_devices, 'discovered':self.discovered_devices }),
                        )
                        
                            
                            
                            
                    elif request.path == '/update':
                        if self.DEBUG:
                            print("/update - Updating a single device")
                            
                        if self.made_agent == False:
                            self.made_agent = True
                            make_agent_output = self.bl.make_agent()
                            if self.DEBUG:
                                print("make agent output: " + str(make_agent_output))
                            
                        if self.scanning == True:
                            if self.DEBUG:
                                print("/update - cancelling current scan")
                            #self.cancel_scan = True
                            self.bl.stop_scan()
                            self.scanning = False
                            sleep(.2)
                            
                            #self.bl.make_discoverable(False)
                            #sleep(.2)
                            #self.bl.make_pairable()
                            #sleep(.2)
                            
                        
                            #get_device_info
                    
                        try:
                            state = 'ok'
                            action = str(request.body['action'])
                            mac = str(request.body['mac'])
                            update = "" 
                            
                            print("update action: " + str(action))
                            
                            if action == 'info':
                                if self.DEBUG:
                                    print("getting info")
                                update = 'Unable to get detailed information'
                                try:
                                    update = self.bl.get_device_info(mac)
                                    #sleep(2)
                                except Exception as ex:
                                    print("error getting device info: " + str(ex))
                                    state = False
                                
                            elif action == 'pair':
                                if self.DEBUG:
                                    print("pairing...")
                                update = ''
                                state = False
                                try:
                                    #update = self.bl.trust(mac)
                                    #print(str(update))
                                    state = self.bl.pair(mac)
                                    #sleep(2)
                                    if self.DEBUG:
                                        print("pair succes?____")
                                        print(str(state))
                                        print("---------")
                                    """
                                    sleep(2)
                                    if state:
                                        update = 'paired succesfully'
                                        state = self.bl.connect(mac)
                                        if self.DEBUG:
                                            print("connect success?_____")
                                            print(str(state))
                                            print("---------")
                                        sleep(2)
                                        if state:
                                            update = 'paired and connected succesfully'
                                            state2 = self.bl.trust(mac)
                                            if self.DEBUG:
                                                print("connect success?")
                                                print(str(state2))
                                            if state2:
                                                update = 'paired, connected and trusted succesfully'
                                            else:
                                                update = 'paired, connected succesfully, but was unable to setup automatic reconnecting (trust)'
                                    """
                                except Exception as ex:
                                    print("error pairing: " + str(ex))
                                    state = False
                            
                                if state:
                                    update = 'paired succesfully'
                                    self.get_paired_devices_list()
                            
                            
                            elif action == 'connect':
                                if self.DEBUG:
                                    print("connecting...")
                                update = ''
                                try:
                                    
                                    state = self.bl.connect(mac)
                                    #sleep(2)
                                    if self.DEBUG:
                                        print("connect succes?____")
                                        print(str(state))
                                        print("---------")
                                        
                                    time.sleep(2)
                                    try:
                                        info_test = self.bl.get_device_info(mac)
                                        #print(str(info_test))
                                        for line in info_test:
                                            if self.DEBUG:
                                                print(str(line))
                                            if 'Connected: yes' in line:
                                                if self.DEBUG:
                                                    print("it was connected")
                                                state = True
                                    except Exception as ex:
                                        print("error doing extra test if connected: " + str(ex))
                                        
                                    
                                    #state = self.bl.trust(mac)
                                    #if state:
                                        #if self.DEBUG:
                                            #print("Succesfully trusted device")
                                        
                                    
                                        
                                    
                                        
                                        #sleep(2)
                                    if state:
                                        update = 'connected succesfully'
                                except Exception as ex:
                                    print("error in connecting: " + str(ex))
                                    state = False
                                
                            
                                
                            elif action == 'trust':
                                if self.DEBUG:
                                    print("trusting...")
                                update = 'Failed to trust device'
                                try:
                                    state = self.bl.trust(mac)
                                    if self.DEBUG:
                                        print("trust success?______")
                                        print(str(state))
                                        print("---------")
                                        
                                    if state:
                                        update = 'Succesfully trusted device'
                                    #sleep(2)
                                except Exception as ex:
                                    print("error in trusting: " + str(ex))
                                    state = False
                                    
                                    
                            elif action == 'distrust':
                                if self.DEBUG:
                                    print("trusting...")
                                update = 'Failed to trust device'
                                try:
                                    state = self.bl.trust(mac)
                                    if self.DEBUG:
                                        print("trust success?______")
                                        print(str(state))
                                        print("---------")
                                        
                                    if state:
                                        update = 'Succesfully trusted device'
                                    #sleep(2)
                                except Exception as ex:
                                    print("error in trusting: " + str(ex))
                                    state = False
                                    
                                
                            elif action == 'disconnect':
                                if self.DEBUG:
                                    print("disconnecting...")
                                update = 'Unable to disconnect'
                                try:
                                    state = self.bl.disconnect(mac)
                                    if self.DEBUG:
                                        print("disconnect success?______")
                                        print(str(state))
                                        print("---------")
                                    #sleep(2)
                                    if state:
                                        update = 'Succesfully disconnected'
                                except Exception as ex:
                                    print("error in disconnecting: " + str(ex))
                                    state = False
                            
                                
                            elif action == 'unpair':
                                if self.DEBUG:
                                    print("unpairing...")
                                update = 'Unable to unpair'
                                try:
                                    state = self.bl.remove(mac)
                                    if self.DEBUG:
                                        print("remove success?______")
                                        print(str(state))
                                        print("---------")
                                    #sleep(2)
                                except Exception as ex:
                                    print("error in unpairing: " + str(ex))
                                    state = False
                                
                                time.sleep(2)
                                try:
                                    info_test = self.bl.get_device_info(mac)
                                    #print(str(info_test))
                                    for line in info_test:
                                        if self.DEBUG:
                                            print(str(line))
                                        if 'Paired: yes' in line:
                                            if self.DEBUG:
                                                print("it was still paired")
                                            state = False
                                except Exception as ex:
                                    print("error doing extra test if connected: " + str(ex))
                                
                                if state:
                                    update = 'succesfully unpaired'
                                    self.get_paired_devices_list()
                                        

                            self.scanning = False
                            
                            return APIResponse(
                                status=200,
                                content_type='application/json',
                                content=json.dumps({'state' : state, 'mac': mac,'update' : update }),
                            )
                        except Exception as ex:
                            print("Error updating: " + str(ex))
                            return APIResponse(
                                status=500,
                                content_type='application/json',
                                content=json.dumps({'state' : "Error while updating device", 'update' : "Server error"}),
                            )
                        
                        
                            
                    
                    elif request.path == '/exit':
                        try:
                            if self.DEBUG:
                                print("/exit called")
                            #self.bl.stop_scan()
                            self.bl.make_pairable(False)
                            time.sleep(.2)
                            self.bl.make_discoverable(False)
                            time.sleep(.2)
                            self.bl.exit()
                            
                            return APIResponse(
                                status=200,
                                content_type='application/json',
                                content=json.dumps({'state' : 'ok'}),
                            )
                        except Exception as ex:
                            print("Error exiting: " + str(ex))
                            return APIResponse(
                                status=500,
                                content_type='application/json',
                                content=json.dumps({'state' : 'error exiting'}),
                            )
                        
                    else:
                        return APIResponse(
                            status=500,
                            content_type='application/json',
                            content=json.dumps("Invalid path"),
                        )
                        
                        
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

       

    def unload(self):
        if self.DEBUG:
            print("Shutting down Bluetooth Pairing")
        self.running = False
        time.sleep(2)
        
        #self.save_persistent_data()
        
#
#  Bluetooth class


# from Github user castis
# Based on ReachView code from Egor Fedorov (egor.fedorov@emlid.com)
# Updated for Python 3.6.8 on a Raspberry  Pi


class Bluetoothctl:
    """A wrapper for bluetoothctl utility."""

    def __init__(self):
        subprocess.check_output("rfkill unblock bluetooth", shell=True)
        
        self.logger = logging.getLogger("btctl")

    def exit(self):
        pass
            
    def send(self, command, pause=0):
        result = run_command("sudo bluetoothctl " + command)
        if result != None:
            result = result.strip()
        else:
            result = ""
        print("send result: " + str(result))
        time.sleep(pause)
        return result

    def get_output(self, command):
        """Run a command in bluetoothctl prompt, return output as a list of lines."""
        result = self.send(command)
        if result != None:
            result = result.split("\n")
        print("get_output result: " + str(result))
        return result

    def power_on(self):
        """Send power on."""
        try:
            self.send("power on")
        except Exception as e:
            print("Error in bl power_on: " + str(e))
            self.logger.error(e)

    def start_scan(self):
        """Start bluetooth scanning process."""
        try:
            return self.get_output("--timeout 18 scan on")
            #result = []
            #fire_command("sudo bluetoothctl --timeout 10 scan on")
            
            #for line in run_timed_command("sudo bluetoothctl scan on"):
            #    print("adding scan on line: " + str(line))
            #    result.append(line)
            #return result
            
        except Exception as e:
            print("Error in bl start_scan: " + str(e))
            self.logger.error(e)

    def stop_scan(self):
        """Stop bluetooth scanning process."""
        try:
            self.send("scan off")
        except Exception as e:
            print("Error in bl stop_scan: " + str(e))
            self.logger.error(e)

    def make_discoverable(self,state=True):
        """Make device discoverable."""
        try:
            if state:
                print("-making discoverable")
                self.send("discoverable on")
            else:
                #print("-making undiscoverable")
                self.send("discoverable off")
        except Exception as e:
            self.logger.error(e)


    def make_pairable(self,state=True):
        """Make device pairable."""
        try:
            if state:
                print("-making pariable")
                self.send("pairable on")
            else:
                #print("-making unpariable")
                self.send("pairable off")
        except Exception as e:
            self.logger.error(e)
            
    def make_agent(self):
        """Make agent on."""
        try:
            result = self.send("agent on") 
            # was agent on
            result += self.send("default-agent")
            
            return result
        except Exception as e:
            print("Error in bl make_agent: " + str(e))
            self.logger.error(e)
            return 'Error'
            


    def parse_device_info(self, info_string):
        """Parse a string corresponding to a device."""
        device = {}
        block_list = ["[\x1b[0;", "removed"]
        if not any(keyword in info_string for keyword in block_list):
            try:
                device_position = info_string.index("Device")
            except ValueError:
                pass
            else:
                if device_position > -1:
                    attribute_list = info_string[device_position:].split(" ", 2)
                    device = {
                        "mac": attribute_list[1],
                        "name": attribute_list[2],
                    }
        return device

    def parse_controller_info(self, info_string):
        """Parse a string corresponding to a controller."""
        return info_string

    def get_available_controllers(self):
        """Return a list of tuples of bluetooth controllers."""
        available_controllers = []
        try:
            out = self.get_output("list")
        except Exception as e:
            self.logger.error(e)
        else:
            for line in out:
                controller = self.parse_controller_info(line)
                if controller:
                    available_controllers.append(controller)
        return available_controllers

    def get_available_devices(self):
        """Return a list of tuples of paired and discoverable devices."""
        available_devices = []
        try:
            out = self.get_output("devices")
        except Exception as e:
            self.logger.error(e)
        else:
            for line in out:
                print("get_available_devices line: " + str(line))
                device = self.parse_device_info(line)
                if device:
                    available_devices.append(device)
        return available_devices

    def get_paired_devices(self):
        """Return a list of tuples of paired devices."""
        paired_devices = []
        try:
            out = self.get_output("paired-devices")
        except Exception as e:
            print("Error in bl get_paired_devices: " + str(e))
            self.logger.error(e)
        else:
            print("out: " + str(out))
            for line in out:
                print("paaaiiirrreeed??: " + str(line))
                device = self.parse_device_info(line)
                if device:
                    print("-device: " + str(device))
                    paired_devices.append(device)
        return paired_devices

    def get_discoverable_devices(self):
        """Filter paired devices out of available."""
        available = self.get_available_devices()
        paired = self.get_paired_devices()
        return [d for d in available if d not in paired]

    def get_device_info(self, mac_address):
        """Get device info by mac address."""
        try:
            out = self.get_output(f"info {mac_address}")
        except Exception as e:
            self.logger.error(e)
            return False
        else:
            return out

    def pair(self, mac_address):
        """Try to pair with a device by mac address."""
        try:
            result = self.send(f"pair {mac_address}", 4)
            
            if 'Pairing successful' in result:
                return True
            else:
                return False
            
        except Exception as e:
            self.logger.error(e)
            return False

    def trust(self, mac_address):
        try:
            result = self.send(f"trust {mac_address}", 4)
            if 'Pairing successful' in result:
                return True
            else:
                return False
        except Exception as e:
            self.logger.error(e)
            return False
        #else:
        #    res = self.process.expect(
        #        ["Failed to trust", "Pairing successful", pexpect.EOF]
        #    )
        #    return res == 1

    def remove(self, mac_address):
        """Remove paired device by mac address, return success of the operation."""
        try:
            result = self.send(f"remove {mac_address}", 3)
            if 'Device has been removed' in result:
                return True
            else:
                return False
            #self.send(f"remove {mac_address}", 3)
        except Exception as e:
            self.logger.error(e)
            return False
        #else:
        #    res = self.process.expect(
        #        ["not available", "Device has been removed", pexpect.EOF]
        #    )
        #    return res == 1


    def connect(self, mac_address):
        """Try to connect to a device by mac address."""
        try:
            result = self.send(f"conect {mac_address}", 2)
            if 'Connection successful' in result:
                return True
            else:
                return False
            #self.send(f"connect {mac_address}", 2)
        except Exception as e:
            print("Error in bl connect: " + str(e))
            self.logger.error(e)
            return False
        #else:
        #    res = self.process.expect(
        #        ["Failed to connect", "Connection successful", pexpect.EOF]
        #    )
        #    return res == 1


    def disconnect(self, mac_address):
        """Try to disconnect to a device by mac address."""
        try:
            #self.send(f"disconnect {mac_address}", 2)
            result = self.send(f"disconnect {mac_address}", 2)
            if 'Successful disconnected' in result:
                return True
            else:
                return False
        except Exception as e:
            self.logger.error(e)
            return False
        #else:
        #    res = self.process.expect(
        #        ["Failed to disconnect", "Successful disconnected", pexpect.EOF]
        #    )
        #    return res == 1



















def run_timed_command(command):
    check_count = 0
    p = subprocess.Popen(command,
                         stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE,
                         shell=True)
    # Read stdout from subprocess until the buffer is empty !
    for line in iter(p.stdout.readline, b''):
        if line: # Don't print blank lines
            print("llllline: " + str(line))
            yield line
    # This ensures the process has completed, AND sets the 'returncode' attr
    while p.poll() is None and check_count < 100:                                                                                                                                        
        sleep(.1) #Don't waste CPU-cycles
        print("brr")
        check_count += 1
    # Empty STDERR buffer
    err = p.stderr.read()
    if p.returncode != 0:
       # The run_command() function is responsible for logging STDERR 
       print("Error: " + str(err))






def fire_command(cmd, timeout_seconds=3):
    subprocess.Popen(cmd.split(), stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True, universal_newlines=True)



        
        
def run_command(cmd, timeout_seconds=30):
    try:
        #p = subprocess.Popen(cmd.split(), stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True, universal_newlines=True)
        p = subprocess.run(cmd, timeout=timeout_seconds, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True, universal_newlines=True)

        if p.returncode == 0:
            return p.stdout #.decode('utf-8')
            #yield("Command success")
        else:
            if p.stderr:
                return "Error: " + str(p.stderr) #.decode('utf-8'))

    except Exception as e:
        print("Error running command: "  + str(e))
        
        
def valid_mac(mac):
    return mac.count(':') == 5 and \
        all(0 <= int(num, 16) < 256 for num in mac.rstrip().split(':')) and \
        not all(int(num, 16) == 255 for num in mac.rstrip().split(':'))
