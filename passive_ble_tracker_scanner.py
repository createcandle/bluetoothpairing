import os
import sys
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'lib'))
import json
import base64
import struct
import asyncio


from bleak import BleakScanner
from bleak.args.bluez import OrPattern, BlueZScannerArgs
from bleak.assigned_numbers import AdvertisementDataType

timeout_seconds = 2
if len(sys.argv) > 1:
    timeout_seconds = int(sys.argv[1])
#print("timeout_seconds: ", timeout_seconds)
#address_to_look_for = 'F1:D9:3B:39:4D:A2'
#service_id_to_look_for = '0000feaa-0000-1000-8000-00805f9b34fb'

class MyScanner:
    def __init__(self):
        self.results = []
        """
        args=BlueZScannerArgs(                                                                                                                                                          
           or_patterns=[                                                                                                                                                                  
             OrPattern(0, AdvertisementDataType.FLAGS, b"\x00"),                                                                                                                          
             OrPattern(0, AdvertisementDataType.FLAGS, b"\x01"),                                                                                                                          
             OrPattern(0, AdvertisementDataType.FLAGS, b"\x02"),                                                                                                                          
             OrPattern(0, AdvertisementDataType.FLAGS, b"\x03"),                                                                                                                          
             OrPattern(0, AdvertisementDataType.FLAGS, b"\x04"),                                                                                                                          
             OrPattern(0, AdvertisementDataType.FLAGS, b"\x05"),                                                                                                                          
             OrPattern(0, AdvertisementDataType.FLAGS, b"\x06"),                                                                                                                          
             OrPattern(0, AdvertisementDataType.FLAGS, b"\x07"),                                                                                                                          
             OrPattern(0, AdvertisementDataType.FLAGS, b"\x08"),                                                                                                                          
             OrPattern(0, AdvertisementDataType.FLAGS, b"\x09"),                                                                                                                          
             OrPattern(0, AdvertisementDataType.FLAGS, b"\x0a"),                                                                                                                          
             OrPattern(0, AdvertisementDataType.FLAGS, b"\x0b"),                                                                                                                          
             OrPattern(0, AdvertisementDataType.FLAGS, b"\x0c"),                                                                                                                          
             OrPattern(0, AdvertisementDataType.FLAGS, b"\x0d"),                                                                                                                          
             OrPattern(0, AdvertisementDataType.FLAGS, b"\x0e"),                                                                                                                          
             OrPattern(0, AdvertisementDataType.FLAGS, b"\x0f"),                                                                                                                          
                                                                                                                                                                                  
             OrPattern(0, AdvertisementDataType.FLAGS, b"\x10"),                                                                                                                          
             OrPattern(0, AdvertisementDataType.FLAGS, b"\x11"),                                                                                                                          
             OrPattern(0, AdvertisementDataType.FLAGS, b"\x12"),                                                                                                                          
             OrPattern(0, AdvertisementDataType.FLAGS, b"\x13"),                                                                                                                          
             OrPattern(0, AdvertisementDataType.FLAGS, b"\x14"),                                                                                                                          
             OrPattern(0, AdvertisementDataType.FLAGS, b"\x15"),                                                                                                                          
             OrPattern(0, AdvertisementDataType.FLAGS, b"\x16"),                                                                                                                          
             OrPattern(0, AdvertisementDataType.FLAGS, b"\x17"),                                                                                                                          
             OrPattern(0, AdvertisementDataType.FLAGS, b"\x18"),                                                                                                                          
             OrPattern(0, AdvertisementDataType.FLAGS, b"\x19"),                                                                                                                          
             OrPattern(0, AdvertisementDataType.FLAGS, b"\x1a"),                                                                                                                          
             OrPattern(0, AdvertisementDataType.FLAGS, b"\x1b"),                                                                                                                          
             OrPattern(0, AdvertisementDataType.FLAGS, b"\x1c"),                                                                                                                          
             OrPattern(0, AdvertisementDataType.FLAGS, b"\x1d"),                                                                                                                          
             OrPattern(0, AdvertisementDataType.FLAGS, b"\x1e"),                                                                                                                          
             OrPattern(0, AdvertisementDataType.FLAGS, b"\x1f")                                                                                                                           
           ]                                                                                                                                                                              
         )
        """
        
        args=BlueZScannerArgs(
            or_patterns=[
                OrPattern(0, AdvertisementDataType.FLAGS, b"\x02"),
                OrPattern(0, AdvertisementDataType.FLAGS, b"\x06"),
                OrPattern(0, AdvertisementDataType.FLAGS, b"\x10"),
                OrPattern(0, AdvertisementDataType.FLAGS, b"\xff"),
                OrPattern(0, AdvertisementDataType.FLAGS, b"\x1a")
            ]
        )
        self._scanner = BleakScanner(bluez=args, return_adv=True, detection_callback=self.detection_callback,scanning_mode="passive")
        #self._scanner.register_detection_callback(self.detection_callback)
        self.scanning = asyncio.Event()

    def detection_callback(self, device, advertisement_data):
        # Looking for:
        # AdvertisementData(service_data={
        # '0000feaa-0000-1000-8000-00805f9b34fb': b'\x00\xf6\x00\x00\x00Jupiter\x00\x00\x00\x00\x00\x0b'},
        # service_uuids=['0000feaa-0000-1000-8000-00805f9b34fb'])
        
        #print("device.address: ", device.address)
        
        # https://bleak.readthedocs.io/en/latest/api/index.html
        
        """
        found = {
            "address":device.address,
            "name":device.name,
            "details":device.details,
            "advertisement":{}
            }
            
        # https://bleak.readthedocs.io/en/latest/backends/index.html#bleak.backends.scanner.AdvertisementData
        found['advertisement']['local_name'] = advertisement_data.local_name
        found['advertisement']['manufacturer_data'] = advertisement_data.manufacturer_data
        found['advertisement']['platform_data'] = list(advertisement_data.platform_data)
        found['advertisement']['rssi'] = advertisement_data.rssi
        found['advertisement']['service_data'] = advertisement_data.service_data
        found['advertisement']['service_uuids'] = advertisement_data.service_uuids
        found['advertisement']['tx_power'] = advertisement_data.tx_power
        """
        
        cleaned = {'manufacturer':0,'type':'normal','name':str(device.name)}
        
        properties = device.details['props']
        for k in properties:
            #print("$ " + str(k) + " - " + str(type( properties[k] )))
            if isinstance(properties[k], dict):
                cleaned[k.lower()] = {}
                for u in properties[k]:
                    
                    if type(properties[k][u]) == bytearray:
                        properties[k][u] = bytes(properties[k][u])
                    
                    #print(">> " + str(u))
                    #print("-->>" + str(properties[k][u]))
                    cleaned[k.lower()][u] = str(properties[k][u])
                    if k == 'ManufacturerData':
                        #print("manufacturerdata spotted")
                        cleaned['manufacturer'] = u
                        cleaned['binary'] = str(properties[k][u])
                        #print("[0]: " + str(properties[k][u][0]))
                        #print("[1]: " + str(properties[k][u][1]))
                        #print("[2]: " + str(properties[k][u][2]))
                        #print("[3]: " + str(properties[k][u][3]))
                        
                        if "'\\x12\\x19" in cleaned['binary']:
                            #print(">> Airtag spotted")
                            cleaned['name'] = 'Airtag'
                            cleaned['type'] = 'tracker'                            
                            cleaned['airtag_status'] = str(properties[k][u][3])
                            cleaned['airtag_public_key'] = str(properties[k][u][4]) + '.' + str(properties[k][u][5]) + '.' + str(properties[k][u][6]) + '.' + str(properties[k][u][7]) + '.' + str(properties[k][u][8]) + '.' + str(properties[k][u][9])
                            
                        
                        if "'\\x02\\x15" in cleaned['binary']:
                            #print(">> Beacon spotted")
                            cleaned['name'] = 'Beacon'
                            cleaned['type'] = 'tracker'
                            
            elif isinstance(properties[k], list):
                try:
                    cleaned[k.lower()] = []
                    for u in properties[k]:
                        cleaned[k.lower()].append(str(u))
                except Exception as ex:
                    #print("list error: " + str(ex))
                    pass
                    
            elif not isinstance(properties[k], bytes):
                if k == 'Name':
                    if 'tile' in properties[k].lower():
                        #print(">> TILE SPOTTED")
                        cleaned['type'] = 'tracker'
                else:
                    cleaned[k.lower()] = properties[k]
                    #print("type: " + str(type(properties[k])))
                    if type(properties[k]) == bytearray:
                        properties[k]= bytes(properties[k])
                        
                    cleaned[k.lower()] = str(properties[k])
        
        
        #found['tracker_details'] = cleaned
        
        
        
        
        
        
        self.results.append(cleaned)
        
        #print("found: ", found)
        
        #print("device: ", type(device), device)
        #print("device.keys(): ", device.keys())
        #print("advertisement_data: ", type(advertisement_data), advertisement_data)
        #if device.address == address_to_look_for:
        #    byte_data = advertisement_data.service_data.get(service_id_to_look_for)
        #    num_to_test, = struct.unpack_from('<I', byte_data, 0)
        #    if num_to_test == 62976:
        #        print('\t\tDevice found so we terminate')
        #        self.scanning.clear()

    async def run(self):
        
        def custom_encoder(obj):
            if isinstance(obj, bytes):
                return base64.b64encode(obj).decode('utf-8')  # Convert bytes to Base64 string
                #return obj.decode('utf-8')  # Convert bytes to string
            raise TypeError(f'Object of type {type(obj)} is not JSON serializable')
            
        await self._scanner.start()
        self.scanning.set()
        end_time = loop.time() + timeout_seconds
        while self.scanning.is_set():
            if loop.time() > end_time:
                self.scanning.clear()
                #end_time = loop.time() + timeout_seconds
                #with open('/run/ble_advertisements.json', 'w') as json_file:
                #    json.dump(self.results, json_file, default=custom_encoder, indent=2)
                #print(json.dumps(results, default=custom_encoder, indent=2))
                print(json.dumps(self.results, indent=4))
                #self.results = []
            await asyncio.sleep(0.1)
        await self._scanner.stop()


if __name__ == '__main__':
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    my_scanner = MyScanner()
    #loop = asyncio.get_event_loop()
    loop.run_until_complete(my_scanner.run())

    
    
