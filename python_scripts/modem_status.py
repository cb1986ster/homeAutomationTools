#!/usr/bin/env python3.6

import telnetlib, time
import requests
import json
import re
import paho.mqtt.publish as publish
import datetime

# Local domoticz update
def updateDomoticz(idx,value):
    data = {
    	'idx':idx,
    	'svalue':str(value)
    }
    msg = json.dumps(data)
    publish.single("domoticz/in", msg, hostname="192.168.1.35", port=1883)


# Telnet interface for ZTE MF823
class zteMf823:
    telnet_user_name = b'root'
    telnet_user_pass = b'zte9x15'

    host = '192.168.0.1'

    _con = None
    _prompt = b"!!!!!MAGIC_PROMPT!!!!!"

    def __init__(self):
        self.__last_web_data_read = datetime.datetime.now()
        self.reload_web_data(force=True)
        self.connect()

    def run(self,cmd,timeout=30):
        cmd = bytes(cmd,'utf-8') + b"\n"
        self._con.write(cmd)
        self._con.read_until(b"\r\n")
        ret = self._con.read_until(self._prompt,timeout)[:-len(self._prompt)]
        return ret.decode('utf-8')

    def read(self,file):
        return self.run("cat \"{}\"".format(file))

    def connect(self):
        self._con = telnetlib.Telnet(self.host)
        self._con.read_until(b"login: ")
        self._con.write(self.telnet_user_name + b"\n")
        self._con.read_until(b"Password:")
        self._con.write(self.telnet_user_pass + b"\n")
        self._con.write(b"PS1="+self._prompt+b"\r\n")
        while self._con.read_until(self._prompt,0.5) != b'':pass

    def disconnect(self):
        self._con.write(b"exit\n")
        self._con.read_all()

    def get_load(self):
        return [int(float(v)*100) for v in self.read('/proc/loadavg').strip().split()[:3] ]

    def get_temp(self):
        return int(self.read('/sys/class/thermal/thermal_zone0/temp').strip())

    def get_txrx(self):
        tx,rx = None,None
        for line in self.run('ifconfig rmnet0').strip().splitlines():
            m = re.findall('^.*RX bytes:(\d*) .*TX bytes:(\d*) .*$',line)
            if m:
                rx,tx = int(m[0][0]),int(m[0][1])
        return tx,rx

    def get_lte_rssi(self):
        self.reload_web_data()
        return self.__web_data['lte_rssi']

    def get_lte_snr(self):
        self.reload_web_data()
        return self.__web_data['lte_snr']

    __last_web_data_read = None
    __web_data = {}
    def reload_web_data(self, force = False):
        n = datetime.datetime.now()
        td = n - self.__last_web_data_read
        if force or td.total_seconds() > 20:
            self.__last_web_data_read = n
            url = 'http://{}/goform/goform_get_cmd_process?cmd=signalbar,wan_csq,network_type,network_provider,ppp_status,modem_main_state,rmcc,rmnc,,domain_stat,cell_id,rssi,rscp,lte_rssi,lte_rsrq,lte_rsrp,lte_snr,ecio,sms_received_flag,sts_received_flag,simcard_roam&multi_data=1&sms_received_flag_flag=0&sts_received_flag_flag=0'.format(self.host)
            self.__web_data = json.loads(requests.get(url).text)


def main():
    while True:
        try:
            modem = zteMf823()
            last_txrx = modem.get_txrx()
            while True:
                updateDomoticz(50,modem.get_lte_rssi())
                updateDomoticz(49,modem.get_lte_snr())
                updateDomoticz(47,modem.get_temp())
                updateDomoticz(46,modem.get_load()[1])
                time.sleep(60)
                txrx = modem.get_txrx()
                rtx = float(txrx[0]+txrx[1]) / (1024**2)
                last_rtx = float(last_txrx[0]+last_txrx[1]) / (1024**2)
                if rtx > last_rtx:
                    val = rtx - last_rtx
                    if val > 0:
                        speed = val/60
                        updateDomoticz(51,round(1024*speed,3))
                        val = round(val,6)
                        updateDomoticz(48,val)
                last_txrx = txrx
        except Exception as e:
            time.sleep(10)

if __name__ == "__main__":
    main()
