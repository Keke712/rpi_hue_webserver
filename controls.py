import simplepyble # type: ignore
from errors import NO_ADAPTERS_FOUND, NO_DEVICE_FOUND, ERROR_CONNECTING

class Service:
	def __init__(self):
		self.service_uuid = None
		self.characteristic = None

class Adapter:
	def __init__(self):
		# scan adapter
		adapters = simplepyble.Adapter.get_adapters()
		if len(adapters) == 0:
			return NO_ADAPTERS_FOUND

		# select adapter
		self.adapter = adapters[0]
		self.identifier = self.adapter.identifier()
		self.address = self.adapter.address()

	def scan_devices(self):
		# Scan for 5 seconds
		print("Adapter scanning devices (5s)")
		self.adapter.scan_for(5000)
		return self.adapter.scan_get_results()

	def select_device(self, dlist, address):
		for i in dlist:
			if i.address() == address:
				return i
		print(NO_DEVICE_FOUND)
		return False

	# select peri
	def connect(self, device):
		# connect peri
		try:
			device.connect()
			print("Connected")
			return True
		except Exception:
			print(ERROR_CONNECTING + str(Exception))
			return False

	def scan_services(self, device):
		# scan services
		services = device.services()
		service_characteristic_pair = []
		for service in services:
			for characteristic in service.characteristics():
				service_characteristic_pair.append((service.uuid(), characteristic.uuid()))
		return service_characteristic_pair

	def get_uuid_by_char(self, device, slist, char):
		# select services
		for i, (service_uuid, characteristic) in enumerate(slist):
			if characteristic == char:
				return service_uuid

	def write(self, device, service_uuid, characteristic_uuid, content):
		# write
		device.write_request(service_uuid, characteristic_uuid, content)
		return True

	def read(self, device, service_uuid, characteristic_uuid):
		return device.read(service_uuid, characteristic_uuid)