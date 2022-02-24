import os
import sys
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'lib'))


import asyncio
from uuid import UUID

from construct import Array, Byte, Const, Int8sl, Int16ub, Struct
from construct.core import ConstError

from bleak import BleakScanner
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData

#print("import complete")
ibeacon_format = Struct(
    "type_length" / Const(b"\x12\x19"),
    "uuid" / Array(16, Byte),
    "major" / Int16ub,
    "minor" / Int16ub,
    "power" / Int8sl,
)


def device_found(
    device: BLEDevice, advertisement_data: AdvertisementData
):
#    print(device.address, "RSSI:", device.rssi, advertisement_data)



    """Decode iBeacon."""
    try:

        apple_data = advertisement_data.manufacturer_data[0x004C]
        ibeacon = ibeacon_format.parse(apple_data)
        uuid = UUID(bytes=bytes(ibeacon.uuid))
#        print(device.address, "RSSI:", device.rssi, advertisement_data)
#        print(f"MAC= {device.address}")
        print(f"Airtag {device.address} {device.rssi} {uuid} {advertisement_data.manufacturer_data[0x004C]}")
#        print(f"UUID= {uuid}")
#        print(f"Major    : {ibeacon.major}")
#        print(f"Minor    : {ibeacon.minor}")
#        print(f"TX power : {ibeacon.power} dBm")
#        print(f"RSSI= {device.rssi}")
#        print(device.address, "RSSI:", device.rssi, advertisement_data)

#        print(47 * "-")
    except KeyError:
#        print("\nnot an apple device\n")
        # Apple company ID (0x004c) not found
        pass
    except ConstError:
#        print("no ibeacon type")
        # No iBeacon (type 0x02 and length 0x15)
        pass


async def main():
    """Scan for devices."""
    scanner = BleakScanner()
    scanner.register_detection_callback(device_found)

    #while True:
#    print("boop")
    await scanner.start()
    await asyncio.sleep(10.0)
    await scanner.stop()
    #await asyncio.sleep(5.0)

#print("Starting asyncio thread")
asyncio.run(main())


