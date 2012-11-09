"""
A python class to manage caching of data from Comic Vine
"""

"""
Copyright 2012  Anthony Beville

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

	http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

from pprint import pprint 

import sqlite3 as lite
import sys
import os
import datetime

class ComicVineCacher:

	def __init__(self, settings_folder ):
		self.settings_folder = settings_folder
		self.db_file = os.path.join( self.settings_folder, "cv_cache.db")
		
		if not os.path.exists( self.db_file ):
			self.create_cache_db()

	def create_cache_db( self ):
		
		# this will wipe out any existing version
		open( self.db_file, 'w').close()

		con = lite.connect( self.db_file )
		
		# create tables 
		with con:
			
			cur = con.cursor()    
			#name,id,start_year,publisher,image,description,count_of_issues
			cur.execute("CREATE TABLE VolumeSearchCache(" +
							"search_term TEXT," +
							"id INT," +
							"name TEXT," +
							"start_year INT," +
							"publisher TEXT," +
							"count_of_issues INT," +
							"image_url TEXT," +
							"description TEXT," +
							"timestamp TEXT)" 
						)
						
			cur.execute("CREATE TABLE Volumes(" +
							"id INT," +
							"name TEXT," +
							"publisher TEXT," +
							"count_of_issues INT," +
							"timestamp TEXT," +
							"PRIMARY KEY (id) )" 
						)

			cur.execute("CREATE TABLE Issues(" +
							"id INT," +
							"volume_id INT," +
							"name TEXT," +
							"issue_number TEXT," +
							"image_url TEXT," +
							"image_hash TEXT," +
							"thumb_image_url TEXT," +
							"thumb_image_hash TEXT," +
							"timestamp TEXT,"  +
							"PRIMARY KEY (id ) )" 
						)

	def add_search_results( self, search_term, cv_search_results ):
		
		con = lite.connect( self.db_file )

		with con:
			
			cur = con.cursor()    
			
			# remove all previous entries with this search term
			cur.execute("DELETE FROM VolumeSearchCache WHERE search_term = '{0}'".format(search_term.lower()))
			
			# now add in new results
			for record in cv_search_results:
				timestamp = datetime.datetime.now()

				if record['publisher'] is None:
					pub_name = ""
				else:
					pub_name = record['publisher']['name']
					
				if record['image'] is None:
					url = ""
				else:
					url = record['image']['super_url']
					
				cur.execute("INSERT INTO VolumeSearchCache VALUES( ?, ?, ?, ?, ?, ?, ?, ?, ? )" ,
								( search_term.lower(),
								record['id'],
								record['name'],
								record['start_year'],
								pub_name,
								record['count_of_issues'],
								url,
								record['description'],
								timestamp ) 
							)
							
	def get_search_results( self, search_term ):
		
		results = list()
		con = lite.connect( self.db_file )
		with con:
			cur = con.cursor() 
			
			# TODO purge stale search results ( older than a day, maybe??)
			
			# fetch
			cur.execute("SELECT * FROM VolumeSearchCache WHERE search_term=?", [ search_term.lower() ] )
			rows = cur.fetchall()
			# now process the results
			for record in rows:
				
				result = dict()
				result['id'] = record[1]
				result['name'] = record[2]
				result['start_year'] = record[3]
				result['publisher'] = dict()
				result['publisher']['name'] = record[4]
				result['count_of_issues'] = record[5]
				result['image'] = dict()
				result['image']['super_url'] = record[6]
				result['description'] = record[7]
				
				results.append(result)
				
		return results


	def add_volume_info( self, cv_volume_record ):
		
		con = lite.connect( self.db_file )

		with con:
			
			cur = con.cursor()    
			
			timestamp = datetime.datetime.now()

			data = { 
						"name":            cv_volume_record['name'], 
						"publisher":       cv_volume_record['publisher']['name'], 
						"count_of_issues": cv_volume_record['count_of_issues'],
						"timestamp":       timestamp 
					}
			self.upsert( cur, "volumes", "id", cv_volume_record['id'], data)

			# now add in issues

			for issue in cv_volume_record['issues']:
				
				data = { 
				         "volume_id":    cv_volume_record['id'], 
				         "name":         issue['name'], 
				         "issue_number": issue['issue_number'], 
				         "timestamp":    timestamp 
				       }
				self.upsert( cur, "issues" , "id", issue['id'], data)
			

	def get_volume_info( self, volume_id ):
		
		result = None

		con = lite.connect( self.db_file )
		with con:
			cur = con.cursor() 
			
			# TODO purge stale volume records ( older than a week, maybe??)
			
			# fetch
			cur.execute("SELECT id,name,publisher,count_of_issues FROM Volumes WHERE id = ?", [ volume_id ] )
			
			row = cur.fetchone()
			
			if row is None :
				return result
			
			result = dict()
			
			#since ID is primary key, there is only one row
			result['id'] =                row[0]
			result['name'] =              row[1]
			result['publisher'] = dict()
			result['publisher']['name'] = row[2]
			result['count_of_issues'] =   row[3]
			result['issues'] = list()

			cur.execute("SELECT id,name,issue_number,image_url,image_hash FROM Issues WHERE volume_id = ?", [ volume_id ] )
			rows = cur.fetchall()
			
			# now process the results
			for row in rows:
				record = dict()
				record['id'] =           row[0]
				record['name'] =         row[1]
				record['issue_number'] = row[2]
				record['image_url'] =    row[3]
				record['image_hash'] =   row[4]
				
				result['issues'].append(record)
		
		return result


	def add_issue_image_url( self, issue_id, image_url ):
		
		con = lite.connect( self.db_file )

		with con:
			cur = con.cursor()    
			timestamp = datetime.datetime.now()
			
			data = { 
			          "image_url": image_url, 
			          "timestamp": timestamp 
			       }
			self.upsert( cur, "issues" , "id", issue_id, data)
			
				

	def get_issue_image_url( self, issue_id ):
		
		con = lite.connect( self.db_file )
		with con:
			cur = con.cursor() 
			
			cur.execute("SELECT image_url FROM Issues WHERE id=?", [ issue_id ])
			row = cur.fetchone()

			if row[0] is None :
				return None
			else:
				return row[0]
			
			
	def upsert( self, cur, tablename, pkname, pkval, data):
		"""
		This does an insert if the given PK doesn't exist, and an update it if does
		"""
		
		# TODO - look into checking if UPDATE is needed
		# TODO - should the cursor be created here, and not up the stack?
		
		ins_count = len(data) + 1

		keys = ""
		vals = list()
		ins_slots = ""
		set_slots = ""
		
		for key in data:
			
			if keys !=  "":
				keys += ", "
			if ins_slots !=  "":
				ins_slots += ", "
			if set_slots !=  "":
				set_slots += ", "
				
			keys += key
			vals.append( data[key] )
			ins_slots += "?"
			set_slots += key + " = ?"

		keys += ", " + pkname
		vals.append( pkval )
		ins_slots += ", ?"
		condition = pkname + " = ?"

		sql_ins = ( "INSERT OR IGNORE INTO " + tablename  + 
			" ( " + keys  + " ) " + 
			" VALUES ( " +  ins_slots + " )"  )
		cur.execute( sql_ins , vals )
		
		sql_upd =  ( "UPDATE " + tablename  + 
			" SET " + set_slots + " WHERE " + condition )
		cur.execute( sql_upd , vals )




