#!/usr/bin/python
# coding: utf-8

import re
import json
import urllib2
import os

from bs4 import BeautifulSoup
from xml.sax.saxutils import quoteattr # Escape " and ' in XML

class CVE:
	def __init__(self, name):
		self.name = name
		self.note = ""

	def add_note(self, note):
		self.note += note


class DXA:
	def __init__(self, typ, name, soft, year, CVE, synopsys):
		self.typ = typ
		self.name = name
		self.description = ""
		self.soft = soft
		self.year = year
		self.link = "http://www.debian.org/security/" + self.year + "/" + self.name
		self.CVE = CVE
		self.synopsys = synopsys
		self.packages = list()
		self.versions = list()
		self.notes = ""
	
	def set_description(self, description):
		self.description = description

	def set_packages(self, packages):
		self.packages = packages

	def set_versions(self, versions):
		self.versions = versions

	def set_notes(self, notes):
		self.notes = notes
	

def request_url(url):
	request = urllib2.Request(url)
	try:
		request_handle = urllib2.urlopen(request)
	except urllib2.HTTPError, error:
		print "HTTP error on" + " " + url + " " + "code" + " " + str(error.code)
		exit(4)
	except urllib2.URLError, error:
		print "URL error on" + " " + url + " " + "reason" + " " + str(error.reason)
		exit(5)
	return request_handle.read()

def get_versions_from_cve(html_soup):
	versions = list()
	description = html_soup.find_all("table")[0].select('td')
	table  = html_soup.find_all("table")[1] # get second table
	source = (((table.select('tr')[1]).select('td')[0]).getText()).replace(" (PTS)","")

	for row in table:
		columns = row.select('td')
		parsed_array = []
		for column in columns:
			parsed_array.append(column.text)

		if(len(parsed_array) == 4):
			versions.append(parsed_array[2])
	return versions

def	get_description_from_cve(html_soup):
	des = html_soup.find_all("tr")[1].get_text()
	des = re.sub(r'Description', '', des)
	if des:
		return des
	else:
		print "NULL"

def generate_CVE():
	CVE_array = list()
	CVE_objects = list()

	#Transform file in array
	with open("secure-testing/data/CVE/list", "r") as CVE_file:
		for cve in CVE_file:
			CVE_array.append(cve)

	current_CVE = ""
	note = ""
	cve = None
	regex = re.compile("NOTE: (.*)$")

	for index, line in enumerate(CVE_array):
		if "CVE" in line:
			try:
				current_CVE = re.search(r'CVE-[0-9]*-[0-9]*', line).group(0)
			except AttributeError:
				pass
			if cve and cve.note:
				cve.note = cve.note.rstrip(' ') # remove training ' '
				CVE_objects.append(cve)
			elif cve:
				cve.add_note("Not Available")
				CVE_objects.append(cve)
				
			cve = CVE(current_CVE)

		elif "NOTE: " in line:
			note = regex.search(line).group(1)
			cve.add_note(note + ' ')

	return CVE_objects
	
def create_DLA():
	DLA_array = list()
	with open("secure-testing/data/DLA/list", "r") as DLA_file:
		for line in DLA_file:
			try:
				DLA_date = re.search(r'^\[.*([0-8]{4})\]', line).group(1)
				DLA_name = re.search('DLA-[0-9]*-[0-9]*', line).group(0)
				DLA_soft =  re.match(r'\[.*\] DLA-[0-9\-]* (.*) -.*', line).group(1)
				DLA_syno = re.search(" - (.*)$", line).group(1)

				nex = next(DLA_file) # Look next line of file for corresponding CVE
				CVE_names = re.findall(r'CVE-[0-9]*-[0-9]*', nex)
				DLA_synopsys = DLA_soft + " -- " + DLA_syno

				## Add new object to DLA array
				DLA_array.append(DXA('DLA', DLA_name, DLA_soft, DLA_date, CVE_names, DLA_synopsys))
			except AttributeError: # Regex will not always match
				pass
	return DLA_array
	

def create_DSA():
	DSA_array = list()
	with open("secure-testing/data/DSA/list", "r") as DSA_file:
		for line in DSA_file:
			try:
				DSA_date = re.search(r'^\[.*([0-8]{4})\]', line).group(1)
				DSA_name = re.search('DSA-[0-9]*-[0-9]*', line).group(0)
				DSA_soft =  re.match(r'\[.*\] DSA-[0-9\-]* (.*) -.*', line).group(1)
				DSA_syno = re.search(" - (.*)$", line).group(1)

				nex = next(DSA_file) # Look next line of file for corresponding CVE
				CVE_names = re.findall(r'CVE-[0-9]*-[0-9]*', nex)
				DSA_synopsys = DSA_soft + " -- " + DSA_syno

				## Add new object to DLA array
				DXA_array.append(DXA('DSA', DSA_name, DSA_soft, DSA_date, CVE_names, DSA_synopsys))
			except AttributeError: # Regex will not always match
				pass
	return DSA_array


def set_missing(DXA_array):
	for dxa in DXA_array:
		print '------------------------------------------------'
		try:
			description = ""
			packages = list()
			versions = list()
			if dxa.CVE:
				for cve in dxa.CVE:
					# Get description
					html_data = request_url("https://security-tracker.debian.org/tracker/" + cve)
					soup = BeautifulSoup(html_data, "html.parser")
					description += get_description_from_cve(soup)
					versions.extend(get_versions_from_cve(soup))
					for c in CVE_objects:
						if c.name == cve:
							dxa.set_notes(c.note)
							break
								
				dxa.set_description(description)
				dxa.set_versions(versions)
			else:
				print "NO CVE"

			# Get packages
			html_doc = ""
			if dxa.soft == "typo3-sec":
				html_doc = request_url("https://tracker.debian.org/pkg/typo3-src")
			elif dxa.soft == "phpymadmin":
				html_doc = request_url("https://tracker.debian.org/pkg/phpmyadmin")
			else:
				html_doc = request_url("https://tracker.debian.org/pkg/" + dxa.soft)

			print "Trying URL " + "https://tracker.debian.org/pkg/" + dxa.soft
			soup = BeautifulSoup(html_doc, "html.parser")
			pack = soup.find_all("ul")[3].select('a')

			for ul in pack:
				packages.append(ul.get_text())

			dxa.set_packages(packages)
		except KeyError:
			print "KEYERROR : ", dxa.soft, dxa.name, dxa.CVE
		except IndexError:
			print "INDEXERROR : ", dxa.soft

def create_xml_file(DXA_array):
	with open('XML', 'a') as xml_file:
		xml_file.write('<?xml version="1.0" encoding="ASCII"?>\n')
		xml_file.write('<opt>\n')
		for dla in DXA_array:
			to_write = '  <' + dla.name + ' description=' + quoteattr(dla.description) \
				+ ' from="Debian CVS english security report" multirelease="1" notes="' + dla.notes + '" product="Debian Linux" references="' \
				+ dla.link + '" release="1" solution="Not available" synopsis="' + dla.synopsys \
				+'" topic="' + dla.synopsys + '" type="Security Advisory" security_name="' + dla.name +'">\n'
			xml_file.write(to_write)
			for pack in dla.packages:
				for version in dla.versions:
					to_write = '    <packages>' + pack + '-' + version + '.amd64-deb.deb</packages>\n'
					xml_file.write(to_write)

			to_write = '  </' + dla.name + '>\n'	
			xml_file.write(to_write)
		xml_file.write('</opt>')


	
"""
Main program
"""
if __name__ == "__main__":
	os.system("svn update secure-testing")	
	DXA_array = create_DLA()
	DXA_array.extend(create_DSA())
	CVE_objects = generate_CVE()
	set_missing(DXA_array)
	create_xml_file(DXA_array)
