import os
import sys
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'lib'))
import json
import asyncio
from uuid import UUID

from construct import Array, Byte, Const, Int8sl, Int16ub, Struct
from construct.core import ConstError

from bleak import BleakScanner
#from bleak.assigned_numbers import AdvertisementDataType
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData
from bleak.backends.bluezdbus.advertisement_monitor import OrPattern
from bleak.backends.bluezdbus.scanner import BlueZScannerArgs, BlueZDiscoveryFilters

#print("import complete")
ibeacon_format = Struct(
    "type_length" / Const(b"\x12\x19"),
    "uuid" / Array(16, Byte),
    "major" / Int16ub,
    "minor" / Int16ub,
    "power" / Int8sl,
)

duration = 2 # seconds to scan
if len(sys.argv) > 1:
    duration = int(sys.argv[1])


spotted = []

def device_found(device: BLEDevice, advertisement_data: AdvertisementData):

    try:
        
        #print(f"\nTAG: address:{device.address}, \nname:{device.name}, \ndetails:{device.details} \n{device.rssi} \n{advertisement_data}")
        #print("advertisement_data.manufacturer_data: " + str(advertisement_data.manufacturer_data))
        #print(f"{device.name}")
        #device_name = f"{device.name}"
        
        #print("device_name: " + str(device_name))
        #print(f"{device.details}")
        
        #remove binary values, which hinder JSON printing
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
                    #if type(properties[k]) == str or type(properties[k]) == bool or type(properties[k]) == int:
                    #    cleaned[k.lower()] = properties[k]
                    #else:
                    #    cleaned[k.lower()] = properties[k].decode('utf8', errors='ignore')
                
        spotted.append(cleaned)
        
                
        # manufacturer ID's can be looked up here: https://www.bluetooth.com/specifications/assigned-numbers/company-identifiers/

        #apple_data = advertisement_data.manufacturer_data[0x004C]
        #ibeacon = ibeacon_format.parse(apple_data)
        #uuid = UUID(bytes=bytes(ibeacon.uuid))
        
#        print(device.address, "RSSI:", device.rssi, advertisement_data)
#        print(f"MAC= {device.address}")
        #print(f"Airtag {device.address} {device.rssi} {uuid} {advertisement_data.manufacturer_data[0x004C]}")
#        print(f"UUID= {uuid}")
#        print(f"Major    : {ibeacon.major}")
#        print(f"Minor    : {ibeacon.minor}")
#        print(f"TX power : {ibeacon.power} dBm")
#        print(f"RSSI= {device.rssi}")
#        print(device.address, "RSSI:", device.rssi, advertisement_data)

#        print(47 * "-")
    except KeyError as ex:
        #print("\nnot an apple device: " + str(ex))
        # Apple company ID (0x004c) not found
        pass
    except ConstError:
        #print("no ibeacon type")
        # No iBeacon (type 0x02 and length 0x15)
        pass


async def main():
    """Scan for devices."""
    
    #or_patterns = [
    #    OrPattern(0, AdvertisementDataType.FLAGS, b"\x06"),
    #]
    args = BlueZScannerArgs(
        #or_patterns=[OrPattern(0, AdvertisementDataType.MANUFACTURER_SPECIFIC_DATA, b"")]
        #or_patterns=[OrPattern(0, AdvertisementDataType.MANUFACTURER_SPECIFIC_DATA, b"")]
        or_patterns=[OrPattern(0, AdvertisementDataType.FLAGS, b"\x06")],
    )
    
    
    scanner = BleakScanner(bluez=args,detection_callback=device_found,scanning_mode="passive")
    #scanner.register_detection_callback(device_found)

    #while True:
#    print("boop")
    await scanner.start()
    await asyncio.sleep(duration)
    await scanner.stop()
    print(str(json.dumps(spotted, indent=4)))
    #await asyncio.sleep(5.0)

#print("Starting asyncio thread")
asyncio.run(main())


