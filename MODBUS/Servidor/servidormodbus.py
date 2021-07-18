import random
from pyModbusTCP.server import DataBank, ModbusServer
from time import sleep

class ServidorMODBUS():
    """
    Classe Servidor MODBUS
    """
    def __init__(self,host_ip,porta):
        """
        Construtor da Classe Servidor MODBUS
        """
        self._server = ModbusServer(host=host_ip,port=porta, no_block=True)
        self._db = DataBank()

    def run(self):
        """
        Inicia a execução do serviço
        """
        try:
            self._server.start()
            print("Servidor MODBUS em Execução")
            while True:
                self._db.set_words(1000, [random.randrange(int(0.95*400), int(1.05*400))])
                print('-'*50)
                print('Tabela MODBUS')
                print(f'Holding Register  \r\n R1000: {self._db.get_words(1000)} \r \n R2000: {self._db.get_words(2000)}')
                print(f'Coil \r\n R1000: {self._db.get_bits(1000)}')
                sleep(1)
        except Exception as e:
            print("Erro ", e.args)

