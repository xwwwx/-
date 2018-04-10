#!/usr/bin/env python
# coding: utf-8
from google.appengine.ext import ndb

class Beacon(ndb.Model):
	station_name = ndb.StringProperty()
	deivce_message = ndb.StringProperty()
	hw_id = ndb.StringProperty()
class User(ndb.Model):
	username = ndb.StringProperty()
	time = ndb.DateTimeProperty(auto_now_add=True)
class Remind(ndb.Model):
	station_name = ndb.StringProperty()
	deivce_message = ndb.StringProperty()
	hw_id = ndb.StringProperty()
