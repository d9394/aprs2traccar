#!/usr/bin/python3.8
#coding=utf8

import sys
sys.path.append('./aprs-python-master/')
import aprslib
from socket import * 
import requests
import re,json,threading,queue
import time
from datetime import datetime,timedelta
import http.server
import base64
import urllib.request

config={
	"udp_car_server":("10.1.1.1:50025",),
	"udp_aprs_server":("aprs.hellocq.net:14580",),
	"relay_aprs_id":("AA111-5","BB2BB-7","cc3cc-6",),
	"relay_car_id":("00000000","00000001","LM0C0174","00000059","00000072",),
	"aprs_user":('N0CALL-1','13023'),
	"tcp_aprs_server":("china.aprs2.net:14580"),
	"aprs_user_pwd":("N0CALL-1",13023),
	"event_port":18001,
	"traccar_api":"http://127.0.0.1:8082",
	"traccar_auth":base64.b64encode(b"admin:password").decode(),
	"sms_gateway":"http://127.0.0.1:8001",
	"map_zoom":12,
	"geoapify_key":"1234567890",
}

data_queue=queue.Queue(1000)

class EventHandler(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length)
        try:
            body = raw.decode()
        except UnicodeDecodeError:
            body = raw.decode("gbk", errors="replace")
        payload = json.loads(body)
        ev = payload.get("event", {})
        print(f"[EVENT] receive {ev.get('type','?')}")

        if ev.get("type") in ("deviceUnknown", "deviceOffline", "deviceOnline"):
            dev = payload.get("device", {})
            did = dev.get("id")

            phone = ""
            if did:
                dev_url = f"{config['traccar_api']}/api/devices/{did}"
                req = urllib.request.Request(dev_url, headers={"Authorization": f"Basic {config['traccar_auth']}"})
                try:
                    with urllib.request.urlopen(req, timeout=10) as r:
                        dv = json.loads(r.read())
                        phone = dv.get("phone", "")
                except Exception as e:
                    print(f"[EVENT] device API error: {e}")

            if not phone:
                print(f"[EVENT] skip: device {dev.get('name','?')} has no phone")
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"OK")
                return

            lat = lng = None
            addr_text = ""
            if did:
                api_url = f"{config['traccar_api']}/api/positions?deviceId={did}&limit=1"
                req = urllib.request.Request(api_url, headers={"Authorization": f"Basic {config['traccar_auth']}"})
                try:
                    with urllib.request.urlopen(req, timeout=10) as r:
                        pl = json.loads(r.read())
                        if pl:
                            p = pl[0]
                            lat, lng = p["latitude"], p["longitude"]
                            spd = p.get("speed", 0) * 1.852
                            addr_text = f"坐标: {lat:.5f},{lng:.5f} 速度: {spd:.1f}km/h"
                            if p.get("address"):
                                addr_text = f"地址: {p['address']}\n{addr_text}"
                except Exception as e:
                    print(f"[EVENT] API error: {e}")

            caption = f"设备{dev.get('name','?')} {ev['type']}\n{addr_text}"
            print(f"[EVENT] send to {phone}: {caption}")
            try:
                if lat is not None:
                    map_url = (f"https://maps.geoapify.com/v1/staticmap"
                               f"?style=osm-bright-smooth&width=800&height=600"
                               f"&center=lonlat:{lng},{lat}&zoom={config['map_zoom']}"
                               f"&marker=lonlat:{lng},{lat};color:red;size:medium"
                               f"&apiKey={config['geoapify_key']}")
                    map_resp = requests.get(map_url, timeout=15)
                    if map_resp.status_code == 200:
                        requests.post(config['sms_gateway'],
                                      data={"from":"Traccar","usr":phone,"msg":caption},
                                      files={"file":("map.png",map_resp.content,"image/png")},
                                      timeout=15)
                    else:
                        requests.post(config['sms_gateway'],
                                      data={"from":"Traccar","usr":phone,"msg":caption},
                                      timeout=10)
                else:
                    requests.post(config['sms_gateway'],
                                  data={"from":"Traccar","usr":phone,"msg":caption},
                                  timeout=10)
            except Exception as e:
                print(f"[EVENT] SMS error: {e}")

        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

    def log_message(self, *a):
        pass

def event_server():
    server = http.server.HTTPServer(("0.0.0.0", config['event_port']), EventHandler)
    print(f"[EVENT] HTTP server listen on :{config['event_port']}")
    server.serve_forever()

def send_udp(func,msg):
	nmSocket = socket(AF_INET,SOCK_DGRAM)
	for target in config[func]:
		server = target.strip().split(":")
		ip_port = (gethostbyname(server[0]), int(server[1]))
		if func.find("_aprs_") > 0 and msg.find("user") <0 and msg.find("pass")<0 :
			msg = ("user %s pass %s ver python-aprs 1.0 filter b/B* \n" % (config['aprs_user_pwd'][0], config['aprs_user_pwd'][1])) + msg
		print("%s Send udp (%s) %s to %s" % (time.ctime(), func, msg, server))
		nmSocket.sendto(msg.encode('utf-8'),ip_port)
	nmSocket.close()

def car_udp_server():
	mSocket = socket(AF_INET,SOCK_DGRAM)
	mSocket.bind(("",50025)) 
	while True:
		recvData, (remoteHost, remotePort) = mSocket.recvfrom(1024)
		mSocket.sendto("R".encode("UTF-8"),(remoteHost, remotePort))
		recvData=recvData.strip()
		print("Recv CAR UDP: %s, from %s:%s\n" % (recvData,remoteHost, remotePort))
		if len(recvData)>0 :
			try:
				recvData = recvData.decode("gb2312")
			except :
				print("recvData decode error")
			recvData=recvData[:60] + time.strftime('%Y%m%d',time.localtime(time.time()))[2:]+ recvData[66:]
			GPS_Info = car_decode(recvData)
			if GPS_Info :
				data_queue.put(("traccar_server", GPS_Info))
				if remoteHost!="10.108.22.166" :
					data_queue.put(("udp_car_server", recvData))
			else:
				print("Decode error : %s" % GPS_Info)
	mSocket.close()

def aprs_udp_server():
	mSocket = socket(AF_INET,SOCK_DGRAM)
	mSocket.bind(("",14580)) 
	while True:
		recvData, (remoteHost, remotePort) = mSocket.recvfrom(1024)
		recvData=recvData.decode("gb2312").strip()
		print("%s Recv APRS UDP: %s\n from %s:%s" % (time.strftime('%Y-%m-%d %H:%M:%S',time.localtime(time.time())), recvData,remoteHost, remotePort))
		mSocket.sendto("R".encode("UTF-8"),(remoteHost, remotePort))
		if len(recvData)>0 :
			GPS_Info = aprs_decode(recvData)
			print("%s APRS Decode 结果: %s " % (time.ctime(),GPS_Info))
			if GPS_Info :
				data_queue.put(("traccar_server", GPS_Info))
				if GPS_Info['id'] in config['relay_aprs_id'] :
					data_queue.put(("udp_aprs_server",recvData))
			else:
				print("APRS parsing result error : %s" % recvData)
	mSocket.close()

def aprs_decode(udp_packet):
	k={}
	aprs_data=udp_packet.split("\n")
	if len(aprs_data)>1 :
		try:
			if 1 :
				try:
					packet = aprslib.parse(aprs_data[1])
				except (aprslib.ParseError, aprslib.UnknownFormat) as exp:
					print("Aprs parse error %s" % exp)
					print("Aprs packet %s " % udp_packet)
					packet = None
				else:
					k['id']=packet['from'].upper()
					try:
						k['lat']=packet['latitude']
					except:
						k['lat']=0
					try:
						k['lon']=packet['longitude']
					except:
						k['lon']=0
					try:
						k['speed']=packet['speed']
					except:
						k['speed']=0
					try:
						k['hdop']=packet['course']
					except:
						k['hdop']=0
					try:
						k['timestamp']=packet['timestamp']
					except:
						k['timestamp']=int(time.time())
					try:
						k['altitude']=packet['altitude']
					except:
						k['altitude']=0
					try:
						k['gpsfixstatus']=packet['gpsfixstatus']
					except:
						pass
					try:
						k['format']=packet['format']
					except:
						pass
		except Exception as e:
			print("Aprs split error : %s (error info : %s)" % (udp_packet[:80], e))
	else:
		print("Aprs packet : %s " % udp_packet)
	return k

def car_decode(udp_packet):
	k={}
	p=re.compile(r'\$SJHX,(?P<id>[A-Z0-9]{8})7E7E(?P<car_status>[0-1]{4})7E7E[0-9]{6}(?P<gps_lock>[0,8])(?P<car_lock>[0,1])(?P<lat>[0-9]{8})(?P<lon>[0-9]{10})(?P<speed>[0-9]{4})(?P<hdop>[0-9]{4})(?P<timestamp>[0-9]{12})(?P<gps_sign>[0-9]{2})(?P<car_bat>[0-9]{3})(?P<car_temp>[0-9]{5}).*', re.S)
	for m in p.finditer(udp_packet) :
		k = m.groupdict()
	if len(k) > 0:
		try:
			temp=k['id']
			k['id']=temp[6:8]+temp[4:6]+temp[2:4]+temp[0:2]
			temp=k['lon']
			k['lon']=float(temp[0:4]) + (float(temp[4:10])/10000/60)
			temp=k['lat']
			k['lat']=float(temp[0:2]) + (float(temp[2:8])/10000/60)
			k['speed']=str(int(k['speed'])/10*1.852)
			k['hdop']=k['hdop'][0:3] + "." + k['hdop'][3:]
			k_time = datetime.strptime("20"+k['timestamp'], "%Y%m%d%H%M%S") + timedelta(hours=8)
			k['timestamp']=str(int(time.mktime(k_time.timetuple() )))
			k['altitude']=0
		except Exception as e:
			print("car decode error : %s\n%s\n" % (k,e))
			k = None
		return k
	
def send_traccar(msg):
	Http_url = u'http://127.0.0.1:5055/?'
	for mm in msg:
		if mm=="speed" :
			msg[mm] = float(msg[mm]) * 0.54
		if mm=="hdop":
			Http_url = Http_url + "bearing=" + str(msg[mm]) + "&"
		else :
			Http_url = Http_url + mm + "=" + str(msg[mm]) + "&"
	Http_url = Http_url[:-1].encode('utf-8').decode('utf-8')
	_ = get_threading(Http_url)
	return

def get_threading(get_url):
	request_result=""
	print("\n%s, Request URL : %s" % (time.strftime('%Y-%m-%d %H:%M:%S',time.localtime(time.time())),get_url))
	try:
		req_session = requests.session()
		recvData = req_session.get(get_url, timeout=5)
		request_result="OK"
	except Exception as e:
		request_result=("Send Data to traccar Server Error : %s" % e)
	print("Update traccar : %s" % request_result)
	return request_result

def data_send_client ():
	while True:
		if data_queue.qsize() > 0:
			func, msg = data_queue.get()
			if func == "udp_car_server" :
				send_udp("udp_car_server", msg)
			elif func == "traccar_server" :
				send_traccar(msg)
			elif func == "udp_aprs_server" :
				send_udp("udp_aprs_server", msg)
			data_queue.task_done()
		else :
			time.sleep(1)

## 线程状态管理
threads = {}
thread_targets = {
	'car_udp_server': car_udp_server,
	'aprs_udp_server': aprs_udp_server,
	'data_send_client': data_send_client,
	'event_server': event_server,
}

def start_thread(name, target):
	thread = threading.Thread(target=target, name=name)
	thread.setDaemon(True)
	thread.start()
	threads[name] = thread
	print("%s Starting %s thread" % (time.ctime(),name))

def check_threads():
	while True:
		for name, thread in threads.items():
			if not thread.is_alive():
				start_thread(name, thread_targets[name])
		time.sleep(5)  

if __name__ == '__main__':
	for name, target in thread_targets.items():
		start_thread(name, target)
	
	check_thread = threading.Thread(target=check_threads)
	check_thread.setDaemon(True)
	check_thread.start()
	
	try:
		while True:
			time.sleep(10)
	except KeyboardInterrupt:
		print("Shutting down...")
