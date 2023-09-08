#!/usr/bin/python3.8
#coding=utf8

from socket import * 
import requests
import re
import uuid
import threading
import aprslib
import time,json
from datetime import datetime,timedelta
#import sys
#if sys.getdefaultencoding() != 'utf8' :
#	reload(sys)
#	sys.setdefaultencoding('utf8')

config={
	"udp_car_server":("10.1.2.1:50025",),
	"udp_aprs_server":("192.168.1.1:14580","aprs.hellocq.net:14580","202.141.176.2:14580",),
	"relay_aprs_id":("BB1BB-5","BB2BB-7","BB3BB-6",),
	"relay_car_id":("00000000","00000001","LM0C0174","00000059","00000072",)
}

def send_udp(type,msg):
	nmSocket = socket(AF_INET,SOCK_DGRAM)
	for ii in config[type]:
		jj = ii.strip().split(":")
		print("Send udp (%s) %s to %s" % (type, msg, jj))
		ip_port = (gethostbyname(jj[0]), int(jj[1]))
		nmSocket.sendto(msg.encode('utf-8'),ip_port)
	nmSocket.close()

def send_aprs_udp(msg):
	#print(u'使用UDP转发')
	nmSocket = socket(AF_INET,SOCK_DGRAM)
	try:
		#ip_port = (gethostbyname("aprs.hellocq.net"), 14580)
		ip_port = (gethostbyname("srvr.aprs-is.net"), 8080)
		nmSocket.sendto(msg.encode('utf-8'),ip_port)
		print(u"Send APRS packet : %s" % (msg) )
	except Exception as e:
		print("Send APRS udp packet error %s" % e)
	nmSocket.close()

def send_aprs_tcp(msg):
#	print(u'使用TCP转发')
	tcp_client_socket = socket(AF_INET,SOCK_STREAM)
	try:
		tcp_client_socket.connect(("202.141.176.2",14580))
		aprs_data=msg.split("\r\n")
		for mm in aprs_data:
#			print(u'发送数据：%s' % mm.encode('utf-8'))
			tcp_client_socket.send(mm.encode('utf-8')+'\n')
			recv_data = tcp_client_socket.recv(1024)
			if not recv_data:
				print(u"对方已离线。。")
				break
#			else:
#				print(u"返回的消息为:",recv_data.decode('utf-8'))
	except Exception as e:
		print(u"连接上级APRS服务器出错：%s" % e)
	tcp_client_socket.close()

#def string2timestamp(strValue):
#	timeStamp=""
#	try:
#		d = datetime.strptime(strValue, "%Y%m%d%H%M%S")
#		t = d.timetuple()
#		timeStamp = int(time.mktime(t))
#		timeStamp = float(str(timeStamp) + str("%06d" % d.microsecond))/1000000
#		print timeStamp
#	except ValueError as e:
#		print("Change %s to timestamp error : %s" %(strValue,e))
#		timeStamp=time.time()
#	return timeStamp

def car_udp():
	mSocket = socket(AF_INET,SOCK_DGRAM)
	mSocket.bind(("",50025)) 
	while True:
		recvData, (remoteHost, remotePort) = mSocket.recvfrom(1024)
#		recvData="$SJHX,341200007E7E00007E7E020301803955352401161766210162090501010108191625132655351234567F12345F1"
#		recvData="$SJHX,720000007E7E01007E7E02030100230531480113152627000000001811110956440609400000000000000000001"
		mSocket.sendto("R".encode("UTF-8"),(remoteHost, remotePort))
		recvData=recvData.strip()
		print("Recv CAR UDP: %s, from %s:%s\n" % (recvData,remoteHost, remotePort))
		if len(recvData)>0 :
			try:
				recvData = recvData.decode("gb2312")
			except :
				print("recvData decode error")
			#可能car星历有问题，日期错乱，以当前日期时间替换
			#recvData=recvData[:60] + datetime.datetime.now().strftime('%Y%m%d%H%M%S')[2:] + recvData[72:]
			recvData=recvData[:60] + time.strftime('%Y%m%d',time.localtime(time.time()))[2:]+ recvData[66:]
			GPS_Info = car_decode(recvData)
			#print("Decode : %s " % GPS_Info)
			if GPS_Info :
				result = send_traccar(GPS_Info)
				if remoteHost!="10.108.22.166" :
					send_udp("udp_car_server", recvData)
			else:
				print("Decode error : %s" % GPS_Info)
	mSocket.close()

def aprs_udp():
	mSocket = socket(AF_INET,SOCK_DGRAM)
	mSocket.bind(("",14580)) 
	while True:
		recvData, (remoteHost, remotePort) = mSocket.recvfrom(1024)
		recvData=recvData.decode("gb2312").strip()
		print("%s Recv APRS UDP: %s\n from %s:%s" % (time.strftime('%Y-%m-%d %H:%M:%S',time.localtime(time.time())), recvData,remoteHost, remotePort))
		if len(recvData)>0 :
			GPS_Info = aprs_decode(recvData)
			print("Decode : %s " % GPS_Info)
			if GPS_Info :
				result = send_traccar(GPS_Info)				#转发GPS数据去traccar服务器
#				send_udp("udp_car_server", recvData)
#				if GPS_Info['id'][0]=='B' :
				if GPS_Info['id'] in config['relay_aprs_id'] :
#					send_aprs_tcp(recvData)				#转发aprs去202.141.176.2服务器
					send_aprs_udp(recvData)
#					pass
			else:
#				result = "APRS parsing result null"
				print("APRS parsing result error : %s" % recvData)

	mSocket.close()

def aprs_decode(udp_packet):
	k={}
	aprs_data=udp_packet.split("\n")
	if len(aprs_data)>1 :
#		aa=aprs_data[1].split(" ")
#		print("APRS data split : %s " % aa)
		try:
#			if aa[3]==str(aprslib.passcode(aa[1].encode("UTF-8").upper())) :
			if 1 :
				try:
					packet = aprslib.parse(aprs_data[1])
				except (aprslib.ParseError, aprslib.UnknownFormat) as exp:
					print("Aprs parse error %s" % exp)
					print("Aprs packet %s " % udp_packet)
					packet = None
				else:
					print("aprs decode info : %s" % packet)
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
			print("Aprs split : %s (error info : %s)" % (aa,e))
	else:
		print("Aprs packet : %s " % udp_packet)
	return k

def car_decode(udp_packet):
	k={}
	p=re.compile(r'\$SJHX,(?P<id>[A-Z0-9]{8})7E7E(?P<car_status>[0-1]{4})7E7E[0-9]{6}(?P<gps_lock>[0,8])(?P<car_lock>[0,1])(?P<lat>[0-9]{8})(?P<lon>[0-9]{10})(?P<speed>[0-9]{4})(?P<hdop>[0-9]{4})(?P<timestamp>[0-9]{12})(?P<gps_sign>[0-9]{2})(?P<car_bat>[0-9]{3})(?P<car_temp>[0-9]{5}).*', re.S)
	for m in p.finditer(udp_packet) :
		k = m.groupdict()
	if len(k) > 0:
		#{'hdop': u'0905', 'gps_sign': u'51', 'car_lock': u'0', 'lon': u'0116176621', 'id': u'72000000', 'gps_lock': u'8', 'car_bat': u'326', 'timestamp': u'200209119162', 'lat': u'39553524', 'speed': u'0162', 'car_status': u'0000', 'car_temp': u'55351'}

		#细项转换
		try:
			temp=k['id']
			k['id']=temp[6:8]+temp[4:6]+temp[2:4]+temp[0:2]
			temp=k['lon']
			k['lon']=float(temp[0:4]) + (float(temp[4:10])/10000/60)
			temp=k['lat']
			k['lat']=float(temp[0:2]) + (float(temp[2:8])/10000/60)
			k['speed']=str(int(k['speed'])/10*1.852)		#原始上传速度为：节，需转换为公里/小时
			k['hdop']=k['hdop'][0:3] + "." + k['hdop'][3:]
			k_time = datetime.strptime("20"+k['timestamp'], "%Y%m%d%H%M%S") + timedelta(hours=8)
			#k_time = datetime.strptime("20"+k['timestamp'], "%Y%m%d%H%M%S")
			#timestamp为UTC时间，要转换为GMT+8时间
			k['timestamp']=str(int(time.mktime(k_time.timetuple() )))
			#CAR星历可能有问题，上报日期错误，直接取当前日期时间
			#k_time=str(int(time.mktime(time.localtime())))
			k['altitude']=0
		except Exception as e:
			print("car decode error : %s\n%s\n" % (k,e))
			k = None
		return k
	
def send_traccar(msg):
	Http_url = u'http://127.0.0.1:5055/?'
	for mm in msg:
		if mm=="speed" :
			msg[mm] = msg[mm] * 0.54		#根据traccar(OsmAnd)速度单位为：节
		Http_url = Http_url + mm + "=" + str(msg[mm]) + "&"
	Http_url = Http_url[:-1].encode('utf-8').decode('utf-8')
	t = threading.Thread(target=get_threading,args=(Http_url,), name=uuid.uuid1())
	t.start()
	return

def get_threading(get_url):
	request_result=""
	print("\n%s, Request URL : %s" % (time.strftime('%Y-%m-%d %H:%M:%S',time.localtime(time.time())),get_url))
	try:
		req_session = requests.session()
		recvData = req_session.get(get_url)
		time.sleep(15)
		req_session.close()
		request_result="OK"
#	except urllib2.HTTPError, e:
	except Exception as e:
		request_result=("Send Data to traccar Server Error : %s" % e)
	print("Update traccar : %s" % request_result)
	return request_result

if __name__ == '__main__':
	t1 = threading.Thread(target=car_udp, name='car_udp_server')  # 线程对象.
	t1.start()
	t2 = threading.Thread(target=aprs_udp, name='aprs_udp_server')  # 线程对象.
	t2.start()
	
	print("==Service Started== %s" % time.strftime('%Y-%m-%d %H:%M:%S',time.localtime(time.time())))
#	while True:
#		time.sleep(60)
