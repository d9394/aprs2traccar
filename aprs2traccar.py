#!/usr/bin/python
#coding=utf8
from socket import * 
import requests
import time
import re
import uuid
import threading
import aprslib
import datetime,time,json
import sys
if sys.getdefaultencoding() != 'utf8' :
	reload(sys)
	sys.setdefaultencoding('utf8')
	
def string2timestamp(strValue):
	timeStamp=""
	try:
		d = datetime.datetime.strptime(strValue, "%Y%m%d%H%M%S")
		t = d.timetuple()
		timeStamp = int(time.mktime(t))
		timeStamp = float(str(timeStamp) + str("%06d" % d.microsecond))/1000000
		print timeStamp
		return timeStamp
	except ValueError as e:
		print e
		print timeStamp
		return timeStamp

def car_udp():
	mSocket = socket(AF_INET,SOCK_DGRAM)
	mSocket.bind(("",50025)) 
	while True:
		revcData, (remoteHost, remotePort) = mSocket.recvfrom(1024)
#		revcData="$SJHX,341200007E7E00007E7E020301803955352401161766210162090501010108191625132655351234567F12345F1"
		revcData=revcData.decode("gb2312").strip()
		print("Recv CAR UDP: %s, from %s:%s" % (revcData,remoteHost, remotePort))
		if len(revcData)>0 :
			GPS_Info = car_decode(revcData)
#			print("Decode : %s " % GPS_Info)
			if GPS_Info :
				result = send_traccar(GPS_Info)
			else:
				print("Decode error : %s" % GPS_Info)
	mSocket.close()

def aprs_udp():
	mSocket = socket(AF_INET,SOCK_DGRAM)
	mSocket.bind(("",14580)) 
	while True:
		revcData, (remoteHost, remotePort) = mSocket.recvfrom(1024)
		revcData=revcData.decode("gb2312").strip()
		print("%s Recv APRS UDP: %s\n from %s:%s" % (time.strftime('%Y-%m-%d %H:%M:%S',time.localtime(time.time())), revcData,remoteHost, remotePort))
		if len(revcData)>0 :
			GPS_Info = aprs_decode(revcData)
#			print("Decode : %s " % GPS_Info)
			if GPS_Info :
				result = send_traccar(GPS_Info)
			else:
#				result = "APRS parsing result null"
				print("APRS parsing result error : %s" % revcData)
	mSocket.close()

def aprs_decode(udp_packet):
	k={}
	aprs_data=udp_packet.split("\n")
	if len(aprs_data)>1 :
		aa=aprs_data[0].split(" ")
		try:
			if aa[3]==str(aprslib.passcode(aa[1].encode("UTF-8"))) :
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
						k['timestamp']=packet['']
					except:
						k['timestamp']=int(time.time())
					try:
						k['altitude']=packet['altitude']
					except:
						k['altitude']=0
		except :
			print("Aprs split : %s " % aa)
	else:
		print("Aprs packet : %s " % udp_packet)
	return k

def car_decode(udp_packet):
	k={}
	p=re.compile(r'\$SJHX,(?P<id>[A-Z0-9]{8})7E7E(?P<car_status>[0-1]{4})7E7E[0-9]{6}(?P<gps_lock>[0,8])(?P<car_lock>[0,1])(?P<lat>[0-9]{8})(?P<lon>[0-9]{10})(?P<speed>[0-9]{4})(?P<hdop>[0-9]{4})(?P<timestamp>[0-9]{12})(?P<gps_sign>[0-9]{2})(?P<car_bat>[0-9]{3})(?P<car_temp>[0-9]{5}).*', re.S)
	for m in p.finditer(udp_packet) :
		k = m.groupdict()
	if len(k) > 0:
		#{'hdop': '0905', 'gps_sign': '25', 'car_lock': '0', 'lon': '0116176621', 'id': '34120000', 'gps_lock': '8', 'car_bat': '132', 'timestamp': '010101081916', 'lat': '39553524', 'speed': '0162', 'car_status': '0000', 'car_temp': '65535'}
		#细项转换
		try:
			temp=k['id']
			k['id']=temp[6:8]+temp[4:6]+temp[2:4]+temp[0:2]
			k['lon']=k['lon'][0:4] + "." + k['lon'][4:]
			k['lat']=k['lat'][0:2] + "." + k['lat'][2:]
			k['speed']=str(int(k['speed'])/10*1.852)
			k['hdop']=k['hdop'][0:3] + "." + k['hdop'][3:]
			k['timestamp']=str(int(string2timestamp("20"+k['timestamp'])))
			k['altitude']=0
		except:
			k = None
		return k
	
def send_traccar(msg):
	Http_url = 'http://127.0.0.1:5055/?'
	for mm in msg:
		Http_url = Http_url + mm + "=" + str(msg[mm]) + "&"
	Http_url = Http_url[:-1].decode('utf-8')
	t = threading.Thread(target=get_threading,args=(Http_url,), name=uuid.uuid1())
	t.start()
	return

def get_threading(get_url):
	request_result=""
	print("%s, Request URL : %s" % (time.strftime('%Y-%m-%d %H:%M:%S',time.localtime(time.time())),get_url))
	try:
		req_session = requests.session()
		revcData = req_session.get(get_url)
		time.sleep(15)
		req_session.close()
		request_result="OK"
	except urllib2.HTTPError, e:
		request_result=("Send Data to traccar Server Error : %s" % e)
	return request_result


if __name__ == '__main__':
	t1 = threading.Thread(target=car_udp, name='car_udp_server')  # 线程对象.
	t1.start()
	t2 = threading.Thread(target=aprs_udp, name='aprs_udp_server')  # 线程对象.
	t2.start()
	
	print("==Service Started== %s" % time.strftime('%Y-%m-%d %H:%M:%S',time.localtime(time.time())))
#	while True:
#		time.sleep(60)
