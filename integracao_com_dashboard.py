import time
from machine import UART
import struct
import network
import umqtt.robust

# ---------- CONFIGURAÇÕES ----------
WIFI_SSID = 'MinhaRede'
WIFI_PASSWORD = 'ypga2508'

# Sessão única para o Freeboard (mude para outro nome se quiser separar dashboards)
EASYMQTT_SESSION = "dashboard_Integrac_BIPES"

# Broker BIPES
MQTT_SERVER = "bipes.net.br"
MQTT_PORT = 1883
MQTT_USER = "bipes"
MQTT_PASSWORD = "m8YLUr5uW3T"

# ---------- FUNÇÕES AUXILIARES ----------
def calculate_crc(data):
    """Calcula o CRC Modbus."""
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x0001:
                crc >>= 1
                crc ^= 0xA001
            else:
                crc >>= 1
    return crc & 0xFFFF

def setup_uart():
    """Configura UART para Modbus RTU."""
    return UART(2, baudrate=9600, tx=17, rx=16, parity=None, stop=2, bits=8, timeout=200)

def create_modbus_request(slave_address, function_code, start_address, register_count):
    """Cria pacote Modbus de leitura."""
    start_address_high = (start_address >> 8) & 0xFF
    start_address_low = start_address & 0xFF
    register_count_high = (register_count >> 8) & 0xFF
    register_count_low = register_count & 0xFF

    request = bytearray([
        slave_address,
        function_code,
        start_address_high,
        start_address_low,
        register_count_high,
        register_count_low
    ])

    crc = calculate_crc(request)
    request += bytearray([crc & 0xFF, (crc >> 8) & 0xFF])
    return request

def process_response(response):
    """Processa resposta Modbus RTU."""
    if not response:
        return None, "Nenhuma resposta recebida."

    data = response[:-2]
    received_crc = struct.unpack('<H', response[-2:])[0]
    calculated_crc = calculate_crc(data)

    if received_crc != calculated_crc:
        return None, "Erro: CRC inválido."

    byte_count = response[2]
    registers = [
        (response[i] << 8) | response[i + 1]
        for i in range(3, 3 + byte_count, 2)
    ]

    return registers, "CRC válido."

def setup_wifi():
    """Conecta ao Wi-Fi."""
    sta_if = network.WLAN(network.STA_IF)
    sta_if.active(True)
    sta_if.connect(WIFI_SSID, WIFI_PASSWORD)
    print("Conectando ao Wi-Fi...")
    while not sta_if.isconnected():
        time.sleep(1)
    print("Wi-Fi conectado:", sta_if.ifconfig())
    return sta_if

def setup_mqtt():
    """Configura cliente MQTT para broker do BIPES."""
    mqtt_client = umqtt.robust.MQTTClient(
        "umqtt_client",
        server=MQTT_SERVER,
        port=MQTT_PORT,
        user=MQTT_USER,
        password=MQTT_PASSWORD
    )
    mqtt_client.connect()
    print("MQTT conectado ao BIPES")
    return mqtt_client

# ---------- PROGRAMA PRINCIPAL ----------
def main():
    uart = setup_uart()
    setup_wifi()
    mqtt_client = setup_mqtt()

    slave_address = 0x01
    function_code = 0x03
    start_address = 0x4338
    register_count = 0x04

    request = create_modbus_request(slave_address, function_code, start_address, register_count)
    print("Enviando pacote Modbus:", request)

    contador = 0
    while True:
        uart.write(request)
        time.sleep(1)
        response = uart.read(16)

        registers, message = process_response(response)
        print(message)

        if registers is not None:
            contador += 1
            # Publica cada valor de forma legível para o Freeboard
            mqtt_client.publish(EASYMQTT_SESSION + "/registro1", str(registers[0]))
            mqtt_client.publish(EASYMQTT_SESSION + "/registro2", str(registers[1]))
            mqtt_client.publish(EASYMQTT_SESSION + "/registro3", str(registers[2]))
            mqtt_client.publish(EASYMQTT_SESSION + "/registro4", str(registers[3]))

            print(f"Enviado para dashboard sessão {EASYMQTT_SESSION}: {registers}")

        time.sleep(1)

if __name__ == "__main__":
    main()

