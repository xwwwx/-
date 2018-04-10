# coding: utf-8
import os,json
import requests
import logging
from datetime import datetime
from flask import Flask,request, abort
from linebot import (
    LineBotApi, WebhookHandler
)
from linebot.exceptions import (
    InvalidSignatureError
)
from linebot.models import *
from google.appengine.api import taskqueue
from google.appengine.ext import ndb,db
from db_model import *

app = Flask(__name__)

YOUR_CHANNEL_ACCESS_TOKEN = 'YOUR_CHANNEL_ACCESS_TOKEN'
YOUR_CHANNEL_SECRET = 'YOUR_CHANNEL_SECRET'
line_bot_api = LineBotApi(YOUR_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(YOUR_CHANNEL_SECRET)
	
@app.route("/callback", methods=['POST'])
def callback():
    try:
		# get X-Line-Signature header value
		signature = request.headers['X-Line-Signature']

		# get request body as text
		body = request.get_data(as_text=True)
		# print 'request body' info 
		app.logger.info("Request body: " + body)
		#print("Request body: %s" % body)
		taskqueue.add(url='/task',
					      queue_name='default',
						  params={'body': body,
								  'signature': signature,
								  },
						  method="POST")
		# handle webhook body
		return 'OK'
    except InvalidSignatureError:
        abort(400)    

@app.route('/task',methods=['POST'])
def task():
	handler.handle(request.form['body'], request.form['signature'])
	return 'OK'		

@handler.add(BeaconEvent)
def handle_beacon(event):
	station = Beacon.query(Beacon.hw_id == event.beacon.hwid)
	station = station.fetch()
	if len(station) != 0:
		user = User(id = event.source.user_id)
		if user.key.get() is None:
			logging.info('add')
			profile = line_bot_api.get_profile(user_id=event.source.user_id)
			user = User(username=profile.display_name,id=event.source.user_id)
			user.put()
			user = User(id = event.source.user_id)
		user = user.key.get()
		now_time = datetime.now()
		last_time = datetime.strptime(str(user.time),"%Y-%m-%d %H:%M:%S.%f")
		user.time = now_time
		user.put()
		Remind_station = Remind(id = event.source.user_id)
		if Remind_station.key.get() != None :
			Remind_station = Remind_station.key.get()
			if Remind_station.hw_id == event.beacon.hwid :
				logging.info('hw_id='+Remind_station.hw_id)
				logging.info('event='+event.beacon.hwid)
				line_bot_api.reply_message(
					event.reply_token,
					TextSendMessage(text=(u'您已經抵達'+Remind_station.station_name+u'，請下車')))
				Remind_station.key.delete()
				return 
		if (now_time - last_time).seconds > 600 and Remind_station.key.get() == None:
			confirm_template_message = TemplateSendMessage(
				alt_text='位置確認',
				template=ConfirmTemplate(
					text=u'你位於'+station[0].station_name+u'，是否要使用到站提醒功能?',
					actions=[
						PostbackTemplateAction(
							label='是',
							data='locationchoose=1='+station[0].station_name
						),
						PostbackTemplateAction(
							label='否',
							data='locationchoose=0'
						)
					]
				)
			)
			line_bot_api.reply_message(
				event.reply_token,
				confirm_template_message)
	else:
		line_bot_api.reply_message(
			event.reply_token,
			TextSendMessage(
				text=event.beacon.hwid))

@handler.add(MessageEvent, message=LocationMessage)
def handle_location(event):
    r = requests.get('https://maps.googleapis.com/maps/api/place/nearbysearch/json?location='+str(event.message.latitude)+','+str(event.message.longitude)+'&radius=500&language=zh-TW&type=subway_station&key=AIzaSyCczOKIBiIxzaIkM1_8_rK3Z9FJkstTibE')
    results = json.loads(r.text)['results']
    #print results[0]
    confirm_template_message = TemplateSendMessage(
        alt_text='位置確認',
        template=ConfirmTemplate(
            text=u'你是否在'+results[0]['name']+'?',
            actions=[
                PostbackTemplateAction(
                    label='是',
                    data='locationchoose=1='+results[0]['name']
                ),
                PostbackTemplateAction(
                    label='否',
                    data='locationchoose=0'
                )
            ]
        )
    )
    line_bot_api.reply_message(
        event.reply_token,
        confirm_template_message)
 


	
@handler.add(PostbackEvent)
def handle_postback(event):
    postbackdata = event.postback.data.split('=')
    action = postbackdata[0]
    data = postbackdata[1]
    if(action == 'locationchoose' and data == '1'):
        begin = postbackdata[2]
        line_bot_api.reply_message(
        event.reply_token,
        choose_line())
    elif(action == 'locationchoose' and data == '0'):
        line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=u'請重新傳送位置訊息'))
    elif(action == 'line'):
        targetline = data 
        line_bot_api.reply_message(
        event.reply_token,
        showdatation(data))
    elif(action == 'endstation'):
		endstation = data
		line_bot_api.reply_message(
			event.reply_token,
			TextSendMessage(text=
		remind(endstation,event)))
		
        
        
        
    
def choose_line():
    confirm_template_message = TemplateSendMessage(
        alt_text='路線選擇',
        template=ConfirmTemplate(
            text=u'請選擇欲前往捷運站所在的路線',
            actions=[
                PostbackTemplateAction(
                    label='紅',
                    data='line=1'
                ),
                PostbackTemplateAction(
                    label='橘',
                    data='line=0'
                )
            ]
        )
    )
    return confirm_template_message
def showdatation(line):
    ptx_url='http://ptx.transportdata.tw/MOTC/v2/Rail/Metro/StationOfLine/KRTC?$select=LineID%2CStations&$format=JSON'
    r = requests.get(ptx_url)
    station = json.loads(r.text)[int(line)]['Stations']
    stationname = []
    doordata = []
    door=[]
    carousel_template_message = []
    for i in range(0,len(station),1):
        stationname.append(PostbackTemplateAction(
                        label=station[i]['StationName']['Zh_tw'],
                        data='endstation='+station[i]['StationName']['Zh_tw']
                    )
            )
    if(len(stationname)%3 != 0):
        for i in range(0,3-(len(stationname)%3),1):
            stationname.append(PostbackTemplateAction(
                            label=' ',
                            data=' '
                        ))
    page = len(stationname)/3
    if(page%5 !=0 ):
        time = (page/5)+1
    else:
        time = page/5
    for i in range(0,page,1):
        doordata.append(CarouselColumn(
                thumbnail_image_url='https://upload.wikimedia.org/wikipedia/zh/thumb/7/7f/Kaohsiung_Metro_Logo%28Logo_Only%29.svg/200px-Kaohsiung_Metro_Logo%28Logo_Only%29.svg.png',
                title='請選擇目的地',
                text='請選擇目的地',
                actions=[stationname[i*3],stationname[(i*3)+1],stationname[(i*3)+2]
                     ]
            ))
    if(time <= 1):
        carousel_template_message.append(TemplateSendMessage(
            alt_text='目的地選擇',
            template=CarouselTemplate(
                columns=doordata
            )
        ))
    else:
        
        for i in range(0,time,1):
            tmp = []
            for j in range(0,5,1):
                if(len(doordata) == 0):
                    break;
                tmp.append(doordata.pop(0))
            door.append(tmp)
            carousel_template_message.append(TemplateSendMessage(
            alt_text='目的地選擇',
            template=CarouselTemplate(
                columns=door[i]
            )
        ))
    return carousel_template_message

def remind(endstation,event):
	station = Beacon.query(Beacon.station_name == endstation+u'站').get()
	if  station != None:
		station = station.key.get()
		add = Remind(id = event.source.user_id,hw_id = station.hw_id,deivce_message = station.deivce_message,station_name = station.station_name)
		add.put()
		return u'預約成功!'
	
	

if __name__ == "__main__":
    app.run(host=os.getenv('IP', '0.0.0.0'),port=int(os.getenv('PORT', 8080)))