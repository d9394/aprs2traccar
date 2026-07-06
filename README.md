# aprs2traccar


receive aprs packet and send to traccar server    
  aprs receive with UDP protocol on port 14580   

# gps2traccar   
  

接收gps格式转发现traccar中，另外还带支持接收traccar enevt事件推送流：  
- 要使traccar支持event推送需在traccar.xml配置中增加：
  ``` xml
  	<entry key='event.status.enable'>true</entry>
	<entry key='event.forward.type'>json</entry>
	<entry key='event.forward.url'>http://172.17.0.1:18001/</entry>
  ```
- 目前 gps2traccar 支持对deviceOnline、deviceUnknown、deviceStop事件的处理：  
  -- 推送到SMS（目前是推送到另一项目：weixin_httpd，发送到微信，并附带有地点标注的地图静态图片）
  
