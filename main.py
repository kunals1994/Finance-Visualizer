#!/usr/bin/env python
#
# Copyright 2007 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

credentials = open("credentials", 'rb').read().split('\n')
client_id = credentials[0]
secret = credentials[1]
google_key = credentials[2]
google_request_url = "https://maps.googleapis.com/maps/api/place/textsearch/json?query=%(query)s&key=%(google_key)s"


import webapp2
import urllib
import json
import datetime
from datetime import timedelta
from datetime import date
from google.appengine.ext import db
import operator
import random


class sign_in(db.Model):
	email = db.StringProperty(required = True)
	username = db.IntegerProperty(required = True)
	auth_token = db.StringProperty(required = True)

class Category(db.Model):
	name = db.StringProperty(required = True)
	category = db.StringProperty(required = True)



def date_handler(obj):
    return obj.isoformat() if hasattr(obj, 'isoformat') else obj

def process_data(transactions, dateStart=date.today()-timedelta(days=30), dateEnd=date.today()):
    products = {}
    vendors = {}
    total = 0
    for t in transactions:
    	try:
    		vendors [t["location"]] += float(t["value"])
    	except:
    		vendors [t["location"]] = float(t["value"])
        if t['date'] == dateStart or t['date'] == dateEnd or (dateStart < t['date'] and t['date'] < dateEnd):
            if t['value'] > 0:
                if not(t['cat'] in products):
                    products[t['cat']] = 0
                products[t['cat']] += t['value']
                total += t['value']
    return [{k: products[k]*100/total for k in products}, vendors] #holder

def get_google_category(transaction):

	for possibility in Category.gql("WHERE name = '" + transaction["name"].replace("'","").replace(" ","") + "'"):
		return possibility.category

	google_params = {}
	google_params["query"] = transaction["name"]

	try:
		google_params["query"] += transaction["meta"]["location"]["city"]
		google_params["query"] += transaction["meta"]["location"]["state"]
	except:
		google_params["query"] = google_params["query"][:-4]

	google_params["query"] = google_params["query"].replace(" ", "%20")

	google_params["google_key"] = google_key

	google_json = json.loads(urllib.urlopen(google_request_url % google_params).read())
	
	try:
		ret = google_json["results"][0]["types"][0]
	except:
		ret = "other"

	new_record = Category(name = transaction["name"].replace("'","").replace(" ",""), category = ret.replace("'","").replace(" ",""))
	new_record.put()
	return ret

class HomeHandler(webapp2.RequestHandler):
	def get(self):
		out_template = open("assets/html/index2.html", 'rb').read()

class MainHandler(webapp2.RequestHandler):
    def post(self):
        out_template = open("assets/html/index.html", 'rb').read()

        json_out = json.loads(urllib.urlopen("http://finance-visualizer.appspot.com/reqdata?auth_id=" + self.request.get("auth_id")).read())
        x = []

        for ele in json_out["transactions"]:
        	x.append(ele)
        x.sort(key=operator.itemgetter('value'))

        account_output = ""
       	for account in reversed(json_out["accounts"]):
       		account_output += "$%(value)s, %(name)s | %(ACC_NUM)s <br>" % account

        top_trans_out = ""
        for trans in reversed(x[-5:]):
        	trans["date"] = trans["date"][5:]
        	top_trans_out += "<strong>%(date)s</strong> - %(location)s, $%(value)s <br>" % trans


        percent_out = ""
        chart_data_out = ""
        color_possibilities = ["#e74c3c", "#c0392b", "#8e44ad", "#2c3e50", "#f39c12", "#ecf0f1", "#3498db", "#8e44ad", "#7f8c8d", "#f1c40f", "#27ae60", "#c0392b"]
        for curr in json_out["percentage"]:
        	params_for_chart = {}
        	params_for_chart["value"] = "%.2f" % float(json_out["percentage"][curr])
        	params_for_chart["rand_color"] = random.choice(color_possibilities)
        	params_for_chart["highlight"] = random.choice(color_possibilities)
        	params_for_chart["label"] = curr

        	chart_data_out += ("{value: %(value)s, color:'%(rand_color)s', highlight:'%(highlight)s', label:'%(label)s' },\n")
        	chart_data_out = chart_data_out % params_for_chart
        	percent_out += curr +(" : %.2f <br>" % float(json_out["percentage"][curr]))
        print chart_data_out
        chart_data_out = chart_data_out[:-1]

        params = {}
        params["top_expenses"] = top_trans_out
        params["expenses"] = json_out["expenditures"]
        params["income"] = json_out["income"]
        params["account_info"] = account_output
        params["percentage_listing"] = percent_out
        params["chart_data"] = chart_data_out



        if(float(params["income"]) < float(params["expenses"])):
        	params["99_1"] = "not"
        else:
        	params["99_1"] = ""

        self.response.write(out_template % params)



class BackendHandler(webapp2.RequestHandler):
	request_url = "https://tartan.plaid.com/connect?client_id=%(client_id)s&secret=%(secret)s&access_token=%(auth_id)s"

	def post(self):
		params = {}
		income = 0.0
		expenses = 0.0
		params["auth_id"] = self.request.get("auth_id")
		params["client_id"] = client_id
		params["secret"] = secret

		request_url = self.request_url % params

		string_response = urllib.urlopen(request_url).read()

		json_array = json.loads(string_response)

		accounts = json_array["accounts"]
		transactions = json_array["transactions"]

		accounts_for_processing = []
		transactions_for_processing = []

		acc_id_num = {}

		for account in accounts: 
			new_acc = {}
			new_acc["name"] = account["meta"]["name"]
			new_acc["value"] = int(account["balance"]["current"])
			new_acc["ACC_NUM"] = (12 * "*") + account["meta"]["number"]
			accounts_for_processing.append(new_acc)

			acc_id_num[account["_id"]] = (12 * "*") + account["meta"]["number"]

		for transaction in transactions:
			new_trans = {}

			new_trans["cat"] = get_google_category(transaction)
			new_trans["location"] = transaction["name"]
			new_trans["account"] = acc_id_num[ transaction["_account"] ]
			new_trans["value"] = float(transaction["amount"])

			if(new_trans["value"] < 0):
				income += new_trans["value"]
			else:
				expenses += new_trans["value"]

			date = transaction["date"]
			new_trans["date"] = datetime.date(int(date[:4]), int(date[5:7]), int(date[8:10]))

			transactions_for_processing.append(new_trans)

		out = {}

		out["expenditures"] = str(expenses)
		out["income"] = str(income * -1)

		processed_data = process_data(transactions_for_processing)

		out["accounts"] = accounts_for_processing
		out["transactions"] = transactions_for_processing
		out["percentage"] = processed_data[0]
		out["vendors"] = processed_data[1]

		self.response.write(json.dumps(out, default=date_handler))


app = webapp2.WSGIApplication([
    ('/reqdata', BackendHandler), ('/view', MainHandler), ('/', HomeHandler)
], debug=True)
