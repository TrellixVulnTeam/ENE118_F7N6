from kivymd.uix.screen import MDScreen
from kivymd.uix.snackbar import Snackbar
from popups import ModbusPopup, ConfigPopup , DataGraphPopup
from pyModbusTCP.client import ModbusClient
from threading import Thread, Lock
from time import sleep
from datacards import CardCoil,CardInputRegister,CardHoldingRegister
from datetime import datetime
import random
from kivy.clock import Clock
from functools import partial
from sqlalchemy import engine
from db import Session, Base, engine
from models import DadosCLP
from tabulate import tabulate
from timeseriesgraph import  TimeSeriesGraph

class MainWidget(MDScreen):
    """
    Widget principal da aplicação
    """
    _updateThread = None
    _updateWidgets = True
    _tags = {}
    _max_points = 20

    def __init__(self,**kwargs):
        """
        Construtor do Widget principal
        """
        super().__init__()
        self._velramp = kwargs.get('vel_ramp')
        self._serverIP = kwargs.get('server_ip')
        self._serverPort = kwargs.get('server_port')
        self._modbusPopup = ModbusPopup(self._serverIP,self._serverPort)
        self._configPopup = ConfigPopup(self._velramp)
        self._modbusClient = ModbusClient(host=self._serverIP, port=self._serverPort)
        self._tags = kwargs.get('tags')
        self._meas = {}
        self._meas['timestamp'] = None
        self._meas['values'] = {}
        self._session = Session()
        Base.metadata.create_all(engine)
        self._lock = Lock()
        for tag in self._tags:
            plot_color = (random.random(),random.random(),random.random(),1)
            tag['color'] = plot_color


        for tag in self._tags:
            if tag['type'] == 'input':
                self.ids.modbus_data.add_widget(CardInputRegister(tag,self._modbusClient))
            elif tag['type'] == 'holding':
                self.ids.act_planta.add_widget(CardHoldingRegister(tag,self._modbusClient))
            elif tag['type'] == 'coil':
                self.ids.act_planta.add_widget(CardCoil(tag,self._modbusClient))

 #       self._graph = DataGraphPopup(self._max_points,self._tags['peso_obj']['color'])



    def conect_button(self, button):
        self._modbusPopup.open()


    def startDataRead(self,ip,port):
        """
        Método utilizado para a configuração do IP e porta
        do servidor MODBUS e inicializar uma thread para a
        leitura dos dados e atualização da interface gráfica
        :param ip: Ip do servidor MODBUS
        :param port: Porta do serviço
        """

        self._serverIP = ip
        self._serverPort = int(port)
        self._modbusClient.host = self._serverIP
        self._modbusClient.port = self._serverPort
        try:
            self._modbusClient.open()
            if self._modbusClient.is_open():
                self._guardar_dados = Thread(target=self.guardar_dados)
                self._updateThread = Thread(target=self.updater)
                self._updateThread.start()
                self._guardar_dados.start()

                Snackbar(text='[color=#000000] Conexão Realizada [/color]', bg_color=(0,1,0,1)).open()
                self.ids.status_con.source = 'imgs/conectado.png'
                self._modbusPopup.dismiss()

            else:
                self._modbusClient.last_error()
                self._modbusPopup.setInfo('Falha na Conexão com o Servidor')

        except Exception as e:
            print('Erro: ', e.args)


    def updater(self):
        """"
        Método que invoca as rotinas de leitura, atualização da interface
        e inserção dos dados no Banco de Dados
        """
        try:
            while self._updateWidgets:
                self.readData() # Leitura de dados
                self.updateGUI() # Atualização da IHM
                #self.guardar_dados() # Inserir os Dados no BD
                #Atualização do Gráfico
                #self._graph.ids.graph.updateGraph((self._meas['timestamp'], self._meas['values']['peso_obj']), 0)
                sleep(self._velramp/1000)

        except Exception as e:
            self._modbusClient.close()
            Snackbar(text='Conexão Encerrada',bg_color=(1,0,0,1)).open()
            self.ids.status_con.source = 'imgs/desconectado.png'
            print('Erro: ', e.args)

    def readData(self):
        """
        Método para a leitura dos dados por meio do protocolo MODBUS
        """
        self._meas['timestamp'] = datetime.now()

        for card in self.ids.modbus_data.children:
            if card.tag['type'] == 'input':
                self._meas['values'][card.tag['name']] = card.update_data()

        for card in self.ids.act_planta.children:
            if card.tag['type'] == 'holding' or card.tag['type'] == 'coil':
                self._meas['values'][card.tag['name']] = card.update_data()
    
    def updateImage(self,img_src,dt):
        self.ids['img_peca'].source = img_src

    def updateBackground(self,img_src,dt):
        self.ids['img_planta'].source = img_src



    def updateGUI(self,**kwargs):
        """
        Método para atualização da interface gráfica a partir dos dados lidos
        """
        # Atualização dos Labels

        if self._meas['values']['bt_Desliga_Liga'] == True:
            Clock.schedule_once(partial(self.updateBackground, 'imgs/planta_off.png'))
            Clock.schedule_once(partial(self.updateImage, 'imgs/standby.png'))
        else:
            Clock.schedule_once(partial(self.updateBackground,'imgs/planta_on.jpg'))


            self.ids['info_cor'].text = 'Nenhum Objeto'
            self.ids['info_cor'].color = 0, 0, 0, 1
            self.ids['info_velramp'].text = f"Vel.Esteira: {self._meas['values']['vel_esteira']} m/s"
            self.ids['info_tensaorede'].text = f"Tensão: {self._meas['values']['tensao']} V"
            Clock.schedule_once(partial(self.updateImage,'imgs/load.png'))


            R = G = B = 0

            for card in self.ids.modbus_data.children:
                if card.tag['address'] in [813,814,815,816]:
                    self.ids[card.tag['name']].text = str(self._meas['values'][card.tag['name']])
                if card.tag['address'] == 809:
                    self.ids[card.tag['name']].text = str(self._meas['values'][card.tag['name']]) + ' Kg'
                if card.tag['address'] == 810:
                    R = self._meas['values'][card.tag['name']]
                if card.tag['address'] == 811:
                    G = self._meas['values'][card.tag['name']]
                if card.tag['address'] == 812:
                    B = self._meas['values'][card.tag['name']]


            if R == G == B == 0:
                self.ids['info_cor'].text = 'Preto'
                self.ids['info_cor'].color = 0, 0, 0, 1
                Clock.schedule_once(partial(self.updateImage,'imgs/peca_preta.jpg'))

            if R == G == B == 0:
                self.ids['info_cor'].text = 'Branco'
                self.ids['info_cor'].color = 0.5, 0.5, 0.5, 1
                Clock.schedule_once(partial(self.updateImage,'imgs/peca_branca.png'))

            if R == G > B:
                self.ids['info_cor'].text = 'Amarelo'
                self.ids['info_cor'].color = 1,1,0,1
                Clock.schedule_once(partial(self.updateImage,'imgs/peca_rg.jpg'))

            if R == B > G:
                self.ids['info_cor'].text = 'Rosa'
                self.ids['info_cor'].color = 1,0,1,1
                Clock.schedule_once(partial(self.updateImage,'imgs/peca_rb.jpg'))

            if B == G > R:
                self.ids['info_cor'].text = 'Ciano'
                self.ids['info_cor'].color = 0,1,1,1
                Clock.schedule_once(partial(self.updateImage,'imgs/peca_gb.jpg'))


            if R > G and R > B:
                self.ids['info_cor'].text = 'Vermelho'
                self.ids['info_cor'].color = 1,0,0,1
                Clock.schedule_once(partial(self.updateImage,'imgs/peca_r.png'))



            if G > R and G > B:
                self.ids['info_cor'].text = 'Verde'
                self.ids['info_cor'].color = 0,1,0,1
                Clock.schedule_once(partial(self.updateImage,'imgs/peca_g.jpg'))

            if B > G and B > R:
                self.ids['info_cor'].text = 'Azul'
                self.ids['info_cor'].color = 0,0,1,1
                Clock.schedule_once(partial(self.updateImage,'imgs/peca_b.png'))

            #self._scan_time = self.ids['vel_esteira'].text
            #self._tags_addrs = self._meas['address']




    def stopRefresh(self):
        self._updateWidgets = False

    def guardar_dados(self):
        """
        Método para a leitura dos dados do servidor e armazenamento no BD
        """
        try:
            print("Persistencia iniciada")
            self._modbusClient.is_open()
            data = {}
            while True:
                data['timestamp'] = datetime.now()
                for tag in self._tags:
                    data[tag['name']] = self._meas['values'][tag['name']]
                dado = DadosCLP(**data)
                self._lock.acquire()
                self._session.add(dado)
                self._session.commit()
                self._lock.release()
                sleep(self._velramp/1000)


        except Exception as e:
            print("Erro na persistencia de dados: ", e.args)

    def acesso_dados_historicos(self):
        """
        Método que permite ao usuário acessar dados históricos
        """
        try:
            print("Bem vindo ao sistema de busca de dados históricos")
            while True:
                init = input("Digite o horário inicial para a busca (DD/MM/AAAA HH:MM:SS): ")
                final = input("Digite o horário final para a busca (DD/MM/AAAA HH:MM:SS): ")
                init = datetime.strptime(init,'%d/%m/%Y %H:%M:%S')
                final = datetime.strptime(final,'%d/%m/%Y %H:%M:%S')
                self._lock.acquire()
                result = self._session.query(DadosCLP.timestamp.between(init,final)).all()
                result_fmt_list = [obj.get_attr_printable_list() for obj in result]
                self._lock.release()
                sleep(self._velramp/1000)
                print(tabulate(result_fmt_list,headers=DadosCLP.__table__.columns.keys()))

        except Exception as e:
            print("Erro na persistencia de dados: ", e.args)












